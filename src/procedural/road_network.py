"""Procedural road network generation via an orthogonal grid.

Implements MASTER_PROMPT Section 3.2: road networks are modeled as Planar
Straight-Line Graphs (PSLG) — vertices are intersection nodes, edges are road
segments, and the graph is planar (no crossing edges except at intersections)
and connected.

Straight roads, square (90-degree) intersections only, by deliberate
choice: every node connects only to its immediate grid neighbors (one
step in +x/-x/+y/-y), so every intersection is a clean axis-aligned
crossing. This replaced an earlier perturbed-grid + Delaunay-
triangulation approach (still visible in git history) that produced
organic, arbitrary-angle streets, including diagonal/off-grid roads and
acute-angle intersections. That approach was scrapped because
acute-angle intersections have no exact fix for lane-mesh self-overlap
short of a full angle-aware miter computation (see
KNOWN_GAPS_AND_ISSUES.md's lane-overlap entries for the real, measured
z-fighting this caused when rendered in UE5) -- square intersections
make the existing per-node lane-trim fix (see lane_topology.py) exact
instead of a partial mitigation, at the cost of losing organic street
variety. Diagonal roads may be added back later as an explicit,
additional connection strategy layered on top of this grid, not a
revival of the old point-cloud/Delaunay approach.

Deviations from the master prompt's reference implementation (see
KNOWN_GAPS_AND_ISSUES.md for the full rationale of each):

1. Uses ``numpy.random.Generator`` (PCG64, seeded via ``SeedSequence``)
   instead of the legacy ``numpy.random.RandomState``. ``RandomState`` only
   accepts seeds in ``[0, 2**32 - 1]``, but the master prompt's own test
   suite (Section 3.2.2, ``test_seed_coverage_edge_cases``) requires
   ``seed=2**63-1`` to work. ``Generator`` supports arbitrary-size integer
   seeds while remaining fully deterministic for a fixed seed.
2. ``RoadNode``/``RoadEdge`` dataclasses use ``eq=False``. The default
   dataclass ``__eq__`` compares every field with ``==``, which raises
   ``ValueError`` on the ``position``/``centerline`` ``numpy.ndarray``
   fields ("truth value of an array is ambiguous"). Identity is via
   ``node_id``/``edge_id`` and ``__hash__`` only; no code path needs
   value-equality on these objects.
3. ``RoadEdge.reverse_edge_id`` is typed ``Optional[int]`` (the master
   prompt's snippet types it ``int`` with a ``None`` default, which fails
   ``mypy --strict``).
"""

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Set, Tuple

import numpy as np
import numpy.typing as npt

from src.procedural.scenario import ScenarioTypeConfig

# Constants (immutable, globally defined). See MASTER_PROMPT Section 3.2.1.
MAX_ROAD_LENGTH_METERS = 500.0

# Every road has this many lanes per direction, regardless of hierarchy
# (residential/minor/major) -- deliberately pinned rather than sampled,
# so every road in a scenario renders at the same physical width (see
# lane_topology.py: visual pavement width is num_lanes * LANE_WIDTH_METERS,
# so a varying lane count directly produces visually inconsistent road
# widths, confirmed as a real dogfooding finding, not a hypothetical --
# see KNOWN_GAPS_AND_ISSUES.md). Road hierarchy still varies via
# road_type/speed_limit_kmh; only lane count (and therefore width) is
# fixed at this stage of the project. Revisit once uneven road widths are
# an intentional feature rather than a visual inconsistency to eliminate.
UNIFORM_LANE_COUNT = 2


class RoadType(str, Enum):
    """Road hierarchy."""

    HIGHWAY = "highway"
    MAJOR = "major_arterial"
    MINOR = "minor_street"
    RESIDENTIAL = "residential"
    ALLEY = "alley"


class IntersectionType(str, Enum):
    """Intersection topology, derived from node degree."""

    ISOLATED = "isolated"
    T_JUNCTION = "t_junction"
    FOUR_WAY = "four_way"
    ROUNDABOUT = "roundabout"
    MERGE = "merge"


@dataclass(eq=False)
class RoadNode:  # pylint: disable=too-many-instance-attributes
    """Vertex in the road network graph.

    A plain data container mirroring MASTER_PROMPT Section 3.2.1's schema;
    the attribute count reflects the domain (position, type, adjacency,
    traffic control), not a design smell to refactor away.
    """

    node_id: int
    position: npt.NDArray[np.float64]
    node_type: IntersectionType
    elevation: float = 0.0

    incoming_edges: Set[int] = field(default_factory=set)
    outgoing_edges: Set[int] = field(default_factory=set)

    traffic_light: bool = False
    stop_sign: bool = False

    def __hash__(self) -> int:
        return hash(self.node_id)


@dataclass(eq=False)
class RoadEdge:  # pylint: disable=too-many-instance-attributes
    """Directed edge in the road network (one direction of a road segment).

    A plain data container mirroring MASTER_PROMPT Section 3.2.1's schema;
    see RoadNode's docstring for the same rationale on attribute count.
    """

    edge_id: int
    start_node_id: int
    end_node_id: int
    road_type: RoadType

    centerline: npt.NDArray[np.float64]
    length: float

    num_lanes: int
    speed_limit_kmh: int
    width_meters: float

    allows_turning_left: bool = True
    allows_turning_right: bool = True

    reverse_edge_id: Optional[int] = None

    def __hash__(self) -> int:
        return hash(self.edge_id)


class RoadNetworkGenerator:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Generate procedural road networks using PSLG theory.

    Exposes a single public entry point (``generate``) by design; the rest
    of the class is private implementation detail of that one operation.

    Notes
    -----
    Time complexity: O(N) in the number of grid points (node/edge creation
    plus one connection check per grid-adjacent pair). Space complexity:
    O(N) for node/edge storage.
    """

    def __init__(self, seed: int, config: ScenarioTypeConfig) -> None:
        """
        Parameters
        ----------
        seed : int
            Arbitrary-size non-negative integer seed for reproducibility.
        config : ScenarioTypeConfig
            Configuration defining network properties (block size range,
            etc.).
        """
        self.seed = seed
        self.config = config
        self.rng = np.random.Generator(np.random.PCG64(seed))

        self._node_counter = 0
        self._edge_counter = 0
        self._nodes: Dict[int, RoadNode] = {}
        self._edges: Dict[int, RoadEdge] = {}
        self._grid_node_ids: npt.NDArray[np.int64] = np.empty((0, 0), dtype=np.int64)

    def generate(
        self, bounds: Tuple[float, float, float, float]
    ) -> Tuple[Dict[int, RoadNode], Dict[int, RoadEdge]]:
        """Generate a complete, validated road network.

        Parameters
        ----------
        bounds : Tuple[float, float, float, float]
            (x_min, y_min, x_max, y_max) in meters.

        Returns
        -------
        nodes, edges : Tuple[Dict[int, RoadNode], Dict[int, RoadEdge]]
            Fully connected road graph.

        Raises
        ------
        ValueError
            If the generated network fails topological validation.
        """
        x_coords, y_coords = self._generate_grid_axes(bounds)
        self._create_grid_nodes(x_coords, y_coords)
        self._connect_grid_nodes()
        self._assign_road_attributes()
        self._validate_network()

        return self._nodes, self._edges

    def _generate_grid_axes(
        self, bounds: Tuple[float, float, float, float]
    ) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """Generate the x and y coordinate lines of a regular grid spanning
        ``bounds`` exactly (both axes always include their own ``lo`` and
        ``hi`` endpoint, unlike a plain ``arange`` which can overshoot),
        with ``spacing ~ U(min_block, max_block)`` between interior lines.

        The final interval on either axis may be shorter than ``spacing``
        (to land exactly on the ``hi`` endpoint without overshoot) rather
        than reflected/clipped -- there is no Delaunay triangulation left
        to protect from collinear/degenerate input, so there is no reason
        to distort point spacing to avoid it.
        """
        x_min, y_min, x_max, y_max = bounds
        spacing = self.rng.uniform(
            self.config.avg_block_size[0],
            self.config.avg_block_size[1],
        )
        return self._axis_coords(x_min, x_max, spacing), self._axis_coords(y_min, y_max, spacing)

    @staticmethod
    def _axis_coords(lo: float, hi: float, spacing: float) -> npt.NDArray[np.float64]:
        """Coordinate line from ``lo`` to ``hi`` inclusive, divided into
        equal-width intervals as close to ``spacing`` as an integer
        interval count allows. Degenerates to a single point ``[lo]``
        when ``hi <= lo`` (zero/negative-width axis).

        Real bug fixed here (found via dogfooding -- see
        KNOWN_GAPS_AND_ISSUES.md): the previous implementation
        (``np.arange(lo, hi, spacing)`` plus an appended ``hi``) let the
        final interval be whatever was left over after fitting as many
        full-``spacing`` steps as possible, which could be far shorter
        than every other interval on the axis -- in the worst case,
        arbitrarily close to zero. Visually this
        produced two adjacent same-direction roads separated by a razor-
        thin strip of buildings, which doesn't happen in a real street
        grid. Quantizing to the nearest whole number of equal intervals
        instead guarantees every block on a given axis is the same
        width -- still randomized scenario-to-scenario (``spacing`` is
        sampled per scenario within ``config.avg_block_size``), just
        internally consistent within one scenario's grid.
        """
        if hi <= lo:
            return np.array([lo], dtype=np.float64)

        num_intervals = max(1, round((hi - lo) / spacing))
        return np.linspace(lo, hi, num_intervals + 1)

    def _create_grid_nodes(
        self, x_coords: npt.NDArray[np.float64], y_coords: npt.NDArray[np.float64]
    ) -> None:
        """Create one ``RoadNode`` per (x, y) grid coordinate pair, and
        record each one's (row, col) grid position in ``_grid_node_ids``
        for ``_connect_grid_nodes`` to look up orthogonal neighbors by
        index rather than by nearest-neighbor search."""
        self._grid_node_ids = np.empty((len(y_coords), len(x_coords)), dtype=np.int64)
        for row, y in enumerate(y_coords):
            for col, x in enumerate(x_coords):
                node_id = self._node_counter
                self._nodes[node_id] = RoadNode(
                    node_id=node_id,
                    position=np.array([x, y], dtype=np.float64),
                    node_type=IntersectionType.ISOLATED,
                )
                self._grid_node_ids[row, col] = node_id
                self._node_counter += 1

    def _connect_grid_nodes(self) -> None:
        """Connect every node to its immediate right (+x) and below (+y)
        grid neighbor only -- straight roads, square intersections, by
        design (see module docstring)."""
        num_rows, num_cols = self._grid_node_ids.shape
        for row in range(num_rows):
            for col in range(num_cols):
                node_id = int(self._grid_node_ids[row, col])
                if col + 1 < num_cols:
                    self._connect_if_within_max_length(
                        node_id, int(self._grid_node_ids[row, col + 1])
                    )
                if row + 1 < num_rows:
                    self._connect_if_within_max_length(
                        node_id, int(self._grid_node_ids[row + 1, col])
                    )

    def _connect_if_within_max_length(self, node_id1: int, node_id2: int) -> None:
        """Create a bidirectional edge pair between two nodes, unless doing
        so would exceed ``MAX_ROAD_LENGTH_METERS``."""
        pos1 = self._nodes[node_id1].position
        pos2 = self._nodes[node_id2].position
        length = float(np.linalg.norm(pos2 - pos1))

        if length <= MAX_ROAD_LENGTH_METERS:
            self._create_edge_pair(node_id1, node_id2, length)

    def _create_edge_pair(self, node_id1: int, node_id2: int, length: float) -> None:
        """Create a bidirectional pair of directed ``RoadEdge`` objects."""
        edge_fwd_id = self._edge_counter
        edge_fwd = RoadEdge(
            edge_id=edge_fwd_id,
            start_node_id=node_id1,
            end_node_id=node_id2,
            road_type=RoadType.MAJOR,
            centerline=np.array([self._nodes[node_id1].position, self._nodes[node_id2].position]),
            length=length,
            num_lanes=2,
            speed_limit_kmh=50,
            width_meters=self.config.avg_road_width,
        )
        self._edges[edge_fwd_id] = edge_fwd
        self._edge_counter += 1

        edge_rev_id = self._edge_counter
        edge_rev = RoadEdge(
            edge_id=edge_rev_id,
            start_node_id=node_id2,
            end_node_id=node_id1,
            road_type=RoadType.MAJOR,
            centerline=np.flip(edge_fwd.centerline, axis=0),
            length=length,
            num_lanes=2,
            speed_limit_kmh=50,
            width_meters=self.config.avg_road_width,
            reverse_edge_id=edge_fwd_id,
        )
        self._edges[edge_rev_id] = edge_rev
        self._edge_counter += 1

        edge_fwd.reverse_edge_id = edge_rev_id
        self._nodes[node_id1].outgoing_edges.add(edge_fwd_id)
        self._nodes[node_id2].incoming_edges.add(edge_fwd_id)
        self._nodes[node_id2].outgoing_edges.add(edge_rev_id)
        self._nodes[node_id1].incoming_edges.add(edge_rev_id)

    def _assign_road_attributes(self) -> None:
        """Assign road type, lane count, and speed limit from topology.

        Heuristic (MASTER_PROMPT Section 3.2.1), classified by **road
        connection count** (number of distinct roads meeting at a node):
        0 -> isolated, 1-2 -> pass-through (kept ``ISOLATED`` per the master
        prompt's own classification, despite the misleading name — see
        KNOWN_GAPS_AND_ISSUES.md), 3 -> T-junction, >=4 -> four-way.

        Note: connection count is ``degree // 2``, not raw directed-edge
        degree. Every road is always created as a bidirectional edge pair
        (``_create_edge_pair``), so ``incoming_edges + outgoing_edges`` is
        always even and counts *directed edge slots*, not roads: a true
        3-way intersection has degree 6, not 3. The master prompt's
        reference implementation compares this raw degree directly against
        3 and 4, which is unreachable/miscategorizing (see
        KNOWN_GAPS_AND_ISSUES.md for the full analysis) — fixed here by
        halving before classifying.

        Edge length: <100m -> RESIDENTIAL, 100-300m -> MINOR/MAJOR depending
        on the start node's connection count, >300m -> MAJOR.

        Attributes are computed once per undirected road and applied
        identically to both directed edges of a bidirectional pair. The
        master prompt's reference implementation samples ``num_lanes``
        independently per directed edge, which QOL_RESEARCH_CHECKLIST.md
        Section G.1's own ``test_lane_count_consistent`` explicitly flags
        as wrong (forward/reverse should match) -- confirmed as a real
        bug, not hypothetical: 76 of 118 edges in a routine test scenario
        had mismatched forward/reverse lane counts before this fix. See
        KNOWN_GAPS_AND_ISSUES.md.

        ``num_lanes`` is now always ``UNIFORM_LANE_COUNT`` (see that
        constant's own docstring) rather than sampled per road hierarchy
        -- a deliberate simplification, not a forgotten TODO.
        """
        node_connection_counts = {
            nid: (len(node.incoming_edges) + len(node.outgoing_edges)) // 2
            for nid, node in self._nodes.items()
        }

        for nid, connections in node_connection_counts.items():
            if connections <= 2:
                self._nodes[nid].node_type = IntersectionType.ISOLATED
            elif connections == 3:
                self._nodes[nid].node_type = IntersectionType.T_JUNCTION
            else:
                self._nodes[nid].node_type = IntersectionType.FOUR_WAY

        processed_edge_ids: Set[int] = set()
        for edge in self._edges.values():
            if edge.edge_id in processed_edge_ids:
                continue

            start_connections = node_connection_counts[edge.start_node_id]

            if edge.length < 100:
                road_type = RoadType.RESIDENTIAL
                speed_limit_kmh = 30
            elif edge.length < 300:
                if start_connections >= 3:
                    road_type = RoadType.MAJOR
                    speed_limit_kmh = 50
                else:
                    road_type = RoadType.MINOR
                    speed_limit_kmh = 40
            else:
                road_type = RoadType.MAJOR
                speed_limit_kmh = 60

            edge.road_type = road_type
            edge.num_lanes = UNIFORM_LANE_COUNT
            edge.speed_limit_kmh = speed_limit_kmh
            processed_edge_ids.add(edge.edge_id)

            if edge.reverse_edge_id is not None:
                reverse_edge = self._edges[edge.reverse_edge_id]
                reverse_edge.road_type = road_type
                reverse_edge.num_lanes = UNIFORM_LANE_COUNT
                reverse_edge.speed_limit_kmh = speed_limit_kmh
                processed_edge_ids.add(reverse_edge.edge_id)

    def _validate_network(self) -> None:
        """Validate connectivity, referential consistency, and node degree.

        Raises
        ------
        ValueError
            If the network is empty, disconnected, references a missing
            node, has a non-positive-length edge, or has an isolated
            (degree-0) node.
        """
        if not self._nodes:
            raise ValueError("No nodes in road network")

        start_node = next(iter(self._nodes.keys()))
        reachable = self._bfs_reachable(start_node)

        if len(reachable) < len(self._nodes):
            unreachable = set(self._nodes.keys()) - reachable
            raise ValueError(f"Network not connected. Unreachable nodes: {unreachable}")

        for edge_id, edge in self._edges.items():
            if edge.start_node_id not in self._nodes:
                raise ValueError(f"Edge {edge_id}: start node {edge.start_node_id} not found")
            if edge.end_node_id not in self._nodes:
                raise ValueError(f"Edge {edge_id}: end node {edge.end_node_id} not found")
            if edge.length <= 0:
                raise ValueError(f"Edge {edge_id}: invalid length {edge.length}")

        for node_id, node in self._nodes.items():
            degree = len(node.incoming_edges) + len(node.outgoing_edges)
            if degree == 0:
                raise ValueError(f"Node {node_id}: isolated node")

    def _bfs_reachable(self, start_node_id: int) -> Set[int]:
        """Breadth-first search returning all node IDs reachable from
        ``start_node_id`` by following outgoing edges."""
        visited = {start_node_id}
        queue = deque([start_node_id])

        while queue:
            node_id = queue.popleft()
            node = self._nodes[node_id]

            for edge_id in node.outgoing_edges:
                next_node_id = self._edges[edge_id].end_node_id
                if next_node_id not in visited:
                    visited.add(next_node_id)
                    queue.append(next_node_id)

        return visited
