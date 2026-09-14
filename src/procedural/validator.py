"""Cross-module scenario validation: bounds containment and geometry finiteness.

Implements the two MASTER_PROMPT Section 3.5 ("UE5 Integration & Scene
Loading") test bullets that are actually pure geometry, independent of any
running UE5 instance: "Scene bounds validation" and "No floating-point
errors in geometry." Corresponds to Section 1.1's architecture diagram
entry "Scenario Validator (Topological Analysis)" under the Python-side
Procedural Generation Engine.

The other two Phase 4 test bullets ("UE5 communication latency < 100ms",
"Mesh loading completes in < 2s") are exercised against a real UE5
instance in ``src/ue5/backend.py``'s tests, using a local mock WebSocket
server rather than a live UE5 editor (which isn't installed in this
environment) -- see that module's docstring.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from src.procedural.actor_placement import Pedestrian, Vehicle
from src.procedural.building_placement import Building
from src.procedural.lane_connectivity import LaneConnectivityGraph
from src.procedural.lane_topology import Lane
from src.procedural.mesh_factory import Mesh
from src.procedural.road_network import RoadEdge, RoadNode

Bounds = Tuple[float, float, float, float]


@dataclass
class ValidationReport:
    """Result of validating one generated scenario."""

    issues: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True iff no issues have been recorded."""
        return not self.issues

    def add(self, issue: str) -> None:
        """Record one validation failure's description."""
        self.issues.append(issue)


class ScenarioValidator:  # pylint: disable=too-few-public-methods
    """Validate a fully-generated scenario's geometry against its bounds
    and for numerical well-formedness.

    Exposes a single public entry point (``validate``) by design; the
    rest of the class is private implementation detail of that operation.
    """

    def validate(  # pylint: disable=too-many-arguments
        self,
        bounds: Bounds,
        nodes: Dict[int, RoadNode],
        edges: Dict[int, RoadEdge],
        lanes: Dict[int, Lane],
        buildings: List[Building],
        meshes: List[Mesh],
        vehicles: Optional[List[Vehicle]] = None,
        pedestrians: Optional[List[Pedestrian]] = None,
        lane_connectivity: Optional[LaneConnectivityGraph] = None,
    ) -> ValidationReport:
        """Validate every geometric element of a generated scenario.

        Parameters
        ----------
        bounds : Bounds
            (x_min, y_min, x_max, y_max) the scenario was generated within.
        nodes, edges, lanes, buildings, meshes
            Output of the corresponding generator for this scenario.
        vehicles, pedestrians
            Output of ``ActorPlacementGenerator``, if any -- optional and
            defaulting to none, so every pre-existing caller (and every
            pre-existing test) keeps working unchanged.
        lane_connectivity
            Output of ``LaneConnectivityGenerator``, if any -- optional,
            same reasoning as ``vehicles``/``pedestrians``.

        Returns
        -------
        ValidationReport
            ``report.is_valid`` is True iff every check passed; otherwise
            ``report.issues`` lists every violation found (validation
            does not stop at the first failure, so a caller gets the
            complete picture in one pass).
        """
        report = ValidationReport()

        self._validate_nodes(nodes, bounds, report)
        self._validate_edges(edges, report)
        self._validate_lanes(lanes, report)
        self._validate_buildings(buildings, bounds, report)
        self._validate_meshes(meshes, report)
        self._validate_vehicles(vehicles or [], report)
        self._validate_pedestrians(pedestrians or [], report)
        self._validate_lane_connectivity(lane_connectivity, lanes, report)

        return report

    @staticmethod
    def _validate_nodes(
        nodes: Dict[int, RoadNode], bounds: Bounds, report: ValidationReport
    ) -> None:
        x_min, y_min, x_max, y_max = bounds
        for node_id, node in nodes.items():
            if not np.isfinite(node.position).all():
                report.add(f"Node {node_id}: non-finite position {node.position}")
                continue
            x, y = node.position
            if not (x_min <= x <= x_max and y_min <= y <= y_max):
                report.add(f"Node {node_id}: position {node.position} outside bounds {bounds}")

    @staticmethod
    def _validate_edges(edges: Dict[int, RoadEdge], report: ValidationReport) -> None:
        for edge_id, edge in edges.items():
            if not np.isfinite(edge.centerline).all():
                report.add(f"Edge {edge_id}: non-finite centerline")
            if edge.length <= 0 or not np.isfinite(edge.length):
                report.add(f"Edge {edge_id}: invalid length {edge.length}")

    @staticmethod
    def _validate_lanes(lanes: Dict[int, Lane], report: ValidationReport) -> None:
        for lane_id, lane in lanes.items():
            for name, array in (
                ("centerline", lane.centerline),
                ("left_boundary", lane.left_boundary),
                ("right_boundary", lane.right_boundary),
            ):
                if not np.isfinite(array).all():
                    report.add(f"Lane {lane_id}: non-finite {name}")

    @staticmethod
    def _validate_buildings(
        buildings: List[Building], bounds: Bounds, report: ValidationReport
    ) -> None:
        x_min, y_min, x_max, y_max = bounds
        for building in buildings:
            if not np.isfinite(building.center).all() or not np.isfinite(building.height):
                report.add(f"Building {building.building_id}: non-finite geometry")
                continue
            b_x_min, b_y_min, b_x_max, b_y_max = building.aabb
            if not (
                x_min <= b_x_min and b_x_max <= x_max and y_min <= b_y_min and b_y_max <= y_max
            ):
                report.add(
                    f"Building {building.building_id}: footprint {building.aabb} "
                    f"outside bounds {bounds}"
                )

    @staticmethod
    def _validate_vehicles(vehicles: List[Vehicle], report: ValidationReport) -> None:
        # Finiteness only, no bounds-containment check: vehicles are
        # anchored directly at TrafficNetworkGenerator's own spawn zone
        # positions (lane starts, sidewalk offsets), which are
        # themselves never validated against `bounds` either -- see
        # test_traffic_network.py. Unlike buildings (placed with an
        # explicit ROAD_SETBACK_METERS margin guaranteeing containment),
        # spawn zones near the road network's edge can legitimately sit
        # slightly outside `bounds`; that's a property of the road
        # network's own generation, not a vehicle-placement defect.
        for vehicle in vehicles:
            if not np.isfinite(vehicle.center).all() or not np.isfinite(vehicle.heading_rad):
                report.add(f"Vehicle {vehicle.vehicle_id}: non-finite geometry")

    @staticmethod
    def _validate_pedestrians(pedestrians: List[Pedestrian], report: ValidationReport) -> None:
        # See _validate_vehicles: same rationale for omitting a bounds check.
        for pedestrian in pedestrians:
            if not np.isfinite(pedestrian.center).all() or not np.isfinite(pedestrian.heading_rad):
                report.add(f"Pedestrian {pedestrian.pedestrian_id}: non-finite geometry")

    @staticmethod
    def _validate_lane_connectivity(
        lane_connectivity: Optional[LaneConnectivityGraph],
        lanes: Dict[int, Lane],
        report: ValidationReport,
    ) -> None:
        """Regression safety net, not a check expected to ever fail by
        construction: every connection's from/to lane_id should reference
        a real lane, and never connect a lane to itself."""
        if lane_connectivity is None:
            return
        for connection in lane_connectivity.connections:
            if connection.from_lane_id not in lanes:
                report.add(
                    f"Lane connection: from_lane_id {connection.from_lane_id} " "is not a real lane"
                )
            if connection.to_lane_id not in lanes:
                report.add(
                    f"Lane connection: to_lane_id {connection.to_lane_id} is not a real lane"
                )
            if connection.from_lane_id == connection.to_lane_id:
                report.add(f"Lane connection: lane {connection.from_lane_id} connects to itself")

    @staticmethod
    def _validate_meshes(meshes: List[Mesh], report: ValidationReport) -> None:
        for i, mesh in enumerate(meshes):
            if not np.isfinite(mesh.vertices).all():
                report.add(f"Mesh {i}: non-finite vertices")
            if len(mesh.triangles) % 3 != 0:
                report.add(f"Mesh {i}: triangle index buffer length not a multiple of 3")
            if len(mesh.triangles) > 0 and mesh.triangles.max() >= len(mesh.vertices):
                report.add(f"Mesh {i}: triangle index out of range for its vertex buffer")
