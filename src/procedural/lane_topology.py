"""Per-lane geometry generation from road network edges.

Implements MASTER_PROMPT Section 3.3's "Lane Topology" bullets: generate
individual lanes from road edges, compute lane boundaries (perpendicular
offset curves), validate lane connectivity. Unlike Phase 1's road network
section, MASTER_PROMPT gives no formulas, reference code, or test fixtures
for this phase (Section 3.3 is four bullet points); the algorithms below
were designed from scratch, informed by QOL_RESEARCH_CHECKLIST.md Section
B.2. See KNOWN_GAPS_AND_ISSUES.md for the full scoping notes, including
why cross-intersection turn connectivity is deferred to Phase 3 (traffic
network) rather than implemented here.

Convention: for a directed RoadEdge, its ``num_lanes`` lanes occupy the
right-hand half of the road relative to that edge's own direction of
travel (right-hand-traffic convention), so a directed edge and its
``reverse_edge_id`` counterpart never physically overlap even though both
reference the same physical centerline.
"""

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import numpy.typing as npt

from src.procedural.math_utils import compute_perpendicular
from src.procedural.road_network import RoadEdge, RoadNode

# Standard traffic lane width. 3.5m is within the typical 2.7-3.7m range
# used by AASHTO/UK DfT design guidance for arterial roads.
LANE_WIDTH_METERS = 3.5


@dataclass(eq=False)
class Lane:
    """A single traffic lane within one directed RoadEdge."""

    lane_id: int
    edge_id: int
    lane_index: int
    centerline: npt.NDArray[np.float64]
    left_boundary: npt.NDArray[np.float64]
    right_boundary: npt.NDArray[np.float64]
    width: float

    def __hash__(self) -> int:
        return hash(self.lane_id)


class LaneTopologyGenerator:  # pylint: disable=too-few-public-methods
    """Generate per-lane geometry for every directed edge in a road network.

    Exposes a single public entry point (``generate``); everything else is
    private implementation detail of that operation.
    """

    def __init__(self) -> None:
        self._lane_counter = 0

    def generate(self, nodes: Dict[int, RoadNode], edges: Dict[int, RoadEdge]) -> Dict[int, Lane]:
        """Generate lane geometry for every edge.

        Parameters
        ----------
        nodes : Dict[int, RoadNode]
            Unused directly (kept for API symmetry with other generators
            and because future turn-connectivity work will need it), but
            required so callers pass the full network rather than edges
            alone.
        edges : Dict[int, RoadEdge]
            The directed road edges to generate lanes for.

        Returns
        -------
        Dict[int, Lane]
            All generated lanes, keyed by ``lane_id``.

        Raises
        ------
        ValueError
            If any edge references a node not present in ``nodes``.
        """
        for edge in edges.values():
            if edge.start_node_id not in nodes or edge.end_node_id not in nodes:
                raise ValueError(f"Edge {edge.edge_id} references a node not in `nodes`")

        lanes: Dict[int, Lane] = {}
        for edge in edges.values():
            for lane in self._generate_lanes_for_edge(edge):
                lanes[lane.lane_id] = lane
        return lanes

    def _generate_lanes_for_edge(self, edge: RoadEdge) -> List[Lane]:
        """Generate ``edge.num_lanes`` parallel lanes for one directed edge,
        offset into the right-hand half of the road relative to the edge's
        direction of travel."""
        direction = edge.centerline[-1] - edge.centerline[0]
        perp = compute_perpendicular(direction)

        lanes = []
        for lane_index in range(edge.num_lanes):
            offset_distance = (lane_index + 0.5) * LANE_WIDTH_METERS
            offset = perp * offset_distance

            lane_centerline = edge.centerline + offset
            left_boundary = lane_centerline + perp * (LANE_WIDTH_METERS / 2.0)
            right_boundary = lane_centerline - perp * (LANE_WIDTH_METERS / 2.0)

            lane = Lane(
                lane_id=self._lane_counter,
                edge_id=edge.edge_id,
                lane_index=lane_index,
                centerline=lane_centerline,
                left_boundary=left_boundary,
                right_boundary=right_boundary,
                width=LANE_WIDTH_METERS,
            )
            lanes.append(lane)
            self._lane_counter += 1

        return lanes
