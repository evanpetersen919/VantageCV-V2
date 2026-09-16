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

# A lane's own centerline/boundary is trimmed short of each endpoint node
# by this fraction of the edge's own length at most, so a lane on a very
# short edge (rare, but possible with a perturbed-grid layout) never gets
# trimmed to zero or negative length -- see _generate_lanes_for_edge.
MAX_TRIM_FRACTION_OF_EDGE_LENGTH = 0.4


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

        node_clearance = self._compute_node_clearance(edges)

        lanes: Dict[int, Lane] = {}
        for edge in edges.values():
            start_trim = node_clearance.get(edge.start_node_id, 0.0)
            end_trim = node_clearance.get(edge.end_node_id, 0.0)
            for lane in self._generate_lanes_for_edge(edge, start_trim, end_trim):
                lanes[lane.lane_id] = lane
        return lanes

    @staticmethod
    def _compute_node_clearance(edges: Dict[int, RoadEdge]) -> Dict[int, float]:
        """For each node, the physical half-width (in meters) of the
        widest road meeting there -- the widest of any incident edge's own
        ``num_lanes * LANE_WIDTH_METERS`` (each directed edge's lanes only
        occupy its own right-hand half of the road, per this module's own
        convention, so this is the true worst-case lane extent from the
        node's center in any direction).

        Used to trim every lane short of each node it touches, so lanes
        from different edges meeting at the same intersection don't run
        straight through each other's physical footprint -- found to be a
        real, large-scale problem via dogfooding (real generated
        scenarios showed ~38% of total scenario area covered by
        overlapping road geometry, concentrated almost entirely at
        intersections -- see KNOWN_GAPS_AND_ISSUES.md), not a
        hypothetical edge case.

        This is a real mitigation, not a proper mitered intersection
        surface: it shrinks every lane back far enough that overlap
        between DIFFERENT edges' lanes is eliminated in the vast
        majority of cases, but it does not generate an actual paved
        intersection surface filling the resulting gap -- there will be
        a visible unpaved gap at every intersection instead. A real
        intersection mesh is future work, not attempted here.
        """
        clearance: Dict[int, float] = {}
        for edge in edges.values():
            half_width = edge.num_lanes * LANE_WIDTH_METERS
            for node_id in (edge.start_node_id, edge.end_node_id):
                clearance[node_id] = max(clearance.get(node_id, 0.0), half_width)
        return clearance

    def _generate_lanes_for_edge(  # pylint: disable=too-many-locals
        self, edge: RoadEdge, start_trim: float, end_trim: float
    ) -> List[Lane]:
        """Generate ``edge.num_lanes`` parallel lanes for one directed edge,
        offset into the right-hand half of the road relative to the edge's
        direction of travel, with the centerline trimmed short of each
        endpoint by ``start_trim``/``end_trim`` (see
        ``_compute_node_clearance``) so lanes don't extend through the
        intersections at either end."""
        start, end = edge.centerline[0], edge.centerline[-1]
        direction = end - start
        edge_length = float(np.linalg.norm(direction))
        perp = compute_perpendicular(direction)

        if edge_length > 1e-9:
            unit_direction = direction / edge_length
            max_trim_each_side = edge_length * MAX_TRIM_FRACTION_OF_EDGE_LENGTH
            trimmed_start = start + unit_direction * min(start_trim, max_trim_each_side)
            trimmed_end = end - unit_direction * min(end_trim, max_trim_each_side)
        else:
            # Degenerate (zero-length) edge -- nothing meaningful to trim;
            # compute_perpendicular's own fallback already handles the
            # direction being undefined.
            trimmed_start, trimmed_end = start, end

        trimmed_centerline = np.array([trimmed_start, trimmed_end])

        lanes = []
        for lane_index in range(edge.num_lanes):
            offset_distance = (lane_index + 0.5) * LANE_WIDTH_METERS
            offset = perp * offset_distance

            lane_centerline = trimmed_centerline + offset
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
