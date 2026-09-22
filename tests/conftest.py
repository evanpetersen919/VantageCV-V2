"""Shared pytest configuration and fixtures."""

from typing import Dict, Optional, Tuple

import numpy as np
import pytest
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from src.procedural.lane_topology import Lane, LaneTopologyGenerator
from src.procedural.mesh_factory import Mesh
from src.procedural.road_network import IntersectionType, RoadEdge, RoadNode, RoadType
from src.procedural.scenario import ScenarioType, ScenarioTypeConfig


def straight_road_lanes_and_edges(
    length: float, road_type: RoadType = RoadType.MINOR
) -> Tuple[Dict[int, Lane], Dict[int, RoadEdge]]:
    """One directed edge along +x from the origin with its real lanes --
    shared by any test that just needs a single straight road to place
    curb-line furniture/signals/etc. along."""
    nodes = {
        0: RoadNode(0, np.array([0.0, 0.0]), IntersectionType.ISOLATED),
        1: RoadNode(1, np.array([length, 0.0]), IntersectionType.ISOLATED),
    }
    edge = RoadEdge(0, 0, 1, road_type, np.array([[0.0, 0.0], [length, 0.0]]), length, 2, 50, 7.0)
    edges = {0: edge}
    return LaneTopologyGenerator().generate(nodes, edges), edges


def mesh_to_shapely_footprint(mesh: Mesh) -> Optional[BaseGeometry]:
    """A ``Mesh``'s real, rendered 2D footprint (the union of its actual
    triangles, projected onto the x/y plane) as a Shapely geometry, or
    ``None`` if the mesh has no non-degenerate triangles.

    Used by real-geometry overlap regression tests (lane self-overlap at
    intersections, buildings overlapping lane pavement -- see
    KNOWN_GAPS_AND_ISSUES.md) to check against what actually gets
    rendered, not a reimplementation of the formula a given bug was in.
    """
    vertices_2d = mesh.vertices[:, :2]
    triangles = []
    for i in range(0, len(mesh.triangles), 3):
        a, b, c = mesh.triangles[i : i + 3]
        triangle = Polygon([vertices_2d[a], vertices_2d[b], vertices_2d[c]])
        if triangle.area > 1e-9:
            triangles.append(triangle)
    return unary_union(triangles) if triangles else None


@pytest.fixture(name="urban_config")
def urban_config_fixture() -> ScenarioTypeConfig:
    """Urban dense scenario configuration, shared across road-network
    unit and integration tests."""
    return ScenarioTypeConfig(
        scenario_type=ScenarioType.URBAN_DENSE,
        avg_block_size=(100.0, 150.0),
        avg_road_width=12.0,
        num_intersections=(4, 9),
        intersection_types=["4way", "3way"],
        building_density=0.8,
        building_heights=(20.0, 40.0),
        traffic_density=(0.6, 1.0),
        vehicle_mix={"sedan": 0.6, "suv": 0.25, "truck": 0.1, "bus": 0.05},
        complexity_score=80,
    )


@pytest.fixture(name="bounds")
def bounds_fixture() -> Tuple[float, float, float, float]:
    """Standard test bounds (500m x 500m)."""
    return (-250.0, -250.0, 250.0, 250.0)
