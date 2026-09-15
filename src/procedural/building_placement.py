"""Procedural building placement within road-network city blocks.

Implements MASTER_PROMPT Section 3.3's "Building Placement" bullets:
identify city blocks, place buildings without overlaps, assign heights,
validate no road-building intersections. As with lane_topology.py,
MASTER_PROMPT gives no algorithm, formulas, or tests for this phase --
designed from scratch, informed by QOL_RESEARCH_CHECKLIST.md Section B.3.
See KNOWN_GAPS_AND_ISSUES.md for the block-identification simplification
this module makes (deliberate, and documented there).

Block identification: a general planar-graph face-finding algorithm (to
recover the actual bounded regions enclosed by roads) is a substantially
larger undertaking than anything else specified for this phase. Instead,
this module reuses the same Delaunay triangulation `RoadNetworkGenerator`
already computes internally: each triangle whose all three edges survived
length-filtering (i.e. still exist in the road graph) is treated as one
city block. This is an approximation -- real city blocks are often
quadrilateral-ish regions spanning multiple triangles -- but it is a
correct, non-overlapping partition of the scenario's interior, which is
what building placement actually needs.

Building type/material: MASTER_PROMPT Section 3.3 lists "assign building
types, heights, materials" but gives no taxonomy for either, and this
gap was deliberately left deferred until a mesh/material consumer
existed (see KNOWN_GAPS_AND_ISSUES.md) -- `mesh_factory.py` now is that
consumer. Type is derived from where a building's own sampled height
falls within `config.building_heights`'s own ``(min, max)`` range
(bottom third RESIDENTIAL, middle third MIXED_USE, top third
COMMERCIAL) rather than a fixed absolute threshold, since that range
varies enormously across scenario templates (a parking lot's tallest
building is shorter than urban_dense's shortest) -- a relative split is
the only classification that means the same thing across every scenario
type. Material is then sampled from that type's own plausible material
set.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Set, Tuple

import numpy as np
import numpy.typing as npt
from scipy.spatial import Delaunay, QhullError  # pylint: disable=no-name-in-module

from src.procedural.road_network import RoadEdge, RoadNode
from src.procedural.scenario import ScenarioTypeConfig

# Setback from a road's centerline within which no building may be placed,
# beyond the road's own half-width. Represents sidewalk + minimum clearance;
# a real value would come from config, but no such field exists in
# ScenarioTypeConfig (see KNOWN_GAPS_AND_ISSUES.md) so a fixed constant is
# used, matching real-world minimum sidewalk width guidance (~2m).
ROAD_SETBACK_METERS = 2.0

# Degenerate-triangle threshold: a candidate block below this area is
# treated as unusable (too thin/sliver to hold a building), not an error.
MIN_BLOCK_AREA_SQ_METERS = 25.0

# Building footprint aspect assumptions: width and depth are each sampled
# independently in this range, giving varied but plausible footprints.
BUILDING_FOOTPRINT_SIDE_METERS = (8.0, 25.0)

# Maximum placement attempts per candidate slot before giving up on that
# slot (keeps generation bounded even for a very dense config).
MAX_PLACEMENT_ATTEMPTS_PER_BLOCK = 50

# After this many consecutive slots each exhaust every attempt, treat the
# block as full and stop, rather than burning the remaining target_count
# slots at full attempt cost. See _place_buildings_in_block's docstring.
MAX_CONSECUTIVE_FULL_FAILURES = 5

# (segment start, segment end, padded AABB) -- see generate()'s docstring
# for why the padded AABB is precomputed once rather than per-candidate.
_PaddedSegment = Tuple[
    npt.NDArray[np.float64], npt.NDArray[np.float64], Tuple[float, float, float, float]
]


class BuildingType(str, Enum):
    """Coarse building-use taxonomy, classified by relative height within
    a scenario's own ``config.building_heights`` range -- see module
    docstring for why a relative (not absolute) split is used."""

    RESIDENTIAL = "residential"
    MIXED_USE = "mixed_use"
    COMMERCIAL = "commercial"


# Plausible exterior materials per building type, sampled uniformly per
# building. Not exhaustive real-world taxonomy -- a reasonable, varied
# default set with no rendering/material-authoring phase to validate
# against yet (see KNOWN_GAPS_AND_ISSUES.md's procedural-materials entry).
BUILDING_MATERIALS_BY_TYPE: Dict[BuildingType, Tuple[str, ...]] = {
    BuildingType.RESIDENTIAL: ("brick", "wood_siding", "stucco"),
    BuildingType.MIXED_USE: ("brick", "concrete", "glass_curtain_wall"),
    BuildingType.COMMERCIAL: ("glass_curtain_wall", "concrete", "metal_panel"),
}


def _classify_building_type(height: float, height_range: Tuple[float, float]) -> BuildingType:
    """Classify a building's type from where ``height`` falls within
    ``height_range`` (``config.building_heights``): bottom third
    RESIDENTIAL, middle third MIXED_USE, top third COMMERCIAL.

    A degenerate range (``min == max``, e.g. a scenario config with a
    single fixed height) has no meaningful relative position -- defaults
    to MIXED_USE, the taxonomy's own neutral middle category.
    """
    min_height, max_height = height_range
    span = max_height - min_height
    if span < 1e-9:
        return BuildingType.MIXED_USE

    relative_height = (height - min_height) / span
    if relative_height < 1.0 / 3.0:
        return BuildingType.RESIDENTIAL
    if relative_height < 2.0 / 3.0:
        return BuildingType.MIXED_USE
    return BuildingType.COMMERCIAL


@dataclass(eq=False)
class Building:
    """A single procedurally placed building footprint."""

    building_id: int
    center: npt.NDArray[np.float64]
    width: float
    depth: float
    height: float
    building_type: BuildingType = BuildingType.MIXED_USE
    material: str = "concrete"

    def __hash__(self) -> int:
        return hash(self.building_id)

    @property
    def aabb(self) -> Tuple[float, float, float, float]:
        """Axis-aligned bounding box as (x_min, y_min, x_max, y_max)."""
        x, y = self.center
        return (x - self.width / 2, y - self.depth / 2, x + self.width / 2, y + self.depth / 2)


def _padded_segment_aabb(
    seg_a: npt.NDArray[np.float64], seg_b: npt.NDArray[np.float64], padding: float
) -> Tuple[float, float, float, float]:
    """Axis-aligned bounding box of segment [seg_a, seg_b], expanded by
    ``padding`` on every side -- used as a cheap pre-filter before an
    exact point-segment distance check (see ``BuildingPlacementGenerator
    ._too_close_to_road``)."""
    x_min = float(min(seg_a[0], seg_b[0])) - padding
    x_max = float(max(seg_a[0], seg_b[0])) + padding
    y_min = float(min(seg_a[1], seg_b[1])) - padding
    y_max = float(max(seg_a[1], seg_b[1])) + padding
    return (x_min, y_min, x_max, y_max)


def _aabb_overlap(
    a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]
) -> bool:
    """True if two (x_min, y_min, x_max, y_max) boxes overlap."""
    a_x_min, a_y_min, a_x_max, a_y_max = a
    b_x_min, b_y_min, b_x_max, b_y_max = b
    return a_x_min < b_x_max and a_x_max > b_x_min and a_y_min < b_y_max and a_y_max > b_y_min


def _segment_intersects_aabb(  # pylint: disable=too-many-locals
    seg_a: npt.NDArray[np.float64],
    seg_b: npt.NDArray[np.float64],
    aabb: Tuple[float, float, float, float],
) -> bool:
    """True if segment [seg_a, seg_b] intersects axis-aligned box `aabb`.

    Slab method (parametric clipping): the segment is point(t) = seg_a +
    t * (seg_b - seg_a) for t in [0, 1]; each axis constrains the valid
    t-range to where point(t) falls within that axis's box bounds, and the
    segment intersects the box iff the intersection of both axes' ranges
    with [0, 1] is non-empty.

    This exists because checking only a box's 4 corners against a
    segment's distance (this module's original approach) misses the case
    where a segment runs near-parallel to one of the box's sides and
    passes close to its *middle*, not any corner -- confirmed as a real
    bug via test_no_building_to_building_overlap failing (two buildings on
    opposite sides of a shared road ended up overlapping because neither
    one's corners were close enough to the road to trip the corner-only
    check, even though the road ran close enough to the middle of one
    side of each). See KNOWN_GAPS_AND_ISSUES.md.
    """
    x_min, y_min, x_max, y_max = aabb
    direction = seg_b - seg_a

    t_min, t_max = 0.0, 1.0
    for axis, (box_min, box_max) in enumerate(((x_min, x_max), (y_min, y_max))):
        if abs(direction[axis]) < 1e-12:
            if seg_a[axis] < box_min or seg_a[axis] > box_max:
                return False
            continue
        t1 = (box_min - seg_a[axis]) / direction[axis]
        t2 = (box_max - seg_a[axis]) / direction[axis]
        t_low, t_high = min(t1, t2), max(t1, t2)
        t_min = max(t_min, t_low)
        t_max = min(t_max, t_high)
        if t_min > t_max:
            return False

    return True


def _point_segment_distance(
    point: npt.NDArray[np.float64], seg_a: npt.NDArray[np.float64], seg_b: npt.NDArray[np.float64]
) -> float:
    """Shortest distance from `point` to the segment [seg_a, seg_b]."""
    segment = seg_b - seg_a
    seg_len_sq = float(np.dot(segment, segment))
    if seg_len_sq < 1e-12:
        return float(np.linalg.norm(point - seg_a))
    t = float(np.dot(point - seg_a, segment) / seg_len_sq)
    t = max(0.0, min(1.0, t))
    closest = seg_a + t * segment
    return float(np.linalg.norm(point - closest))


class BuildingPlacementGenerator:  # pylint: disable=too-few-public-methods
    """Place non-overlapping buildings within road-network city blocks.

    Exposes a single public entry point (``generate``) by design; the
    rest of the class is private implementation detail of that operation.
    """

    def __init__(self, seed: int, config: ScenarioTypeConfig) -> None:
        """
        Parameters
        ----------
        seed : int
            Arbitrary-size non-negative integer seed for reproducibility.
        config : ScenarioTypeConfig
            Provides ``building_density`` and ``building_heights``.
        """
        self.seed = seed
        self.config = config
        self.rng = np.random.Generator(np.random.PCG64(seed))
        self._building_counter = 0

    def generate(self, nodes: Dict[int, RoadNode], edges: Dict[int, RoadEdge]) -> List[Building]:
        """Identify city blocks and place buildings within them.

        Parameters
        ----------
        nodes : Dict[int, RoadNode]
            The road network's nodes (used as triangulation input).
        edges : Dict[int, RoadEdge]
            The road network's edges, used to identify which triangulated
            triangles are surviving city blocks (see ``_identify_blocks``).

        Returns
        -------
        List[Building]
            All placed buildings, none overlapping each other or
            encroaching within ``ROAD_SETBACK_METERS`` of their own
            block's boundary.
        """
        blocks = self._identify_blocks(nodes, edges)

        # Checking every candidate corner against every road segment
        # exactly (point-segment distance, with a sqrt) was the dominant
        # cost in an earlier version and made generation take >10s (see
        # KNOWN_GAPS_AND_ISSUES.md). Restricting the check to only a
        # block's own 3 triangle edges was tried next and is faster, but
        # is geometrically unsafe: for a skinny/obtuse triangle, a
        # *different*, non-adjacent real road can still pass within
        # ROAD_SETBACK_METERS of a point deep inside the block -- this was
        # caught by test_no_building_within_road_setback actually
        # failing, not a hypothetical. Fix: precompute each road segment's
        # own padded bounding box once (cheap), then per-candidate, use a
        # cheap AABB pre-filter to skip the vast majority of segments
        # before running the exact (sqrt-based) distance check only on
        # the few that are actually nearby.
        all_segments_padded = [
            (
                nodes[e.start_node_id].position,
                nodes[e.end_node_id].position,
                _padded_segment_aabb(
                    nodes[e.start_node_id].position,
                    nodes[e.end_node_id].position,
                    ROAD_SETBACK_METERS,
                ),
            )
            for e in edges.values()
        ]

        # Correctly enforcing setback against every real road segment (not
        # just a block's own 3 edges) is what makes it safe to skip an
        # explicit cross-block overlap check: Delaunay triangle interiors
        # never overlap each other, roads are the only boundaries between
        # them, and a building kept >=ROAD_SETBACK_METERS from every road
        # cannot cross into a neighboring block's interior. So two
        # buildings in different blocks geometrically cannot overlap,
        # without checking every prior building on every new placement.
        buildings: List[Building] = []
        for block in blocks:
            buildings.extend(self._place_buildings_in_block(block, all_segments_padded))
        return buildings

    def _identify_blocks(
        self, nodes: Dict[int, RoadNode], edges: Dict[int, RoadEdge]
    ) -> List[npt.NDArray[np.float64]]:
        """Re-triangulate node positions and keep triangles whose three
        edges all still exist in the (length-filtered) road graph -- see
        module docstring for why this approximates city blocks."""
        if len(nodes) < 3:
            return []

        node_ids = sorted(nodes.keys())
        positions = np.array([nodes[nid].position for nid in node_ids])

        try:
            tri = Delaunay(positions)
        except QhullError:
            return []

        existing_undirected_edges: Set[Tuple[int, int]] = {
            (min(e.start_node_id, e.end_node_id), max(e.start_node_id, e.end_node_id))
            for e in edges.values()
        }

        blocks = []
        for triangle in tri.simplices:
            triangle_node_ids = [node_ids[idx] for idx in triangle]
            triangle_edges = {
                (min(a, b), max(a, b))
                for a, b in (
                    (triangle_node_ids[0], triangle_node_ids[1]),
                    (triangle_node_ids[1], triangle_node_ids[2]),
                    (triangle_node_ids[2], triangle_node_ids[0]),
                )
            }
            if not triangle_edges.issubset(existing_undirected_edges):
                continue

            polygon = np.array([nodes[nid].position for nid in triangle_node_ids])
            if _polygon_area(polygon) < MIN_BLOCK_AREA_SQ_METERS:
                continue

            blocks.append(polygon)

        return blocks

    def _place_buildings_in_block(  # pylint: disable=too-many-locals
        self, block: npt.NDArray[np.float64], padded_segments: List[_PaddedSegment]
    ) -> List[Building]:
        """Randomly place buildings within one block polygon's bounding
        box, respecting road setback and mutual non-overlap, targeting
        ``config.building_density`` coverage of the block's area.

        Stops early (before reaching ``target_count``) after
        ``MAX_CONSECUTIVE_FULL_FAILURES`` consecutive slots each exhaust
        all ``MAX_PLACEMENT_ATTEMPTS_PER_BLOCK`` attempts -- a strong
        signal the block is effectively full, which random placement
        without backtracking approaches asymptotically without ever
        exactly reaching. Without this, a block whose raw area/density
        implies hundreds of buildings (plausible for a single large,
        sparse triangle) would burn through every one of those slots at
        full attempt cost even once no more buildings physically fit --
        this was the dominant cost in an earlier version that did not
        terminate in reasonable time (see KNOWN_GAPS_AND_ISSUES.md).
        """
        block_area = _polygon_area(block)
        target_building_area = block_area * self.config.building_density
        avg_footprint_area = np.mean(BUILDING_FOOTPRINT_SIDE_METERS) ** 2
        target_count = int(target_building_area / avg_footprint_area)

        x_min, y_min = block.min(axis=0)
        x_max, y_max = block.max(axis=0)

        placed: List[Building] = []
        consecutive_full_failures = 0
        for _ in range(target_count):
            if consecutive_full_failures >= MAX_CONSECUTIVE_FULL_FAILURES:
                break

            placed_this_slot = False
            for _attempt in range(MAX_PLACEMENT_ATTEMPTS_PER_BLOCK):
                width = self.rng.uniform(*BUILDING_FOOTPRINT_SIDE_METERS)
                depth = self.rng.uniform(*BUILDING_FOOTPRINT_SIDE_METERS)
                center = np.array([self.rng.uniform(x_min, x_max), self.rng.uniform(y_min, y_max)])
                height = self.rng.uniform(*self.config.building_heights)
                building_type = _classify_building_type(height, self.config.building_heights)
                material = str(self.rng.choice(BUILDING_MATERIALS_BY_TYPE[building_type]))

                candidate = Building(
                    building_id=self._building_counter,
                    center=center,
                    width=width,
                    depth=depth,
                    height=height,
                    building_type=building_type,
                    material=material,
                )

                if not _polygon_contains_point(block, center):
                    continue
                if self._too_close_to_road(candidate, padded_segments):
                    continue
                if any(_aabb_overlap(candidate.aabb, other.aabb) for other in placed):
                    continue

                placed.append(candidate)
                self._building_counter += 1
                placed_this_slot = True
                break

            consecutive_full_failures = 0 if placed_this_slot else consecutive_full_failures + 1

        return placed

    @staticmethod
    def _too_close_to_road(building: Building, padded_segments: List[_PaddedSegment]) -> bool:
        """True if any road segment passes within ``ROAD_SETBACK_METERS``
        of ``building``'s footprint -- equivalently, whether the segment
        intersects the footprint's AABB inflated by the setback distance
        (see ``_segment_intersects_aabb``'s docstring for why a naive
        corner-distance check is insufficient).

        ``padded_segments`` entries whose precomputed padded AABB doesn't
        even overlap ``building``'s own AABB are skipped first as a cheap
        broad-phase filter -- see ``generate``'s docstring.
        """
        building_aabb = building.aabb
        x_min, y_min, x_max, y_max = building_aabb
        inflated_aabb = (
            x_min - ROAD_SETBACK_METERS,
            y_min - ROAD_SETBACK_METERS,
            x_max + ROAD_SETBACK_METERS,
            y_max + ROAD_SETBACK_METERS,
        )
        for seg_a, seg_b, padded_aabb in padded_segments:
            if not _aabb_overlap(building_aabb, padded_aabb):
                continue
            if _segment_intersects_aabb(seg_a, seg_b, inflated_aabb):
                return True
        return False


def _polygon_area(polygon: npt.NDArray[np.float64]) -> float:
    """Shoelace formula for a simple (non-self-intersecting) polygon."""
    x = polygon[:, 0]
    y = polygon[:, 1]
    return float(0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))))


def _polygon_contains_point(
    polygon: npt.NDArray[np.float64], point: npt.NDArray[np.float64]
) -> bool:
    """Ray-casting point-in-polygon test."""
    n_vertices = len(polygon)
    inside = False
    j = n_vertices - 1
    for i in range(n_vertices):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > point[1]) != (yj > point[1]):
            slope = (xj - xi) / (yj - yi + 1e-15)
            x_intersect = xi + slope * (point[1] - yi)
            if point[0] < x_intersect:
                inside = not inside
        j = i
    return inside
