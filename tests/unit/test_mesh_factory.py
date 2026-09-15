"""Unit tests for MeshFactory.

Covers QOL_RESEARCH_CHECKLIST.md Section D.1: finite vertices, no
degenerate triangles, correct (CCW) winding order, sensible bounds.
"""

import numpy as np
import pytest

from src.procedural.actor_placement import Pedestrian, Vehicle
from src.procedural.building_placement import Building
from src.procedural.lane_topology import Lane, LaneTopologyGenerator
from src.procedural.mesh_factory import MIN_TRIANGLE_AREA_SQ_METERS, MeshFactory, _quad_indices_ccw
from src.procedural.road_network import RoadNetworkGenerator

# urban_config, bounds fixtures: see tests/conftest.py


def _triangle_signed_area(v0, v1, v2) -> float:
    return 0.5 * ((v1[0] - v0[0]) * (v2[1] - v0[1]) - (v2[0] - v0[0]) * (v1[1] - v0[1]))


def _all_meshes_for_scenario(seed: int, config, bounds):
    road_gen = RoadNetworkGenerator(seed, config)
    nodes, edges = road_gen.generate(bounds)
    lanes = LaneTopologyGenerator().generate(nodes, edges)
    return [MeshFactory.build_road_mesh(lane) for lane in lanes.values()]


def test_road_mesh_vertices_finite(urban_config, bounds) -> None:
    """No NaN or Inf in any road mesh's vertices."""
    for mesh in _all_meshes_for_scenario(42, urban_config, bounds):
        assert np.isfinite(mesh.vertices).all()


def test_road_mesh_no_degenerate_triangles(urban_config, bounds) -> None:
    """Every triangle's area exceeds the minimum threshold."""
    for mesh in _all_meshes_for_scenario(42, urban_config, bounds):
        for i in range(0, len(mesh.triangles), 3):
            v0 = mesh.vertices[mesh.triangles[i]]
            v1 = mesh.vertices[mesh.triangles[i + 1]]
            v2 = mesh.vertices[mesh.triangles[i + 2]]
            area = abs(_triangle_signed_area(v0, v1, v2))
            assert area > MIN_TRIANGLE_AREA_SQ_METERS, f"Degenerate triangle: area={area}"


def test_road_mesh_ccw_winding(urban_config, bounds) -> None:
    """Every triangle is wound counter-clockwise (positive signed area)."""
    for mesh in _all_meshes_for_scenario(42, urban_config, bounds):
        for i in range(0, len(mesh.triangles), 3):
            v0 = mesh.vertices[mesh.triangles[i]]
            v1 = mesh.vertices[mesh.triangles[i + 1]]
            v2 = mesh.vertices[mesh.triangles[i + 2]]
            area = _triangle_signed_area(v0, v1, v2)
            assert area > 0, f"Triangle not CCW: signed area={area}"


def test_road_mesh_triangle_count(urban_config, bounds) -> None:
    """A lane with N boundary points produces exactly 2*(N-1) triangles
    (one quad per consecutive pair of boundary points)."""
    for mesh in _all_meshes_for_scenario(42, urban_config, bounds):
        n_points = len(mesh.vertices) // 2
        assert len(mesh.triangles) == 2 * (n_points - 1) * 3


def test_road_mesh_uvs_in_expected_range(urban_config, bounds) -> None:
    """U coordinates are exactly 0 or 1 (across lane width); V is
    non-negative cumulative distance."""
    for mesh in _all_meshes_for_scenario(42, urban_config, bounds):
        assert set(np.unique(mesh.uvs[:, 0])).issubset({0.0, 1.0})
        assert (mesh.uvs[:, 1] >= 0).all()


def test_road_mesh_material() -> None:
    """Road meshes use the asphalt material."""
    lane = Lane(
        lane_id=0,
        edge_id=0,
        lane_index=0,
        centerline=np.array([[0.0, 0.0], [10.0, 0.0]]),
        left_boundary=np.array([[0.0, 2.0], [10.0, 2.0]]),
        right_boundary=np.array([[0.0, -2.0], [10.0, -2.0]]),
        width=4.0,
    )
    mesh = MeshFactory.build_road_mesh(lane)
    assert mesh.material == "asphalt"


def test_building_mesh_vertex_count() -> None:
    """A box building has exactly 8 vertices (4 base + 4 top)."""
    building = Building(
        building_id=0, center=np.array([0.0, 0.0]), width=10.0, depth=8.0, height=20.0
    )
    mesh = MeshFactory.build_building_mesh(building)
    assert len(mesh.vertices) == 8


def test_building_mesh_triangle_count() -> None:
    """A box has 6 faces x 2 triangles = 12 triangles."""
    building = Building(
        building_id=0, center=np.array([0.0, 0.0]), width=10.0, depth=8.0, height=20.0
    )
    mesh = MeshFactory.build_building_mesh(building)
    assert len(mesh.triangles) == 12 * 3


def test_building_mesh_vertices_finite() -> None:
    """No NaN or Inf in a building mesh's vertices."""
    building = Building(
        building_id=0, center=np.array([5.0, -3.0]), width=12.0, depth=9.0, height=30.0
    )
    mesh = MeshFactory.build_building_mesh(building)
    assert np.isfinite(mesh.vertices).all()


def test_building_mesh_height_matches_building() -> None:
    """The top vertices' z-coordinate equals the building's height."""
    building = Building(
        building_id=0, center=np.array([0.0, 0.0]), width=10.0, depth=8.0, height=25.0
    )
    mesh = MeshFactory.build_building_mesh(building)
    top_z_values = mesh.vertices[4:, 2]
    assert np.allclose(top_z_values, 25.0)

    base_z_values = mesh.vertices[:4, 2]
    assert np.allclose(base_z_values, 0.0)


def test_building_mesh_footprint_matches_aabb() -> None:
    """Base vertex x/y coordinates match the building's AABB exactly."""
    building = Building(
        building_id=0, center=np.array([10.0, -5.0]), width=6.0, depth=4.0, height=15.0
    )
    mesh = MeshFactory.build_building_mesh(building)
    x_min, y_min, x_max, y_max = building.aabb

    base_xy = mesh.vertices[:4, :2]
    assert np.isclose(base_xy[:, 0].min(), x_min)
    assert np.isclose(base_xy[:, 0].max(), x_max)
    assert np.isclose(base_xy[:, 1].min(), y_min)
    assert np.isclose(base_xy[:, 1].max(), y_max)


def test_building_mesh_no_degenerate_triangles() -> None:
    """Every one of a building's 12 triangles has non-zero 3D area (the
    2D signed-area check used for road meshes doesn't apply here: a
    vertical wall's 4 corners project to only 2 distinct XY points)."""
    building = Building(
        building_id=0, center=np.array([0.0, 0.0]), width=10.0, depth=8.0, height=20.0
    )
    mesh = MeshFactory.build_building_mesh(building)

    for i in range(0, len(mesh.triangles), 3):
        v0 = mesh.vertices[mesh.triangles[i]]
        v1 = mesh.vertices[mesh.triangles[i + 1]]
        v2 = mesh.vertices[mesh.triangles[i + 2]]
        area = 0.5 * float(np.linalg.norm(np.cross(v1 - v0, v2 - v0)))
        assert area > MIN_TRIANGLE_AREA_SQ_METERS, f"Degenerate triangle: area={area}"


def test_building_mesh_material() -> None:
    """A building constructed without an explicit material (the default)
    produces a mesh using that same default ("concrete")."""
    building = Building(
        building_id=0, center=np.array([0.0, 0.0]), width=10.0, depth=8.0, height=20.0
    )
    mesh = MeshFactory.build_building_mesh(building)
    assert mesh.material == "concrete"


def test_building_mesh_uses_buildings_own_material() -> None:
    """The mesh's material follows building.material, not a hardcoded
    value -- confirms BuildingPlacementGenerator's per-building
    type/material assignment actually reaches the mesh."""
    building = Building(
        building_id=0,
        center=np.array([0.0, 0.0]),
        width=10.0,
        depth=8.0,
        height=20.0,
        material="glass_curtain_wall",
    )
    mesh = MeshFactory.build_building_mesh(building)
    assert mesh.material == "glass_curtain_wall"


def _sample_vehicle(heading_rad: float = 0.0) -> Vehicle:
    return Vehicle(
        vehicle_id=0,
        vehicle_type="sedan",
        center=np.array([10.0, -5.0]),
        heading_rad=heading_rad,
        length=4.6,
        width=1.8,
        height=1.5,
    )


def test_vehicle_mesh_vertex_and_triangle_count() -> None:
    """A vehicle box has 8 vertices and 12 triangles, same topology as a
    building."""
    mesh = MeshFactory.build_vehicle_mesh(_sample_vehicle())
    assert len(mesh.vertices) == 8
    assert len(mesh.triangles) == 12 * 3


def test_vehicle_mesh_vertices_finite() -> None:
    """No NaN or Inf in a vehicle mesh's vertices."""
    mesh = MeshFactory.build_vehicle_mesh(_sample_vehicle(heading_rad=1.2))
    assert np.isfinite(mesh.vertices).all()


def test_vehicle_mesh_material() -> None:
    """Vehicle meshes use the vehicle_paint material."""
    mesh = MeshFactory.build_vehicle_mesh(_sample_vehicle())
    assert mesh.material == "vehicle_paint"


def test_vehicle_mesh_height_matches_vehicle() -> None:
    """Top vertices sit at z=height, base vertices at z=0."""
    vehicle = _sample_vehicle()
    mesh = MeshFactory.build_vehicle_mesh(vehicle)
    assert np.allclose(mesh.vertices[4:, 2], vehicle.height)
    assert np.allclose(mesh.vertices[:4, 2], 0.0)


def test_vehicle_mesh_heading_zero_matches_axis_aligned_footprint() -> None:
    """heading=0's footprint extent matches length/width directly."""
    vehicle = _sample_vehicle(heading_rad=0.0)
    mesh = MeshFactory.build_vehicle_mesh(vehicle)
    base_xy = mesh.vertices[:4, :2]
    assert np.isclose(base_xy[:, 0].max() - base_xy[:, 0].min(), vehicle.length)
    assert np.isclose(base_xy[:, 1].max() - base_xy[:, 1].min(), vehicle.width)


def test_vehicle_mesh_heading_quarter_turn_swaps_footprint_extents() -> None:
    """heading=pi/2 rotates the footprint 90 degrees, swapping its
    world-space x/y extents relative to heading=0."""
    vehicle = _sample_vehicle(heading_rad=np.pi / 2)
    mesh = MeshFactory.build_vehicle_mesh(vehicle)
    base_xy = mesh.vertices[:4, :2]
    assert np.isclose(base_xy[:, 0].max() - base_xy[:, 0].min(), vehicle.width)
    assert np.isclose(base_xy[:, 1].max() - base_xy[:, 1].min(), vehicle.length)


def test_vehicle_mesh_no_degenerate_triangles() -> None:
    """Every one of a vehicle's 12 triangles has non-zero 3D area."""
    mesh = MeshFactory.build_vehicle_mesh(_sample_vehicle(heading_rad=0.7))
    for i in range(0, len(mesh.triangles), 3):
        v0 = mesh.vertices[mesh.triangles[i]]
        v1 = mesh.vertices[mesh.triangles[i + 1]]
        v2 = mesh.vertices[mesh.triangles[i + 2]]
        area = 0.5 * float(np.linalg.norm(np.cross(v1 - v0, v2 - v0)))
        assert area > MIN_TRIANGLE_AREA_SQ_METERS, f"Degenerate triangle: area={area}"


def _sample_pedestrian(heading_rad: float = 0.0) -> Pedestrian:
    return Pedestrian(pedestrian_id=0, center=np.array([1.0, 2.0]), heading_rad=heading_rad)


def test_pedestrian_mesh_vertex_and_triangle_count() -> None:
    """A pedestrian box has 8 vertices and 12 triangles, same topology as
    a building."""
    mesh = MeshFactory.build_pedestrian_mesh(_sample_pedestrian())
    assert len(mesh.vertices) == 8
    assert len(mesh.triangles) == 12 * 3


def test_pedestrian_mesh_vertices_finite() -> None:
    """No NaN or Inf in a pedestrian mesh's vertices."""
    mesh = MeshFactory.build_pedestrian_mesh(_sample_pedestrian(heading_rad=2.1))
    assert np.isfinite(mesh.vertices).all()


def test_pedestrian_mesh_material() -> None:
    """Pedestrian meshes use the pedestrian material."""
    mesh = MeshFactory.build_pedestrian_mesh(_sample_pedestrian())
    assert mesh.material == "pedestrian"


def test_pedestrian_mesh_height_matches_pedestrian() -> None:
    """Top vertices sit at z=height, base vertices at z=0."""
    pedestrian = _sample_pedestrian()
    mesh = MeshFactory.build_pedestrian_mesh(pedestrian)
    assert np.allclose(mesh.vertices[4:, 2], pedestrian.height)
    assert np.allclose(mesh.vertices[:4, 2], 0.0)


@pytest.mark.parametrize(
    "corners",
    [
        ([0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]),  # already CCW
        ([0.0, 0.0], [0.0, 10.0], [10.0, 10.0], [10.0, 0.0]),  # CW input, must be fixed
    ],
)
def test_quad_indices_ccw_always_produces_positive_area(corners) -> None:
    """_quad_indices_ccw normalizes winding regardless of input order."""
    vertices_2d = np.array(corners)
    triangles = _quad_indices_ccw(vertices_2d, 0, 1, 2, 3)

    for tri in triangles:
        v0, v1, v2 = vertices_2d[tri[0]], vertices_2d[tri[1]], vertices_2d[tri[2]]
        assert _triangle_signed_area(v0, v1, v2) >= 0
