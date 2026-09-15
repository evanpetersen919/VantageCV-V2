"""Traffic rule assignment, spawn zones, and navigation graph.

Implements MASTER_PROMPT Section 3.4's "Traffic Network" bullets: compute
traffic rules from road types, generate spawn zones, create a navigation
graph for pathfinding, assign traffic lights at major intersections. As
with Phase 2, MASTER_PROMPT gives no formulas or reference code for this
phase; the design below was informed by the existing (previously unused)
``RoadNode.traffic_light``/``RoadNode.stop_sign`` fields already defined
in road_network.py (comment there says "Will be updated" -- this module
is what finally updates them), plus QOL_RESEARCH_CHECKLIST.md Section G.

Deliberately out of scope (see KNOWN_GAPS_AND_ISSUES.md): parking spawn
zones (no parking-lot-specific geometry exists yet to place them against)
and turn-restriction-aware lane connectivity (needs the traffic rules
this module computes, so it's implemented here at the intersection level,
not per-lane -- full per-lane turn graphs are deferred further still).
"""

import heapq
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import numpy.typing as npt

from src.procedural.lane_topology import Lane
from src.procedural.math_utils import compute_perpendicular
from src.procedural.road_network import IntersectionType, RoadEdge, RoadNode

# Sidewalk offset beyond a road's outer lane edge, within which pedestrian
# spawn zones are placed. Matches the sidewalk-width order of magnitude
# used by ScenarioTypeConfig.road_setback_meters's own default in
# scenario.py/building_placement.py.
SIDEWALK_OFFSET_METERS = 1.5


class TrafficControlType(str, Enum):
    """Right-of-way control present at an intersection node."""

    NONE = "none"
    STOP_SIGN = "stop_sign"
    TRAFFIC_LIGHT = "traffic_light"


class SpawnZoneType(str, Enum):
    """What kind of actor a spawn zone is intended for."""

    DRIVING = "driving"
    PEDESTRIAN = "pedestrian"


@dataclass(eq=False)
class SpawnZone:
    """A single point where an actor (vehicle or pedestrian) may spawn."""

    spawn_zone_id: int
    zone_type: SpawnZoneType
    position: npt.NDArray[np.float64]
    edge_id: int

    def __hash__(self) -> int:
        return hash(self.spawn_zone_id)


@dataclass(eq=False)
class NavigationGraph:
    """A weighted graph over road nodes for shortest-path queries.

    Edge weight is travel time (``length / speed_limit``), not raw
    distance -- shortest *time* path is what routing actually wants, and
    it happens to coincide with a road network's own directed edges, so no
    separate graph structure is needed beyond a weight lookup.
    """

    edges: Dict[int, RoadEdge]
    weights_seconds: Dict[int, float]

    def shortest_path(self, start_node_id: int, end_node_id: int) -> Optional[List[int]]:
        """Dijkstra's algorithm from ``start_node_id`` to ``end_node_id``.

        Returns
        -------
        Optional[List[int]]
            Ordered list of node IDs from start to end (inclusive), or
            ``None`` if no path exists.
        """
        if start_node_id == end_node_id:
            return [start_node_id]

        outgoing_by_node: Dict[int, List[RoadEdge]] = {}
        for edge in self.edges.values():
            outgoing_by_node.setdefault(edge.start_node_id, []).append(edge)

        distances: Dict[int, float] = {start_node_id: 0.0}
        previous: Dict[int, int] = {}
        visited = set()
        queue: List[Tuple[float, int]] = [(0.0, start_node_id)]

        while queue:
            dist, node_id = heapq.heappop(queue)
            if node_id in visited:
                continue
            visited.add(node_id)

            if node_id == end_node_id:
                return self._reconstruct_path(previous, start_node_id, end_node_id)

            for edge in outgoing_by_node.get(node_id, []):
                neighbor = edge.end_node_id
                if neighbor in visited:
                    continue
                new_dist = dist + self.weights_seconds[edge.edge_id]
                if new_dist < distances.get(neighbor, float("inf")):
                    distances[neighbor] = new_dist
                    previous[neighbor] = node_id
                    heapq.heappush(queue, (new_dist, neighbor))

        return None

    @staticmethod
    def _reconstruct_path(
        previous: Dict[int, int], start_node_id: int, end_node_id: int
    ) -> List[int]:
        path = [end_node_id]
        while path[-1] != start_node_id:
            path.append(previous[path[-1]])
        path.reverse()
        return path


@dataclass(eq=False)
class TrafficNetwork:
    """Complete Phase 3 output: intersection controls, spawn zones, and a
    navigation graph, over an existing road network."""

    traffic_controls: Dict[int, TrafficControlType]
    spawn_zones: List[SpawnZone]
    navigation_graph: NavigationGraph


class TrafficNetworkGenerator:  # pylint: disable=too-few-public-methods
    """Generate a TrafficNetwork from an existing road network + lanes.

    Exposes a single public entry point (``generate``) by design; the
    rest of the class is private implementation detail of that operation.
    """

    def __init__(self) -> None:
        self._spawn_zone_counter = 0

    def generate(
        self, nodes: Dict[int, RoadNode], edges: Dict[int, RoadEdge], lanes: Dict[int, Lane]
    ) -> TrafficNetwork:
        """Assign traffic controls, generate spawn zones, and build a
        navigation graph.

        Parameters
        ----------
        nodes : Dict[int, RoadNode]
            The road network's nodes. Mutated in place: ``traffic_light``
            and ``stop_sign`` are set according to each node's
            ``node_type`` (see ``_assign_traffic_controls``).
        edges : Dict[int, RoadEdge]
            The road network's directed edges.
        lanes : Dict[int, Lane]
            Per-edge lane geometry from ``LaneTopologyGenerator``, used to
            place one driving spawn zone per lane and one pedestrian spawn
            zone per edge (offset beyond the outermost lane).

        Returns
        -------
        TrafficNetwork
        """
        traffic_controls = self._assign_traffic_controls(nodes)
        spawn_zones = self._generate_spawn_zones(edges, lanes)
        navigation_graph = self._build_navigation_graph(edges)

        return TrafficNetwork(
            traffic_controls=traffic_controls,
            spawn_zones=spawn_zones,
            navigation_graph=navigation_graph,
        )

    @staticmethod
    def _assign_traffic_controls(
        nodes: Dict[int, RoadNode],
    ) -> Dict[int, TrafficControlType]:
        """Assign traffic lights to four-way intersections and stop signs
        to T-junctions, mutating each RoadNode's own
        ``traffic_light``/``stop_sign`` fields (populated here for the
        first time -- see module docstring) and returning the same
        information as a lookup dict for convenience."""
        controls: Dict[int, TrafficControlType] = {}
        for node_id, node in nodes.items():
            if node.node_type == IntersectionType.FOUR_WAY:
                node.traffic_light = True
                node.stop_sign = False
                controls[node_id] = TrafficControlType.TRAFFIC_LIGHT
            elif node.node_type == IntersectionType.T_JUNCTION:
                node.traffic_light = False
                node.stop_sign = True
                controls[node_id] = TrafficControlType.STOP_SIGN
            else:
                node.traffic_light = False
                node.stop_sign = False
                controls[node_id] = TrafficControlType.NONE
        return controls

    def _generate_spawn_zones(
        self, edges: Dict[int, RoadEdge], lanes: Dict[int, Lane]
    ) -> List[SpawnZone]:
        """One driving spawn zone at the start of every lane, plus one
        pedestrian spawn zone per edge offset beyond its outermost lane."""
        spawn_zones: List[SpawnZone] = []

        for lane in lanes.values():
            spawn_zones.append(
                SpawnZone(
                    spawn_zone_id=self._spawn_zone_counter,
                    zone_type=SpawnZoneType.DRIVING,
                    position=lane.centerline[0].copy(),
                    edge_id=lane.edge_id,
                )
            )
            self._spawn_zone_counter += 1

        lanes_by_edge: Dict[int, List[Lane]] = {}
        for lane in lanes.values():
            lanes_by_edge.setdefault(lane.edge_id, []).append(lane)

        for edge_id, edge_lanes in lanes_by_edge.items():
            outermost_lane = max(edge_lanes, key=lambda lane: lane.lane_index)
            edge = edges[edge_id]
            direction = edge.centerline[-1] - edge.centerline[0]
            perp = compute_perpendicular(direction)
            pedestrian_position = outermost_lane.left_boundary[0] + perp * SIDEWALK_OFFSET_METERS

            spawn_zones.append(
                SpawnZone(
                    spawn_zone_id=self._spawn_zone_counter,
                    zone_type=SpawnZoneType.PEDESTRIAN,
                    position=pedestrian_position,
                    edge_id=edge_id,
                )
            )
            self._spawn_zone_counter += 1

        return spawn_zones

    @staticmethod
    def _build_navigation_graph(edges: Dict[int, RoadEdge]) -> NavigationGraph:
        """Weight every edge by travel time (length / speed), converting
        speed_limit_kmh to m/s."""
        weights_seconds = {}
        for edge_id, edge in edges.items():
            speed_ms = edge.speed_limit_kmh / 3.6
            weights_seconds[edge_id] = edge.length / speed_ms
        return NavigationGraph(edges=edges, weights_seconds=weights_seconds)
