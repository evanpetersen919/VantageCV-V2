"""Per-lane turn connectivity across intersections.

Closes a gap deferred twice already (see KNOWN_GAPS_AND_ISSUES.md):
Phase 2's `lane_topology.py` deferred cross-intersection turn
connectivity to Phase 3 (it needs traffic rules that didn't exist yet);
Phase 3's `traffic_network.py` deferred it again, to "whenever full
per-lane turn graphs are needed" -- this module is that. Nothing here
needed waiting on: turn connectivity is pure geometry (which directions
two edges meet at, `RoadNode.incoming_edges`/`outgoing_edges`) plus the
`RoadEdge.allows_turning_left`/`allows_turning_right` flags that have
existed, unused, since Phase 1.

Movement classification: at an intersection node, every (incoming edge,
outgoing edge) pair that isn't a U-turn (`outgoing_edge is incoming_edge
.reverse_edge_id`) is classified STRAIGHT/LEFT/RIGHT from the signed
angle between the incoming edge's final heading and the outgoing edge's
initial heading -- positive (counter-clockwise) is a left turn, negative
(clockwise) is a right turn, matching `math_utils.compute_perpendicular`'s
own right-hand-rotation convention for this codebase's coordinate frame.
LEFT/RIGHT movements are dropped if the incoming edge's own
``allows_turning_left``/``allows_turning_right`` flag forbids them;
STRAIGHT has no corresponding flag and is never restricted here.

Lane-level mapping (not just edge-level): `lane_topology.py`'s own
right-hand-traffic convention means an edge's lane 0 sits closest to the
road centerline (the "left"/median lane) and its highest-index lane sits
closest to the curb (the "right" lane) -- exactly the lanes a real
driver would use for a left or right turn respectively. So:

- STRAIGHT connects lanes index-for-index, up to the shorter edge's
  lane count (a defensible default absent any dedicated-turn-lane
  concept in this codebase -- see KNOWN_GAPS_AND_ISSUES.md).
- LEFT connects only the incoming edge's lane 0 to the outgoing edge's
  lane 0.
- RIGHT connects only the incoming edge's highest-index lane to the
  outgoing edge's highest-index lane.

Deliberately out of scope: this module produces a connectivity *graph*
(which lane can legally reach which other lane, and how), not vehicle
routing/path-following behavior -- `ActorPlacementGenerator` still places
vehicles statically at spawn zones; nothing here makes them move.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List

import numpy as np

from src.procedural.lane_topology import Lane
from src.procedural.road_network import RoadEdge, RoadNode

# Angle band (radians) within which a turn is classified STRAIGHT rather
# than LEFT/RIGHT. 30 degrees is a common traffic-engineering threshold
# for "through movement" classification at signalized intersections.
STRAIGHT_ANGLE_THRESHOLD_RAD = np.pi / 6


class TurnType(str, Enum):
    """Classification of one lane-to-lane movement through an intersection."""

    STRAIGHT = "straight"
    LEFT = "left"
    RIGHT = "right"


@dataclass(eq=False)
class LaneConnection:
    """One legal lane-to-lane movement through an intersection."""

    from_lane_id: int
    to_lane_id: int
    turn_type: TurnType


@dataclass(eq=False)
class LaneConnectivityGraph:
    """Every legal lane-to-lane movement in a scenario, indexed for
    lookup by originating lane."""

    connections: List[LaneConnection]
    _by_from_lane: Dict[int, List[LaneConnection]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._by_from_lane = {}
        for connection in self.connections:
            self._by_from_lane.setdefault(connection.from_lane_id, []).append(connection)

    def outgoing_from(self, lane_id: int) -> List[LaneConnection]:
        """Every legal movement out of ``lane_id``, or ``[]`` if it has none
        (e.g. a lane on an edge with no downstream intersection, or every
        movement out of it was disallowed/a U-turn)."""
        return self._by_from_lane.get(lane_id, [])


def _classify_turn(incoming_edge: RoadEdge, outgoing_edge: RoadEdge) -> TurnType:
    """Classify the movement from ``incoming_edge`` to ``outgoing_edge``
    by the signed angle between the incoming edge's final heading and the
    outgoing edge's initial heading."""
    incoming_direction = incoming_edge.centerline[-1] - incoming_edge.centerline[-2]
    outgoing_direction = outgoing_edge.centerline[1] - outgoing_edge.centerline[0]

    cross = (
        incoming_direction[0] * outgoing_direction[1]
        - incoming_direction[1] * outgoing_direction[0]
    )
    dot = (
        incoming_direction[0] * outgoing_direction[0]
        + incoming_direction[1] * outgoing_direction[1]
    )
    angle = float(np.arctan2(cross, dot))

    if abs(angle) < STRAIGHT_ANGLE_THRESHOLD_RAD:
        return TurnType.STRAIGHT
    return TurnType.LEFT if angle > 0 else TurnType.RIGHT


def _connect_lanes(
    incoming_lanes: List[Lane], outgoing_lanes: List[Lane], turn_type: TurnType
) -> List[LaneConnection]:
    """Build the lane-level connections for one classified movement --
    see this module's own docstring for the mapping per turn type."""
    if not incoming_lanes or not outgoing_lanes:
        return []

    if turn_type == TurnType.STRAIGHT:
        count = min(len(incoming_lanes), len(outgoing_lanes))
        return [
            LaneConnection(incoming_lanes[i].lane_id, outgoing_lanes[i].lane_id, turn_type)
            for i in range(count)
        ]

    from_lane = incoming_lanes[0] if turn_type == TurnType.LEFT else incoming_lanes[-1]
    to_lane = outgoing_lanes[0] if turn_type == TurnType.LEFT else outgoing_lanes[-1]
    return [LaneConnection(from_lane.lane_id, to_lane.lane_id, turn_type)]


class LaneConnectivityGenerator:  # pylint: disable=too-few-public-methods
    """Generate a LaneConnectivityGraph from an existing road network + lanes.

    Exposes a single public entry point (``generate``) by design; the
    rest of the class is private implementation detail of that operation.
    """

    def generate(
        self, nodes: Dict[int, RoadNode], edges: Dict[int, RoadEdge], lanes: Dict[int, Lane]
    ) -> LaneConnectivityGraph:
        """Compute every legal lane-to-lane movement at every intersection.

        Parameters
        ----------
        nodes : Dict[int, RoadNode]
            Provides each node's ``incoming_edges``/``outgoing_edges`` --
            the candidate movements to classify.
        edges : Dict[int, RoadEdge]
            The road network's directed edges.
        lanes : Dict[int, Lane]
            Per-edge lane geometry from ``LaneTopologyGenerator``.

        Returns
        -------
        LaneConnectivityGraph
        """
        lanes_by_edge: Dict[int, List[Lane]] = {}
        for lane in lanes.values():
            lanes_by_edge.setdefault(lane.edge_id, []).append(lane)
        for edge_lanes in lanes_by_edge.values():
            edge_lanes.sort(key=lambda lane: lane.lane_index)

        connections: List[LaneConnection] = []
        for node in nodes.values():
            for in_edge_id in node.incoming_edges:
                incoming_edge = edges[in_edge_id]
                for out_edge_id in node.outgoing_edges:
                    if out_edge_id == incoming_edge.reverse_edge_id:
                        continue  # no U-turns

                    outgoing_edge = edges[out_edge_id]
                    turn_type = _classify_turn(incoming_edge, outgoing_edge)

                    if turn_type == TurnType.LEFT and not incoming_edge.allows_turning_left:
                        continue
                    if turn_type == TurnType.RIGHT and not incoming_edge.allows_turning_right:
                        continue

                    connections.extend(
                        _connect_lanes(
                            lanes_by_edge.get(in_edge_id, []),
                            lanes_by_edge.get(out_edge_id, []),
                            turn_type,
                        )
                    )

        return LaneConnectivityGraph(connections=connections)
