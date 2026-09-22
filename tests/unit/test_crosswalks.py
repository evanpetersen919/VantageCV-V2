"""Unit tests for the continental (ladder-style) crosswalk markings at
intersection approaches."""

import math
from typing import Dict, List

import numpy as np

from src.orchestration.dataset_generator import generate_scenario
from src.procedural.building_facade import FacadePiece
from src.procedural.crosswalks import (
    BAR_PITCH_M,
    CROSSWALK_DEPTH_M,
    STOP_LINE_ASSET_PATH,
    STOP_LINE_REAL_SIZE_M,
    STOP_LINE_WIDTH_M,
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


def _bars_near_x(pieces: List[FacadePiece], x: float) -> List[FacadePiece]:
    return [p for p in pieces if abs(float(p.position[0]) - x) < 1e-6]


def test_no_edges_means_no_crosswalks() -> None:
    """No roads, nothing to place a crosswalk at."""
    assert not generate_crosswalk_pieces({}, {})


def test_every_piece_is_a_real_stripe_bar() -> None:
    """Every crosswalk piece is the same real, measured stripe mesh --
    no separate toned pad mesh (dropped after it read as an unrealistic
    shade change rather than a crosswalk)."""
    nodes, edges = _two_way_road(100.0)
    pieces = generate_crosswalk_pieces(nodes, edges)
    assert pieces
    for piece in pieces:
        assert piece.asset_path == STOP_LINE_ASSET_PATH


def test_bar_count_fills_the_roads_own_real_width_at_the_real_bar_pitch() -> None:
    """The number of bars is derived from the road's own real combined
    lane width and the real bar pitch (bar width ~= gap width, the
    continental/ladder convention), not a fixed or guessed count."""
    nodes, edges = _two_way_road(100.0, num_lanes=3)
    pieces = generate_crosswalk_pieces(nodes, edges)
    road_width_m = 2 * 3 * LANE_WIDTH_METERS
    expected_bar_count = max(1, round(road_width_m / BAR_PITCH_M))

    depth_center_at_node0 = compute_node_clearance(edges)[0] + CROSSWALK_DEPTH_M / 2.0
    bars_at_node0 = _bars_near_x(pieces, depth_center_at_node0)
    assert len(bars_at_node0) == expected_bar_count


def test_bars_are_symmetric_about_the_roads_centerline() -> None:
    """Bars are laid out symmetrically either side of the centerline
    (y=0 for this east-west road), at the real, fixed bar width -- not
    stretched to fit."""
    nodes, edges = _two_way_road(100.0)
    pieces = generate_crosswalk_pieces(nodes, edges)
    depth_center = compute_node_clearance(edges)[0] + CROSSWALK_DEPTH_M / 2.0
    bars = sorted(_bars_near_x(pieces, depth_center), key=lambda p: float(p.position[1]))

    offsets = [float(p.position[1]) for p in bars]
    assert offsets == sorted(offsets)
    # symmetric: offsets mirror around 0
    for lo, hi in zip(offsets, reversed(offsets)):
        assert abs(lo + hi) < 1e-6

    for stripe in bars:
        assert stripe.scale is not None
        scale_x, scale_y, scale_z = stripe.scale
        assert abs(scale_x - STOP_LINE_WIDTH_M / STOP_LINE_REAL_SIZE_M) < 1e-9
        assert abs(scale_y - CROSSWALK_DEPTH_M / STOP_LINE_REAL_SIZE_M) < 1e-9
        assert scale_z == 1.0


def test_bars_sit_flush_against_the_intersection_pavement_boundary() -> None:
    """Every bar's PIVOT lands at the midpoint of [clearance,
    clearance + depth] from its own node -- not at either edge, since
    the real mesh is centre-pivoted (see this module's docstring for the
    bug this replaced)."""
    nodes, edges = _two_way_road(100.0)
    clearance = compute_node_clearance(edges)
    pieces = generate_crosswalk_pieces(nodes, edges)

    expected_x0 = clearance[0] + CROSSWALK_DEPTH_M / 2.0
    expected_x1 = 100.0 - (clearance[1] + CROSSWALK_DEPTH_M / 2.0)
    bars_0 = _bars_near_x(pieces, expected_x0)
    bars_1 = _bars_near_x(pieces, expected_x1)
    assert bars_0
    assert bars_1

    # Local Y+ = (sin r, -cos r) must point toward each end's own node:
    # node 0 sits at x=0 (so "toward node 0" from a positive-x pivot is
    # -x); node 1 sits at x=100 (so "toward node 1" is +x).
    local_y_0 = (math.sin(bars_0[0].rotation_rad), -math.cos(bars_0[0].rotation_rad))
    local_y_1 = (math.sin(bars_1[0].rotation_rad), -math.cos(bars_1[0].rotation_rad))
    assert local_y_0[0] < -0.99
    assert local_y_1[0] > 0.99


def test_bar_extent_is_exactly_flush_with_the_intersection_pavement() -> None:
    """The rendered bar EXTENT (not just its pivot) has its near edge
    exactly at `clearance` (flush with the paved intersection fill, zero
    gap) and its far edge exactly at `clearance + depth` -- the actual
    invariant the earlier center-pivot bug violated by depth/2."""
    nodes, edges = _two_way_road(100.0)
    clearance = compute_node_clearance(edges)
    pieces = generate_crosswalk_pieces(nodes, edges)

    depth_center = clearance[0] + CROSSWALK_DEPTH_M / 2.0
    stripe = _bars_near_x(pieces, depth_center)[0]
    assert stripe.scale is not None
    half_extent_local_y = (STOP_LINE_REAL_SIZE_M / 2.0) * stripe.scale[1]
    near_edge = float(stripe.position[0]) - half_extent_local_y
    far_edge = float(stripe.position[0]) + half_extent_local_y
    assert abs(near_edge - clearance[0]) < 1e-9
    assert abs(far_edge - (clearance[0] + CROSSWALK_DEPTH_M)) < 1e-9


def test_short_road_gets_no_overlapping_crosswalks() -> None:
    """A road too short to fit clearance + depth without crossing past the
    far node gets no crosswalk bars on that end, rather than overlapping
    geometry."""
    nodes, edges = _two_way_road(1.0)
    assert not generate_crosswalk_pieces(nodes, edges)


def test_real_generated_scenario_places_crosswalks_at_every_physical_road_end(
    urban_config, bounds
) -> None:
    """Smoke test against the real pipeline: every physical road with
    enough room gets its ladder bars, all real, all scaled, all flat."""
    scenario = generate_scenario(42, urban_config, bounds, "crosswalk_test")
    assert scenario.crosswalk_pieces
    for piece in scenario.crosswalk_pieces:
        assert piece.asset_path == STOP_LINE_ASSET_PATH
        assert piece.scale is not None
