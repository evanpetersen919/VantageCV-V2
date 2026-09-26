"""Proxy shapes for objects without a usable render mesh.

A pedestrian is well approximated by an elliptic cylinder: its measured forward and
lateral extents are the ellipse's axes and its height the cylinder's. Projected, that
fits the rendered silhouette's left and right edges to about 4.5 px on average (an
8 m view, 32 pedestrians with random outfit, hair, weight, pose and heading), against
9 px for the corners of the box with the same extents.
"""

import numpy as np
import numpy.typing as npt

from src.ground_truth.bbox_3d import BoundingBox3D

RING_POINTS = 24  # a multiple of 3 so the two rings reshape into (N, 3, 3) pseudo-triangles


def elliptic_cylinder_triangles(box: BoundingBox3D) -> npt.NDArray[np.float64]:
    """The bottom and top rings of the elliptic cylinder inscribed in ``box``, as a
    (2 * RING_POINTS / 3, 3, 3) array so it can be projected like a triangle soup.

    The ellipse's axes are the box's length (along its heading) and width; the box
    centre is the ellipse centre.
    """
    angles = np.linspace(0.0, 2.0 * np.pi, RING_POINTS, endpoint=False)
    half_length, half_width, height = (
        box.dimensions[0] / 2.0,
        box.dimensions[1] / 2.0,
        box.dimensions[2],
    )
    local_x, local_y = half_length * np.cos(angles), half_width * np.sin(angles)
    cos_h, sin_h = np.cos(box.heading_rad), np.sin(box.heading_rad)
    world_x = box.center[0] + cos_h * local_x - sin_h * local_y
    world_y = box.center[1] + sin_h * local_x + cos_h * local_y
    bottom = box.center[2] - height / 2.0
    ring = np.column_stack([world_x, world_y])
    points = np.concatenate(
        [
            np.column_stack([ring, np.full(RING_POINTS, bottom)]),
            np.column_stack([ring, np.full(RING_POINTS, bottom + height)]),
        ]
    )
    return np.asarray(points.reshape((-1, 3, 3)))
