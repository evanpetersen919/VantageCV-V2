"""Unit tests for the paved intersection surface that closes the gap left
by lane trimming at every node."""

import numpy as np

from src.orchestration.dataset_generator import generate_scenario
from src.procedural.intersection_pavement import build_intersection_pavement_meshes
from src.procedural.lane_topology import compute_node_clearance


def test_no_edges_means_no_pavement() -> None:
    """No roads, no nodes with incident lanes, nothing to build."""
    assert not build_intersection_pavement_meshes({}, {})


def test_one_quad_per_node_sized_to_its_own_clearance(urban_config, bounds) -> None:
    """Each node gets one flat, upward-facing, axis-aligned square quad at
    road height (z=0), sized to exactly the same clearance distance every
    incident lane is already trimmed by."""
    scenario = generate_scenario(42, urban_config, bounds, "intersection_pavement_test")
    meshes = build_intersection_pavement_meshes(scenario.nodes, scenario.edges)
    clearance = compute_node_clearance(scenario.edges)

    assert scenario.nodes
    assert len(meshes) == len(clearance)
    for (node_id, half_extent), mesh in zip(clearance.items(), meshes):
        _assert_quad_matches_node(mesh, scenario.nodes[node_id].position, half_extent)


def _assert_quad_matches_node(mesh, node_position, half_extent) -> None:
    center = node_position[:2].astype(float)
    assert mesh.material == "asphalt"
    assert np.allclose(mesh.vertices[:, 2], 0.0)
    assert np.allclose(mesh.vertices[:, :2].min(axis=0), center - half_extent)
    assert np.allclose(mesh.vertices[:, :2].max(axis=0), center + half_extent)
    for first in range(0, 6, 3):
        a, b, c = (mesh.vertices[i] for i in mesh.triangles[first : first + 3])
        assert (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) > 0  # faces up


def test_quad_covers_every_incident_lane_near_node_boundary_point(urban_config, bounds) -> None:
    """The whole point of this module: the quad must fully contain every
    lane touching that node's near-node boundary corners, so there is no
    remaining gap between the lane's own asphalt and the intersection
    fill."""
    scenario = generate_scenario(7, urban_config, bounds, "intersection_pavement_coverage_test")
    meshes_by_center = {
        (round(float(m.vertices[:, 0].mean()), 3), round(float(m.vertices[:, 1].mean()), 3)): m
        for m in build_intersection_pavement_meshes(scenario.nodes, scenario.edges)
    }

    for lane in scenario.lanes.values():
        edge = scenario.edges[lane.edge_id]
        for node_id, boundary_index in ((edge.start_node_id, 0), (edge.end_node_id, -1)):
            node = scenario.nodes[node_id]
            center = (round(float(node.position[0]), 3), round(float(node.position[1]), 3))
            mesh = meshes_by_center[center]
            for boundary in (lane.left_boundary, lane.right_boundary):
                _assert_point_inside_quad(boundary[boundary_index], mesh)


def _assert_point_inside_quad(point, mesh) -> None:
    x_min, y_min = mesh.vertices[:, :2].min(axis=0)
    x_max, y_max = mesh.vertices[:, :2].max(axis=0)
    assert x_min - 1e-6 <= point[0] <= x_max + 1e-6
    assert y_min - 1e-6 <= point[1] <= y_max + 1e-6
