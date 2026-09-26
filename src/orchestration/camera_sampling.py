"""Camera poses for rendered frames: an ego-vehicle view and an overview.

The ego view sits on a driving lane's centreline at a typical sensor height and
looks ahead along the lane with a little yaw jitter. Poses are rejected when the
camera would be inside a building or a parked/driving vehicle, or when a
building blocks the view within ``MIN_CLEAR_AHEAD_M``. Given the scenario bounds, a pose is also
rejected when the city's edge lies within ``CLEAR_TO_EDGE_M`` ahead, since the frame would be
mostly the empty horizon beyond the generated area.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

from src.orchestration.dataset_generator import Bounds, ScenarioResult

EGO_HEIGHT_RANGE_M = (1.4, 1.9)
LOOK_AHEAD_M = 30.0
LOOK_TARGET_HEIGHT_M = 1.2
YAW_JITTER_RAD = np.radians(10.0)
LANE_POSITION_RANGE = (0.1, 0.9)
MIN_CLEAR_AHEAD_M = 15.0
CLEAR_TO_EDGE_M = 60.0
EDGE_MARGIN_M = 5.0
BUILDING_MARGIN_M = 1.0
VEHICLE_MARGIN_M = 0.5
MAX_ATTEMPTS = 80
OVERVIEW_OFFSET_FRACTION = 0.05
OVERVIEW_HEIGHT_FRACTION = 0.35


@dataclass(frozen=True)
class CameraPose:
    """Where the camera is and what it looks at, in python world metres."""

    kind: str
    position: NDArray[np.float64]
    look_at: NDArray[np.float64]


def overview_pose(bounds: Bounds) -> CameraPose:
    """A camera above and outside one corner of ``bounds`` looking at its centre."""
    x_min, y_min, x_max, y_max = bounds
    extent = max(x_max - x_min, y_max - y_min)
    position = np.array(
        [
            x_min - extent * OVERVIEW_OFFSET_FRACTION,
            y_min - extent * OVERVIEW_OFFSET_FRACTION,
            extent * OVERVIEW_HEIGHT_FRACTION,
        ]
    )
    return CameraPose(
        "overview", position, np.array([(x_min + x_max) / 2.0, (y_min + y_max) / 2.0, 0.0])
    )


def _inside(
    point: NDArray[np.float64], aabb: Tuple[float, float, float, float], margin: float
) -> bool:
    """Whether a 2D point lies within an (x_min, y_min, x_max, y_max) box grown by ``margin``."""
    return bool(
        aabb[0] - margin <= point[0] <= aabb[2] + margin
        and aabb[1] - margin <= point[1] <= aabb[3] + margin
    )


def _segment_hits_box(
    start: NDArray[np.float64],
    end: NDArray[np.float64],
    aabb: Tuple[float, float, float, float],
) -> bool:
    """Whether the 2D segment start->end crosses the box (slab test)."""
    delta = end - start
    low, high = 0.0, 1.0
    for axis in range(2):
        lower, upper = aabb[axis], aabb[axis + 2]
        if abs(delta[axis]) < 1e-12:
            if not lower <= start[axis] <= upper:
                return False
            continue
        first, second = (lower - start[axis]) / delta[axis], (upper - start[axis]) / delta[axis]
        low, high = max(low, min(first, second)), min(high, max(first, second))
        if low > high:
            return False
    return True


def _heading_with_jitter(
    direction: NDArray[np.float64], rng: np.random.Generator
) -> NDArray[np.float64]:
    """``direction`` turned by a random yaw within +-YAW_JITTER_RAD."""
    yaw = float(rng.uniform(-YAW_JITTER_RAD, YAW_JITTER_RAD))
    cos_y, sin_y = np.cos(yaw), np.sin(yaw)
    return np.array(
        [direction[0] * cos_y - direction[1] * sin_y, direction[0] * sin_y + direction[1] * cos_y]
    )


def _within(point: NDArray[np.float64], bounds: Bounds, margin: float) -> bool:
    """Whether a 2D point is inside ``bounds`` shrunk by ``margin`` on every side."""
    x_min, y_min, x_max, y_max = bounds
    return bool(
        x_min + margin <= point[0] <= x_max - margin
        and y_min + margin <= point[1] <= y_max - margin
    )


def _candidate(
    scenario: ScenarioResult,
    rng: np.random.Generator,
    lanes: List[int],
    bounds: Optional[Bounds],
) -> Optional[CameraPose]:
    """One random ego pose on a random lane, or ``None`` if it is unusable."""
    lane = scenario.lanes[lanes[int(rng.integers(len(lanes)))]]
    segment = int(rng.integers(len(lane.centerline) - 1))
    start, end = lane.centerline[segment], lane.centerline[segment + 1]
    ground = start + float(rng.uniform(*LANE_POSITION_RANGE)) * (end - start)
    if any(_inside(ground, building.aabb, BUILDING_MARGIN_M) for building in scenario.buildings):
        return None
    if any(_inside(ground, vehicle.aabb, VEHICLE_MARGIN_M) for vehicle in scenario.vehicles):
        return None
    direction = (end - start) / max(float(np.linalg.norm(end - start)), 1e-9)
    heading = _heading_with_jitter(direction, rng)
    if bounds is not None and not _within(
        ground + heading * CLEAR_TO_EDGE_M, bounds, EDGE_MARGIN_M
    ):
        return None
    clear_end = ground + heading * MIN_CLEAR_AHEAD_M
    if any(_segment_hits_box(ground, clear_end, b.aabb) for b in scenario.buildings):
        return None
    target = ground + heading * LOOK_AHEAD_M
    return CameraPose(
        "ego",
        np.array([ground[0], ground[1], float(rng.uniform(*EGO_HEIGHT_RANGE_M))]),
        np.array([target[0], target[1], LOOK_TARGET_HEIGHT_M]),
    )


def sample_ego_pose(
    scenario: ScenarioResult, rng: np.random.Generator, bounds: Optional[Bounds] = None
) -> Optional[CameraPose]:
    """A valid ego camera pose for ``scenario``, or ``None`` if none was found.

    With ``bounds`` (the area the scenario was generated in), views toward the edge are avoided.
    """
    lanes = [lane_id for lane_id, lane in scenario.lanes.items() if len(lane.centerline) >= 2]
    if not lanes:
        return None
    for _ in range(MAX_ATTEMPTS):
        pose = _candidate(scenario, rng, lanes, bounds)
        if pose is not None:
            return pose
    return None
