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

import dataclasses
import math

import numpy as np
import numpy.typing as npt
import pytest

from src.procedural.building_facade import generate_building_facade_pieces
from src.procedural.building_placement import Building
from src.procedural.city_sample_assets import BUILDING_KITS, BUILDING_STYLES, BuildingStyle

KIT = BUILDING_KITS["CHA_L1"]
STYLE = BuildingStyle(name="CHA_L1_ONLY", levels=(KIT,))
CORNER_REACH = KIT.corner_to_first_wall_m
WALL_PITCH = KIT.wall_pitch_m
WALL_WIDTH = KIT.wall_width_m
FLOOR_HEIGHT = KIT.floor_height_m


def _quantized_building(
    building_id: int, wall_count_x: int, wall_count_y: int, floors: int
) -> Building:
    """A Building whose width/depth/height are exact module multiples --
    matches what BuildingPlacementGenerator's quantization guarantees."""
    width = STYLE.edge_length_for_wall_count(wall_count_x)
    depth = STYLE.edge_length_for_wall_count(wall_count_y)
    height = floors * FLOOR_HEIGHT
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
    first = generate_building_facade_pieces(building, STYLE)
    second = generate_building_facade_pieces(building, STYLE)

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

    pieces = generate_building_facade_pieces(building, STYLE)

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
    pieces = generate_building_facade_pieces(building, STYLE)

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
    pieces = generate_building_facade_pieces(building, STYLE)

    z_values = sorted({round(float(p.position[2]), 6) for p in pieces})
    expected = [round(i * FLOOR_HEIGHT, 6) for i in range(floors)]
    assert z_values == expected


def test_facade_wall_pieces_spaced_one_module_apart_along_edge() -> None:
    """Consecutive wall pieces along one straight edge (same rotation,
    same z) are separated by exactly WALL_PITCH -- the
    real geometric condition for seamless tiling confirmed live in UE5
    (see this module's own docstring)."""
    building = _quantized_building(0, wall_count_x=1, wall_count_y=3, floors=1)
    pieces = generate_building_facade_pieces(building, STYLE)

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
        assert gap == pytest.approx(WALL_PITCH)


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
    pieces = generate_building_facade_pieces(building, STYLE)
    corners = [p for p in pieces if p.asset_path == KIT.corner_asset_path]
    assert len(corners) == 4

    for corner in corners:
        true_direction = _true_edge_direction_for(corner.position[:2], building, incoming=False)
        own_edge_rotation = corner.rotation_rad - KIT.corner_yaw_offset_rad
        assert np.allclose(_predicted_direction(own_edge_rotation), true_direction, atol=1e-6)


def test_facade_column_pieces_sit_in_the_real_gap_between_consecutive_walls() -> None:
    """Each Column piece's position must be exactly
    WALL_WIDTH along the tiling direction from the
    wall immediately before it, and exactly
    (WALL_PITCH - WALL_WIDTH) before
    the next wall -- the real, point-cloud-measured 325cm/125cm
    Wall/Column alternation this session found real City Sample
    buildings use (see this module's own docstring), and the real fix
    for the visible reveal gap this project's own generator used to
    leave empty."""
    building = _quantized_building(0, wall_count_x=1, wall_count_y=3, floors=1)
    pieces = generate_building_facade_pieces(building, STYLE)

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
        assert gap_after_wall == pytest.approx(WALL_WIDTH)
    for column, next_wall in zip(columns, walls[1:]):
        gap_before_next_wall = np.linalg.norm(next_wall.position[:2] - column.position[:2])
        assert gap_before_next_wall == pytest.approx(WALL_PITCH - WALL_WIDTH)


def _two_level_style() -> BuildingStyle:
    """A synthetic style whose upper level has a different floor height
    and different asset paths (same horizontal grid), to check per-floor
    kit selection and cumulative z placement."""
    upper = dataclasses.replace(
        KIT,
        wall_asset_path="/Game/Test/UpperWall",
        corner_asset_path="/Game/Test/UpperCorner",
        column_asset_path="/Game/Test/UpperColumn",
        floor_height_m=3.0,
    )
    return BuildingStyle(name="TEST", levels=(KIT, upper))


def test_multi_level_style_uses_per_floor_kit_and_cumulative_z() -> None:
    """Floor 0 uses the ground kit at z=0; floors above use the next
    level's kit, stacked at cumulative heights (5.0, 8.0, 11.0), the last
    level repeating -- mirroring real CHA (L1 5.0m, then 3.0m floors)."""
    style = _two_level_style()
    height = style.total_height(4)
    assert height == pytest.approx(5.0 + 3.0 * 3)
    width = STYLE.edge_length_for_wall_count(2)
    building = Building(0, np.array([0.0, 0.0]), width, width, height)

    pieces = generate_building_facade_pieces(building, style)

    for floor_index, expected_z in enumerate([0.0, 5.0, 8.0, 11.0]):
        expected_wall = style.kit_for_floor(floor_index).wall_asset_path
        walls_here = [
            p
            for p in pieces
            if p.asset_path in (KIT.wall_asset_path, "/Game/Test/UpperWall")
            and p.position[2] == pytest.approx(expected_z)
        ]
        assert len(walls_here) == 8
        assert all(p.asset_path == expected_wall for p in walls_here)


def test_building_style_rejects_mismatched_horizontal_grid() -> None:
    """Levels of one style must share a grid -- otherwise one quantized
    footprint could not tile on every floor."""
    wider = dataclasses.replace(KIT, wall_width_m=KIT.wall_width_m + 0.5)
    with pytest.raises(ValueError):
        BuildingStyle(name="BAD", levels=(KIT, wider))


def test_building_style_height_quantization_rounds_up_to_real_stack() -> None:
    """floor_count_for_height never shrinks a height and lands exactly on
    a cumulative real stack height."""
    style = _two_level_style()
    for sampled in [0.1, 5.0, 5.01, 8.0, 8.5, 20.0]:
        count = style.floor_count_for_height(sampled)
        assert style.total_height(count) >= sampled - 1e-6
        assert count == 1 or style.total_height(count - 1) < sampled


def test_last_wall_ends_one_corner_reach_before_far_vertex() -> None:
    """Real edges (48/48 measured CHA and CHH edges) start the first wall
    one corner reach after the start vertex and end the last wall exactly
    one corner reach before the far vertex (``2C + N*W + (N-1)*P``)."""
    building = _quantized_building(0, wall_count_x=2, wall_count_y=3, floors=1)
    pieces = generate_building_facade_pieces(building, STYLE)
    _, y_min, _, y_max = building.aabb

    # Edge 0 runs down the left side from (x_min, y_max) toward y_min; its
    # walls are the ones stored with rotation_rad == pi (0 + wall offset).
    left_walls = [
        p
        for p in pieces
        if p.asset_path == KIT.wall_asset_path and p.rotation_rad == pytest.approx(math.pi)
    ]
    assert len(left_walls) == 3
    offsets = sorted(y_max - float(p.position[1]) for p in left_walls)
    edge_length = y_max - y_min
    assert offsets[0] == pytest.approx(CORNER_REACH)
    assert offsets[-1] + WALL_WIDTH == pytest.approx(edge_length - CORNER_REACH)


@pytest.mark.parametrize("style_name", sorted(BUILDING_STYLES))
def test_every_registered_style_tiles_a_tall_building_exactly(style_name: str) -> None:
    """Every real style (CHA, CHH, ...) yields the expected piece counts
    for a tall building (10 floors, exercising the repeating top level),
    with the first and last wall of an edge one corner reach from the
    vertices and every floor at that style's cumulative height."""
    style = BUILDING_STYLES[style_name]
    walls_x, walls_y, floors = 3, 2, 10
    building = Building(
        0,
        np.array([0.0, 0.0]),
        style.edge_length_for_wall_count(walls_x),
        style.edge_length_for_wall_count(walls_y),
        style.total_height(floors),
        style_name=style_name,
    )

    pieces = generate_building_facade_pieces(building, style)

    per_floor_walls = 2 * walls_x + 2 * walls_y
    per_floor_columns = 2 * (walls_x - 1) + 2 * (walls_y - 1)
    assert len(pieces) == floors * (4 + per_floor_walls + per_floor_columns)
    z_values = sorted({round(float(p.position[2]), 6) for p in pieces})
    assert z_values == [round(style.floor_base_z(i), 6) for i in range(floors)]
    ground = style.kit_for_floor(0)
    left_walls = [
        p
        for p in pieces
        if p.asset_path == ground.wall_asset_path
        and p.rotation_rad == pytest.approx(ground.wall_yaw_offset_rad)
        and p.position[2] == pytest.approx(0.0)
    ]
    y_max = building.aabb[3]
    offsets = sorted(y_max - float(p.position[1]) for p in left_walls)
    assert offsets[0] == pytest.approx(ground.corner_to_first_wall_m)
    assert offsets[-1] + ground.wall_width_m == pytest.approx(
        building.depth - ground.corner_to_first_wall_m
    )
