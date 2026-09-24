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
import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import numpy.typing as npt

from src.procedural.crosswalks import compute_crosswalk_anchors
from src.procedural.lane_topology import (
    MAX_TRIM_FRACTION_OF_EDGE_LENGTH,
    Lane,
    compute_node_clearance,
)
from src.procedural.math_utils import compute_perpendicular
from src.procedural.road_network import IntersectionType, RoadEdge, RoadNode

# Sidewalk offset beyond a road's outer lane edge, within which pedestrian
# spawn zones are placed. Matches the sidewalk-width order of magnitude
# used by ScenarioTypeConfig.road_setback_meters's own default in
# scenario.py/building_placement.py.
SIDEWALK_OFFSET_METERS = 1.5

# Real, not guessed: Epic's own City Sample ships 4 real
# "MassCrowdZoneGraphSpawnPointGenerator_Density{0-3}" configs
# (Content/AI/AgentConfig) that place candidate pedestrian spawn points
# along a ZoneGraph sidewalk lane -- queried live via a headless
# CitySample Python session's `obj dump` on each one's class default
# object: all 4 (which otherwise differ only by ZoneGraph tag filter,
# not spacing) use the identical
# `MassEntityZoneGraphSpawnPointsGenerator::MinGap = MaxGap = 300.0`
# (centimeters), i.e. a fixed, non-randomized 3.0m gap between candidate
# points along the lane. Reused directly here rather than inventing a
# spacing figure.
PEDESTRIAN_SPAWN_GAP_METERS = 3.0


class TrafficControlType(str, Enum):
    """Right-of-way control present at an intersection node."""

    NONE = "none"
    STOP_SIGN = "stop_sign"
    TRAFFIC_LIGHT = "traffic_light"


class SpawnZoneType(str, Enum):
    """What kind of actor a spawn zone is intended for."""

    DRIVING = "driving"
    PEDESTRIAN = "pedestrian"
    CROSSING = "crossing"


@dataclass(eq=False)
class SpawnZone:
    """A single point where an actor (vehicle or pedestrian) may spawn.

    ``edge_id`` is ``None`` for ``CROSSING`` zones (a crosswalk spans a
    whole road at a node, not one directed edge) and ``heading_rad`` is
    ``None`` for ``DRIVING``/``PEDESTRIAN`` zones (their heading is
    derived from their own edge's direction at placement time instead --
    see ``actor_placement.py``); a ``CROSSING`` zone's ``heading_rad`` is
    the crosswalk's own real across-the-road crossing direction (see
    ``crosswalks.CrosswalkAnchor.perp``), since it has no directed edge
    of its own to derive one from.

    ``node_id`` is populated only for ``CROSSING`` zones, from the same
    real ``CrosswalkAnchor.node_id`` this project's painted crosswalk bars
    already use (``crosswalks.py``) -- the intersection this crosswalk
    belongs to, needed to look up which real signal phase currently
    governs whether crossing here is safe (see ``signal_phasing.py``).

    ``stop_line_position`` is populated only for ``DRIVING`` zones, from
    the same lane's own real trimmed-far-end position
    (``Lane.centerline[-1]``) that ``lane_topology.py`` already computes
    by trimming a lane short of its destination node's real
    ``compute_node_clearance`` boundary -- i.e. the real physical stop
    line a vehicle queues behind when its own approach direction doesn't
    have the right of way (see ``actor_placement.py``'s vehicle
    placement). ``position`` (the lane's near/start end) remains a
    driving zone's normal, flowing-traffic spawn point; this is a
    second, distinct point on the same lane, not a replacement.
    """

    spawn_zone_id: int
    zone_type: SpawnZoneType
    position: npt.NDArray[np.float64]
    edge_id: Optional[int] = None
    heading_rad: Optional[float] = None
    node_id: Optional[int] = None
    stop_line_position: Optional[npt.NDArray[np.float64]] = None

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
            place one driving spawn zone per lane and pedestrian spawn
            zones tiled along each edge's sidewalk (offset beyond the
            outermost lane).

        Returns
        -------
        TrafficNetwork
        """
        traffic_controls = self._assign_traffic_controls(nodes)
        spawn_zones = self._generate_spawn_zones(edges, lanes)
        spawn_zones += self._generate_crossing_zones(nodes, edges)
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

    def _generate_spawn_zones(  # pylint: disable=too-many-locals
        self, edges: Dict[int, RoadEdge], lanes: Dict[int, Lane]
    ) -> List[SpawnZone]:
        """One driving spawn zone at the start of every lane, plus
        pedestrian spawn zones tiled along each edge's sidewalk at the
        real ``PEDESTRIAN_SPAWN_GAP_METERS`` interval (see that
        constant's own docstring) -- not just one fixed slot per edge,
        so a real sidewalk can hold a variable number of people spread
        along its length, matching how City Sample's own crowd system
        generates candidate points.

        Tiling stops short of each end node by that node's own
        ``compute_node_clearance`` value (clamped the same way
        ``LaneTopologyGenerator`` already clamps it,
        ``MAX_TRIM_FRACTION_OF_EDGE_LENGTH``) -- the same real quantity
        that already trims lane geometry short of intersections. Without
        this, a real bug (found live): ``sidewalk_start`` is already
        anchored at the lane's own trimmed start (``left_boundary[0]``),
        but tiling out to the untrimmed ``edge_length`` walks past the
        real trimmed sidewalk's far end, landing candidate points inside
        the intersection's own paved box/crosswalk area -- i.e.
        pedestrians appearing to stand in the road at an intersection,
        not on a sidewalk."""
        spawn_zones: List[SpawnZone] = []

        for lane in lanes.values():
            spawn_zones.append(
                SpawnZone(
                    spawn_zone_id=self._spawn_zone_counter,
                    zone_type=SpawnZoneType.DRIVING,
                    position=lane.centerline[0].copy(),
                    edge_id=lane.edge_id,
                    stop_line_position=lane.centerline[-1].copy(),
                )
            )
            self._spawn_zone_counter += 1

        lanes_by_edge: Dict[int, List[Lane]] = {}
        for lane in lanes.values():
            lanes_by_edge.setdefault(lane.edge_id, []).append(lane)

        node_clearance = compute_node_clearance(edges)

        for edge_id, edge_lanes in lanes_by_edge.items():
            outermost_lane = max(edge_lanes, key=lambda lane: lane.lane_index)
            edge = edges[edge_id]
            direction = edge.centerline[-1] - edge.centerline[0]
            edge_length = float(np.linalg.norm(direction))
            if edge_length < 1e-9:
                continue
            unit_direction = direction / edge_length
            perp = compute_perpendicular(direction)
            sidewalk_start = outermost_lane.left_boundary[0] + perp * SIDEWALK_OFFSET_METERS

            max_trim_each_side = edge_length * MAX_TRIM_FRACTION_OF_EDGE_LENGTH
            start_trim = min(node_clearance.get(edge.start_node_id, 0.0), max_trim_each_side)
            end_trim = min(node_clearance.get(edge.end_node_id, 0.0), max_trim_each_side)
            usable_length = edge_length - start_trim - end_trim
            if usable_length < 1e-9:
                continue

            num_points = int(usable_length // PEDESTRIAN_SPAWN_GAP_METERS) + 1
            for point_index in range(num_points):
                pedestrian_position = sidewalk_start + unit_direction * (
                    point_index * PEDESTRIAN_SPAWN_GAP_METERS
                )
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

    def _generate_crossing_zones(
        self, nodes: Dict[int, RoadNode], edges: Dict[int, RoadEdge]
    ) -> List[SpawnZone]:
        """Pedestrian spawn zones tiled across the real width of every
        real crosswalk (see ``crosswalks.compute_crosswalk_anchors``),
        at the same real ``PEDESTRIAN_SPAWN_GAP_METERS`` interval used
        along sidewalks -- so a real generated scenario can show people
        actually crossing a road, not just standing on its sidewalks."""
        spawn_zones: List[SpawnZone] = []
        for anchor in compute_crosswalk_anchors(nodes, edges):
            heading_rad = math.atan2(float(anchor.perp[1]), float(anchor.perp[0]))
            num_points = max(1, round(anchor.road_width_m / PEDESTRIAN_SPAWN_GAP_METERS))
            pitch_m = anchor.road_width_m / num_points
            for point_index in range(num_points):
                offset_m = -anchor.road_width_m / 2.0 + pitch_m * (point_index + 0.5)
                spawn_zones.append(
                    SpawnZone(
                        spawn_zone_id=self._spawn_zone_counter,
                        zone_type=SpawnZoneType.CROSSING,
                        position=anchor.pivot + anchor.perp * offset_m,
                        heading_rad=heading_rad,
                        node_id=anchor.node_id,
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
