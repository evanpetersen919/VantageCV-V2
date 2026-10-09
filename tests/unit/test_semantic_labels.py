"""Full-scene class maps: every part has a class, groups are right, the capture composes the map."""

# pylint: disable=missing-function-docstring,too-few-public-methods

import asyncio
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest
from PIL import Image
from pycocotools import mask as mask_utils

from src.export.coco_exporter import CocoFrame
from src.ground_truth.bbox_2d import BoundingBox2D
from src.ground_truth.semantic_classes import (
    BUILDING,
    CAR,
    EGO_VEHICLE,
    PERSON,
    ROAD,
    SIDEWALK,
    SKY,
    TERRAIN,
    TRAFFIC_LIGHT,
    TRUCK,
    asset_class,
    mesh_class,
)
from src.orchestration.dataset_generator import generate_scenario
from src.orchestration.hood import clip_exact_to_hood, hood_mask
from src.orchestration.scenario_serializer import serialize_scenario
from src.orchestration.semantic_labels import (
    DEPTH_SCALE,
    SemanticMaps,
    capture_semantic,
    class_groups,
    save_maps,
    unmapped_parts,
)
from src.procedural.environment import TimeOfDay, Weather, scenario_environment
from src.sensors.camera_model import Camera, CameraExtrinsics, CameraIntrinsics
from src.utils.config_loader import load_scenario_config

BOUNDS = (-150.0, -150.0, 150.0, 150.0)
CONFIG = "configs/scenario_templates/urban_dense_v13r.yaml"


def _payload(seed: int, time_of_day: TimeOfDay, weather: Weather) -> Any:
    scenario = generate_scenario(
        seed, load_scenario_config(CONFIG), BOUNDS, "t", time_of_day=time_of_day
    )
    environment = scenario_environment(scenario.season, time_of_day, weather, seed, "v7")
    return scenario, serialize_scenario(scenario, environment)


@pytest.mark.parametrize(
    "time_of_day,weather", [(TimeOfDay.DAY, Weather.OVERCAST), (TimeOfDay.NIGHT, Weather.CLEAR)]
)
def test_every_part_of_generated_scenes_has_a_class(
    time_of_day: TimeOfDay, weather: Weather
) -> None:
    for seed in range(80000, 80010):
        _, payload = _payload(seed, time_of_day, weather)
        assert unmapped_parts(payload) == []


def test_rules_for_the_cases_that_need_a_decision() -> None:
    assert (
        asset_class("/Game/Prop/Kit_StreetLamp_A/Mesh/SM_StreetLamp_A_StopLight_D") == TRAFFIC_LIGHT
    )
    assert (
        asset_class("/Game/Prop/Kit_StreetLamp_A/Mesh/SM_StreetLamp_A_Pole_Large") != TRAFFIC_LIGHT
    )
    assert asset_class("/Game/Megascans/3D_Assets/Modular_Curb_5_M_00/x") == SIDEWALK
    assert (
        asset_class("/Game/VantageCV/Pedestrians/Rocketbox/Male_Adult_01/Male_Adult_01_w0")
        == PERSON
    )
    assert asset_class("/Game/Vehicle/vehTruck_trailer01/x") == TRUCK
    assert asset_class("/Game/Unknown/Thing") == 0
    assert (mesh_class("asphalt"), mesh_class("paint_white")) == (ROAD, ROAD)
    assert (mesh_class("pavement_3"), mesh_class("ground"), mesh_class("roof_2")) == (
        SIDEWALK,
        TERRAIN,
        BUILDING,
    )
    assert mesh_class("something_new") == 0


def test_vehicles_take_the_class_of_their_type_and_lamps_follow_their_vehicle() -> None:
    scenario, payload = _payload(80001, TimeOfDay.NIGHT, Weather.CLEAR)
    groups = dict(class_groups(payload, scenario))
    path_only = dict(class_groups(payload))
    assert groups[CAR]["assets"], "cars are present"
    # every pickup is a car for the class map, as for the annotations, whatever its folder name
    pickups = [
        i for i, a in enumerate(payload["assets"]) if "vehTruck_vehicle04" in a["asset_path"]
    ]
    assert pickups and set(pickups) <= set(groups[CAR]["assets"])
    assert not set(pickups) & set(groups.get(TRUCK, {"assets": []})["assets"])
    assert set(pickups) <= set(path_only[TRUCK]["assets"])  # the path alone would have said truck
    assert sum(len(g["glows"]) for g in groups.values()) == len(payload.get("glows", []))


class _FakeBackend:
    def __init__(self, visible: np.ndarray, depth_cm: np.ndarray) -> None:
        self.visible, self.depth_cm, self.calls = visible, depth_cm, []

    async def call(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append((method, params))
        self.visible.astype("<u2").tofile(params["out_path"])
        self.depth_cm.astype("<f4").tofile(params["depth_path"])
        return {"width": self.visible.shape[1], "height": self.visible.shape[0], "objects": []}


def test_capture_composes_classes_sky_and_hood(tmp_path: Path) -> None:
    height, width = 40, 60
    visible = np.zeros((height, width), dtype=np.uint16)
    visible[20:30, 5:25] = 1  # group 0
    visible[30:38, 5:55] = 2  # group 1
    depth = np.full((height, width), 1500.0, dtype=np.float32)
    depth[:10] = 1.0e9  # sky
    groups: List[Any] = [(CAR, {"assets": [1]}), (ROAD, {"meshes": [2]})]
    backend = _FakeBackend(visible, depth)
    maps = asyncio.run(capture_semantic(backend, groups, (width, height), tmp_path / "s" / "f", 35))
    assert maps.classes[25, 10] == CAR and maps.classes[33, 30] == ROAD
    assert maps.classes[5, 5] == SKY and maps.classes[15, 5] == 0
    covered = hood_mask(35, (width, height))
    assert (maps.classes[covered] == EGO_VEHICLE).all() and (maps.depth_m[covered] == 0).all()
    assert maps.depth_m[15, 5] == pytest.approx(15.0) and maps.depth_m[5, 5] == 0.0
    sent = backend.calls[0][1]["objects"]
    assert sent == [{"assets": [1]}, {"meshes": [2]}]
    assert not list((tmp_path / "s").glob("f.*"))  # scratch files are removed


def test_saved_maps_round_trip(tmp_path: Path) -> None:
    classes = np.arange(12, dtype=np.uint8).reshape(3, 4)
    depth = np.array([[0.0, 1.0, 12.5, 250.0]] * 3, dtype=np.float32)
    semantic_file, depth_file = save_maps(SemanticMaps(classes, depth), tmp_path, "f")
    assert (np.array(Image.open(tmp_path / semantic_file)) == classes).all()
    back = np.array(Image.open(tmp_path / depth_file)).astype(np.float64) / DEPTH_SCALE
    assert np.allclose(back, depth, atol=1.0 / DEPTH_SCALE)


def _frame_with_mask(mask: np.ndarray) -> CocoFrame:
    height, width = mask.shape
    camera = Camera(
        CameraIntrinsics.from_fov(90.0, width, height),
        CameraExtrinsics.looking_at(np.array([0.0, 0.0, 1.5]), np.array([0.0, 10.0, 1.5])),
    )
    rows, columns = np.nonzero(mask)
    box = BoundingBox2D(
        3,
        float(columns.min()),
        float(rows.min()),
        float(columns.max() + 1),
        float(rows.max() + 1),
        visibility=1.0,
        visible_fraction=1.0,
        truncation=0.0,
    )
    encoded = mask_utils.encode(np.asfortranarray(mask.astype(np.uint8)))
    rle = {"size": [int(v) for v in encoded["size"]], "counts": encoded["counts"].decode("ascii")}
    return CocoFrame(1, "a.png", camera, [box], masks_by_id={3: rle})


def test_exact_masks_are_trimmed_to_the_hood_and_vanish_when_fully_covered() -> None:
    height, width, top = 100, 160, 70
    mask = np.zeros((height, width), dtype=bool)
    mask[50:90, 40:80] = True  # crosses the hood's top edge
    result = clip_exact_to_hood(_frame_with_mask(mask), top)
    (box,) = result.bboxes_2d
    kept = mask & ~hood_mask(top, (width, height))
    rows, columns = np.nonzero(kept)
    assert (box.y_min, box.y_max) == (float(rows.min()), float(rows.max() + 1))
    assert (box.x_min, box.x_max) == (float(columns.min()), float(columns.max() + 1))
    assert 0 < box.visible_fraction < 1.0
    decoded = mask_utils.decode(
        {
            "size": result.masks_by_id[3]["size"],
            "counts": result.masks_by_id[3]["counts"].encode("ascii"),
        }
    )
    assert (decoded > 0).tolist() == kept.tolist()
    under = np.zeros((height, width), dtype=bool)
    under[85:95, 60:100] = True
    assert clip_exact_to_hood(_frame_with_mask(under), top).bboxes_2d == []
