"""The tractor-trailer rig: one vehicle made of the City Sample cab and its trailer.

The cab (``vehTruck_vehicle08``) and the bare trailer (``vehTruck_trailer01``) are separate
City Sample models; the trailer's origin is placed ``TRAILER_HITCH_X_M`` along the cab's x axis (see
``city_sample_assets`` for how that was measured). A rig is placed as one
vehicle on the cab's placement point and heading, with a box that holds both parts, a mesh that
is both parts, and one label (BDD100K and Cityscapes box a tractor-trailer as one truck).
"""

from typing import Tuple

import numpy as np
import numpy.typing as npt

from src.procedural.city_sample_assets import TRACTOR_FOLDER, TRAILER_FOLDER, TRAILER_HITCH_X_M
from src.procedural.vehicle_bounds import VEHICLE_MODEL_BOUNDS

Bounds = Tuple[float, float, float, float, float, float]


def rig_bounds(  # pylint: disable=too-many-locals
    cab: Bounds, trailer: Bounds, hitch_x: float
) -> Bounds:
    """The box that holds a cab and the trailer hitched ``hitch_x`` metres from the cab's placement
    point (negative: behind it), as (length, width, height, centre_x, centre_y, z_min) in the form
    of ``VEHICLE_MODEL_BOUNDS``. The trailer's box is moved by ``hitch_x`` along x first."""
    cab_l, cab_w, cab_h, cab_cx, cab_cy, cab_z = cab
    tr_l, tr_w, tr_h, tr_cx, tr_cy, tr_z = trailer
    tr_cx += hitch_x
    x_min = min(cab_cx - cab_l / 2.0, tr_cx - tr_l / 2.0)
    x_max = max(cab_cx + cab_l / 2.0, tr_cx + tr_l / 2.0)
    y_min = min(cab_cy - cab_w / 2.0, tr_cy - tr_w / 2.0)
    y_max = max(cab_cy + cab_w / 2.0, tr_cy + tr_w / 2.0)
    z_min = min(cab_z, tr_z)
    return (
        x_max - x_min,
        y_max - y_min,
        max(cab_h + cab_z, tr_h + tr_z) - z_min,
        (x_min + x_max) / 2.0,
        (y_min + y_max) / 2.0,
        z_min,
    )


RIG_BOUNDS: Bounds = rig_bounds(
    VEHICLE_MODEL_BOUNDS[TRACTOR_FOLDER],
    VEHICLE_MODEL_BOUNDS[TRAILER_FOLDER],
    TRAILER_HITCH_X_M,
)


def with_trailer(
    vertices: npt.NDArray[np.float64],
    indices: npt.NDArray[np.int64],
    trailer_vertices: npt.NDArray[np.float64],
    trailer_indices: npt.NDArray[np.int64],
) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.int64]]:
    """The cab's mesh followed by the trailer's, the trailer moved to the hitch."""
    moved = trailer_vertices + np.array([TRAILER_HITCH_X_M, 0.0, 0.0])
    return (
        np.vstack([vertices, moved]),
        np.vstack([indices, trailer_indices + len(vertices)]),
    )
