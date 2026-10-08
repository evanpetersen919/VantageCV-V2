"""Exact labels from the engine: the asset mapping, the request, and the replacement of
geometric labels."""

# pylint: disable=missing-function-docstring,duplicate-code

import asyncio
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest
from pycocotools import mask as mask_utils

from src.export.coco_exporter import CocoFrame, export_coco
from src.ground_truth.bbox_2d import BoundingBox2D
from src.orchestration.dataset_generator import generate_scenario
from src.orchestration.exact_labels import ExactLabels, apply_exact, capture_exact
from src.orchestration.live_dataset import _settings
from src.orchestration.scenario_serializer import object_asset_indices, serialize_scenario
from src.procedural.environment import TimeOfDay, Weather, scenario_environment
from src.sensors.camera_model import Camera, CameraExtrinsics, CameraIntrinsics
from src.utils.config_loader import load_scenario_config

BOUNDS = (-150.0, -150.0, 150.0, 150.0)
W, H = 64, 48


def _camera() -> Camera:
    extrinsics = CameraExtrinsics.looking_at(np.array([0.0, 0.0, 1.5]), np.array([0.0, 10.0, 1.5]))
    return Camera(CameraIntrinsics.from_fov(90.0, W, H), extrinsics)


def _box(object_id: int, x0: float, y0: float, x1: float, y1: float) -> BoundingBox2D:
    return BoundingBox2D(
        object_id, x0, y0, x1, y1, visibility=1.0, visible_fraction=1.0, truncation=0.1
    )


def _frame() -> CocoFrame:
    boxes = [
        _box(10, 5, 5, 30, 30),
        _box(11, 5, 5, 30, 30),
        _box(12, 40, 10, 60, 40),
        _box(13, 1, 1, 9, 9),
    ]
    return CocoFrame(1, "a.png", _camera(), boxes)


def _reports() -> List[Dict[str, Any]]:
    return [
        {
            "object": 0,
            "actors_found": 1,
            "amodal_px": 100,
            "visible_px": 40,
            "amodal_bbox": [6, 6, 15, 15],
            "visible_bbox": [8, 9, 17, 14],
        },
        {
            "object": 1,
            "actors_found": 1,
            "amodal_px": 50,
            "visible_px": 0,
            "amodal_bbox": [6, 6, 15, 15],
            "visible_bbox": [W, H, -1, -1],
        },
        {"object": 2, "actors_found": 0},
    ]


def _visible_map() -> np.ndarray:
    visible = np.zeros((H, W), dtype=np.uint16)
    visible[9:15, 8:18] = 1  # object 0 owns a 6 x 10 block
    return visible


def test_object_asset_indices_find_vehicles_trailers_and_pedestrians_in_a_real_scenario() -> None:
    config = load_scenario_config("configs/scenario_templates/urban_dense_v8a.yaml")
    scenario = generate_scenario(70000, config, BOUNDS, "t")
    payload = serialize_scenario(
        scenario,
        scenario_environment(scenario.season, TimeOfDay.DAY, Weather.OVERCAST, 70000, "v7"),
    )
    indices = object_asset_indices(scenario, payload)
    n_buildings, n_vehicles = len(scenario.buildings), len(scenario.vehicles)
    for i, vehicle in enumerate(scenario.vehicles):
        members = indices[vehicle.vehicle_id + n_buildings]
        assert members[0] == i
        assert payload["assets"][i]["asset_path"] == vehicle.asset_path
        assert len(members) == (2 if vehicle.trailer else 1)
        if vehicle.trailer:
            assert members[1] >= n_vehicles
    pedestrians = [k for k in indices if k >= n_buildings + n_vehicles]
    assert len(pedestrians) == len(scenario.pedestrians)
    assert len({m[0] for k, m in indices.items() if k in pedestrians}) == len(
        pedestrians
    )  # all distinct
    first = scenario.pedestrians[0]
    entry = payload["assets"][indices[first.pedestrian_id + n_buildings + n_vehicles][0]]
    assert entry["asset_path"].endswith(first.asset_path.split("/")[-1])


class _FakeBackend:  # pylint: disable=too-few-public-methods
    def __init__(self, visible: np.ndarray, reports: List[Dict[str, Any]]) -> None:
        self.visible, self.reports, self.calls = visible, reports, []

    async def call(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append((method, params))
        self.visible.astype("<u2").tofile(params["out_path"])
        return {"width": W, "height": H, "objects": self.reports}


def test_capture_exact_asks_for_the_mapped_objects_and_reads_the_map_back(tmp_path: Path) -> None:
    backend = _FakeBackend(_visible_map(), _reports())
    members = {10: [3], 11: [4, 5], 12: [6]}  # object 13 has no actors
    exact = asyncio.run(
        capture_exact(backend, members, _frame(), (W, H), tmp_path / "scratch" / "m.u16")
    )
    assert exact is not None
    method, params = backend.calls[0]
    assert method == "CaptureObjectMasks"
    assert params["objects"] == [[3], [4, 5], [6]] and Path(params["out_path"]).is_absolute()
    assert params["width"] == W and params["vertical_fov_deg"] > 0
    assert exact.order == [10, 11, 12]
    assert int((exact.visible_map == 1).sum()) == 60
    assert not (tmp_path / "scratch" / "m.u16").exists()  # the scratch file is removed


def test_capture_exact_without_mapped_objects_makes_no_request(tmp_path: Path) -> None:
    backend = _FakeBackend(_visible_map(), _reports())
    assert asyncio.run(capture_exact(backend, {}, _frame(), (W, H), tmp_path / "m.u16")) is None
    assert not backend.calls


def test_apply_exact_replaces_hides_and_keeps_the_right_objects() -> None:
    exact = ExactLabels(_visible_map(), [10, 11, 12], _reports())
    result = apply_exact(_frame(), exact)
    by_id = {b.object_id: b for b in result.bboxes_2d}
    assert set(by_id) == {10, 12, 13}  # 11 is not visible in the engine; 12 and 13 have no data
    box = by_id[10]
    assert (box.x_min, box.y_min, box.x_max, box.y_max) == (
        8.0,
        9.0,
        18.0,
        15.0,
    )  # inclusive pixels + 1
    assert box.visible_fraction == pytest.approx(0.4) and box.truncation == pytest.approx(0.1)
    assert (by_id[12].x_min, by_id[12].x_max) == (40, 60)  # kept as geometry
    assert (by_id[13].x_min, by_id[13].x_max) == (1, 9)
    decoded = mask_utils.decode(
        {
            "size": result.masks_by_id[10]["size"],
            "counts": result.masks_by_id[10]["counts"].encode("ascii"),
        }
    )
    assert decoded.sum() == 60 and decoded[9:15, 8:18].all()
    assert 12 not in result.masks_by_id and 13 not in result.masks_by_id


def test_exported_annotations_carry_the_mask_only_for_exact_objects() -> None:
    exact = ExactLabels(_visible_map(), [10, 11, 12], _reports())
    result = export_coco([apply_exact(_frame(), exact)])
    by_box = {tuple(a["bbox"]): a for a in result["annotations"]}
    exact_annotation = by_box[(8.0, 9.0, 10.0, 6.0)]
    assert exact_annotation["mask_rle"]["size"] == [H, W]
    assert sum("mask_rle" in a for a in result["annotations"]) == 1


def test_older_runs_settings_are_unchanged_by_the_new_flag() -> None:
    config = load_scenario_config("configs/scenario_templates/urban_dense_v8a.yaml")
    from src.export.annotation_policy import (  # pylint: disable=import-outside-toplevel
        AnnotationPolicy,
    )

    plain = _settings(config, BOUNDS, ("ego",), 1, AnnotationPolicy(), "v7")
    assert "exact_labels" not in plain
    assert (
        _settings(config, BOUNDS, ("ego",), 1, AnnotationPolicy(), "v7", True)["exact_labels"]
        is True
    )
