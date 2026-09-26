"""A building's real extent: the union of its placed facade pieces.

A building is tiled from real kit meshes whose geometry (window sills, columns,
cornices, parapets) reaches past the footprint line the tiling follows. Measured over
615 buildings, the pieces extend 0.28-0.94 m beyond the footprint on every side (mean
0.59 m) and up to 1.75 m above the nominal height (mean 0.76 m), so the footprint box
is inside the visible building. The label is the union of the pieces' measured bounds
(``facade_piece_bounds.py``), placed with their position, rotation and scale.
"""

from typing import List, Optional, Tuple

import numpy as np
import numpy.typing as npt

from src.procedural.building_facade import FacadePiece
from src.procedural.facade_piece_bounds import FACADE_PIECE_BOUNDS

Extent = Tuple[float, float, float, float, float]  # x_min, y_min, x_max, y_max, z_max


def piece_corners(
    piece: FacadePiece, bounds: Tuple[float, float, float, float, float, float]
) -> npt.NDArray[np.float64]:
    """The eight world-space corners of a placed piece's local bounds."""
    scale = np.array(piece.scale if piece.scale is not None else (1.0, 1.0, 1.0))
    xs, ys, zs = (bounds[0], bounds[3]), (bounds[1], bounds[4]), (bounds[2], bounds[5])
    local = np.array([[x, y, z] for x in xs for y in ys for z in zs]) * scale
    cos_r, sin_r = np.cos(piece.rotation_rad), np.sin(piece.rotation_rad)
    rotated = np.column_stack(
        [
            local[:, 0] * cos_r - local[:, 1] * sin_r,
            local[:, 0] * sin_r + local[:, 1] * cos_r,
            local[:, 2],
        ]
    )
    return np.asarray(rotated + piece.position)


def building_extent(pieces: List[FacadePiece]) -> Optional[Extent]:
    """(x_min, y_min, x_max, y_max, z_max) of the union of the pieces' bounds, or ``None``
    if none of the pieces has measured bounds."""
    corners = [
        piece_corners(piece, FACADE_PIECE_BOUNDS[piece.asset_path])
        for piece in pieces
        if piece.asset_path in FACADE_PIECE_BOUNDS
    ]
    if not corners:
        return None
    cloud = np.concatenate(corners)
    return (
        float(cloud[:, 0].min()),
        float(cloud[:, 1].min()),
        float(cloud[:, 0].max()),
        float(cloud[:, 1].max()),
        float(cloud[:, 2].max()),
    )
