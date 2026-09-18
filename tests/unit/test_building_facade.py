"""Unit tests for building_facade's real modular kit-piece tiling.

Covers the invariants the live UE5 proof-of-concept this module is based
on needs to hold in code: deterministic piece placement, exact
corner/wall/column counts derived from a quantized footprint, no two
pieces landing at the same position, and consecutive wall/column/corner
pieces along one edge spaced exactly the real, point-cloud-measured
module widths apart (see KNOWN_GAPS_AND_ISSUES.md and
building_placement.py's own module-constants comment for the full real
numbers this session re-measured). Entrance pieces are deliberately never
emitted (see building_facade.py's own docstring for the real, confirmed
material bug that gated this) -- covered here by asserting no entrance
asset ever appears.
"""

import math

import numpy as np
import numpy.typing as npt
import pytest

from src.procedural.building_facade import generate_building_facade_pieces
from src.procedural.building_placement import (
    FACADE_CORNER_TO_FIRST_WALL_METERS,
    FACADE_FLOOR_HEIGHT_METERS,
    FACADE_WALL_MODULE_METERS,
    FACADE_WALL_REAL_WIDTH_METERS,
    Building,
)
from src.procedural.city_sample_assets import BUILDING_KITS

KIT = BUILDING_KITS["CHA_L1"]


def _quantized_building(
    building_id: int, wall_count_x: int, wall_count_y: int, floors: int
) -> Building:
    """A Building whose width/depth/height are exact module multiples --
    matches what BuildingPlacementGenerator's quantization guarantees."""
    width = FACADE_CORNER_TO_FIRST_WALL_METERS + wall_count_x * FACADE_WALL_MODULE_METERS
    depth = FACADE_CORNER_TO_FIRST_WALL_METERS + wall_count_y * FACADE_WALL_MODULE_METERS
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
    """Each floor gets exactly 4 vertices, each with ONE plain corner
    piece (real point-cloud evidence, re-measured this session: the
    plain CornerEx asset is what Epic's own generator uses at 15 of 16
    real corner-vertex instances -- see this module's own docstring),
    plus the real wall count each edge's quantized length implies, plus
    one real Column piece between every pair of consecutive walls on the
    same edge (``wall_count - 1`` per edge, when ``wall_count >= 1`` --
    real point-cloud evidence of an exact, zero-exception Wall/Column
    alternation); no entrance pieces appear (see this module's own
    docstring)."""
    wall_count_x, wall_count_y, floors = 2, 3, 2
    building = _quantized_building(0, wall_count_x, wall_count_y, floors)

    pieces = generate_building_facade_pieces(building, KIT)

    corners = [p for p in pieces if p.asset_path == KIT.corner_asset_path]
    walls = [p for p in pieces if p.asset_path == KIT.wall_asset_path]
    columns = [p for p in pieces if p.asset_path == KIT.column_asset_path]
    entrances = [p for p in pieces if p.asset_path == KIT.entrance_asset_path]

    assert len(corners) == 4 * floors
    walls_per_floor = 2 * wall_count_x + 2 * wall_count_y
    columns_per_floor = 2 * max(0, wall_count_x - 1) + 2 * max(0, wall_count_y - 1)
    assert len(entrances) == 0
    assert len(walls) == walls_per_floor * floors
    assert len(columns) == columns_per_floor * floors


def test_facade_pieces_no_duplicate_positions() -> None:
    """No two pieces of the SAME asset land at the exact same position --
    a real symptom a tiling-math bug (e.g. double-counting a wall) would
    produce. Duplicates are checked within each asset path, not across
    all pieces, since different asset types (e.g. a wall and a column)
    are never expected to share a position anyway."""
    building = _quantized_building(0, wall_count_x=2, wall_count_y=2, floors=3)
    pieces = generate_building_facade_pieces(building, KIT)

    positions_by_asset: dict[str, list[tuple[float, ...]]] = {}
    for p in pieces:
        positions_by_asset.setdefault(p.asset_path, []).append(
            tuple(np.round(p.position, decimals=6))
        )
    for asset_path, positions in positions_by_asset.items():
        assert len(positions) == len(set(positions)), f"duplicate position for {asset_path}"


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

    # Wall pieces store rotation_rad + pi (the outward-facing orientation
    # fix -- see building_facade.py's module docstring), but their
    # TILING direction is still governed by the underlying, unmodified
    # rotation, so pieces on the edge tiling along -y are the ones whose
    # stored rotation_rad is pi (0.0 + pi), not 0.0 (the left edge, from
    # corners[0]=(x_min,y_max) to corners[1]=(x_min,y_min) -- see
    # _corner_points).
    wall_run = sorted(
        (
            p
            for p in pieces
            if p.asset_path == KIT.wall_asset_path and p.rotation_rad == pytest.approx(math.pi)
        ),
        key=lambda p: -p.position[1],
    )
    assert len(wall_run) == 3
    for earlier, later in zip(wall_run, wall_run[1:]):
        gap = np.linalg.norm(later.position[:2] - earlier.position[:2])
        assert gap == pytest.approx(FACADE_WALL_MODULE_METERS)


def _true_edge_direction_for(
    position: npt.NDArray[np.float64], building: Building, incoming: bool = False
) -> npt.NDArray[np.float64]:
    """The real geometric direction of the edge touching whichever true
    footprint vertex ``position`` (a corner piece's pivot) is nearest to
    -- the edge STARTING there by default, or (``incoming=True``) the
    edge ENDING there (the previous edge around the perimeter)."""
    x_min, y_min, x_max, y_max = building.aabb
    vertices = [
        np.array([x_min, y_max]),
        np.array([x_min, y_min]),
        np.array([x_max, y_min]),
        np.array([x_max, y_max]),
    ]
    nearest_index = int(np.argmin([np.linalg.norm(position - v) for v in vertices]))
    if incoming:
        direction = vertices[nearest_index] - vertices[(nearest_index - 1) % 4]
    else:
        direction = vertices[(nearest_index + 1) % 4] - vertices[nearest_index]
    normalized: npt.NDArray[np.float64] = direction / np.linalg.norm(direction)
    return normalized


def _predicted_direction(rotation_rad: float) -> npt.NDArray[np.float64]:
    """A wall placed with rotation_rad=0 is confirmed (this module's own
    docstring) to tile along world (0, -1); rotating that by rotation_rad
    (the corrected, non-negated convention -- see
    building_facade._rotate_2d's own docstring) predicts the real edge
    direction for that rotation."""
    cos_r, sin_r = np.cos(rotation_rad), np.sin(rotation_rad)
    rotation_matrix = np.array([[cos_r, -sin_r], [sin_r, cos_r]])
    predicted: npt.NDArray[np.float64] = rotation_matrix @ np.array([0.0, -1.0])
    return predicted


def test_corner_piece_rotation_matches_its_own_edge_direction() -> None:
    """Each corner's STORED rotation_rad is the own-edge tiling rotation
    plus one extra quarter turn (see building_facade.py's own module
    docstring/inline comment) -- a real, live-screenshot-confirmed fix
    for the corner mesh's own local orientation convention differing
    from the wall's by 90 degrees (the same class of fix as the wall's
    own rotation_rad + pi flip, just a different real offset for this
    different mesh). Subtracting that quarter turn back out before
    predicting a direction recovers the underlying own-edge tiling
    rotation, which must still match the REAL geometric direction of the
    edge STARTING at that corner (its own edge) -- the absolute-
    correctness check the older spacing/count tests didn't cover (they
    kept passing even when a real rotation-sign bug had every corner's
    rotation backwards, since spacing between consecutive same-rotation
    walls stays correct regardless of which absolute direction "forward"
    is)."""
    building = _quantized_building(0, wall_count_x=1, wall_count_y=1, floors=1)
    pieces = generate_building_facade_pieces(building, KIT)
    corners = [p for p in pieces if p.asset_path == KIT.corner_asset_path]
    assert len(corners) == 4

    for corner in corners:
        true_direction = _true_edge_direction_for(corner.position[:2], building, incoming=False)
        own_edge_rotation = corner.rotation_rad - (math.pi / 2.0)
        assert np.allclose(_predicted_direction(own_edge_rotation), true_direction, atol=1e-6)


def test_facade_column_pieces_sit_in_the_real_gap_between_consecutive_walls() -> None:
    """Each Column piece's position must be exactly
    FACADE_WALL_REAL_WIDTH_METERS along the tiling direction from the
    wall immediately before it, and exactly
    (FACADE_WALL_MODULE_METERS - FACADE_WALL_REAL_WIDTH_METERS) before
    the next wall -- the real, point-cloud-measured 325cm/125cm
    Wall/Column alternation this session found real City Sample
    buildings use (see this module's own docstring), and the real fix
    for the visible reveal gap this project's own generator used to
    leave empty."""
    building = _quantized_building(0, wall_count_x=1, wall_count_y=3, floors=1)
    pieces = generate_building_facade_pieces(building, KIT)

    # Same edge-selection convention as
    # test_facade_wall_pieces_spaced_one_module_apart_along_edge.
    walls = sorted(
        (
            p
            for p in pieces
            if p.asset_path == KIT.wall_asset_path and p.rotation_rad == pytest.approx(math.pi)
        ),
        key=lambda p: -p.position[1],
    )
    columns = sorted(
        (
            p
            for p in pieces
            if p.asset_path == KIT.column_asset_path and p.rotation_rad == pytest.approx(math.pi)
        ),
        key=lambda p: -p.position[1],
    )
    assert len(walls) == 3
    assert len(columns) == 2  # one fewer than walls -- no column after the last wall

    for wall, column in zip(walls, columns):
        gap_after_wall = np.linalg.norm(column.position[:2] - wall.position[:2])
        assert gap_after_wall == pytest.approx(FACADE_WALL_REAL_WIDTH_METERS)
    for column, next_wall in zip(columns, walls[1:]):
        gap_before_next_wall = np.linalg.norm(next_wall.position[:2] - column.position[:2])
        assert gap_before_next_wall == pytest.approx(
            FACADE_WALL_MODULE_METERS - FACADE_WALL_REAL_WIDTH_METERS
        )
