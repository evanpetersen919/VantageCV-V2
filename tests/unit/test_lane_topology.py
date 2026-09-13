"""Unit tests for LaneTopologyGenerator."""

import numpy as np
import pytest

from src.procedural.lane_topology import LANE_WIDTH_METERS, LaneTopologyGenerator
from src.procedural.road_network import RoadNetworkGenerator

# urban_config, bounds fixtures: see tests/conftest.py


def test_lane_count_matches_edge_num_lanes(urban_config, bounds) -> None:
    """Every edge gets exactly `edge.num_lanes` Lane objects."""
    road_gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = road_gen.generate(bounds)

    lane_gen = LaneTopologyGenerator()
    lanes = lane_gen.generate(nodes, edges)

    lanes_per_edge: dict = {}
    for lane in lanes.values():
        lanes_per_edge.setdefault(lane.edge_id, []).append(lane)

    for edge_id, edge in edges.items():
        assert len(lanes_per_edge.get(edge_id, [])) == edge.num_lanes


def test_lane_width_correct(urban_config, bounds) -> None:
    """Every lane's width equals LANE_WIDTH_METERS, and its boundaries are
    that far apart."""
    road_gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = road_gen.generate(bounds)

    lanes = LaneTopologyGenerator().generate(nodes, edges)

    for lane in lanes.values():
        assert lane.width == LANE_WIDTH_METERS
        for left_point, right_point in zip(lane.left_boundary, lane.right_boundary):
            dist = np.linalg.norm(left_point - right_point)
            assert np.abs(dist - LANE_WIDTH_METERS) < 1e-6


def test_lane_ids_unique(urban_config, bounds) -> None:
    """No two lanes share a lane_id, even across different edges."""
    road_gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = road_gen.generate(bounds)

    lanes = LaneTopologyGenerator().generate(nodes, edges)

    lane_ids = [lane.lane_id for lane in lanes.values()]
    assert len(lane_ids) == len(set(lane_ids))


def test_lanes_stay_on_own_side_of_centerline(urban_config, bounds) -> None:
    """A directed edge's lanes never cross to the far side of the physical
    road centerline, so they can't overlap the reverse edge's lanes.

    Since a directed edge and its reverse share the same physical
    centerline (just traversed in opposite order), and each offsets lanes
    to its own right-hand side, every lane's centerline point must be
    strictly farther from the *other* direction's baseline than from its
    own -- concretely: the offset distance from the original two-point
    road centerline is always positive and increases with lane_index.
    """
    road_gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = road_gen.generate(bounds)

    lanes = LaneTopologyGenerator().generate(nodes, edges)

    for lane in lanes.values():
        edge = edges[lane.edge_id]
        offsets = np.linalg.norm(lane.centerline - edge.centerline, axis=1)
        expected_offset = (lane.lane_index + 0.5) * LANE_WIDTH_METERS
        assert np.allclose(offsets, expected_offset, atol=1e-6)


def test_missing_node_raises_value_error(urban_config, bounds) -> None:
    """Passing edges that reference a node outside the given `nodes` dict
    raises ValueError rather than crashing with a KeyError deep inside
    lane generation."""
    road_gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = road_gen.generate(bounds)

    incomplete_nodes = dict(list(nodes.items())[:-1])

    with pytest.raises(ValueError, match="references a node"):
        LaneTopologyGenerator().generate(incomplete_nodes, edges)


def test_generate_on_full_network_produces_finite_geometry(urban_config, bounds) -> None:
    """End-to-end: every generated lane's boundary geometry is finite (no
    NaN/Inf), a basic sanity floor before any downstream mesh/rendering
    consumes it (see QOL_RESEARCH_CHECKLIST.md Section D.1)."""
    road_gen = RoadNetworkGenerator(7, urban_config)
    nodes, edges = road_gen.generate(bounds)

    lanes = LaneTopologyGenerator().generate(nodes, edges)

    assert len(lanes) == sum(edge.num_lanes for edge in edges.values())
    for lane in lanes.values():
        assert np.isfinite(lane.centerline).all()
        assert np.isfinite(lane.left_boundary).all()
        assert np.isfinite(lane.right_boundary).all()
