"""Unit tests for the real curved sidewalk/curb corners at intersections."""

import math

import numpy as np

from src.orchestration.dataset_generator import generate_scenario
from src.procedural.building_placement import identify_city_blocks
from src.procedural.curved_corners import (
    CORNER_ASSET_PATH,
    CORNER_FILL_ASSET_PATH,
    CURB_CORNER_ASSET_PATH,
    CURB_CORNER_ROTATION_OFFSET_RAD,
    build_curved_corner_pieces,
)
from src.procedural.lane_topology import LANE_WIDTH_METERS
from src.procedural.road_edge_kit import DEFAULT_ROAD_EDGE_KIT


def test_no_edges_means_no_corners() -> None:
    """Nothing to bound a block, so nothing is built."""
    assert not build_curved_corner_pieces({}, {})


def test_three_pieces_per_corner_per_block(urban_config, bounds) -> None:
    """Every block gets exactly 3 pieces (sidewalk corner + fill + curb)
    at each of its 4 real inset corners."""
    scenario = generate_scenario(42, urban_config, bounds, "curved_corner_test")
    blocks = identify_city_blocks(scenario.nodes, scenario.edges)
    pieces = build_curved_corner_pieces(scenario.nodes, scenario.edges)

    assert blocks
    assert len(pieces) == len(blocks) * 4 * 3


def test_pieces_sit_at_the_same_inset_corners_block_pavement_uses(urban_config, bounds) -> None:
    """Each corner's (x, y) exactly matches the block's own inset corner
    (block_pavement.py's identical inset rectangle math), so the curve
    starts exactly where the flat fill's corner would otherwise be."""
    scenario = generate_scenario(42, urban_config, bounds, "curved_corner_test")
    blocks = identify_city_blocks(scenario.nodes, scenario.edges)
    pieces = build_curved_corner_pieces(scenario.nodes, scenario.edges)
    inset = max(e.num_lanes for e in scenario.edges.values()) * LANE_WIDTH_METERS

    xy_positions = {
        (round(float(p.position[0]), 6), round(float(p.position[1]), 6)) for p in pieces
    }
    for block in blocks:
        x_min, y_min = block.min(axis=0) + inset
        x_max, y_max = block.max(axis=0) - inset
        for corner in ((x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)):
            assert any(
                math.isclose(corner[0], x, abs_tol=1e-6)
                and math.isclose(corner[1], y, abs_tol=1e-6)
                for x, y in xy_positions
            )


def test_corner_and_fill_share_position_and_rotation_curb_is_separate_height() -> None:
    """Corner_01 and Corner_Fill_01 are placed identically (position and
    rotation), per the real live-verified fact that placing them
    identically produces a seamless paved corner; the curb piece shares
    the same position and sits at the curb's own real height, but is
    rotated an extra half-turn (a real, live-observed mesh-authoring
    mismatch, not a guess -- see CURB_CORNER_ROTATION_OFFSET_RAD's own
    comment)."""
    lanes_edges = _two_by_two_grid()
    pieces = build_curved_corner_pieces(*lanes_edges)

    by_corner = {}
    for piece in pieces:
        key = (round(float(piece.position[0]), 6), round(float(piece.position[1]), 6))
        by_corner.setdefault(key, []).append(piece)

    for group in by_corner.values():
        assert len(group) == 3
        paths = {p.asset_path for p in group}
        assert paths == {CORNER_ASSET_PATH, CORNER_FILL_ASSET_PATH, CURB_CORNER_ASSET_PATH}
        sidewalk = [p for p in group if p.asset_path in (CORNER_ASSET_PATH, CORNER_FILL_ASSET_PATH)]
        curb = next(p for p in group if p.asset_path == CURB_CORNER_ASSET_PATH)
        sidewalk_rotations = {round(p.rotation_rad, 9) for p in sidewalk}
        assert len(sidewalk_rotations) == 1  # corner + fill share the same rotation
        (sidewalk_rotation,) = sidewalk_rotations
        assert math.isclose(curb.rotation_rad, sidewalk_rotation + CURB_CORNER_ROTATION_OFFSET_RAD)
        assert all(p.position[2] == DEFAULT_ROAD_EDGE_KIT.sidewalk_z_m for p in sidewalk)
        assert curb.position[2] == DEFAULT_ROAD_EDGE_KIT.curb_z_m


# pylint: disable-next=too-many-locals
def test_rotation_points_each_corners_bulk_into_its_own_block_interior() -> None:
    """The derived rotation rule (see curved_corners.py's own docstring):
    at rotation ``r`` the piece's paved bulk points toward python direction
    ``(cos r - sin r, sin r + cos r)``. For each of a block's 4 corners,
    that direction must point toward the block's own interior (away from
    the corner, into the block), not out into the road."""
    lanes_edges = _two_by_two_grid()
    nodes, edges = lanes_edges
    blocks = identify_city_blocks(nodes, edges)
    pieces = build_curved_corner_pieces(nodes, edges)
    inset = max(e.num_lanes for e in edges.values()) * LANE_WIDTH_METERS

    piece_by_xy = {
        (round(float(p.position[0]), 6), round(float(p.position[1]), 6)): p
        for p in pieces
        if p.asset_path == CORNER_ASSET_PATH
    }

    for block in blocks:
        x_min, y_min = block.min(axis=0) + inset
        x_max, y_max = block.max(axis=0) - inset
        center = np.array([(x_min + x_max) / 2.0, (y_min + y_max) / 2.0])
        for corner in ((x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)):
            key = (round(corner[0], 6), round(corner[1], 6))
            piece = piece_by_xy[key]
            r = piece.rotation_rad
            bulk_dir = np.array([math.cos(r) - math.sin(r), math.sin(r) + math.cos(r)])
            interior_dir = center - np.array(corner)
            assert np.dot(bulk_dir, interior_dir) > 0


def _two_by_two_grid():
    """A 2x2 grid of blocks (3x3 nodes), matching the real
    ``RoadNetworkGenerator``/``identify_city_blocks`` shape, without the
    cost of a full ``generate_scenario`` call."""
    # pylint: disable=import-outside-toplevel
    from src.procedural.lane_topology import LaneTopologyGenerator
    from src.procedural.road_network import IntersectionType, RoadEdge, RoadNode, RoadType

    spacing = 40.0
    nodes = {}
    node_ids = {}
    nid = 0
    for row in range(3):
        for col in range(3):
            node_ids[(row, col)] = nid
            nodes[nid] = RoadNode(
                nid, np.array([col * spacing, row * spacing]), IntersectionType.FOUR_WAY
            )
            nid += 1

    edges = {}
    eid = 0

    def add_edge(a: int, b: int) -> None:
        nonlocal eid
        pos_a, pos_b = nodes[a].position, nodes[b].position
        length = float(np.linalg.norm(pos_b - pos_a))
        edges[eid] = RoadEdge(
            eid,
            a,
            b,
            RoadType.MINOR,
            np.array([pos_a, pos_b]),
            length,
            2,
            50,
            2 * LANE_WIDTH_METERS,
        )
        eid += 1
        edges[eid] = RoadEdge(
            eid,
            b,
            a,
            RoadType.MINOR,
            np.array([pos_b, pos_a]),
            length,
            2,
            50,
            2 * LANE_WIDTH_METERS,
        )
        eid += 1

    for row in range(3):
        for col in range(2):
            add_edge(node_ids[(row, col)], node_ids[(row, col + 1)])
    for row in range(2):
        for col in range(3):
            add_edge(node_ids[(row, col)], node_ids[(row + 1, col)])

    LaneTopologyGenerator().generate(nodes, edges)
    return nodes, edges
