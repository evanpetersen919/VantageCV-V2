"""Rocketbox pedestrians: the catalog, the swap (same scenes, new avatars), the payload entry and
the labels' mapping."""

# pylint: disable=missing-function-docstring

import math

import pytest

from src.orchestration.dataset_generator import generate_scenario
from src.orchestration.scenario_serializer import object_asset_indices, serialize_scenario
from src.procedural.environment import TimeOfDay, Weather, scenario_environment
from src.procedural.rocketbox_pedestrians import (
    ASSET_ROOT,
    ROCKETBOX_FORWARD_OFFSET_RAD,
    catalog,
    is_rocketbox,
    mesh_path,
)
from src.utils.config_loader import load_scenario_config

BOUNDS = (-150.0, -150.0, 150.0, 150.0)
CITY = "configs/scenario_templates/urban_dense_v7_peds.yaml"
BOX = "configs/scenario_templates/urban_dense_v13r.yaml"
SEEDS = (70000, 70001, 70002)


def test_catalog_has_every_avatar_with_three_standing_and_six_walking_poses() -> None:
    avatars = catalog()["avatars"]
    assert len(avatars) == 38
    for avatar in avatars:
        assert avatar["gender"] == ("f" if avatar["avatar"].startswith("Female") else "m")
        kinds = [pose["kind"] for pose in avatar["poses"]]
        assert kinds.count("walking") == 6 and kinds.count("standing") == 3
        for pose in avatar["poses"]:
            assert 1.5 < pose["z"] < 2.0 and 0.2 < pose["x"] < 1.0 and 0.2 < pose["y"] < 1.2


def test_default_source_is_city_sample_and_unknown_source_is_rejected() -> None:
    config = load_scenario_config(CITY)
    assert config.pedestrian_source == "city_sample"
    assert load_scenario_config(BOX).pedestrian_source == "rocketbox"
    with pytest.raises(ValueError):
        config.model_copy(update={"pedestrian_source": "x"}).model_validate(
            {**config.model_dump(), "pedestrian_source": "x"}
        )


@pytest.mark.parametrize("seed", SEEDS)
def test_swap_keeps_the_scene_and_changes_only_the_avatars(seed: int) -> None:
    original = generate_scenario(seed, load_scenario_config(CITY), BOUNDS, "a")
    swapped = generate_scenario(seed, load_scenario_config(BOX), BOUNDS, "b")
    assert len(original.pedestrians) == len(swapped.pedestrians) > 0
    for before, after in zip(original.pedestrians, swapped.pedestrians):
        assert after.pedestrian_id == before.pedestrian_id
        assert tuple(after.center) == tuple(before.center)
        assert after.heading_rad == before.heading_rad and after.surface_z == before.surface_z
        assert is_rocketbox(after.asset_path) and after.part_paths == []
        gender = before.asset_path.split("/")[-1].split("_")[1]
        assert ("Female" if gender == "f" else "Male") in after.asset_path
        assert after.box_offset == (0.0, 0.0)
    assert [(v.vehicle_id, v.asset_path, tuple(v.box_center)) for v in original.vehicles] == [
        (v.vehicle_id, v.asset_path, tuple(v.box_center)) for v in swapped.vehicles
    ]
    assert len(original.buildings) == len(swapped.buildings)


def test_swap_is_deterministic_and_matches_the_catalog_extents() -> None:
    first = generate_scenario(70000, load_scenario_config(BOX), BOUNDS, "a")
    second = generate_scenario(70000, load_scenario_config(BOX), BOUNDS, "b")
    assert [p.asset_path for p in first.pedestrians] == [p.asset_path for p in second.pedestrians]
    poses = {
        mesh_path(avatar["avatar"], pose["pose"]): pose
        for avatar in catalog()["avatars"]
        for pose in avatar["poses"]
    }
    for pedestrian in first.pedestrians:
        pose = poses[pedestrian.asset_path]
        assert (pedestrian.width, pedestrian.depth, pedestrian.height) == (
            pose["x"],
            pose["y"],
            pose["z"],
        )


def test_swap_keeps_walking_and_standing() -> None:
    original = generate_scenario(70000, load_scenario_config(CITY), BOUNDS, "a")
    swapped = generate_scenario(70000, load_scenario_config(BOX), BOUNDS, "b")
    kinds = {
        mesh_path(a["avatar"], p["pose"]): p["kind"]
        for a in catalog()["avatars"]
        for p in a["poses"]
    }
    standing_before = [320 <= p.pose_frame <= 429 for p in original.pedestrians]
    standing_after = [kinds[p.asset_path] == "standing" for p in swapped.pedestrians]
    assert standing_before == standing_after


def test_payload_entry_is_a_plain_static_mesh_turned_to_its_heading_and_maps_to_the_labels() -> (
    None
):
    scenario = generate_scenario(70000, load_scenario_config(BOX), BOUNDS, "a")
    payload = serialize_scenario(
        scenario,
        scenario_environment(scenario.season, TimeOfDay.DAY, Weather.OVERCAST, 70000, "v7"),
    )
    indices = object_asset_indices(scenario, payload)
    n_before = len(scenario.buildings) + len(scenario.vehicles)
    for pedestrian in scenario.pedestrians:
        (index,) = indices[pedestrian.pedestrian_id + n_before]
        entry = payload["assets"][index]
        assert entry["asset_path"].startswith(ASSET_ROOT) and entry["part_paths"] == []
        assert "material_scalar_overrides" not in entry
        assert entry["rotation_rad"] == pytest.approx(
            pedestrian.heading_rad + ROCKETBOX_FORWARD_OFFSET_RAD
        )
    assert math.isclose(ROCKETBOX_FORWARD_OFFSET_RAD, -math.pi / 2)
