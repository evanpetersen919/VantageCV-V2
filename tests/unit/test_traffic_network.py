"""Unit tests for TrafficNetworkGenerator.

Covers MASTER_PROMPT Section 3.4's own listed test topics ("Traffic rule
validity", "Navigation path existence") plus QOL_RESEARCH_CHECKLIST.md
Section G considerations.
"""

from typing import Dict, List

import numpy as np
import pytest

from src.procedural.lane_topology import LaneTopologyGenerator
from src.procedural.road_network import IntersectionType, RoadEdge, RoadNetworkGenerator, RoadType
from src.procedural.traffic_network import (
    PEDESTRIAN_SPAWN_GAP_METERS,
    NavigationGraph,
    SpawnZone,
    SpawnZoneType,
    TrafficControlType,
    TrafficNetworkGenerator,
)

# urban_config, bounds fixtures: see tests/conftest.py


def _generate_full_network(seed: int, config, bounds):
    road_gen = RoadNetworkGenerator(seed, config)
    nodes, edges = road_gen.generate(bounds)
    lanes = LaneTopologyGenerator().generate(nodes, edges)
    traffic = TrafficNetworkGenerator().generate(nodes, edges, lanes)
    return nodes, edges, lanes, traffic


def test_traffic_control_matches_node_type(urban_config, bounds) -> None:
    """Traffic rule validity: FOUR_WAY nodes get a traffic light,
    T_JUNCTION nodes get a stop sign, everything else gets no control."""
    nodes, _, _, traffic = _generate_full_network(42, urban_config, bounds)

    for node_id, node in nodes.items():
        control = traffic.traffic_controls[node_id]
        if node.node_type == IntersectionType.FOUR_WAY:
            assert control == TrafficControlType.TRAFFIC_LIGHT
            assert node.traffic_light is True
            assert node.stop_sign is False
        elif node.node_type == IntersectionType.T_JUNCTION:
            assert control == TrafficControlType.STOP_SIGN
            assert node.stop_sign is True
            assert node.traffic_light is False
        else:
            assert control == TrafficControlType.NONE
            assert node.traffic_light is False
            assert node.stop_sign is False


def test_every_node_gets_exactly_one_control(urban_config, bounds) -> None:
    """Every node has a traffic control assignment, and never both a
    traffic light and a stop sign simultaneously."""
    nodes, _, _, traffic = _generate_full_network(42, urban_config, bounds)

    assert set(traffic.traffic_controls.keys()) == set(nodes.keys())
    for node in nodes.values():
        assert not (node.traffic_light and node.stop_sign)


def test_navigation_path_exists_between_connected_nodes(urban_config, bounds) -> None:
    """Navigation path existence: since the road network is validated
    connected (RoadNetworkGenerator._validate_network), a shortest path
    must exist between any two of its nodes."""
    nodes, _, _, traffic = _generate_full_network(42, urban_config, bounds)

    node_ids = list(nodes.keys())
    start, end = node_ids[0], node_ids[-1]

    path = traffic.navigation_graph.shortest_path(start, end)

    assert path is not None
    assert path[0] == start
    assert path[-1] == end


def test_navigation_path_is_contiguous(urban_config, bounds) -> None:
    """Every consecutive pair of nodes in a returned path is joined by a
    real directed edge in the network."""
    nodes, edges, _, traffic = _generate_full_network(42, urban_config, bounds)

    node_ids = list(nodes.keys())
    path = traffic.navigation_graph.shortest_path(node_ids[0], node_ids[-1])
    assert path is not None

    directed_pairs = {(e.start_node_id, e.end_node_id) for e in edges.values()}
    for i in range(len(path) - 1):
        assert (path[i], path[i + 1]) in directed_pairs


def test_shortest_path_same_start_and_end() -> None:
    """A trivial path (start == end) is a single-node path, not None."""
    graph = NavigationGraph(edges={}, weights_seconds={})
    path = graph.shortest_path(5, 5)
    assert path == [5]


def test_shortest_path_no_route_returns_none() -> None:
    """An unreachable target returns None rather than raising."""
    edge = RoadEdge(
        edge_id=0,
        start_node_id=0,
        end_node_id=1,
        road_type=RoadType.MAJOR,
        centerline=np.array([[0.0, 0.0], [10.0, 0.0]]),
        length=10.0,
        num_lanes=2,
        speed_limit_kmh=50,
        width_meters=10.0,
    )
    graph = NavigationGraph(edges={0: edge}, weights_seconds={0: 1.0})
    path = graph.shortest_path(0, 99)
    assert path is None


def test_driving_spawn_zone_per_lane(urban_config, bounds) -> None:
    """Exactly one driving spawn zone exists per generated lane."""
    _, _, lanes, traffic = _generate_full_network(42, urban_config, bounds)

    driving_zones = [z for z in traffic.spawn_zones if z.zone_type == SpawnZoneType.DRIVING]
    assert len(driving_zones) == len(lanes)


def test_pedestrian_spawn_zones_tiled_along_each_edge(  # pylint: disable=too-many-locals
    urban_config, bounds
) -> None:
    """Pedestrian spawn zones are tiled along every edge that has lanes,
    at the real PEDESTRIAN_SPAWN_GAP_METERS interval (see that constant's
    own docstring) -- not just one fixed slot per edge."""
    _, edges, lanes, traffic = _generate_full_network(42, urban_config, bounds)

    edges_with_lanes = {lane.edge_id for lane in lanes.values()}
    pedestrian_zones = [z for z in traffic.spawn_zones if z.zone_type == SpawnZoneType.PEDESTRIAN]
    assert len(edges_with_lanes) <= len(edges)
    assert len(pedestrian_zones) > len(edges_with_lanes)  # more than one slot per edge now

    zones_by_edge: Dict[int, List[SpawnZone]] = {}
    for zone in pedestrian_zones:
        zones_by_edge.setdefault(zone.edge_id, []).append(zone)
    assert set(zones_by_edge) == edges_with_lanes

    for edge_id, zones in zones_by_edge.items():
        edge = edges[edge_id]
        edge_length = float(np.linalg.norm(edge.centerline[-1] - edge.centerline[0]))
        expected_count = int(edge_length // PEDESTRIAN_SPAWN_GAP_METERS) + 1
        assert len(zones) == expected_count
        for zone_a, zone_b in zip(zones, zones[1:]):
            gap = float(np.linalg.norm(zone_b.position - zone_a.position))
            assert gap == pytest.approx(PEDESTRIAN_SPAWN_GAP_METERS)


def test_spawn_zone_ids_unique(urban_config, bounds) -> None:
    """No two spawn zones share a spawn_zone_id."""
    _, _, _, traffic = _generate_full_network(42, urban_config, bounds)

    ids = [z.spawn_zone_id for z in traffic.spawn_zones]
    assert len(ids) == len(set(ids))


def test_spawn_zone_positions_finite(urban_config, bounds) -> None:
    """All spawn zone positions are finite (no NaN/Inf)."""
    _, _, _, traffic = _generate_full_network(42, urban_config, bounds)

    for zone in traffic.spawn_zones:
        assert np.isfinite(zone.position).all()


def test_no_lanes_yields_no_spawn_zones(urban_config, bounds) -> None:
    """An empty lane dict produces no spawn zones at all."""
    road_gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = road_gen.generate(bounds)

    traffic = TrafficNetworkGenerator().generate(nodes, edges, {})

    assert not traffic.spawn_zones


@pytest.mark.parametrize("seed", [0, 1, 99])
def test_determinism_across_seeds(urban_config, bounds, seed) -> None:
    """Same seed produces identical traffic control assignments."""
    nodes1, _, _, traffic1 = _generate_full_network(seed, urban_config, bounds)
    nodes2, _, _, traffic2 = _generate_full_network(seed, urban_config, bounds)

    assert traffic1.traffic_controls == traffic2.traffic_controls
    assert len(nodes1) == len(nodes2)
