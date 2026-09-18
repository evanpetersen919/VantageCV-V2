"""Unit tests for building_facade's real modular kit-piece tiling.

Covers the invariants the live UE5 proof-of-concept this module is based
on needs to hold in code: deterministic piece placement, exact
corner/wall counts derived from a quantized footprint, no two pieces
landing at the same position, and consecutive wall/corner pieces along one
edge spaced exactly one module width apart (the real geometric condition
for seamless tiling -- see KNOWN_GAPS_AND_ISSUES.md). Entrance pieces are
deliberately never emitted (see building_facade.py's own docstring for the
real, confirmed material bug that gated this) -- covered here by
asserting no entrance asset ever appears.
"""

import numpy as np
import numpy.typing as npt
import pytest

from src.procedural.building_facade import generate_building_facade_pieces
from src.procedural.building_placement import (
    FACADE_CORNER_MODULE_METERS,
    FACADE_FLOOR_HEIGHT_METERS,
    FACADE_WALL_MODULE_METERS,
    Building,
)
from src.procedural.city_sample_assets import BUILDING_KITS

KIT = BUILDING_KITS["CHA_L1"]


def _quantized_building(
    building_id: int, wall_count_x: int, wall_count_y: int, floors: int
) -> Building:
    """A Building whose width/depth/height are exact module multiples --
    matches what BuildingPlacementGenerator's quantization guarantees."""
    width = 2.0 * FACADE_CORNER_MODULE_METERS + wall_count_x * FACADE_WALL_MODULE_METERS
    depth = 2.0 * FACADE_CORNER_MODULE_METERS + wall_count_y * FACADE_WALL_MODULE_METERS
    height = floors * FACADE_FLOOR_HEIGHT_METERS
    return Building(
        building_id=building_id,
        center=np.array([0.0, 0.0]),
        width=width,
        depth=depth,
        height=height,
    )


def test_facade_pieces_deterministic() -> None:
    """The same Building + kit always produces the exact same piece
    list -- a pure function, no RNG."""
    building = _quantized_building(0, wall_count_x=2, wall_count_y=3, floors=2)
    first = generate_building_facade_pieces(building, KIT)
    second = generate_building_facade_pieces(building, KIT)

    assert len(first) == len(second)
    for piece_a, piece_b in zip(first, second):
        assert piece_a.asset_path == piece_b.asset_path
        assert np.allclose(piece_a.position, piece_b.position)
        assert piece_a.rotation_rad == piece_b.rotation_rad


def test_facade_pieces_correct_count_per_floor() -> None:
    """Each floor gets exactly 4 corners plus the real wall count each
    edge's quantized length implies; no entrance pieces appear (see this
    module's own docstring)."""
    wall_count_x, wall_count_y, floors = 2, 3, 2
    building = _quantized_building(0, wall_count_x, wall_count_y, floors)

    pieces = generate_building_facade_pieces(building, KIT)

    corners = [p for p in pieces if p.asset_path == KIT.corner_asset_path]
    walls = [p for p in pieces if p.asset_path == KIT.wall_asset_path]
    entrances = [p for p in pieces if p.asset_path == KIT.entrance_asset_path]

    assert len(corners) == 4 * floors
    walls_per_floor = 2 * wall_count_x + 2 * wall_count_y
    assert len(entrances) == 0
    assert len(walls) == walls_per_floor * floors


def test_facade_pieces_no_duplicate_positions() -> None:
    """No two pieces land at the exact same position -- a real symptom
    a tiling-math bug (e.g. double-counting a corner) would produce."""
    building = _quantized_building(0, wall_count_x=2, wall_count_y=2, floors=3)
    pieces = generate_building_facade_pieces(building, KIT)

    positions = [tuple(np.round(p.position, decimals=6)) for p in pieces]
    assert len(positions) == len(set(positions))


def test_facade_pieces_floor_count_matches_height() -> None:
    """Ground-floor-only pieces (z=0) appear exactly once per building,
    and the highest floor's z matches (num_floors - 1) * FLOOR_HEIGHT."""
    floors = 4
    building = _quantized_building(0, wall_count_x=1, wall_count_y=1, floors=floors)
    pieces = generate_building_facade_pieces(building, KIT)

    z_values = sorted({round(float(p.position[2]), 6) for p in pieces})
    expected = [round(i * FACADE_FLOOR_HEIGHT_METERS, 6) for i in range(floors)]
    assert z_values == expected


def test_facade_wall_pieces_spaced_one_module_apart_along_edge() -> None:
    """Consecutive wall pieces along one straight edge (same rotation,
    same z) are separated by exactly FACADE_WALL_MODULE_METERS -- the
    real geometric condition for seamless tiling confirmed live in UE5
    (see this module's own docstring)."""
    building = _quantized_building(0, wall_count_x=1, wall_count_y=3, floors=1)
    pieces = generate_building_facade_pieces(building, KIT)

    # rotation_rad == 0.0 pieces tile along -y (see building_facade.py's
    # module docstring) on the edge whose length is wall_count_y modules
    # (the left edge, from corners[0]=(x_min,y_max) to corners[1]=
    # (x_min,y_min) -- see _corner_points).
    wall_run = sorted(
        (p for p in pieces if p.asset_path == KIT.wall_asset_path and p.rotation_rad == 0.0),
        key=lambda p: -p.position[1],
    )
    assert len(wall_run) == 3
    for earlier, later in zip(wall_run, wall_run[1:]):
        gap = np.linalg.norm(later.position[:2] - earlier.position[:2])
        assert gap == pytest.approx(FACADE_WALL_MODULE_METERS)


def _true_edge_direction_for(
    position: npt.NDArray[np.float64], building: Building
) -> npt.NDArray[np.float64]:
    """The real geometric direction of the edge starting at whichever true
    footprint vertex ``position`` (a corner piece's pivot) is nearest to."""
    x_min, y_min, x_max, y_max = building.aabb
    vertices = [
        np.array([x_min, y_max]),
        np.array([x_min, y_min]),
        np.array([x_max, y_min]),
        np.array([x_max, y_max]),
    ]
    nearest_index = int(np.argmin([np.linalg.norm(position - v) for v in vertices]))
    direction = vertices[(nearest_index + 1) % 4] - vertices[nearest_index]
    normalized: npt.NDArray[np.float64] = direction / np.linalg.norm(direction)
    return normalized


def test_corner_piece_rotation_matches_its_own_edge_direction() -> None:
    """Each corner's rotation_rad must make a wall placed at that same
    rotation tile along the REAL geometric direction of the edge starting
    at that corner -- the absolute-correctness check the older
    spacing/count tests didn't cover (they kept passing even when a real
    rotation-sign bug had every corner's rotation backwards, since
    spacing between consecutive same-rotation walls stays correct
    regardless of which absolute direction "forward" is)."""
    building = _quantized_building(0, wall_count_x=1, wall_count_y=1, floors=1)
    pieces = generate_building_facade_pieces(building, KIT)
    corners = [p for p in pieces if p.asset_path == KIT.corner_asset_path]
    assert len(corners) == 4

    # A wall placed with rotation_rad=0 is confirmed (this module's own
    # docstring) to tile along world (0, -1); rotating that by
    # rotation_rad (the corrected, non-negated convention -- see
    # building_facade._rotate_2d's own docstring) must reproduce each
    # corner's real edge direction.
    for corner in corners:
        true_direction = _true_edge_direction_for(corner.position[:2], building)
        cos_r, sin_r = np.cos(corner.rotation_rad), np.sin(corner.rotation_rad)
        rotation_matrix = np.array([[cos_r, -sin_r], [sin_r, cos_r]])
        predicted_direction = rotation_matrix @ np.array([0.0, -1.0])
        assert np.allclose(predicted_direction, true_direction, atol=1e-6)
