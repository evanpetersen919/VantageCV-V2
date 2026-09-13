"""Shared geometric utilities for procedural generation.

Implements the generic geometry helpers referenced (but not defined) by
MASTER_PROMPT's file tree (Section 3.1.3 lists ``src/procedural/math_utils.py``)
and directly exercised by QOL_RESEARCH_CHECKLIST.md Section B.2's own test
signatures (``compute_lane_boundaries``) and Section A.4's degeneracy
pattern (``compute_perpendicular``).
"""

from typing import Tuple

import numpy as np
import numpy.typing as npt

# Degenerate-vector threshold: below this length, direction is undefined
# (division would blow up or divide by ~0). See QOL_RESEARCH_CHECKLIST.md
# Section A.4.
DEGENERATE_VECTOR_LENGTH = 1e-9


def compute_perpendicular(vector: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """Compute the unit right-hand perpendicular of a 2D vector.

    "Right-hand" here means: rotate ``vector`` -90 degrees (clockwise in a
    standard x-right/y-up frame), i.e. the direction to the right of
    someone facing along ``vector``. Used to offset lane geometry to one
    side of a road centerline in a convention consistent with right-hand
    traffic.

    Parameters
    ----------
    vector : npt.NDArray[np.float64]
        A 2-element [dx, dy] direction vector. Need not be normalized.

    Returns
    -------
    npt.NDArray[np.float64]
        Unit vector perpendicular to ``vector``, rotated -90 degrees. If
        ``vector`` is degenerate (length < DEGENERATE_VECTOR_LENGTH),
        returns ``[1.0, 0.0]`` rather than dividing by ~zero -- an
        arbitrary but finite and documented fallback, per
        QOL_RESEARCH_CHECKLIST.md Section A.4.
    """
    length = float(np.linalg.norm(vector))
    if length < DEGENERATE_VECTOR_LENGTH:
        return np.array([1.0, 0.0])
    return np.array([vector[1], -vector[0]]) / length


def compute_lane_boundaries(
    centerline: npt.NDArray[np.float64], width: float, lanes: int
) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Compute left/right road-width boundary polylines from a centerline.

    Offsets every centerline point by ``width / 2`` along the local
    perpendicular direction, to each side. ``lanes`` is accepted for API
    symmetry with per-lane callers (MASTER_PROMPT's module list implies a
    lane-aware boundary function) but does not change the *total* width --
    lane count only matters for subdividing the boundary into individual
    lanes, done separately in ``lane_topology.py``.

    For an interior point (not the first or last), the perpendicular is
    computed from the average of the incoming and outgoing segment
    directions, so the boundary stays smooth (no kink) through a bend --
    this is what QOL_RESEARCH_CHECKLIST.md's own
    ``test_lane_boundary_perpendicular`` exercises with a 3-point bent
    centerline.

    Parameters
    ----------
    centerline : npt.NDArray[np.float64]
        [N, 2] polyline, N >= 2.
    width : float
        Total road width in meters (must be > 0).
    lanes : int
        Number of lanes this road carries (must be >= 1); accepted for API
        completeness, not used in this function's own computation.

    Returns
    -------
    left, right : Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]
        [N, 2] boundary polylines, each offset by ``width / 2`` from
        ``centerline``.

    Raises
    ------
    ValueError
        If ``centerline`` has fewer than 2 points, ``width <= 0``, or
        ``lanes < 1``.
    """
    if len(centerline) < 2:
        raise ValueError("centerline must have at least 2 points")
    if width <= 0:
        raise ValueError(f"width must be positive, got {width}")
    if lanes < 1:
        raise ValueError(f"lanes must be >= 1, got {lanes}")

    half_width = width / 2.0
    n_points = len(centerline)

    left = np.zeros_like(centerline, dtype=np.float64)
    right = np.zeros_like(centerline, dtype=np.float64)

    for i in range(n_points):
        directions = []
        if i > 0:
            directions.append(centerline[i] - centerline[i - 1])
        if i < n_points - 1:
            directions.append(centerline[i + 1] - centerline[i])

        avg_direction = np.mean(directions, axis=0)
        perp = compute_perpendicular(avg_direction)

        left[i] = centerline[i] + perp * half_width
        right[i] = centerline[i] - perp * half_width

    return left, right
