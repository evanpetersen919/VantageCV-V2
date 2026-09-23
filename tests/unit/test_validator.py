"""Unit tests for ScenarioValidator."""

# pylint: disable=duplicate-code
# Several tests here construct a minimal RoadEdge/Lane by hand to isolate
# one validator check, which inevitably resembles similar hand-built
# fixtures in test_traffic_network.py/test_mesh_factory.py -- shared
# fixtures would couple those unrelated test files together for no benefit.

import numpy as np

from src.procedural.actor_placement import ActorPlacementGenerator, Pedestrian, Vehicle
from src.procedural.building_placement import Building, BuildingPlacementGenerator
from src.procedural.city_sample_assets import PEDESTRIAN_ASSET_PATHS
from src.procedural.lane_connectivity import (
    LaneConnection,
    LaneConnectivityGenerator,
    LaneConnectivityGraph,
    TurnType,
)
from src.procedural.lane_topology import Lane, LaneTopologyGenerator
from src.procedural.mesh_factory import Mesh, MeshFactory
from src.procedural.road_network import (
    IntersectionType,
    RoadEdge,
    RoadNetworkGenerator,
    RoadNode,
    RoadType,
)
from src.procedural.traffic_network import TrafficNetworkGenerator
from src.procedural.validator import ScenarioValidator

# urban_config, bounds fixtures: see tests/conftest.py


def _generate_everything(seed: int, config, bounds):
    road_gen = RoadNetworkGenerator(seed, config)
    nodes, edges = road_gen.generate(bounds)
    lanes = LaneTopologyGenerator().generate(nodes, edges)
    buildings = BuildingPlacementGenerator(seed, config).generate(nodes, edges)
    meshes = [MeshFactory.build_road_mesh(lane) for lane in lanes.values()]
    meshes += [MeshFactory.build_building_mesh(b) for b in buildings]
    return nodes, edges, lanes, buildings, meshes


def _generate_everything_with_actors(seed: int, config, bounds):
    nodes, edges, lanes, buildings, meshes = _generate_everything(seed, config, bounds)
    traffic = TrafficNetworkGenerator().generate(nodes, edges, lanes)
    vehicles, pedestrians = ActorPlacementGenerator(seed, config).generate(edges, traffic)
    meshes += [MeshFactory.build_vehicle_mesh(v) for v in vehicles]
    meshes += [MeshFactory.build_pedestrian_mesh(p) for p in pedestrians]
    lane_connectivity = LaneConnectivityGenerator().generate(nodes, edges, lanes)
    return nodes, edges, lanes, buildings, meshes, vehicles, pedestrians, lane_connectivity


def test_full_generated_scenario_is_valid(urban_config, bounds) -> None:
    """A genuine end-to-end generated scenario passes validation cleanly."""
    nodes, edges, lanes, buildings, meshes = _generate_everything(42, urban_config, bounds)

    report = ScenarioValidator().validate(bounds, nodes, edges, lanes, buildings, meshes)

    assert report.is_valid, report.issues


def test_node_outside_bounds_flagged() -> None:
    """A node positioned outside the declared bounds is reported."""
    nodes = {
        0: RoadNode(
            node_id=0, position=np.array([1000.0, 1000.0]), node_type=IntersectionType.ISOLATED
        )
    }
    report = ScenarioValidator().validate((0.0, 0.0, 100.0, 100.0), nodes, {}, {}, [], [])

    assert not report.is_valid
    assert any("outside bounds" in issue for issue in report.issues)


def test_node_non_finite_position_flagged() -> None:
    """A NaN node position is reported, not silently passed through the
    bounds check (which would otherwise raise or give a wrong answer)."""
    nodes = {
        0: RoadNode(
            node_id=0, position=np.array([np.nan, 0.0]), node_type=IntersectionType.ISOLATED
        )
    }
    report = ScenarioValidator().validate((0.0, 0.0, 100.0, 100.0), nodes, {}, {}, [], [])

    assert not report.is_valid
    assert any("non-finite" in issue for issue in report.issues)


def test_edge_zero_length_flagged() -> None:
    """An edge with zero (or negative) length is reported."""
    edge = RoadEdge(
        edge_id=0,
        start_node_id=0,
        end_node_id=1,
        road_type=RoadType.MAJOR,
        centerline=np.array([[0.0, 0.0], [0.0, 0.0]]),
        length=0.0,
        num_lanes=2,
        speed_limit_kmh=50,
        width_meters=10.0,
    )
    report = ScenarioValidator().validate((0.0, 0.0, 100.0, 100.0), {}, {0: edge}, {}, [], [])

    assert not report.is_valid
    assert any("invalid length" in issue for issue in report.issues)


def test_edge_non_finite_centerline_flagged() -> None:
    """An edge with an Inf centerline coordinate is reported."""
    edge = RoadEdge(
        edge_id=0,
        start_node_id=0,
        end_node_id=1,
        road_type=RoadType.MAJOR,
        centerline=np.array([[0.0, 0.0], [np.inf, 0.0]]),
        length=10.0,
        num_lanes=2,
        speed_limit_kmh=50,
        width_meters=10.0,
    )
    report = ScenarioValidator().validate((0.0, 0.0, 100.0, 100.0), {}, {0: edge}, {}, [], [])

    assert not report.is_valid
    assert any("non-finite centerline" in issue for issue in report.issues)


def test_lane_non_finite_boundary_flagged() -> None:
    """A lane with a NaN boundary point is reported."""
    lane = Lane(
        lane_id=0,
        edge_id=0,
        lane_index=0,
        centerline=np.array([[0.0, 0.0], [10.0, 0.0]]),
        left_boundary=np.array([[0.0, 2.0], [np.nan, 2.0]]),
        right_boundary=np.array([[0.0, -2.0], [10.0, -2.0]]),
        width=4.0,
    )
    report = ScenarioValidator().validate((0.0, 0.0, 100.0, 100.0), {}, {}, {0: lane}, [], [])

    assert not report.is_valid
    assert any("left_boundary" in issue for issue in report.issues)


def test_building_outside_bounds_flagged() -> None:
    """A building whose footprint extends outside the declared bounds is
    reported (even if its center is inside)."""
    building = Building(
        building_id=0, center=np.array([95.0, 50.0]), width=20.0, depth=10.0, height=15.0
    )
    report = ScenarioValidator().validate((0.0, 0.0, 100.0, 100.0), {}, {}, {}, [building], [])

    assert not report.is_valid
    assert any("outside bounds" in issue for issue in report.issues)


def test_building_non_finite_height_flagged() -> None:
    """A building with a non-finite height is reported."""
    building = Building(
        building_id=0, center=np.array([50.0, 50.0]), width=10.0, depth=10.0, height=np.nan
    )
    report = ScenarioValidator().validate((0.0, 0.0, 100.0, 100.0), {}, {}, {}, [building], [])

    assert not report.is_valid
    assert any("non-finite" in issue for issue in report.issues)


def test_full_generated_scenario_with_actors_is_valid(urban_config, bounds) -> None:
    """A genuine end-to-end scenario including vehicles/pedestrians
    passes validation cleanly."""
    (
        nodes,
        edges,
        lanes,
        buildings,
        meshes,
        vehicles,
        pedestrians,
        lane_connectivity,
    ) = _generate_everything_with_actors(42, urban_config, bounds)
    assert vehicles  # sanity: this seed/config actually places some
    assert lane_connectivity.connections  # sanity: this seed/config actually connects some

    report = ScenarioValidator().validate(
        bounds, nodes, edges, lanes, buildings, meshes, vehicles, pedestrians, lane_connectivity
    )
    assert report.is_valid, report.issues


def test_vehicle_non_finite_center_flagged() -> None:
    """A vehicle with a NaN center is reported."""
    vehicle = Vehicle(
        vehicle_id=0,
        vehicle_type="sedan",
        asset_path="/Game/Vehicle/vehCar_vehicle02/BP_vehCar_vehicle02_Sandbox",
        center=np.array([np.nan, 0.0]),
        heading_rad=0.0,
        length=4.6,
        width=1.8,
        height=1.5,
    )
    report = ScenarioValidator().validate(
        (0.0, 0.0, 100.0, 100.0), {}, {}, {}, [], [], [vehicle], []
    )

    assert not report.is_valid
    assert any("non-finite" in issue for issue in report.issues)


def test_vehicle_non_finite_heading_flagged() -> None:
    """A vehicle with a non-finite heading is reported."""
    vehicle = Vehicle(
        vehicle_id=0,
        vehicle_type="sedan",
        asset_path="/Game/Vehicle/vehCar_vehicle02/BP_vehCar_vehicle02_Sandbox",
        center=np.array([50.0, 50.0]),
        heading_rad=np.nan,
        length=4.6,
        width=1.8,
        height=1.5,
    )
    report = ScenarioValidator().validate(
        (0.0, 0.0, 100.0, 100.0), {}, {}, {}, [], [], [vehicle], []
    )

    assert not report.is_valid
    assert any("non-finite" in issue for issue in report.issues)


def test_vehicle_outside_bounds_not_flagged() -> None:
    """A vehicle positioned outside `bounds` is deliberately NOT
    flagged -- see ScenarioValidator._validate_vehicles's own docstring
    comment: spawn zone positions (which anchor every vehicle) are never
    bounds-checked, unlike buildings."""
    vehicle = Vehicle(
        vehicle_id=0,
        vehicle_type="sedan",
        asset_path="/Game/Vehicle/vehCar_vehicle02/BP_vehCar_vehicle02_Sandbox",
        center=np.array([500.0, 500.0]),
        heading_rad=0.0,
        length=4.6,
        width=1.8,
        height=1.5,
    )
    report = ScenarioValidator().validate(
        (0.0, 0.0, 100.0, 100.0), {}, {}, {}, [], [], [vehicle], []
    )
    assert report.is_valid


def test_pedestrian_non_finite_center_flagged() -> None:
    """A pedestrian with a NaN center is reported."""
    pedestrian = Pedestrian(
        pedestrian_id=0,
        center=np.array([np.nan, 0.0]),
        heading_rad=0.0,
        asset_path=PEDESTRIAN_ASSET_PATHS[0],
    )
    report = ScenarioValidator().validate(
        (0.0, 0.0, 100.0, 100.0), {}, {}, {}, [], [], [], [pedestrian]
    )

    assert not report.is_valid
    assert any("non-finite" in issue for issue in report.issues)


def _sample_lane(lane_id: int = 0) -> Lane:
    return Lane(
        lane_id=lane_id,
        edge_id=0,
        lane_index=0,
        centerline=np.array([[0.0, 0.0], [10.0, 0.0]]),
        left_boundary=np.array([[0.0, 2.0], [10.0, 2.0]]),
        right_boundary=np.array([[0.0, -2.0], [10.0, -2.0]]),
        width=4.0,
    )


def test_lane_connection_unknown_from_lane_flagged() -> None:
    """A connection whose from_lane_id isn't a real lane is reported."""
    lane = _sample_lane(lane_id=0)
    connectivity = LaneConnectivityGraph(
        connections=[LaneConnection(from_lane_id=999, to_lane_id=0, turn_type=TurnType.STRAIGHT)]
    )
    report = ScenarioValidator().validate(
        (0.0, 0.0, 100.0, 100.0), {}, {}, {0: lane}, [], [], [], [], connectivity
    )

    assert not report.is_valid
    assert any("from_lane_id 999" in issue for issue in report.issues)


def test_lane_connection_unknown_to_lane_flagged() -> None:
    """A connection whose to_lane_id isn't a real lane is reported."""
    lane = _sample_lane(lane_id=0)
    connectivity = LaneConnectivityGraph(
        connections=[LaneConnection(from_lane_id=0, to_lane_id=999, turn_type=TurnType.STRAIGHT)]
    )
    report = ScenarioValidator().validate(
        (0.0, 0.0, 100.0, 100.0), {}, {}, {0: lane}, [], [], [], [], connectivity
    )

    assert not report.is_valid
    assert any("to_lane_id 999" in issue for issue in report.issues)


def test_lane_connection_self_loop_flagged() -> None:
    """A connection from a lane to itself is reported."""
    lane = _sample_lane(lane_id=0)
    connectivity = LaneConnectivityGraph(
        connections=[LaneConnection(from_lane_id=0, to_lane_id=0, turn_type=TurnType.STRAIGHT)]
    )
    report = ScenarioValidator().validate(
        (0.0, 0.0, 100.0, 100.0), {}, {}, {0: lane}, [], [], [], [], connectivity
    )

    assert not report.is_valid
    assert any("connects to itself" in issue for issue in report.issues)


def test_lane_connectivity_none_is_skipped() -> None:
    """Omitting lane_connectivity entirely (the default) doesn't run this
    check at all -- every pre-existing caller keeps working unchanged."""
    lane = _sample_lane(lane_id=0)
    report = ScenarioValidator().validate((0.0, 0.0, 100.0, 100.0), {}, {}, {0: lane}, [], [])
    assert report.is_valid


def test_mesh_non_finite_vertices_flagged() -> None:
    """A mesh with a NaN vertex is reported."""
    mesh = Mesh(
        vertices=np.array([[0.0, 0.0, 0.0], [np.nan, 1.0, 0.0], [1.0, 0.0, 0.0]]),
        triangles=np.array([0, 1, 2]),
        uvs=np.zeros((3, 2)),
        material="asphalt",
    )
    report = ScenarioValidator().validate((0.0, 0.0, 100.0, 100.0), {}, {}, {}, [], [mesh])

    assert not report.is_valid
    assert any("non-finite vertices" in issue for issue in report.issues)


def test_mesh_triangle_index_out_of_range_flagged() -> None:
    """A triangle index referencing a non-existent vertex is reported."""
    mesh = Mesh(
        vertices=np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
        triangles=np.array([0, 1, 99]),
        uvs=np.zeros((3, 2)),
        material="asphalt",
    )
    report = ScenarioValidator().validate((0.0, 0.0, 100.0, 100.0), {}, {}, {}, [], [mesh])

    assert not report.is_valid
    assert any("index out of range" in issue for issue in report.issues)


def test_mesh_malformed_triangle_buffer_length_flagged() -> None:
    """A triangle index buffer whose length isn't a multiple of 3 is
    reported."""
    mesh = Mesh(
        vertices=np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]),
        triangles=np.array([0, 1]),
        uvs=np.zeros((2, 2)),
        material="asphalt",
    )
    report = ScenarioValidator().validate((0.0, 0.0, 100.0, 100.0), {}, {}, {}, [], [mesh])

    assert not report.is_valid
    assert any("multiple of 3" in issue for issue in report.issues)


def test_empty_scenario_is_valid() -> None:
    """A scenario with no elements at all trivially passes (nothing to
    violate any check)."""
    report = ScenarioValidator().validate((0.0, 0.0, 100.0, 100.0), {}, {}, {}, [], [])
    assert report.is_valid


def test_report_collects_multiple_independent_issues() -> None:
    """Validation doesn't stop at the first failure -- multiple
    independent violations are all reported in one pass."""
    nodes = {
        0: RoadNode(
            node_id=0, position=np.array([1000.0, 0.0]), node_type=IntersectionType.ISOLATED
        )
    }
    building = Building(
        building_id=0, center=np.array([2000.0, 0.0]), width=10.0, depth=10.0, height=10.0
    )
    report = ScenarioValidator().validate((0.0, 0.0, 100.0, 100.0), nodes, {}, {}, [building], [])

    assert len(report.issues) >= 2
