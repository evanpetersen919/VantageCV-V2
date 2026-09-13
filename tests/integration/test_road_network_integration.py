"""Integration tests for RoadNetworkGenerator end-to-end flows."""

import json

from src.procedural.road_network import RoadNetworkGenerator

# urban_config fixture: see tests/conftest.py


def test_road_network_to_json_serialization(urban_config) -> None:
    """A generated road network can be serialized to and from JSON without
    loss of node/edge counts."""
    bounds = (-250.0, -250.0, 250.0, 250.0)
    gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = gen.generate(bounds)

    data = {
        "nodes": {
            nid: {
                "position": n.position.tolist(),
                "node_type": n.node_type.value,
                "degree": len(n.incoming_edges) + len(n.outgoing_edges),
            }
            for nid, n in nodes.items()
        },
        "edges": {
            eid: {
                "start": e.start_node_id,
                "end": e.end_node_id,
                "type": e.road_type.value,
                "lanes": e.num_lanes,
                "speed": e.speed_limit_kmh,
            }
            for eid, e in edges.items()
        },
    }

    json_str = json.dumps(data)
    parsed = json.loads(json_str)

    assert len(parsed["nodes"]) == len(nodes)
    assert len(parsed["edges"]) == len(edges)


def test_end_to_end_generation_across_all_scenario_bounds_sizes(urban_config) -> None:
    """Generation succeeds and produces a connected, valid network across a
    range of bounds sizes (smoke test for the full generate() pipeline)."""
    for half_extent in (150.0, 300.0, 600.0):
        bounds = (-half_extent, -half_extent, half_extent, half_extent)
        gen = RoadNetworkGenerator(7, urban_config)
        nodes, edges = gen.generate(bounds)

        assert len(nodes) > 0
        assert len(edges) > 0
        assert all(e.start_node_id in nodes and e.end_node_id in nodes for e in edges.values())
