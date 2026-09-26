"""Draw 3D ground-truth boxes on a rendered frame, for eyeballing labels.

Boxes are projected through the same ``Camera`` the labels were made with, so
what is drawn is what a dataset consumer gets. The front (+x) face of every box
is crossed so heading can be checked as well as size and position.
"""

from typing import Dict, Optional, Tuple

import numpy as np
from numpy.typing import NDArray
from PIL import ImageDraw

from src.ground_truth.bbox_3d import BoundingBox3D
from src.ground_truth.categories import BUILDING, BUS, PEDESTRIAN, SEDAN, SUV, TRUCK
from src.sensors.camera_model import Camera

NEAR_PLANE_M = 0.2

COLOURS: Dict[int, Tuple[int, int, int]] = {
    SEDAN: (255, 40, 40),
    SUV: (255, 150, 0),
    TRUCK: (255, 0, 220),
    BUS: (0, 200, 255),
    PEDESTRIAN: (60, 255, 60),
    BUILDING: (255, 255, 0),
}
EDGES = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4)] + [
    (i, i + 4) for i in range(4)
]
FRONT_FACE = (1, 2, 6, 5)


def _clip_to_near(
    start: NDArray[np.float64], end: NDArray[np.float64]
) -> Optional[Tuple[NDArray[np.float64], NDArray[np.float64]]]:
    """Clip a camera-space segment to z >= the near plane, or drop it."""
    if start[2] < NEAR_PLANE_M and end[2] < NEAR_PLANE_M:
        return None
    if start[2] < NEAR_PLANE_M or end[2] < NEAR_PLANE_M:
        fraction = (NEAR_PLANE_M - start[2]) / (end[2] - start[2])
        cut = start + fraction * (end - start)
        return (cut, end) if start[2] < NEAR_PLANE_M else (start, cut)
    return start, end


def _pixel(camera: Camera, point_camera: NDArray[np.float64]) -> Tuple[float, float]:
    """Pinhole projection of a camera-space point."""
    matrix = camera.intrinsics.get_intrinsic_matrix()
    homogeneous = matrix @ (point_camera / point_camera[2])
    return float(homogeneous[0]), float(homogeneous[1])


def _draw_segment(
    draw: ImageDraw.ImageDraw,
    camera: Camera,
    ends: Tuple[NDArray[np.float64], NDArray[np.float64]],
    colour: Tuple[int, int, int],
    width: int,
) -> None:
    """Draw one world-space segment, clipped at the near plane."""
    to_camera = camera.extrinsics.world_to_camera
    clipped = _clip_to_near(to_camera(ends[0]), to_camera(ends[1]))
    if clipped is not None:
        draw.line(
            [_pixel(camera, clipped[0]), _pixel(camera, clipped[1])], fill=colour, width=width
        )


def draw_box_3d(
    draw: ImageDraw.ImageDraw, camera: Camera, box: BoundingBox3D, width: int, dim: bool
) -> None:
    """The 12 edges of the box, plus a cross on its front (+x) face."""
    corners = box.corners()
    colour = COLOURS.get(box.category_id, (255, 255, 255))
    if dim:
        colour = (colour[0] // 3, colour[1] // 3, colour[2] // 3)
    for first, second in EDGES:
        _draw_segment(draw, camera, (corners[first], corners[second]), colour, width)
    _draw_segment(draw, camera, (corners[FRONT_FACE[0]], corners[FRONT_FACE[2]]), colour, width)
    _draw_segment(draw, camera, (corners[FRONT_FACE[1]], corners[FRONT_FACE[3]]), colour, width)
