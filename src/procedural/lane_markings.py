"""Painted lane markings for the generated streets: centre lines, lane lines and stop lines.

Dimensions follow the MUTCD 11th edition (Part 3, Dec 2023); the section for each is in the comment
on its constant. Where the manual gives a range and this module picks a value, the comment says
"choice".

What is drawn, per physical road (a directed edge plus its reverse, which share one centreline;
lane ``i`` of a directed edge spans lateral offsets ``i * LANE_WIDTH`` to ``(i + 1) * LANE_WIDTH``
on that edge's right-hand side):

* a **double solid yellow centre line** on every two-way road (3B.01: undivided two-way streets
  with four or more lanes need it, and a single solid yellow line is not allowed on two-lane
  streets; the generator has no centre turn lane or passing configuration);
* a **white broken lane line** between adjacent lanes of the same direction (3B.06);
* a **white stop line** across the approaching lanes at each end, at least 4 ft ahead of the
  crosswalk (3B.19).

Edge lines are not drawn: they are required only on freeways, expressways and busy rural arterials,
and may be omitted where curbs or parking delineate the edge (3B.09, 3B.10), which is every street
here. Lines end at the stop line and are not continued through intersections (3B.11 allows
optional dotted extensions; not drawn). Turn-lane arrows, words and bike lanes are not drawn; the
generator has no turn lanes or bike lanes.

Paint is a thin quad ``PAINT_Z_M`` above the flat road, in two project-owned materials
(``paint_white`` and ``paint_yellow``). Nothing here edits Epic content.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

import numpy as np
import numpy.typing as npt

from src.procedural.crosswalks import (
    CROSSWALK_DEPTH_M,
    MARKED_STOP_LINE_FROM_CLEARANCE_M,
    MARKED_STOP_LINE_SETBACK_M,
    MARKED_STOP_LINE_WIDTH_M,
)
from src.procedural.lane_topology import LANE_WIDTH_METERS, compute_node_clearance
from src.procedural.math_utils import compute_perpendicular
from src.procedural.mesh_factory import Mesh
from src.procedural.road_network import RoadEdge

INCH = 0.0254
FOOT = 0.3048

# MUTCD 3A.04: a normal longitudinal line is 4 to 6 in wide. Choice: 4 in on a road with one lane
# each way, 6 in where there are two or more lanes in a direction.
LINE_WIDTH_NARROW_M = 4.0 * INCH
LINE_WIDTH_WIDE_M = 6.0 * INCH
# MUTCD 3A.04 paragraph 6: a broken line is a 10 ft segment and a 30 ft gap (1:3).
DASH_M = 10.0 * FOOT
DASH_GAP_M = 30.0 * FOOT
# MUTCD 3A.04: double lines have pavement showing between them, the gap at most twice a line's
# width. Choice: one line width.
DOUBLE_LINE_GAP_FACTOR = 1.0
# MUTCD 3B.19: a stop line is 12 to 24 in wide (choice: 24 in) and at least 4 ft ahead of the
# nearest crosswalk line. The values and the queue position behind the line live in crosswalks.py
# (see there for why).
STOP_LINE_WIDTH_M = MARKED_STOP_LINE_WIDTH_M
STOP_LINE_SETBACK_M = MARKED_STOP_LINE_SETBACK_M
STOP_LINE_FROM_CLEARANCE_M = MARKED_STOP_LINE_FROM_CLEARANCE_M
# Dashes shorter than this (the clipped end of a run) are not drawn.
MIN_DASH_M = 0.5
# Paint sits this far above the flat road surface (the crosswalk stripes use the same lift).
PAINT_Z_M = 0.01
UV_TILE_M = 4.0

MATERIAL_WHITE = "paint_white"
MATERIAL_YELLOW = "paint_yellow"

Quads = List[npt.NDArray[np.float64]]
Span = Tuple[float, float]


@dataclass
class _Road:  # pylint: disable=too-many-instance-attributes
    """One physical road in its own frame: ``along`` runs start to end, ``perp`` is to the right."""

    start: npt.NDArray[np.float64]
    unit: npt.NDArray[np.float64]
    perp: npt.NDArray[np.float64]
    length: float
    lanes_here: int  # lanes of the directed edge (on the right-hand side, offsets > 0)
    lanes_back: int  # lanes of its reverse edge (offsets < 0)
    width: float  # line width
    run_start: float  # where the painted run begins along the road
    run_end: float

    def quad(self, along: Span, across: Span) -> npt.NDArray[np.float64]:
        """Four corners of a rectangle ``along`` the road and ``across`` it (right-hand offsets).

        The road-side perpendicular is to the right, so this corner order is counter-clockwise
        seen from above."""
        corners = [
            (along[0], across[0]),
            (along[0], across[1]),
            (along[1], across[1]),
            (along[1], across[0]),
        ]
        return np.array(
            [[*(self.start + self.unit * a + self.perp * c), PAINT_Z_M] for a, c in corners],
            dtype=np.float64,
        )

    def line(self, centre: float, along: Span) -> npt.NDArray[np.float64]:
        """A painted line ``self.width`` wide centred at lateral offset ``centre``."""
        return self.quad(along, (centre - self.width / 2.0, centre + self.width / 2.0))


def line_width(lanes_in_direction: int) -> float:
    """The line width of a road with this many lanes in its busier direction."""
    return LINE_WIDTH_WIDE_M if lanes_in_direction >= 2 else LINE_WIDTH_NARROW_M


def dash_ranges(start: float, end: float) -> List[Span]:
    """The (start, end) of each painted dash of a broken line over ``start`` to ``end``.

    The first dash begins at ``start``; the last is clipped to ``end`` and dropped if shorter than
    ``MIN_DASH_M``."""
    ranges: List[Span] = []
    position = start
    while position < end:
        stop = min(position + DASH_M, end)
        if stop - position >= MIN_DASH_M:
            ranges.append((position, stop))
        position += DASH_M + DASH_GAP_M
    return ranges


def _mesh(quads: Quads, material: str) -> Mesh:
    """One mesh from many upward-facing quads (corners counter-clockwise from above)."""
    vertices = np.vstack(quads)
    triangles: List[int] = []
    for index in range(len(quads)):
        base = 4 * index
        triangles += [base, base + 1, base + 2, base, base + 2, base + 3]
    return Mesh(
        vertices=vertices,
        triangles=np.array(triangles, dtype=np.int64),
        uvs=vertices[:, :2] / UV_TILE_M,
        material=material,
    )


def _physical_roads(edges: Dict[int, RoadEdge]) -> List[Tuple[RoadEdge, int, int]]:
    """Each physical road once: (edge with the lower id, its lanes, the reverse edge's lanes)."""
    seen: Set[Tuple[int, ...]] = set()
    roads: List[Tuple[RoadEdge, int, int]] = []
    for edge in sorted(edges.values(), key=lambda e: e.edge_id):
        reverse = None
        if edge.reverse_edge_id is not None:
            reverse = edges.get(edge.reverse_edge_id)
        key = (edge.edge_id,) if reverse is None else tuple(sorted((edge.edge_id, reverse.edge_id)))
        if key in seen:
            continue
        seen.add(key)
        roads.append((edge, edge.num_lanes, reverse.num_lanes if reverse is not None else 0))
    return roads


def _stop_lines(road: _Road, edge: RoadEdge, clearance: Dict[int, float]) -> Quads:
    """The stop line at each end that has a crosswalk; shortens the painted run to end at it."""
    quads: Quads = []
    half = STOP_LINE_WIDTH_M / 2.0
    for at_start, node_id in ((True, edge.start_node_id), (False, edge.end_node_id)):
        node_clearance = clearance.get(node_id, 0.0)
        if node_clearance + CROSSWALK_DEPTH_M > road.length:
            continue  # too short for a crosswalk here (crosswalks.py), so no stop line either
        centre = node_clearance + STOP_LINE_FROM_CLEARANCE_M
        approaching = road.lanes_back if at_start else road.lanes_here  # lanes arriving here
        if at_start:
            road.run_start = centre + half
            along: Span = (centre - half, centre + half)
            across: Span = (-approaching * LANE_WIDTH_METERS, 0.0)
        else:
            road.run_end = road.length - centre - half
            along = (road.length - centre - half, road.length - centre + half)
            across = (0.0, approaching * LANE_WIDTH_METERS)
        if approaching > 0:
            quads.append(road.quad(along, across))
    return quads


def _centre_line(road: _Road) -> Quads:
    """The double solid yellow centre line of a two-way road."""
    if road.lanes_here == 0 or road.lanes_back == 0:
        return []
    offset = road.width * (1.0 + DOUBLE_LINE_GAP_FACTOR) / 2.0
    return [road.line(side * offset, (road.run_start, road.run_end)) for side in (-1.0, 1.0)]


def _lane_lines(road: _Road) -> Quads:
    """White broken lines between adjacent lanes of the same direction."""
    quads: Quads = []
    for sign, lanes in ((1.0, road.lanes_here), (-1.0, road.lanes_back)):
        for boundary in range(1, lanes):
            centre = sign * boundary * LANE_WIDTH_METERS
            quads += [road.line(centre, dash) for dash in dash_ranges(road.run_start, road.run_end)]
    return quads


def lane_marking_meshes(edges: Dict[int, RoadEdge]) -> List[Mesh]:
    """The painted lines of every road as at most two meshes (white, yellow)."""
    clearance = compute_node_clearance(edges)
    white: Quads = []
    yellow: Quads = []
    for edge, lanes_here, lanes_back in _physical_roads(edges):
        start = np.asarray(edge.centerline[0], dtype=float)
        end = np.asarray(edge.centerline[-1], dtype=float)
        length = float(np.linalg.norm(end - start))
        if length < 1e-9:
            continue
        unit = (end - start) / length
        road = _Road(
            start,
            unit,
            compute_perpendicular(unit),
            length,
            lanes_here,
            lanes_back,
            line_width(max(lanes_here, lanes_back)),
            clearance.get(edge.start_node_id, 0.0),
            length - clearance.get(edge.end_node_id, 0.0),
        )
        white += _stop_lines(road, edge, clearance)
        if road.run_end - road.run_start >= MIN_DASH_M:
            yellow += _centre_line(road)
            white += _lane_lines(road)
    meshes = []
    if white:
        meshes.append(_mesh(white, MATERIAL_WHITE))
    if yellow:
        meshes.append(_mesh(yellow, MATERIAL_YELLOW))
    return meshes


def marking_summary(meshes: List[Mesh]) -> Dict[str, float]:
    """Painted area in square metres per material (for checks and the dataset card)."""
    totals: Dict[str, float] = {}
    for mesh in meshes:
        quads = mesh.vertices.reshape(-1, 4, 3)
        area = sum(math.dist(q[0][:2], q[1][:2]) * math.dist(q[1][:2], q[2][:2]) for q in quads)
        totals[mesh.material] = totals.get(mesh.material, 0.0) + area
    return totals
