"""Unit tests for LaneConnectivityGenerator.

Covers turn classification (straight/left/right), lane-level mapping per
turn type, U-turn exclusion, allows_turning_left/right enforcement, and
correctness against a real generated network.
"""

import numpy as np
import pytest

from src.procedural.lane_connectivity import (
    STRAIGHT_ANGLE_THRESHOLD_RAD,
    LaneConnectivityGenerator,
    TurnType,
)
from src.procedural.lane_topology import LaneTopologyGenerator
from src.procedural.road_network import (
    IntersectionType,
    RoadEdge,
    RoadNetworkGenerator,
    RoadNode,
    RoadType,
)

# urban_config, bounds fixtures: see tests/conftest.py

# pylint: disable=duplicate-code
# Hand-built RoadNode/RoadEdge intersection fixtures inevitably resemble
# similar fixtures in test_traffic_network.py/test_validator.py -- a
# shared fixture would couple those unrelated test files for no benefit.


def _edge(  # pylint: disable=too-many-arguments
    edge_id: int,
    start_node_id: int,
    end_node_id: int,
    centerline,
    num_lanes: int = 1,
    allows_turning_left: bool = True,
    allows_turning_right: bool = True,
    reverse_edge_id=None,
) -> RoadEdge:
    centerline = np.array(centerline)
    length = float(np.linalg.norm(centerline[-1] - centerline[0]))
    return RoadEdge(
        edge_id=edge_id,
        start_node_id=start_node_id,
        end_node_id=end_node_id,
        road_type=RoadType.MAJOR,
        centerline=centerline,
        length=length,
        num_lanes=num_lanes,
        speed_limit_kmh=50,
        width_meters=10.0,
        allows_turning_left=allows_turning_left,
        allows_turning_right=allows_turning_right,
        reverse_edge_id=reverse_edge_id,
    )


def _four_way_intersection(num_lanes: int = 1, **edge_kwargs):
    """A 4-way intersection at the origin: one edge arrives from the
    west (heading east, into the node), and three edges leave heading
    north (left turn), east (straight), and south (right turn)."""
    node = RoadNode(node_id=0, position=np.array([0.0, 0.0]), node_type=IntersectionType.FOUR_WAY)
    incoming = _edge(0, 1, 0, [[-10.0, 0.0], [0.0, 0.0]], num_lanes=num_lanes, **edge_kwargs)
    out_straight = _edge(1, 0, 2, [[0.0, 0.0], [10.0, 0.0]], num_lanes=num_lanes)
    out_left = _edge(2, 0, 3, [[0.0, 0.0], [0.0, 10.0]], num_lanes=num_lanes)
    out_right = _edge(3, 0, 4, [[0.0, 0.0], [0.0, -10.0]], num_lanes=num_lanes)

    node.incoming_edges = {0}
    node.outgoing_edges = {1, 2, 3}

    nodes = {0: node}
    edges = {0: incoming, 1: out_straight, 2: out_left, 3: out_right}
    lanes = LaneTopologyGenerator().generate(
        {
            0: node,
            1: RoadNode(
                node_id=1, position=np.array([-10.0, 0.0]), node_type=IntersectionType.ISOLATED
            ),
            2: RoadNode(
                node_id=2, position=np.array([10.0, 0.0]), node_type=IntersectionType.ISOLATED
            ),
            3: RoadNode(
                node_id=3, position=np.array([0.0, 10.0]), node_type=IntersectionType.ISOLATED
            ),
            4: RoadNode(
                node_id=4, position=np.array([0.0, -10.0]), node_type=IntersectionType.ISOLATED
            ),
        },
        edges,
    )
    return nodes, edges, lanes


def _lanes_for_edge(lanes, edge_id):
    return sorted(
        (lane for lane in lanes.values() if lane.edge_id == edge_id), key=lambda l: l.lane_index
    )


def test_classifies_straight_left_right_correctly() -> None:
    """The three outgoing edges are classified straight/left/right as
    their geometry dictates."""
    nodes, edges, lanes = _four_way_intersection()
    graph = LaneConnectivityGenerator().generate(nodes, edges, lanes)

    incoming_lane = _lanes_for_edge(lanes, 0)[0]
    movements = {c.to_lane_id: c.turn_type for c in graph.outgoing_from(incoming_lane.lane_id)}

    straight_lane = _lanes_for_edge(lanes, 1)[0]
    left_lane = _lanes_for_edge(lanes, 2)[0]
    right_lane = _lanes_for_edge(lanes, 3)[0]

    assert movements[straight_lane.lane_id] == TurnType.STRAIGHT
    assert movements[left_lane.lane_id] == TurnType.LEFT
    assert movements[right_lane.lane_id] == TurnType.RIGHT


def test_no_u_turn_connection() -> None:
    """The incoming edge's own reverse is never a connection target."""
    node = RoadNode(node_id=0, position=np.array([0.0, 0.0]), node_type=IntersectionType.T_JUNCTION)
    incoming = _edge(0, 1, 0, [[-10.0, 0.0], [0.0, 0.0]], reverse_edge_id=1)
    reverse = _edge(1, 0, 1, [[0.0, 0.0], [-10.0, 0.0]], reverse_edge_id=0)
    node.incoming_edges = {0}
    node.outgoing_edges = {1}

    nodes = {
        0: node,
        1: RoadNode(
            node_id=1, position=np.array([-10.0, 0.0]), node_type=IntersectionType.ISOLATED
        ),
    }
    edges = {0: incoming, 1: reverse}
    lanes = LaneTopologyGenerator().generate(nodes, edges)

    graph = LaneConnectivityGenerator().generate(nodes, edges, lanes)
    incoming_lane = _lanes_for_edge(lanes, 0)[0]
    assert graph.outgoing_from(incoming_lane.lane_id) == []


def test_left_turn_disallowed_by_flag() -> None:
    """allows_turning_left=False on the incoming edge suppresses the left connection."""
    nodes, edges, lanes = _four_way_intersection(allows_turning_left=False)
    graph = LaneConnectivityGenerator().generate(nodes, edges, lanes)

    incoming_lane = _lanes_for_edge(lanes, 0)[0]
    turn_types = {c.turn_type for c in graph.outgoing_from(incoming_lane.lane_id)}
    assert TurnType.LEFT not in turn_types
    assert TurnType.STRAIGHT in turn_types
    assert TurnType.RIGHT in turn_types


def test_right_turn_disallowed_by_flag() -> None:
    """allows_turning_right=False on the incoming edge suppresses the right connection."""
    nodes, edges, lanes = _four_way_intersection(allows_turning_right=False)
    graph = LaneConnectivityGenerator().generate(nodes, edges, lanes)

    incoming_lane = _lanes_for_edge(lanes, 0)[0]
    turn_types = {c.turn_type for c in graph.outgoing_from(incoming_lane.lane_id)}
    assert TurnType.RIGHT not in turn_types
    assert TurnType.STRAIGHT in turn_types
    assert TurnType.LEFT in turn_types


def test_straight_movement_never_restricted() -> None:
    """There is no allows_straight flag -- straight is always permitted
    regardless of the turning flags."""
    nodes, edges, lanes = _four_way_intersection(
        allows_turning_left=False, allows_turning_right=False
    )
    graph = LaneConnectivityGenerator().generate(nodes, edges, lanes)

    incoming_lane = _lanes_for_edge(lanes, 0)[0]
    turn_types = {c.turn_type for c in graph.outgoing_from(incoming_lane.lane_id)}
    assert turn_types == {TurnType.STRAIGHT}


def test_straight_connects_lanes_index_for_index() -> None:
    """A 2-lane-to-2-lane straight movement connects lane 0->0 and 1->1."""
    nodes, edges, lanes = _four_way_intersection(num_lanes=2)
    graph = LaneConnectivityGenerator().generate(nodes, edges, lanes)

    incoming_lanes = _lanes_for_edge(lanes, 0)
    straight_lanes = _lanes_for_edge(lanes, 1)

    for incoming_lane, straight_lane in zip(incoming_lanes, straight_lanes):
        connections = graph.outgoing_from(incoming_lane.lane_id)
        straight_targets = {c.to_lane_id for c in connections if c.turn_type == TurnType.STRAIGHT}
        assert straight_targets == {straight_lane.lane_id}


def test_left_turn_only_connects_lane_zero() -> None:
    """A left turn only connects the incoming edge's lane 0 (median lane)
    to the outgoing edge's lane 0."""
    nodes, edges, lanes = _four_way_intersection(num_lanes=2)
    graph = LaneConnectivityGenerator().generate(nodes, edges, lanes)

    incoming_lanes = _lanes_for_edge(lanes, 0)
    left_lanes = _lanes_for_edge(lanes, 2)

    left_connections = [
        c
        for lane in incoming_lanes
        for c in graph.outgoing_from(lane.lane_id)
        if c.turn_type == TurnType.LEFT
    ]
    assert len(left_connections) == 1
    assert left_connections[0].from_lane_id == incoming_lanes[0].lane_id
    assert left_connections[0].to_lane_id == left_lanes[0].lane_id


def test_right_turn_only_connects_outermost_lane() -> None:
    """A right turn only connects the incoming edge's highest-index lane
    (curb lane) to the outgoing edge's highest-index lane."""
    nodes, edges, lanes = _four_way_intersection(num_lanes=2)
    graph = LaneConnectivityGenerator().generate(nodes, edges, lanes)

    incoming_lanes = _lanes_for_edge(lanes, 0)
    right_lanes = _lanes_for_edge(lanes, 3)

    right_connections = [
        c
        for lane in incoming_lanes
        for c in graph.outgoing_from(lane.lane_id)
        if c.turn_type == TurnType.RIGHT
    ]
    assert len(right_connections) == 1
    assert right_connections[0].from_lane_id == incoming_lanes[-1].lane_id
    assert right_connections[0].to_lane_id == right_lanes[-1].lane_id


def test_missing_lanes_for_an_edge_produces_no_connections_through_it() -> None:
    """If an edge has no lanes in the `lanes` dict (e.g. a partial/filtered
    lane set), movements through it produce no connections rather than
    crashing."""
    nodes, edges, lanes = _four_way_intersection()
    lanes_without_incoming = {lane_id: lane for lane_id, lane in lanes.items() if lane.edge_id != 0}

    graph = LaneConnectivityGenerator().generate(nodes, edges, lanes_without_incoming)
    assert not graph.connections


def test_outgoing_from_unknown_lane_returns_empty() -> None:
    """A lane_id with no connections returns [] rather than raising."""
    nodes, edges, lanes = _four_way_intersection()
    graph = LaneConnectivityGenerator().generate(nodes, edges, lanes)
    assert graph.outgoing_from(999999) == []


def test_empty_network_yields_empty_graph() -> None:
    """No nodes/edges/lanes at all produces an empty connectivity graph."""
    graph = LaneConnectivityGenerator().generate({}, {}, {})
    assert not graph.connections


def test_real_generated_network_connections_reference_real_lanes(urban_config, bounds) -> None:
    """Every connection's from/to lane_id is a real lane in the network,
    and no connection targets the incoming edge's own reverse edge."""
    road_gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = road_gen.generate(bounds)
    lanes = LaneTopologyGenerator().generate(nodes, edges)

    graph = LaneConnectivityGenerator().generate(nodes, edges, lanes)
    assert graph.connections  # sanity: this config/seed produces some

    lane_ids = set(lanes.keys())
    for connection in graph.connections:
        assert connection.from_lane_id in lane_ids
        assert connection.to_lane_id in lane_ids

        from_edge = edges[lanes[connection.from_lane_id].edge_id]
        to_edge_id = lanes[connection.to_lane_id].edge_id
        assert to_edge_id != from_edge.reverse_edge_id


@pytest.mark.parametrize("seed", [0, 1, 99])
def test_determinism_across_seeds(urban_config, bounds, seed) -> None:
    """Same seed produces an identical connectivity graph."""
    road_gen = RoadNetworkGenerator(seed, urban_config)
    nodes, edges = road_gen.generate(bounds)
    lanes = LaneTopologyGenerator().generate(nodes, edges)

    graph1 = LaneConnectivityGenerator().generate(nodes, edges, lanes)
    graph2 = LaneConnectivityGenerator().generate(nodes, edges, lanes)

    connections1 = {(c.from_lane_id, c.to_lane_id, c.turn_type) for c in graph1.connections}
    connections2 = {(c.from_lane_id, c.to_lane_id, c.turn_type) for c in graph2.connections}
    assert connections1 == connections2


def test_straight_angle_threshold_is_positive_and_under_90_degrees() -> None:
    """Sanity check on the module's own classification constant."""
    assert 0.0 < STRAIGHT_ANGLE_THRESHOLD_RAD < np.pi / 2
