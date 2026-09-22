"""Real continental (NYC-style "ladder") crosswalk markings at every road
approach to an intersection.

Two earlier approaches at this were tried and replaced after live
feedback, not silently discarded -- see ``KNOWN_GAPS_AND_ISSUES.md`` for
the full history:

1. A real Epic crosswalk PAD mesh (``SM_ROAD_19_3_0_19_crosswalk``,
   material ``M_Asphalt_Master_Inst_Crosswalk``) plus a single stop-line
   bar across the road. Live review: the pad's own distinct tone read as
   an unrealistic "different shade of road", not a crosswalk -- most real
   crosswalks (and specifically the New York City style asked for here)
   are just painted stripes on ordinary asphalt, not a separate paved
   pad. So the pad is dropped entirely: the surface under a crosswalk is
   now whatever's already there (this project's own flat, consistently
   matte asphalt -- see ``intersection_pavement.py``), with only real
   paint-stripe geometry placed on top.
2. A single stop-line bar (one line across the road). Live review: this
   doesn't read as "a crosswalk" the way NYC's actual continental/ladder
   markings do -- parallel bars running WITH the direction of travel,
   not one line across it.

**Real-world reference used instead of more Epic data-mining**: Epic's
own per-instance decal placements near real crosswalks were too
irregular/hand-jittered to reverse-engineer a reliable formula (see the
module history above). Rather than guess at a made-up pattern, this uses
the published continental/"ladder" crosswalk specification both the
FHWA's MUTCD (Section 3B.18) and the NYC DOT Street Design Manual define:
parallel bars oriented along the direction of pedestrian travel (i.e.
across the road, spanning curb to curb), each bar 24 inches (0.61m)
wide, laid out with the bar width roughly equal to the gap between bars.
That 0.61m width is not a fresh guess either -- it matches, to within a
centimetre, the one clearly real, measured value found in Epic's own
decal data: 12 of 14 real stripe-decal placements near a crosswalk used
``scale_y = 0.12`` on ``SM_White_Line_00_inst`` (a real, migrated, flat
512x512cm square mesh -- measured via this project's own
``GetStaticMeshBounds`` RPC), giving ``512cm * 0.12 = 61.4cm``.

Placement: each bar is a scaled instance of that same real mesh, its
long axis (local Y) running along the road, its short axis (local X,
fixed at the real 0.61m width, never stretched) across it. Bars are laid
out symmetrically about the road's own centerline, spaced (pitch = bar
width + gap, gap chosen so the whole row fits the road's own real
combined lane width exactly -- the same "real per-instance
``FacadePiece.scale``, fit to the road's own exact width" mechanism the
earlier pad and every other road-edge piece in this project already
uses) rather than stretching the one real, measured bar width to make it
fit.

**A real placement bug, found from live feedback and fixed, not just a
taste adjustment**: ``SM_White_Line_00_inst``'s own pivot sits at its
mesh CENTER (``GetStaticMeshBounds``: origin ``(0,0,0)``, symmetric
``+-256cm`` extent) -- unlike the earlier pad mesh, which was pivoted at
one edge. The first version of this module reused the edge-pivot math
from that pad (placing each bar's pivot at ``clearance + depth`` and
assuming the mesh extended from there back toward the node), which for a
CENTER-pivoted mesh actually centers the bar there instead -- leaving a
real, unintended ``depth / 2`` gap between the crosswalk and the
intersection pavement's own edge. Fixed by centering each bar at
``clearance + depth / 2`` instead, so the crossing's near edge lands
exactly at ``clearance`` (flush, zero gap, matching the paved
intersection fill's own boundary) and its far edge at
``clearance + depth`` -- both provable, both covered by dedicated tests
that check the actual bar EXTENT (not just its pivot).

**Crossing depth, derived not guessed**: sized so five people can walk
the crossing side by side, using the pedestrian shoulder-width figure
from pedestrian planning literature (Fruin's "Pedestrian Planning and
Design", the basis for the Highway Capacity Manual's pedestrian LOS
methodology): about 0.75m of shoulder width per walking person.
``5 * 0.75m = 3.75m``.
"""

import math
from typing import Dict, List, Set, Tuple

import numpy as np
import numpy.typing as npt

from src.procedural.building_facade import FacadePiece
from src.procedural.lane_topology import LANE_WIDTH_METERS, compute_node_clearance
from src.procedural.math_utils import compute_perpendicular
from src.procedural.road_network import RoadEdge, RoadNode

STOP_LINE_ASSET_PATH = (
    "/Game/Road/Kit_MeshDecals_A/Mesh/SM_White_Line_00_inst.SM_White_Line_00_inst"
)

# Real measured/derived dimensions -- see this module's own docstring.
# 5 people abreast x ~0.75m/person real pedestrian shoulder width (Fruin).
CROSSWALK_DEPTH_M = 3.75
STOP_LINE_REAL_SIZE_M = 5.12
STOP_LINE_WIDTH_SCALE = 0.12
STOP_LINE_WIDTH_M = STOP_LINE_REAL_SIZE_M * STOP_LINE_WIDTH_SCALE

# Continental/ladder bar-to-gap ratio: bar width roughly equal to the gap
# between bars (FHWA MUTCD 3B.18 / NYC DOT Street Design Manual).
BAR_PITCH_M = 2.0 * STOP_LINE_WIDTH_M

# A hair above the road surface so bars never z-fight with it.
STOP_LINE_Z_LIFT_M = 0.01


def _physical_road_pairs(edges: Dict[int, RoadEdge]) -> List[Tuple[RoadEdge, int]]:
    """Every physical road (a directed edge plus its combined lane count
    across both directions), each returned once, not once per directed
    edge -- a crosswalk spans the full road, both directions at once."""
    seen: Set[Tuple[int, int]] = set()
    result: List[Tuple[RoadEdge, int]] = []
    for edge in edges.values():
        pair_key: Tuple[int, int]
        if edge.reverse_edge_id is not None:
            low, high = sorted((edge.edge_id, edge.reverse_edge_id))
            pair_key = (low, high)
        else:
            pair_key = (edge.edge_id, edge.edge_id)
        if pair_key in seen:
            continue
        seen.add(pair_key)
        reverse = edges.get(edge.reverse_edge_id) if edge.reverse_edge_id is not None else None
        total_lanes = edge.num_lanes + (reverse.num_lanes if reverse is not None else 0)
        result.append((edge, total_lanes))
    return result


def _ladder_bars_at(
    pivot: npt.NDArray[np.float64],
    rotation_rad: float,
    perp: npt.NDArray[np.float64],
    road_width_m: float,
) -> List[FacadePiece]:
    """The parallel continental-style bars for one crosswalk end, spaced
    symmetrically across ``road_width_m`` at the real, fixed bar width."""
    bar_count = max(1, round(road_width_m / BAR_PITCH_M))
    pitch_m = road_width_m / bar_count
    depth_scale = CROSSWALK_DEPTH_M / STOP_LINE_REAL_SIZE_M
    width_scale = STOP_LINE_WIDTH_M / STOP_LINE_REAL_SIZE_M

    bars = []
    for i in range(bar_count):
        offset_m = -road_width_m / 2.0 + pitch_m * (i + 0.5)
        bar_position = pivot + perp * offset_m
        bars.append(
            FacadePiece(
                asset_path=STOP_LINE_ASSET_PATH,
                position=np.array([bar_position[0], bar_position[1], STOP_LINE_Z_LIFT_M]),
                rotation_rad=rotation_rad,
                scale=(width_scale, depth_scale, 1.0),
            )
        )
    return bars


def generate_crosswalk_pieces(  # pylint: disable=too-many-locals
    nodes: Dict[int, RoadNode], edges: Dict[int, RoadEdge]
) -> List[FacadePiece]:
    """Continental-style crosswalk bars at each end of every physical
    road, spanning that road's own real combined pavement width and
    positioned flush against the paved intersection surface at that
    end."""
    clearance = compute_node_clearance(edges)
    pieces: List[FacadePiece] = []

    for edge, total_lanes in _physical_road_pairs(edges):
        road_width_m = total_lanes * LANE_WIDTH_METERS

        start, end = edge.centerline[0], edge.centerline[-1]
        direction = end - start
        edge_length = float(np.linalg.norm(direction))
        if edge_length < 1e-9:
            continue
        unit_direction = direction / edge_length
        perp = compute_perpendicular(unit_direction)

        for node_id, away_from_node in (
            (edge.start_node_id, unit_direction),
            (edge.end_node_id, -unit_direction),
        ):
            node_clearance = clearance.get(node_id, 0.0)
            far_edge = node_clearance + CROSSWALK_DEPTH_M
            if far_edge > edge_length:
                continue  # road too short to hold a non-overlapping crosswalk here
            # SM_White_Line_00_inst is pivoted at its own mesh CENTER (see
            # this module's docstring), so the bar's pivot must sit at the
            # midpoint of [clearance, clearance + depth], not at either
            # edge, for the near edge to land exactly on `clearance`.
            depth_center = node_clearance + CROSSWALK_DEPTH_M / 2.0
            pivot = nodes[node_id].position + away_from_node * depth_center
            toward_node = -away_from_node
            rotation_rad = math.atan2(float(toward_node[0]), -float(toward_node[1]))
            pieces += _ladder_bars_at(pivot, rotation_rad, perp, road_width_m)
    return pieces
