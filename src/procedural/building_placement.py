"""Procedural building placement within road-network city blocks.

Implements MASTER_PROMPT Section 3.3's "Building Placement" bullets:
identify city blocks, place buildings without overlaps, assign heights,
validate no road-building intersections. As with lane_topology.py,
MASTER_PROMPT gives no algorithm, formulas, or tests for this phase --
designed from scratch, informed by QOL_RESEARCH_CHECKLIST.md Section B.3.
See KNOWN_GAPS_AND_ISSUES.md for the block-identification simplification
this module makes (deliberate, and documented there).

Block identification: since `RoadNetworkGenerator` now generates a plain
orthogonal grid (straight roads, square intersections only -- see that
module's docstring for why), each block is identified directly as one
rectangular grid cell: the 4 nodes at a cell's corners, provided all 4
connecting edges actually exist (an edge can be missing if
`MAX_ROAD_LENGTH_METERS` dropped it). This used to be a triangle-based
*approximation* of city blocks (reusing `RoadNetworkGenerator`'s own,
now-removed, Delaunay triangulation and keeping only triangles whose
edges all survived length-filtering) -- real city blocks in a grid city
genuinely are rectangles, so this is now exact, not an approximation.

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
from typing import Dict, List, Sequence, Set, Tuple

import numpy as np
import numpy.typing as npt

from src.procedural.city_sample_assets import DEFAULT_BUILDING_STYLE, BuildingStyle
from src.procedural.lane_topology import LANE_WIDTH_METERS, SIDEWALK_WIDTH_METERS
from src.procedural.road_network import RoadEdge, RoadNode
from src.procedural.scenario import ScenarioTypeConfig

# Grid coordinates within this tolerance of each other are treated as the
# same axis line when reconstructing the road grid's rows/columns in
# _identify_blocks -- generous relative to POSITION_TOLERANCE-scale
# concerns since block identification only needs to distinguish genuinely
# different grid lines, not sub-millimeter precision.
GRID_COORDINATE_DECIMALS = 6

# Degenerate-triangle threshold: a candidate block below this area is
# treated as unusable (too thin/sliver to hold a building), not an error.
MIN_BLOCK_AREA_SQ_METERS = 25.0

# Building footprint aspect assumptions: width and depth are each sampled
# independently in this range, giving varied but plausible footprints.
BUILDING_FOOTPRINT_SIDE_METERS = (8.0, 25.0)

# Real City Sample "Kit_Bldg_CHA_L1_A" modular kit dimensions (meters) --
# converged from THREE independent real sources found in the actual
# CitySample project on disk (not measured/inferred from our own
# migrated-assets-only copy):
#
# 1. ``Content/Building/HDA/Bldg/BDF/CHA_primary.bdf``, a plain-JSON
#    Houdini "Building Definition File" -- the real authored config
#    Epic's own generator uses. ``Modules["1"]["C_E"]["Mod_Dim"] =
#    [1.5, 5.0]`` for the plain exterior corner, ``["W1"]["Mod_Dim"] =
#    [3.25, 5.0]`` for the wall, ``["P1"]["Mod_Dim"] = [1.25, 5.0]`` for
#    the column/pillar module (``SM_BLDG_CHA_L01_A_Column_01_N1`` --
#    already migrated into VantageCV_UE5's own Content, confirmed present
#    on disk). ``LevelsGrammar``/``Levels["1"]["F0"]`` gives the real
#    per-edge facade grammar strings, e.g.
#    ``"C|W1*|(W1-P1)|E1|P1|E1|P1|E1|(P1-W1)|W1*|C"`` (an edge with
#    entrances, walls interspersed with columns) and ``"C|(W1)*|C"`` (a
#    plain edge with no entrance, no column -- see point 2 below for why
#    that variant is NOT what the values below model).
# 2. ``Content/Building/Library/pointclouds/All_Buildings_Lineup_pc``,
#    the real per-instance transform database (SQLite-backed point
#    cloud) behind Epic's actual "Slice And Dice" building generator
#    output -- read directly via a Python Editor Script
#    (``unreal.PointCloud``/``PointCloudView`` API). This session queried
#    it rigorously (not a single cherry-picked vertex): every real
#    ``Kit_Bldg_CHA_L1_A`` instance across the 4 real buildings that use
#    it (building ids 0, 5, 8, 9; 332 real points total), grouped into
#    16 real straight edges and walked corner-to-corner. Findings, EVERY
#    one exact/consistent with zero exceptions unless noted:
#    - A corner's distance to the first wall of the edge that STARTS at
#      that corner (matching its own yaw) is exactly 150cm in all 16/16
#      real edges measured -- matches BDF's C_E Mod_Dim and this
#      module's own CHA_L1 ``corner_to_first_wall_m`` exactly. The
#      corner-to-wall connection is NOT the source of the visible
#      top-down gap this session was asked to investigate -- see
#      building_facade.py's own module docstring for what is.
#    - Consecutive Wall->Column->Wall->Column spacing, on the 3/4 real
#      buildings that have entrances (ids 0, 5, 9; the same buildings
#      whose grammar is the "W1*|(W1-P1)|E1|P1|..." variant from point 1
#      above), is EXACTLY 325.0cm (wall) then EXACTLY 125.0cm (column)
#      alternating, across 128 real column instances and 152 real wall
#      instances -- zero exceptions. 325cm matches BDF's W1 Mod_Dim
#      exactly; 125cm matches BDF's P1 Mod_Dim exactly. This is the real
#      identity of the "450cm wall-to-wall spacing, 125cm larger than
#      the wall mesh's own 325cm bounding box" this project's earlier
#      sessions measured and had written off as "a deliberate reveal/gap
#      ... not a bug to close up" -- that conclusion was WRONG. It is not
#      an empty reveal at all: real Epic buildings fill that exact 125cm
#      with a real Column mesh (BDF module "P1") that this project's own
#      generator was never emitting. Fixed this session -- see
#      building_facade.py.
#    - The 4th real building (id 8) has NO entrances and NO columns at
#      all -- its wall-to-wall spacing is non-round (330.31cm on one
#      edge, 343.68cm on another), i.e. Epic's Houdini generator
#      non-uniformly STRETCHES each wall module's own scale to exactly
#      fill that edge's real length with zero remainder and zero gap,
#      matching the plain "C|(W1)*|C" grammar from point 1. This is a
#      REAL, different tiling strategy this module does NOT implement:
#      doing so would require a per-instance non-uniform mesh SCALE,
#      which ``FacadePiece``/the scenario serializer's asset-placement
#      convention has no field for today (deliberately not added this
#      session -- a real architecture change, not something to guess the
#      shape of under this project's own no-guessing rule). Since this
#      project's own generator never emits entrances either (see
#      building_facade.py's docstring), the Wall+Column fixed-period
#      model below is a deliberate choice to match the ENTRANCE-having
#      grammar's fixed-period sub-pattern (available real evidence, zero
#      exceptions in 128+152 samples) rather than the stretchy
#      no-entrance grammar (which this project's data model cannot
#      represent yet) -- flagged here, not silently guessed past.
#    - Corner asset variant usage: of the 16 real corner-vertex instances
#      measured, 15 use the PLAIN ``CornerEx_01`` asset and only 1 uses
#      ``CornerExR_01``; ``CornerExL_01`` is used 0/16 times, and no real
#      vertex ever stacks two corner pieces at the same position. This
#      contradicts an earlier session's conclusion (based on ONE
#      cherry-picked real vertex, generalized without checking
#      frequency) that every vertex needs a stacked CornerExL+CornerExR
#      pair -- see building_facade.py's docstring for the real fix this
#      session made (reverted to emitting the single plain
#      ``corner_asset_path`` piece per vertex, matching the real 15/16
#      majority). The lone real CornerExR instance is flagged, not
#      chased further -- not enough real samples to determine what
#      distinguishes it (could be a specific footprint-width edge case,
#      could be an authoring inconsistency); a future session with a
#      larger point-cloud sample across more kits could resolve this.
# 3. The hand-placed reference assembly
#    ``Content/Building/Library/Kit_Ref_Bldg/CHA_Ref_N1`` independently
#    confirms a corner's pivot IS the true rectangle vertex (no
#    pivot-to-vertex offset) with no perpendicular offset for any piece
#    on an edge -- still used below. (Its own corner-to-first-wall
#    reading had appeared to be ~475cm, but that is now understood
#    precisely: the point cloud shows a real edge can have a "stretchy"
#    plain wall directly after the corner's own 150cm reserve, before
#    the fixed 325/125 alternation begins -- e.g. real building 0's west
#    edge is corner(0)->wall(150)->wall(541.8) -- so an isolated
#    hand-measurement landing near 475cm is consistent with sampling one
#    such stretchy join, not a contradiction of the 150cm figure.)
#
# Only ONE corner reservation per edge (at that edge's own start, not
# both ends): the real point cloud confirms (16/16 real edges) the FAR
# (non-own) corner connection is just whatever remainder is left in that
# specific building's real dimensions (e.g. 391.8cm, 502.55cm, 471.7cm,
# 337.26cm, 371.15cm across the real edges measured -- no fixed value),
# not a second fixed reservation -- our own generator instead eliminates
# that remainder entirely by quantizing footprint sides to exact
# multiples (see _quantize_footprint_side).
# These real numbers now live on ``BuildingKit``/``BuildingStyle`` in
# ``city_sample_assets.py`` (CHA_L1: wall 3.25m, column 1.25m -> wall
# pitch 4.5m, corner-to-first-wall 1.5m, floor height 5.0m) so each kit
# carries its own real grid and heights; the evidence above justifies
# those values.


def _quantize_footprint_side(sampled_side: float, style: BuildingStyle) -> float:
    """Round a sampled width/depth up to the nearest exact
    ``2*corner + N*wall + (N-1)*column`` fit (smallest ``N >= 1`` covering
    ``sampled_side``) -- rounding up, never down, so a quantized building is
    never smaller than what density/setback logic already assumed when
    ``sampled_side`` was drawn from ``BUILDING_FOOTPRINT_SIDE_METERS``.

    A corner reach is reserved at BOTH ends of every edge: real
    point-cloud measurement (48 of 48 CHA and CHH edges, zero error) shows
    the last wall ends exactly one corner reach short of the far vertex,
    so an edge holding N walls is ``2C + N*W + (N-1)*P`` long. (An earlier
    version used ``C + N*(W+P)``, which is 0.25m short for CHA -- hidden
    inside the corner mesh -- and would be off by 2.25m for CHH.)
    """
    wall_count = max(
        1,
        int(
            np.ceil(
                (sampled_side - 2.0 * style.corner_to_first_wall_m + style.column_width_m)
                / style.wall_pitch_m
            )
        ),
    )
    return style.edge_length_for_wall_count(wall_count)


def _quantize_height(sampled_height: float, style: BuildingStyle, max_height: float) -> float:
    """Round a sampled height to a whole floor stack of ``style`` (at
    least 1 floor): up by default, never shrinking the sample. Floors may
    differ in height per level (real CHA: 5.0m ground floor, then 3.0m
    floors), so stack heights are not multiples of one number and rounding
    up can overshoot ``max_height`` -- in that case use the tallest stack
    that still fits within ``max_height`` so ``config.building_heights``
    remains a hard bound."""
    floor_count = style.floor_count_for_height(sampled_height)
    while style.total_height(floor_count) > max_height and floor_count > 1:
        floor_count -= 1
    return style.total_height(floor_count)


# Maximum placement attempts per candidate slot before giving up on that
# slot (keeps generation bounded even for a very dense config).
MAX_PLACEMENT_ATTEMPTS_PER_BLOCK = 50

# After this many consecutive slots each exhaust every attempt, treat the
# block as full and stop, rather than burning the remaining target_count
# slots at full attempt cost. See _place_buildings_in_block's docstring.
MAX_CONSECUTIVE_FULL_FAILURES = 5

# (segment start, segment end, padded AABB, this segment's own setback
# distance) -- see generate()'s docstring for why the padded AABB is
# precomputed once rather than per-candidate, and _too_close_to_road's
# docstring for why the setback distance is per-segment, not global.
_PaddedSegment = Tuple[
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    Tuple[float, float, float, float],
    float,
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
class Building:  # pylint: disable=too-many-instance-attributes
    """A single procedurally placed building footprint."""

    building_id: int
    center: npt.NDArray[np.float64]
    width: float
    depth: float
    height: float
    building_type: BuildingType = BuildingType.MIXED_USE
    material: str = "concrete"
    style_name: str = DEFAULT_BUILDING_STYLE.name

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


def identify_city_blocks(  # pylint: disable=too-many-locals
    nodes: Dict[int, RoadNode], edges: Dict[int, RoadEdge]
) -> List[npt.NDArray[np.float64]]:
    """Identify each rectangular grid cell of the road network as one
    city block: the 4 nodes at a cell's corners, in order around the
    rectangle, provided all 4 connecting edges actually exist (an
    edge can be missing if ``MAX_ROAD_LENGTH_METERS`` dropped it --
    see ``RoadNetworkGenerator``). See module docstring for why this
    is exact, not an approximation, now that the road network itself
    is a plain orthogonal grid.

    Reconstructs the grid's rows/columns purely from node positions
    (this module only receives the generic ``nodes``/``edges`` dicts,
    not ``RoadNetworkGenerator``'s own internal grid-index array) --
    every node in the same grid row/column shares the exact same
    y/x float value by construction (``RoadNetworkGenerator`` reuses
    the same coordinate array element for every node in a row/column,
    rather than recomputing it), so grouping by a rounded coordinate
    is a safe, simple way to recover axis lines generically.
    """
    if len(nodes) < 4:
        return []

    node_by_position: Dict[Tuple[float, float], int] = {
        (
            round(float(n.position[0]), GRID_COORDINATE_DECIMALS),
            round(float(n.position[1]), GRID_COORDINATE_DECIMALS),
        ): nid
        for nid, n in nodes.items()
    }
    x_coords = sorted({pos[0] for pos in node_by_position})
    y_coords = sorted({pos[1] for pos in node_by_position})

    existing_undirected_edges: Set[Tuple[int, int]] = {
        (min(e.start_node_id, e.end_node_id), max(e.start_node_id, e.end_node_id))
        for e in edges.values()
    }

    blocks = []
    for row in range(len(y_coords) - 1):
        for col in range(len(x_coords) - 1):
            corners = [
                (x_coords[col], y_coords[row]),
                (x_coords[col + 1], y_coords[row]),
                (x_coords[col + 1], y_coords[row + 1]),
                (x_coords[col], y_coords[row + 1]),
            ]
            resolved_corner_ids: List[int] = []
            for corner in corners:
                node_id = node_by_position.get(corner)
                if node_id is None:
                    break
                resolved_corner_ids.append(node_id)
            if len(resolved_corner_ids) != 4:
                continue  # a corner node here got dropped/merged; skip this cell
            corner_ids = resolved_corner_ids

            cell_edges = {
                (min(a, b), max(a, b)) for a, b in zip(corner_ids, corner_ids[1:] + corner_ids[:1])
            }
            if not cell_edges.issubset(existing_undirected_edges):
                continue  # an edge here was dropped (e.g. exceeded MAX_ROAD_LENGTH_METERS)

            polygon = np.array([nodes[cid].position for cid in corner_ids])
            if _polygon_area(polygon) < MIN_BLOCK_AREA_SQ_METERS:
                continue

            blocks.append(polygon)

    return blocks


class BuildingPlacementGenerator:  # pylint: disable=too-few-public-methods
    """Place non-overlapping buildings within road-network city blocks.

    Exposes a single public entry point (``generate``) by design; the
    rest of the class is private implementation detail of that operation.
    """

    def __init__(
        self,
        seed: int,
        config: ScenarioTypeConfig,
        styles: Sequence[BuildingStyle] = (DEFAULT_BUILDING_STYLE,),
    ) -> None:
        """
        Parameters
        ----------
        seed : int
            Arbitrary-size non-negative integer seed for reproducibility.
        config : ScenarioTypeConfig
            Provides ``building_density`` and ``building_heights``.
        styles : Sequence[BuildingStyle]
            The facade styles buildings may use. Each placed building
            draws one (recorded as ``Building.style_name``) and its
            footprint and height are quantized to THAT style's real grid
            and floor heights. With a single style no extra random draw is
            made, so single-style output is unchanged.
        """
        if not styles:
            raise ValueError("BuildingPlacementGenerator needs at least one style")
        self.seed = seed
        self.config = config
        self.styles = tuple(styles)
        self.rng = np.random.Generator(np.random.PCG64(seed))
        self._building_counter = 0

    def _pick_style(self) -> BuildingStyle:
        """Uniformly pick one of the styles whose shortest possible
        building (one floor of its ground-floor kit) still fits under
        ``config.building_heights``' maximum -- e.g. SFA's 12.75m ground
        floor cannot appear in a scenario capped at 10m. If none fit, all
        styles stay eligible. No random draw is made when only one style
        is eligible, keeping single-style output identical."""
        max_height = self.config.building_heights[1]
        eligible = [s for s in self.styles if s.total_height(1) <= max_height] or list(self.styles)
        if len(eligible) == 1:
            return eligible[0]
        return eligible[int(self.rng.integers(len(eligible)))]

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
            encroaching within ``config.road_setback_meters`` of their
            own block's boundary.
        """
        blocks = self._identify_blocks(nodes, edges)

        # Checking every candidate corner against every road segment
        # exactly (point-segment distance, with a sqrt) was the dominant
        # cost in an earlier version and made generation take >10s (see
        # KNOWN_GAPS_AND_ISSUES.md). Restricting the check to only a
        # block's own 3 triangle edges was tried next and is faster, but
        # is geometrically unsafe: for a skinny/obtuse triangle, a
        # *different*, non-adjacent real road can still pass within the
        # setback of a point deep inside the block -- this was caught by
        # test_no_building_within_road_setback actually failing, not a
        # hypothetical. Fix: precompute each road segment's own padded
        # bounding box once (cheap), then per-candidate, use a cheap AABB
        # pre-filter to skip the vast majority of segments before running
        # the exact (sqrt-based) distance check only on the few that are
        # actually nearby.
        # Setback is measured from the road *centerline*, but the actual
        # paved surface extends up to `e.num_lanes * LANE_WIDTH_METERS`
        # from that centerline on this edge's own (right-hand) side --
        # config.road_setback_meters alone (a small fixed margin, e.g.
        # 2-4m) doesn't account for that, so on any multi-lane road a
        # building could pass this check while still standing inside the
        # actual lane pavement. Confirmed as a real, large-scale problem
        # via dogfooding (a real generated scenario had 194 of 283
        # buildings, ~69%, overlapping real lane geometry -- see
        # KNOWN_GAPS_AND_ISSUES.md), not a hypothetical. Fixed by adding
        # each edge's own lane half-width to the setback used against it.
        # The setback margin beyond the pavement is at least the real
        # sidewalk width (a 3m sidewalk runs along every road's outside
        # edge -- see road_edge_kit.py), so a building never stands on it.
        margin = max(self.config.road_setback_meters, SIDEWALK_WIDTH_METERS)
        all_segments_padded = [
            (
                nodes[e.start_node_id].position,
                nodes[e.end_node_id].position,
                _padded_segment_aabb(
                    nodes[e.start_node_id].position,
                    nodes[e.end_node_id].position,
                    margin + e.num_lanes * LANE_WIDTH_METERS,
                ),
                margin + e.num_lanes * LANE_WIDTH_METERS,
            )
            for e in edges.values()
        ]

        # Correctly enforcing setback against every real road segment (not
        # just a block's own 3 edges) is what makes it safe to skip an
        # explicit cross-block overlap check: Delaunay triangle interiors
        # never overlap each other, roads are the only boundaries between
        # them, and a building kept >=road_setback_meters from every road
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
        """See ``identify_city_blocks``."""
        return identify_city_blocks(nodes, edges)

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
                style = self._pick_style()
                width = _quantize_footprint_side(
                    self.rng.uniform(*BUILDING_FOOTPRINT_SIDE_METERS), style
                )
                depth = _quantize_footprint_side(
                    self.rng.uniform(*BUILDING_FOOTPRINT_SIDE_METERS), style
                )
                center = np.array([self.rng.uniform(x_min, x_max), self.rng.uniform(y_min, y_max)])
                height = _quantize_height(
                    self.rng.uniform(*self.config.building_heights),
                    style,
                    self.config.building_heights[1],
                )
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
                    style_name=style.name,
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

    def _too_close_to_road(self, building: Building, padded_segments: List[_PaddedSegment]) -> bool:
        """True if any road segment passes within its own effective
        setback distance (``config.road_setback_meters`` plus that edge's
        own lane pavement half-width -- see ``generate``'s docstring on
        why this is per-segment, not a single global value) of
        ``building``'s footprint -- equivalently, whether the segment
        intersects the footprint's AABB inflated by that segment's own
        setback distance (see ``_segment_intersects_aabb``'s docstring
        for why a naive corner-distance check is insufficient).

        ``padded_segments`` entries whose precomputed padded AABB doesn't
        even overlap ``building``'s own AABB are skipped first as a cheap
        broad-phase filter -- see ``generate``'s docstring.
        """
        building_aabb = building.aabb
        x_min, y_min, x_max, y_max = building_aabb
        for seg_a, seg_b, padded_aabb, setback in padded_segments:
            if not _aabb_overlap(building_aabb, padded_aabb):
                continue
            inflated_aabb = (
                x_min - setback,
                y_min - setback,
                x_max + setback,
                y_max + setback,
            )
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
