"""Unit tests for RoadNetworkGenerator.

Mirrors the test cases specified in MASTER_PROMPT Section 3.2.2, adjusted
for the Generator/PCG64 seeding change and eq=False dataclasses documented
in road_network.py's module docstring.
"""

import time
from collections import deque

import numpy as np
import pytest

from src.procedural.road_network import (
    MAX_ROAD_LENGTH_METERS,
    IntersectionType,
    RoadNetworkGenerator,
    RoadType,
)

# urban_config, bounds fixtures: see tests/conftest.py

# Tests below exercise generator internals (_find_or_create_node,
# _connect_nodes, _nodes) directly to isolate specific algorithmic
# behaviors (merging, degeneracy handling) from the full generate()
# pipeline -- see MASTER_PROMPT/CLAUDE_SKILLS_AND_PROMPTS.md Skill 5.
# pylint: disable=protected-access


def _bfs_reachable_count(nodes, edges, start_node_id: int) -> int:
    visited = {start_node_id}
    queue = deque([start_node_id])
    while queue:
        node_id = queue.popleft()
        for edge_id in nodes[node_id].outgoing_edges:
            next_node_id = edges[edge_id].end_node_id
            if next_node_id not in visited:
                visited.add(next_node_id)
                queue.append(next_node_id)
    return len(visited)


def test_grid_generation_deterministic(urban_config, bounds) -> None:
    """Grid generation with the same seed produces identical results."""
    seed = 42

    gen1 = RoadNetworkGenerator(seed, urban_config)
    gen2 = RoadNetworkGenerator(seed, urban_config)

    nodes1, edges1 = gen1.generate(bounds)
    nodes2, edges2 = gen2.generate(bounds)

    assert len(nodes1) == len(nodes2)
    assert len(edges1) == len(edges2)

    for nid, node1 in nodes1.items():
        assert (node1.position == nodes2[nid].position).all()


def test_different_seeds_produce_different_networks(urban_config, bounds) -> None:
    """Different seeds produce different (but valid) networks."""
    gen1 = RoadNetworkGenerator(42, urban_config)
    gen2 = RoadNetworkGenerator(43, urban_config)

    nodes1, _ = gen1.generate(bounds)
    nodes2, _ = gen2.generate(bounds)

    common_ids = set(nodes1) & set(nodes2)
    assert common_ids, "Expected at least one shared node id to compare"

    total_diff = sum(
        float(((nodes1[n].position - nodes2[n].position) ** 2).sum()) ** 0.5 for n in common_ids
    )
    assert total_diff > 0.0, "Different seeds produced identical positions"


def test_network_connectivity(urban_config, bounds) -> None:
    """Generated network is fully connected."""
    gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = gen.generate(bounds)

    start_node = next(iter(nodes.keys()))
    visited_count = _bfs_reachable_count(nodes, edges, start_node)

    assert visited_count == len(nodes), f"Network not connected: {visited_count} / {len(nodes)}"


def test_all_node_positions_within_bounds(urban_config, bounds) -> None:
    """Every node's position stays within the declared bounds, even after
    Gaussian perturbation. Regression test: grid generation can overshoot
    by up to one spacing per axis, and perturbation can push a point
    further out; both went unchecked until ScenarioValidator (Phase 4)
    caught nodes up to ~70m outside a 500m-wide bounds region on a
    real generated scenario. See KNOWN_GAPS_AND_ISSUES.md."""
    gen = RoadNetworkGenerator(42, urban_config)
    nodes, _ = gen.generate(bounds)

    x_min, y_min, x_max, y_max = bounds
    for node_id, node in nodes.items():
        x, y = node.position
        assert x_min <= x <= x_max, f"Node {node_id}: x={x} outside [{x_min}, {x_max}]"
        assert y_min <= y <= y_max, f"Node {node_id}: y={y} outside [{y_min}, {y_max}]"


@pytest.mark.parametrize("seed", range(20))
def test_all_node_positions_within_bounds_across_seeds(urban_config, bounds, seed) -> None:
    """Bounds containment holds across many seeds, not just one lucky
    case (reflection math should be seed-independent)."""
    gen = RoadNetworkGenerator(seed, urban_config)
    nodes, _ = gen.generate(bounds)

    x_min, y_min, x_max, y_max = bounds
    for node in nodes.values():
        x, y = node.position
        assert x_min <= x <= x_max
        assert y_min <= y <= y_max


def test_edge_length_constraints(urban_config, bounds) -> None:
    """All edges satisfy length constraints."""
    gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = gen.generate(bounds)

    for edge_id, edge in edges.items():
        assert edge.length > 0, f"Edge {edge_id}: zero length"
        assert (
            edge.length < MAX_ROAD_LENGTH_METERS
        ), f"Edge {edge_id}: length {edge.length} > max {MAX_ROAD_LENGTH_METERS}"
        assert edge.start_node_id in nodes
        assert edge.end_node_id in nodes


def test_node_types_assigned_correctly(urban_config, bounds) -> None:
    """Node types match their road-connection count (degree // 2) per the
    documented heuristic. Degree itself is always even (every road is a
    bidirectional edge pair), so classification must halve it first --
    see road_network.py's _assign_road_attributes docstring and
    KNOWN_GAPS_AND_ISSUES.md."""
    gen = RoadNetworkGenerator(42, urban_config)
    nodes, _ = gen.generate(bounds)

    for node in nodes.values():
        degree = len(node.incoming_edges) + len(node.outgoing_edges)
        assert degree % 2 == 0, "Degree should always be even (bidirectional edge pairs)"
        connections = degree // 2

        if connections <= 2:
            assert node.node_type == IntersectionType.ISOLATED
        elif connections == 3:
            assert node.node_type == IntersectionType.T_JUNCTION
        else:
            assert node.node_type == IntersectionType.FOUR_WAY


def test_three_way_junction_classified_as_t_junction(urban_config, bounds) -> None:
    """A node where exactly 3 distinct roads meet (degree 6) is classified
    T_JUNCTION, not FOUR_WAY -- the bug this fix addresses."""
    gen = RoadNetworkGenerator(42, urban_config)
    nodes, _ = gen.generate(bounds)

    three_way_nodes = [
        n for n in nodes.values() if (len(n.incoming_edges) + len(n.outgoing_edges)) // 2 == 3
    ]
    assert three_way_nodes, "Expected at least one 3-connection node at this seed/bounds"
    for node in three_way_nodes:
        assert node.node_type == IntersectionType.T_JUNCTION


def test_road_attributes_assigned(urban_config, bounds) -> None:
    """Road types, lanes, and speeds are assigned to every edge."""
    gen = RoadNetworkGenerator(42, urban_config)
    _, edges = gen.generate(bounds)

    for edge in edges.values():
        assert edge.road_type in RoadType
        assert edge.num_lanes >= 1
        assert edge.speed_limit_kmh >= 20


def test_forward_reverse_edge_attributes_match(urban_config, bounds) -> None:
    """A directed edge and its reverse counterpart have identical
    num_lanes, road_type, and speed_limit_kmh -- QOL_RESEARCH_CHECKLIST.md
    Section G.1's test_lane_count_consistent. Regression test: this failed
    for 76/118 edges before _assign_road_attributes was fixed to compute
    attributes once per undirected road (see KNOWN_GAPS_AND_ISSUES.md)."""
    gen = RoadNetworkGenerator(42, urban_config)
    _, edges = gen.generate(bounds)

    checked = 0
    for edge in edges.values():
        if edge.reverse_edge_id is None:
            continue
        reverse_edge = edges[edge.reverse_edge_id]
        assert edge.num_lanes == reverse_edge.num_lanes
        assert edge.road_type == reverse_edge.road_type
        assert edge.speed_limit_kmh == reverse_edge.speed_limit_kmh
        checked += 1

    assert checked > 0, "Expected at least one bidirectional edge pair at this seed/bounds"


def test_large_scenario_performance(urban_config) -> None:
    """Large scenario generation completes in reasonable time."""
    large_bounds = (-1000.0, -1000.0, 1000.0, 1000.0)

    gen = RoadNetworkGenerator(42, urban_config)

    start = time.perf_counter()
    nodes, edges = gen.generate(large_bounds)
    elapsed = time.perf_counter() - start

    assert elapsed < 10.0, f"Generation took {elapsed}s"
    assert len(nodes) > 50, f"Too few nodes: {len(nodes)}"
    assert len(edges) > len(nodes), "More nodes than edges in network"


@pytest.mark.parametrize("seed", [0, 42, 12345, 2**32 - 1, 2**63 - 1])
def test_seed_coverage_edge_cases(seed, urban_config, bounds) -> None:
    """Handles edge-case seed values, including beyond RandomState's
    2**32-1 limit (see road_network.py module docstring, deviation #1)."""
    gen = RoadNetworkGenerator(seed, urban_config)
    nodes, edges = gen.generate(bounds)

    assert len(nodes) > 0
    assert len(edges) > 0
    assert all(e.start_node_id in nodes for e in edges.values())
    assert all(e.end_node_id in nodes for e in edges.values())


def test_no_self_loops(urban_config, bounds) -> None:
    """No edge connects a node to itself."""
    gen = RoadNetworkGenerator(42, urban_config)
    _, edges = gen.generate(bounds)

    for edge in edges.values():
        assert edge.start_node_id != edge.end_node_id, f"Self-loop: edge {edge.edge_id}"


def test_no_duplicate_directed_edges(urban_config, bounds) -> None:
    """No two edges share the same (start, end) directed pair."""
    gen = RoadNetworkGenerator(42, urban_config)
    _, edges = gen.generate(bounds)

    seen = set()
    for edge in edges.values():
        pair = (edge.start_node_id, edge.end_node_id)
        assert pair not in seen, f"Duplicate directed edge: {pair}"
        seen.add(pair)


def test_reverse_edge_pairing_is_symmetric(urban_config, bounds) -> None:
    """If edge A's reverse is B, then B's reverse is A, and A/B connect the
    same two nodes in opposite directions."""
    gen = RoadNetworkGenerator(42, urban_config)
    _, edges = gen.generate(bounds)

    for edge in edges.values():
        assert edge.reverse_edge_id is not None
        reverse = edges[edge.reverse_edge_id]
        assert reverse.reverse_edge_id == edge.edge_id
        assert reverse.start_node_id == edge.end_node_id
        assert reverse.end_node_id == edge.start_node_id


def test_zero_area_bounds_raises_isolated_node_error(urban_config) -> None:
    """A zero-area bounds region (x_min==x_max and y_min==y_max) produces
    exactly one grid point and thus one isolated node, which fails
    validation by design.

    Note: bounds with x_max > x_min always yield >= 2 grid points per axis
    regardless of how small the extent is relative to block spacing --
    ``np.arange(x_min, x_max + spacing, spacing)`` always includes both
    ``x_min`` and ``x_min + spacing`` whenever ``x_max > x_min``. Only a
    literal zero-width/zero-height region collapses to one point. See
    KNOWN_GAPS_AND_ISSUES.md.
    """
    zero_area_bounds = (5.0, 5.0, 5.0, 5.0)
    gen = RoadNetworkGenerator(42, urban_config)

    with pytest.raises(ValueError, match="isolated node"):
        gen.generate(zero_area_bounds)


def test_nearby_points_merge_into_single_node(urban_config) -> None:
    """Two points within MIN_INTERSECTION_DISTANCE_METERS merge into one
    node rather than creating a duplicate intersection. See
    QOL_RESEARCH_CHECKLIST.md Section A.1."""
    gen = RoadNetworkGenerator(42, urban_config)

    node_id1 = gen._find_or_create_node(np.array([100.0, 200.0]))
    node_id2 = gen._find_or_create_node(np.array([100.0 + 1e-7, 200.0]))

    assert node_id1 == node_id2, "Points within tolerance should merge into the same node"
    assert len(gen._nodes) == 1


def test_points_beyond_merge_distance_stay_separate(urban_config) -> None:
    """Two points farther apart than MIN_INTERSECTION_DISTANCE_METERS do
    not merge."""
    gen = RoadNetworkGenerator(42, urban_config)

    node_id1 = gen._find_or_create_node(np.array([0.0, 0.0]))
    node_id2 = gen._find_or_create_node(np.array([50.0, 0.0]))

    assert node_id1 != node_id2
    assert len(gen._nodes) == 2


def test_collinear_points_raise_value_error_not_qhull_error(urban_config) -> None:
    """Perfectly collinear node positions make Delaunay triangulation fail
    (Qhull cannot construct a simplex from < 3-dimensional input); this is
    wrapped as a ValueError rather than leaking QhullError. This is a real
    limitation of Delaunay-based connectivity for straight-line layouts
    (e.g. highway scenarios) -- see KNOWN_GAPS_AND_ISSUES.md."""
    gen = RoadNetworkGenerator(42, urban_config)
    for x in (0.0, 10.0, 20.0, 30.0):
        gen._find_or_create_node(np.array([x, 0.0]))

    with pytest.raises(ValueError, match="Delaunay triangulation failed"):
        gen._connect_nodes()


def test_two_node_network_creates_bidirectional_edge_pair(urban_config) -> None:
    """Exactly two well-separated nodes yield one bidirectional edge pair."""
    config = urban_config.model_copy(update={"avg_block_size": (60.0, 60.0)})
    bounds = (0.0, 0.0, 60.0, 0.0)
    gen = RoadNetworkGenerator(42, config)

    nodes, edges = gen.generate(bounds)

    assert len(nodes) == 2
    assert len(edges) == 2
