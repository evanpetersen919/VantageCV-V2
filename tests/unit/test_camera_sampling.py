"""Tests for ego and overview camera pose sampling."""

from pathlib import Path

import numpy as np
import pytest

from src.orchestration.camera_sampling import (
    BUILDING_MARGIN_M,
    EGO_HEIGHT_RANGE_M,
    LOOK_AHEAD_M,
    overview_pose,
    sample_ego_pose,
)
from src.orchestration.dataset_generator import ScenarioResult, generate_scenario
from src.utils.config_loader import load_scenario_config

BOUNDS = (-150.0, -150.0, 150.0, 150.0)
CONFIG = Path("configs/scenario_templates/urban_dense.yaml")


def _scenario(seed: int = 100) -> ScenarioResult:
    """A small real scenario."""
    return generate_scenario(seed, load_scenario_config(CONFIG), BOUNDS, "cam")


def test_overview_pose_is_outside_the_corner_and_looks_at_the_centre() -> None:
    """The overview camera sits above and outside one corner, aimed at the middle."""
    pose = overview_pose(BOUNDS)
    assert pose.kind == "overview"
    assert pose.position[0] < BOUNDS[0] and pose.position[1] < BOUNDS[1]
    assert pose.position[2] == pytest.approx(300.0 * 0.35)
    np.testing.assert_allclose(pose.look_at, [0.0, 0.0, 0.0])


def test_ego_pose_is_deterministic_for_a_seed() -> None:
    """The same rng stream gives the same pose."""
    scenario = _scenario()
    first = sample_ego_pose(scenario, np.random.Generator(np.random.PCG64([1, 2])))
    second = sample_ego_pose(scenario, np.random.Generator(np.random.PCG64([1, 2])))
    assert first is not None and second is not None
    np.testing.assert_allclose(first.position, second.position)
    np.testing.assert_allclose(first.look_at, second.look_at)


def test_ego_poses_are_usable_positions() -> None:
    """Ego cameras are at sensor height, outside buildings and vehicles, looking ahead."""
    scenario = _scenario()
    rng = np.random.Generator(np.random.PCG64([7, 7]))
    for _ in range(20):
        pose = sample_ego_pose(scenario, rng)
        assert pose is not None
        assert pose.kind == "ego"
        assert EGO_HEIGHT_RANGE_M[0] <= pose.position[2] <= EGO_HEIGHT_RANGE_M[1]
        ground = pose.position[:2]
        for building in scenario.buildings:
            x_min, y_min, x_max, y_max = building.aabb
            assert not (
                x_min - BUILDING_MARGIN_M <= ground[0] <= x_max + BUILDING_MARGIN_M
                and y_min - BUILDING_MARGIN_M <= ground[1] <= y_max + BUILDING_MARGIN_M
            )
        for vehicle in scenario.vehicles:
            x_min, y_min, x_max, y_max = vehicle.aabb
            assert not (x_min <= ground[0] <= x_max and y_min <= ground[1] <= y_max)
        assert np.linalg.norm(pose.look_at[:2] - ground) == pytest.approx(LOOK_AHEAD_M)


def test_ego_pose_needs_lanes() -> None:
    """A scenario without lanes has no ego pose."""
    scenario = _scenario()
    scenario.lanes = {}
    assert sample_ego_pose(scenario, np.random.Generator(np.random.PCG64([1]))) is None
