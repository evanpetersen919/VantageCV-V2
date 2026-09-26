"""Tests for ego and overview camera pose sampling."""

from pathlib import Path

import numpy as np
import pytest

from src.orchestration.camera_sampling import (  # pylint: disable=protected-access
    BUILDING_MARGIN_M,
    CLEAR_TO_EDGE_M,
    EGO_EDGE_INSET_M,
    EGO_HEIGHT_RANGE_M,
    LOOK_AHEAD_M,
    MIN_CLEAR_AHEAD_VEHICLE_M,
    _segment_hits_box,
    overview_pose,
    sample_ego_pose,
    sample_lot_pose,
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


def test_ego_views_keep_a_clear_corridor_to_the_city_edge() -> None:
    """With bounds given, the point 60 m ahead of every ego pose is still inside the city."""
    scenario = _scenario()
    rng = np.random.Generator(np.random.PCG64([3, 3]))
    for _ in range(30):
        pose = sample_ego_pose(scenario, rng, BOUNDS)
        assert pose is not None
        direction = pose.look_at[:2] - pose.position[:2]
        ahead = pose.position[:2] + direction / np.linalg.norm(direction) * CLEAR_TO_EDGE_M
        assert BOUNDS[0] <= ahead[0] <= BOUNDS[2] and BOUNDS[1] <= ahead[1] <= BOUNDS[3]


def test_lot_pose_is_inside_a_lot_on_its_aisle_looking_inward() -> None:
    """The lot camera sits just inside a driveway entrance, aimed away from the road."""
    config = load_scenario_config(CONFIG).model_copy(update={"parking_lot_fraction": 0.7})
    scenario = generate_scenario(100, config, BOUNDS, "lot")
    lots = [lot for lot in scenario.parking_lots if lot.driveway is not None]
    assert lots
    rng = np.random.Generator(np.random.PCG64([5, 5]))
    for _ in range(20):
        pose = sample_lot_pose(scenario, rng)
        assert pose is not None and pose.kind == "lot"
        ground = pose.position[:2]
        inside = [
            lot
            for lot in lots
            if lot.bounds[0] <= ground[0] <= lot.bounds[2]
            and lot.bounds[1] <= ground[1] <= lot.bounds[3]
        ]
        assert inside
        lot = inside[0]
        driveway = lot.driveway
        assert driveway is not None
        inward = {"x0": (1, 0), "x1": (-1, 0), "y0": (0, 1), "y1": (0, -1)}[driveway.side]
        direction = (pose.look_at[:2] - ground) / np.linalg.norm(pose.look_at[:2] - ground)
        assert float(np.dot(direction, inward)) > 0.9


def test_no_lot_pose_without_lots() -> None:
    """A scenario with no lots has no lot view."""
    scenario = _scenario()
    scenario.parking_lots = []
    assert sample_lot_pose(scenario, np.random.Generator(np.random.PCG64([1]))) is None


def test_ego_poses_stay_inset_from_the_city_edge() -> None:
    """The camera itself (not just the point ahead) must be EGO_EDGE_INSET_M inside the bounds:
    a wide FOV can see the void to the side even when the road ahead is clear."""
    scenario = _scenario()
    rng = np.random.Generator(np.random.PCG64([9, 9]))
    for _ in range(30):
        pose = sample_ego_pose(scenario, rng, BOUNDS)
        assert pose is not None
        ground = pose.position[:2]
        assert BOUNDS[0] + EGO_EDGE_INSET_M <= ground[0] <= BOUNDS[2] - EGO_EDGE_INSET_M
        assert BOUNDS[1] + EGO_EDGE_INSET_M <= ground[1] <= BOUNDS[3] - EGO_EDGE_INSET_M


def test_ego_pose_is_not_framed_nose_in_against_a_parked_vehicle() -> None:
    """A vehicle a few metres directly ahead disqualifies the pose (the earlier version only
    checked whether the ground point itself sat inside a vehicle's footprint, missing a vehicle
    a short distance further along the same heading -- a real bug found by eye in a live render:
    the camera ended up effectively inside the vehicle's body, a near-black, useless frame)."""
    scenario = _scenario()
    rng = np.random.Generator(np.random.PCG64([11, 11]))
    for _ in range(30):
        pose = sample_ego_pose(scenario, rng)
        assert pose is not None
        ground = pose.position[:2]
        direction = pose.look_at[:2] - ground
        direction = direction / np.linalg.norm(direction)
        close_ahead = ground + direction * MIN_CLEAR_AHEAD_VEHICLE_M
        for vehicle in scenario.vehicles:
            assert not _segment_hits_box(ground, close_ahead, vehicle.aabb)
