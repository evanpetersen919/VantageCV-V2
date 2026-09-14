"""Procedural road network generation via perturbed-grid + Delaunay filtering.

Implements MASTER_PROMPT Section 3.2: road networks are modeled as Planar
Straight-Line Graphs (PSLG) — vertices are intersection nodes, edges are road
segments, and the graph is planar (no crossing edges except at intersections)
and connected.

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
from scipy.spatial import Delaunay, QhullError  # pylint: disable=no-name-in-module

from src.procedural.scenario import ScenarioTypeConfig

# QhullError is exported dynamically by scipy.spatial (confirmed at runtime,
# scipy 1.11.4); pylint's static analysis of the compiled extension module
# can't see it.


# Constants (immutable, globally defined). See MASTER_PROMPT Section 3.2.1.
MAX_ROAD_LENGTH_METERS = 500.0
MIN_INTERSECTION_DISTANCE_METERS = 10.0
GRID_PERTURBATION_RATIO = 0.15

# Tolerance rationale: 1e-6 m is smaller than GPS precision (0.01 m) and
# smaller than any road-scale quantity of interest; safe for geometric
# equality checks. See QOL_RESEARCH_CHECKLIST.md Section A.1.
POSITION_TOLERANCE = 1e-6


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


class RoadNetworkGenerator:  # pylint: disable=too-few-public-methods
    """Generate procedural road networks using PSLG theory.

    Exposes a single public entry point (``generate``) by design; the rest
    of the class is private implementation detail of that one operation.

    Notes
    -----
    Time complexity: O(N log N) dominated by Delaunay triangulation, where N
    is the number of grid points. Space complexity: O(N) for node/edge
    storage.
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
        grid_points = self._generate_grid_points(bounds)
        perturbed_points = self._perturb_grid(grid_points)
        contained_points = self._keep_within_bounds(perturbed_points, bounds)
        self._create_nodes_from_points(contained_points)
        self._connect_nodes()
        self._assign_road_attributes()
        self._validate_network()

        return self._nodes, self._edges

    def _generate_grid_points(
        self, bounds: Tuple[float, float, float, float]
    ) -> npt.NDArray[np.float64]:
        """Generate a regular grid of points spanning ``bounds``.

        Mathematical formula::

            x_i = x_min + i * spacing, for i in {0, ..., num_x}
            y_j = y_min + j * spacing, for j in {0, ..., num_y}

        where ``spacing ~ U(min_block, max_block)``.
        """
        x_min, y_min, x_max, y_max = bounds

        spacing = self.rng.uniform(
            self.config.avg_block_size[0],
            self.config.avg_block_size[1],
        )

        x_coords = np.arange(x_min, x_max + spacing, spacing)
        y_coords = np.arange(y_min, y_max + spacing, spacing)

        xx, yy = np.meshgrid(x_coords, y_coords)
        grid_points = np.column_stack((xx.ravel(), yy.ravel()))

        return grid_points

    def _perturb_grid(self, grid_points: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Add Gaussian perturbation to grid points.

        Mathematical formula::

            p'_i = p_i + N(0, sigma^2 * I)
            sigma = GRID_PERTURBATION_RATIO * spacing

        Purpose: remove artificial regularity, create an organic street
        layout.
        """
        if len(grid_points) < 2:
            return grid_points

        dists = np.linalg.norm(np.diff(grid_points, axis=0), axis=1)
        avg_spacing = np.median(dists)

        sigma = GRID_PERTURBATION_RATIO * avg_spacing

        perturbation = self.rng.normal(0, sigma, grid_points.shape)
        perturbed_points = grid_points + perturbation

        return perturbed_points

    @staticmethod
    def _keep_within_bounds(
        points: npt.NDArray[np.float64], bounds: Tuple[float, float, float, float]
    ) -> npt.NDArray[np.float64]:
        """Fold any point that fell outside ``bounds`` back inside it by
        reflection at the violated edge(s), falling back to a hard clip
        for the rare case reflection alone doesn't suffice.

        Both grid generation (``_generate_grid_points`` can overshoot by
        up to one full ``spacing`` per axis by construction -- see
        KNOWN_GAPS_AND_ISSUES.md) and Gaussian perturbation
        (``_perturb_grid``) can push a point outside the caller's declared
        ``bounds``. This was never checked or corrected before
        ScenarioValidator's bounds-containment check caught it on a real
        generated scenario: e.g. a node at (-271.6, -234.4) with
        bounds=(-250, -250, 250, 250).

        Reflection ("bounce back off the wall"), not a hard clip, is used
        because a hard clip collapses every overshooting point on the
        same side onto one exact boundary line -- for 3+ points that is
        an *exactly collinear* configuration, which crashes Delaunay
        triangulation in ``_connect_nodes`` (a real, previously
        established failure mode -- see
        test_collinear_points_raise_value_error_not_qhull_error).
        Reflection preserves each point's relative offset, so
        overshooting points stay spread out rather than collapsing onto a
        line. The final ``np.clip`` is a safety net only, for the
        practically-unreachable case where a single reflection isn't
        enough to bring a point back in range.
        """
        x_min, y_min, x_max, y_max = bounds
        reflected = points.copy()

        for axis, (lo, hi) in enumerate(((x_min, x_max), (y_min, y_max))):
            below = reflected[:, axis] < lo
            reflected[below, axis] = lo + (lo - reflected[below, axis])
            above = reflected[:, axis] > hi
            reflected[above, axis] = hi - (reflected[above, axis] - hi)

        reflected[:, 0] = np.clip(reflected[:, 0], x_min, x_max)
        reflected[:, 1] = np.clip(reflected[:, 1], y_min, y_max)

        return reflected

    def _create_nodes_from_points(self, points: npt.NDArray[np.float64]) -> None:
        """Create ``RoadNode`` objects from a point cloud, merging points
        within ``MIN_INTERSECTION_DISTANCE_METERS`` of an existing node.
        """
        for point in points:
            self._find_or_create_node(point)

    def _find_or_create_node(self, position: npt.NDArray[np.float64]) -> int:
        """Find an existing node near ``position``, or create a new one.

        Uses linear search (O(N)); acceptable at the scenario sizes this
        generator targets (hundreds of nodes). A KDTree would reduce this
        to O(log N) if profiling in Phase 1 performance tests shows it's a
        bottleneck (see KNOWN_GAPS_AND_ISSUES.md).
        """
        for node_id, node in self._nodes.items():
            distance = np.linalg.norm(node.position - position)
            if distance < MIN_INTERSECTION_DISTANCE_METERS:
                return node_id

        node_id = self._node_counter
        self._nodes[node_id] = RoadNode(
            node_id=node_id,
            position=position.astype(np.float64),
            node_type=IntersectionType.ISOLATED,
        )
        self._node_counter += 1

        return node_id

    def _connect_nodes(self) -> None:
        """Connect nodes with edges using Delaunay triangulation.

        Delaunay triangulation maximizes the minimum angle across all
        triangles, giving a natural connectivity pattern for urban streets
        while guaranteeing planarity (triangle edges never cross).
        """
        if len(self._nodes) < 3:
            self._connect_small_network()
            return

        node_ids = sorted(self._nodes.keys())
        positions = np.array([self._nodes[nid].position for nid in node_ids])

        try:
            tri = Delaunay(positions)
        except QhullError as exc:
            raise ValueError(f"Delaunay triangulation failed: {exc}") from exc

        for idx1, idx2 in self._extract_triangulation_edges(tri):
            self._connect_if_within_max_length(node_ids[idx1], node_ids[idx2])

    def _connect_small_network(self) -> None:
        """Handle the 0/1/2-node case, where Delaunay triangulation (which
        requires >=3 non-collinear points) does not apply."""
        if len(self._nodes) != 2:
            return
        node_id1, node_id2 = sorted(self._nodes.keys())
        self._connect_if_within_max_length(node_id1, node_id2)

    @staticmethod
    def _extract_triangulation_edges(tri: Delaunay) -> Set[Tuple[int, int]]:
        """Extract the unique undirected edge set from a Delaunay
        triangulation's simplices, as (point_index, point_index) pairs."""
        edges_set: Set[Tuple[int, int]] = set()
        for triangle in tri.simplices:
            for i in range(3):
                p1, p2 = int(triangle[i]), int(triangle[(i + 1) % 3])
                edges_set.add((min(p1, p2), max(p1, p2)))
        return edges_set

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
                num_lanes = 2
                speed_limit_kmh = 30
            elif edge.length < 300:
                if start_connections >= 3:
                    road_type = RoadType.MAJOR
                    num_lanes = int(self.rng.choice([2, 3, 4]))
                    speed_limit_kmh = 50
                else:
                    road_type = RoadType.MINOR
                    num_lanes = 2
                    speed_limit_kmh = 40
            else:
                road_type = RoadType.MAJOR
                num_lanes = int(self.rng.choice([3, 4]))
                speed_limit_kmh = 60

            edge.road_type = road_type
            edge.num_lanes = num_lanes
            edge.speed_limit_kmh = speed_limit_kmh
            processed_edge_ids.add(edge.edge_id)

            if edge.reverse_edge_id is not None:
                reverse_edge = self._edges[edge.reverse_edge_id]
                reverse_edge.road_type = road_type
                reverse_edge.num_lanes = num_lanes
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
