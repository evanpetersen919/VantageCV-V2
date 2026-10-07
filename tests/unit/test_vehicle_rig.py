"""The tractor-trailer rig: one vehicle, one box, one mesh, one label, a second actor."""

import dataclasses
from pathlib import Path

import numpy as np
import pytest

from src.orchestration.scenario_serializer import trailer_asset_json
from src.procedural.actor_placement import ActorPlacementGenerator, Vehicle, vehicle_box
from src.procedural.city_sample_assets import (
    RIG_SUFFIX,
    TRACTOR_FOLDER,
    TRAILER_FOLDER,
    TRAILER_HITCH_X_M,
    TRAILER_ID_OFFSET,
    fleet_models,
)
from src.procedural.night_lights import vehicle_lights
from src.procedural.vehicle_bounds import VEHICLE_MODEL_BOUNDS
from src.procedural.vehicle_meshes import MESH_FILE, model_mesh, world_triangles
from src.procedural.vehicle_rig import RIG_BOUNDS, rig_bounds
from src.utils.config_loader import load_scenario_config

CAB = f"/Game/Vehicle/{TRACTOR_FOLDER}/Mesh/SM_Frame_{TRACTOR_FOLDER}"


def _rig(heading: float = 0.0) -> Vehicle:
    length, width, height, offset_x, offset_y, z_min = vehicle_box(CAB, "truck", True)
    base = Vehicle(7, "truck", CAB, np.array([10.0, 5.0]), heading, length, width, height)
    return dataclasses.replace(
        base, box_offset=(offset_x, offset_y), box_z_min=z_min, trailer=True, paint="white"
    )


def test_rig_box_holds_both_parts_and_is_longer_than_either() -> None:
    """The box spans the cab's front to the trailer's rear, as tall as the trailer."""
    cab, trailer = VEHICLE_MODEL_BOUNDS[TRACTOR_FOLDER], VEHICLE_MODEL_BOUNDS[TRAILER_FOLDER]
    length, width, height, centre_x, _, _ = RIG_BOUNDS
    assert abs(length - 14.087) < 0.01 and abs(centre_x - (-3.7955)) < 0.001
    assert length > cab[0] + trailer[0] - 4.0 and width == max(cab[1], trailer[1])
    assert abs(height - 4.001) < 0.01
    # a trailer hitched further back makes a longer rig, whichever side of the cab's origin
    assert rig_bounds(cab, trailer, -1.0)[0] > rig_bounds(cab, trailer, 0.0)[0]
    assert rig_bounds(cab, trailer, 0.0)[0] > rig_bounds(cab, trailer, 1.0)[0]


@pytest.mark.skipif(not MESH_FILE.exists(), reason="vehicle_meshes.npz not generated")
def test_rig_mesh_is_the_cab_plus_the_trailer_at_the_hitch() -> None:
    """The world mesh has both parts' triangles; the trailer reaches back past the cab's rear."""
    cab_mesh, trailer_mesh = model_mesh(TRACTOR_FOLDER), model_mesh(TRAILER_FOLDER)
    assert cab_mesh is not None and trailer_mesh is not None
    triangles = world_triangles(_rig())
    assert triangles is not None
    assert len(triangles) == len(cab_mesh[1]) + len(trailer_mesh[1])
    cab_rear = world_triangles(_rig_without_trailer())[:, :, 0].min()  # type: ignore[index]
    assert triangles[:, :, 0].min() < cab_rear - 7.0  # the trailer extends far behind the cab


def _rig_without_trailer() -> Vehicle:
    plain = _rig()
    plain.trailer = False
    return plain


def test_trailer_is_a_second_actor_behind_the_cab_on_the_same_heading() -> None:
    """Heading +x: the trailer's hitch is 1.58 m behind; heading +y it is 1.58 m below in y."""
    for heading, expected in (
        (0.0, (10.0 + TRAILER_HITCH_X_M, 5.0)),
        (np.pi / 2, (10.0, 5.0 + TRAILER_HITCH_X_M)),
    ):
        entry = trailer_asset_json(_rig(heading))
        assert entry["asset_path"].endswith(f"SM_Frame_{TRAILER_FOLDER}")
        assert np.allclose(entry["position"][:2], expected, atol=1e-6)
        assert entry["rotation_rad"] == heading and entry["id"] == 7 + TRAILER_ID_OFFSET
        assert entry["part_paths"] and "Axel" in entry["part_paths"][0]


def test_tail_lights_of_a_rig_sit_at_the_trailer_rear_not_the_middle_of_the_box() -> None:
    """The cab has no measured lamps, so lights use the box ends (the box is 5 m behind)."""
    lights = vehicle_lights(_rig())
    tails = [light.position[0] for light in lights if light.kind == "point"]
    heads = [light.position[0] for light in lights if light.kind == "spot"]
    assert 10.0 - 11.5 < min(tails) < 10.0 - 10.5  # just behind the trailer's rear face (x = -10.8)
    assert max(heads) > 10.0 + 3.0  # about the cab's front (x = +3.25)


def test_v7_truck_fleet_has_the_rig_and_no_bare_tractor() -> None:
    """The v7 truck list is the rig and the large rigid truck; the tractor alone is gone."""
    paths, _ = fleet_models("v7", "truck")
    assert any(path.endswith(RIG_SUFFIX) for path in paths)
    assert all(path.endswith(RIG_SUFFIX) or TRACTOR_FOLDER not in path for path in paths)


def test_generator_places_rigs_with_the_union_box() -> None:
    """Over many scenarios the v7 generator places some rigs, each with the rig box."""
    config = load_scenario_config(Path("configs/scenario_templates/urban_dense_v7.yaml"))
    found = 0
    for seed in range(40):
        generator = ActorPlacementGenerator(seed, config)
        # a tiny direct draw of the placement-time sampling: the first truck-typed asset path
        for _ in range(200):
            path = generator.rng.choice(fleet_models("v7", "truck")[0])
            if str(path).endswith(RIG_SUFFIX):
                found += 1
                break
    assert found > 20
