"""Unit tests for the real Epic crosswalk tiles at intersection approaches."""

import math
from typing import Dict

import numpy as np

from src.orchestration.dataset_generator import generate_scenario
from src.procedural.crosswalks import (
    CROSSWALK_ASSET_PATH,
    CROSSWALK_DEPTH_M,
    CROSSWALK_REAL_WIDTH_M,
    CROSSWALK_Z_SCALE,
    STOP_LINE_ASSET_PATH,
    STOP_LINE_REAL_SIZE_M,
    STOP_LINE_THICKNESS_SCALE,
    STOP_LINE_Z_LIFT_M,
    generate_crosswalk_pieces,
)
from src.procedural.lane_topology import LANE_WIDTH_METERS, compute_node_clearance
from src.procedural.road_network import IntersectionType, RoadEdge, RoadNode, RoadType


def _two_way_road(length: float, num_lanes: int = 2) -> tuple:
    """A bidirectional road along +x from the origin: one directed edge
    each way, sharing the same physical centerline."""
    nodes: Dict[int, RoadNode] = {
        0: RoadNode(0, np.array([0.0, 0.0]), IntersectionType.ISOLATED),
        1: RoadNode(1, np.array([length, 0.0]), IntersectionType.ISOLATED),
    }
    forward = RoadEdge(
        0, 0, 1, RoadType.MINOR, np.array([[0.0, 0.0], [length, 0.0]]), length, num_lanes, 50, 7.0
    )
    reverse = RoadEdge(
        1, 1, 0, RoadType.MINOR, np.array([[length, 0.0], [0.0, 0.0]]), length, num_lanes, 50, 7.0
    )
    forward.reverse_edge_id = 1
    reverse.reverse_edge_id = 0
    edges = {0: forward, 1: reverse}
    return nodes, edges


def test_no_edges_means_no_crosswalks() -> None:
    """No roads, nothing to place a crosswalk at."""
    assert not generate_crosswalk_pieces({}, {})


def _pads(pieces):
    return [p for p in pieces if p.asset_path == CROSSWALK_ASSET_PATH]


def _stop_lines(pieces):
    return [p for p in pieces if p.asset_path == STOP_LINE_ASSET_PATH]


def test_one_physical_road_gets_exactly_two_crosswalks() -> None:
    """A long enough bidirectional road gets one crosswalk pad and one
    stop-line at each end, not one per directed edge (a crosswalk spans
    both directions)."""
    nodes, edges = _two_way_road(100.0)
    pieces = generate_crosswalk_pieces(nodes, edges)
    assert len(pieces) == 4
    pads, stop_lines = _pads(pieces), _stop_lines(pieces)
    assert len(pads) == 2
    assert len(stop_lines) == 2
    for piece in pads:
        assert piece.position[2] == 0.0
    for piece in stop_lines:
        assert piece.position[2] == STOP_LINE_Z_LIFT_M


def test_crosswalk_is_scaled_to_the_roads_own_real_pavement_width() -> None:
    """scale.x stretches the real 20.04m crosswalk mesh to exactly the
    combined lane width of both directions -- not a separate guess."""
    nodes, edges = _two_way_road(100.0, num_lanes=3)
    pieces = generate_crosswalk_pieces(nodes, edges)
    expected_width_m = 2 * 3 * LANE_WIDTH_METERS
    for piece in _pads(pieces):
        assert piece.scale is not None
        scale_x, scale_y, scale_z = piece.scale
        assert abs(scale_x - expected_width_m / CROSSWALK_REAL_WIDTH_M) < 1e-9
        assert scale_y == 1.0
        assert scale_z == CROSSWALK_Z_SCALE


def test_stop_line_is_scaled_to_the_roads_width_at_its_real_thickness() -> None:
    """The stop-line's scale.x stretches its real 5.12m size to the road's
    own real width; scale.y is Epic's own real, measured thickness scale
    (0.12), not a separate guess."""
    nodes, edges = _two_way_road(100.0, num_lanes=3)
    pieces = generate_crosswalk_pieces(nodes, edges)
    expected_width_m = 2 * 3 * LANE_WIDTH_METERS
    for piece in _stop_lines(pieces):
        assert piece.scale is not None
        scale_x, scale_y, scale_z = piece.scale
        assert abs(scale_x - expected_width_m / STOP_LINE_REAL_SIZE_M) < 1e-9
        assert scale_y == STOP_LINE_THICKNESS_SCALE
        assert scale_z == 1.0


def test_crosswalk_sits_flush_against_the_intersection_pavement_boundary() -> None:
    """The piece's pivot is exactly clearance + depth from the node, along
    the road, with local Y+ (where the mesh's real 3m band extends)
    pointing back toward the node -- so the band covers [clearance,
    clearance + depth] exactly, flush with the paved intersection fill."""
    nodes, edges = _two_way_road(100.0)
    clearance = compute_node_clearance(edges)
    pieces = generate_crosswalk_pieces(nodes, edges)

    by_x = sorted(_pads(pieces), key=lambda p: p.position[0])
    near_node0, near_node1 = by_x[0], by_x[1]

    expected_x0 = clearance[0] + CROSSWALK_DEPTH_M
    expected_x1 = 100.0 - (clearance[1] + CROSSWALK_DEPTH_M)
    assert abs(float(near_node0.position[0]) - expected_x0) < 1e-9
    assert abs(float(near_node1.position[0]) - expected_x1) < 1e-9
    assert near_node0.position[1] == 0.0

    # Local Y+ = (sin r, -cos r) must point toward each piece's own node:
    # node 0 sits at x=0 (so "toward node 0" from a positive-x pivot is
    # -x); node 1 sits at x=100 (so "toward node 1" from a pivot at a
    # smaller x is +x).
    local_y_0 = (math.sin(near_node0.rotation_rad), -math.cos(near_node0.rotation_rad))
    local_y_1 = (math.sin(near_node1.rotation_rad), -math.cos(near_node1.rotation_rad))
    assert local_y_0[0] < -0.99
    assert local_y_1[0] > 0.99


def test_short_road_gets_no_overlapping_crosswalks() -> None:
    """A road too short to fit clearance + depth without crossing past the
    far node gets no crosswalk on that end, rather than overlapping
    geometry."""
    nodes, edges = _two_way_road(1.0)
    assert not generate_crosswalk_pieces(nodes, edges)


def test_real_generated_scenario_places_crosswalks_at_every_physical_road_end(
    urban_config, bounds
) -> None:
    """Smoke test against the real pipeline: every physical road with
    enough room gets its pad and stop-line, all real, all scaled."""
    scenario = generate_scenario(42, urban_config, bounds, "crosswalk_test")
    assert scenario.crosswalk_pieces
    pads, stop_lines = _pads(scenario.crosswalk_pieces), _stop_lines(scenario.crosswalk_pieces)
    assert pads
    assert len(pads) == len(stop_lines)
    for piece in pads + stop_lines:
        assert piece.scale is not None
    for piece in pads:
        assert piece.position[2] == 0.0
    for piece in stop_lines:
        assert piece.position[2] == STOP_LINE_Z_LIFT_M
