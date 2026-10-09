"""Polygons that follow a binary mask exactly, for COCO's ``segmentation`` field.

The boundary of every connected region (4-connectivity) is traced along pixel edges, so the
polygon's vertices are integer pixel corners and its filled area is the mask's pixel count. Only
outer boundaries are returned: COCO polygons cannot hold holes (an enclosed gap, such as the space
between an arm and a torso, is covered); the exact mask stays available as run-length encoding
(``mask_rle``).
"""

from typing import Dict, List, Tuple

import numpy as np
import numpy.typing as npt

Vertex = Tuple[int, int]
Edge = Tuple[Vertex, Vertex]


def _boundary_edges(mask: npt.NDArray[np.bool_]) -> List[Edge]:
    """Unit edges between inside and outside pixels, directed with the inside on the right."""
    padded = np.pad(mask, 1)
    inside = padded[1:-1, 1:-1]
    edges: List[Edge] = []
    for rows, cols in np.argwhere(inside & ~padded[:-2, 1:-1]):  # top: left to right
        edges.append(((int(cols), int(rows)), (int(cols) + 1, int(rows))))
    for rows, cols in np.argwhere(inside & ~padded[1:-1, 2:]):  # right: top to bottom
        edges.append(((int(cols) + 1, int(rows)), (int(cols) + 1, int(rows) + 1)))
    for rows, cols in np.argwhere(inside & ~padded[2:, 1:-1]):  # bottom: right to left
        edges.append(((int(cols) + 1, int(rows) + 1), (int(cols), int(rows) + 1)))
    for rows, cols in np.argwhere(inside & ~padded[1:-1, :-2]):  # left: bottom to top
        edges.append(((int(cols), int(rows) + 1), (int(cols), int(rows))))
    return edges


def _turn(previous: Edge, candidate: Edge) -> int:
    """0 for a right turn, 1 straight, 2 left (y down); right turns hug the inside."""
    dx0, dy0 = previous[1][0] - previous[0][0], previous[1][1] - previous[0][1]
    dx1, dy1 = candidate[1][0] - candidate[0][0], candidate[1][1] - candidate[0][1]
    cross = dx0 * dy1 - dy0 * dx1  # positive: clockwise on screen, a right turn
    if cross > 0:
        return 0
    return 1 if cross == 0 else 2


def _loops(edges: List[Edge]) -> List[List[Vertex]]:
    """Closed loops of vertices: each edge continues with the right-most turn at its end, which
    keeps regions that touch only at a corner apart (4-connectivity)."""
    outgoing: Dict[Vertex, List[Edge]] = {}
    for edge in edges:
        outgoing.setdefault(edge[0], []).append(edge)
    following: Dict[Edge, Edge] = {
        edge: min(outgoing[edge[1]], key=lambda c, e=edge: _turn(e, c))  # type: ignore[misc]
        for edge in edges
    }
    loops: List[List[Vertex]] = []
    seen: set[Edge] = set()
    for start in edges:
        if start in seen:
            continue
        loop: List[Vertex] = []
        edge = start
        while edge not in seen:
            seen.add(edge)
            loop.append(edge[0])
            edge = following[edge]
        loops.append(loop)
    return loops


def _simplify(loop: List[Vertex]) -> List[Vertex]:
    """Drop vertices that lie on a straight run."""
    kept: List[Vertex] = []
    count = len(loop)
    for index, vertex in enumerate(loop):
        before, after = loop[index - 1], loop[(index + 1) % count]
        if (vertex[0] - before[0]) * (after[1] - vertex[1]) != (vertex[1] - before[1]) * (
            after[0] - vertex[0]
        ):
            kept.append(vertex)
    return kept


def _signed_area(loop: List[Vertex]) -> float:
    total = 0
    for index, (x0, y0) in enumerate(loop):
        x1, y1 = loop[(index + 1) % len(loop)]
        total += x0 * y1 - x1 * y0
    return total / 2.0


def mask_to_polygons(mask: npt.NDArray[np.bool_]) -> List[List[float]]:
    """Outer boundaries of ``mask`` as flat ``[x0, y0, x1, y1, ...]`` lists, one per region."""
    polygons: List[List[float]] = []
    for loop in _loops(_boundary_edges(mask)):
        loop = _simplify(loop)
        if len(loop) >= 3 and _signed_area(loop) > 0:  # clockwise on screen = outer boundary
            polygons.append([float(value) for vertex in loop for value in vertex])
    return polygons
