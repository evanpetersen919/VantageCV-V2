"""Tight 2D labels from an object's projected render mesh.

The 2D box of a projected 3D label box is loose: the rectangle around all eight
projected corners is about 1.5x the area of a car seen obliquely (measured over
2273 vehicles in generated frames: mean IoU 0.70 with the mesh's own tight box).
For objects with a real mesh the label is instead the extent of the projected
mesh vertices, and the segmentation polygon is their convex hull.

The box is the whole object's extent clipped to the image (amodal within the
frame); how much of it is visible is ``BoundingBox2D.visible_fraction``. A mesh
with any vertex at or behind the camera cannot be projected cleanly, so the
caller keeps the box-derived label for it.
"""

from dataclasses import replace
from typing import Dict, List, Optional, Tuple

import numpy as np
import numpy.typing as npt
from scipy.spatial import ConvexHull, QhullError  # pylint: disable=no-name-in-module

from src.ground_truth.bbox_2d import BoundingBox2D
from src.sensors.camera_model import Camera

MIN_DEPTH_M = 0.3


def project_vertices(
    camera: Camera, triangles: npt.NDArray[np.float64]
) -> Optional[npt.NDArray[np.float64]]:
    """Pixel positions of every triangle vertex, or ``None`` if any is within
    ``MIN_DEPTH_M`` of (or behind) the camera."""
    points = triangles.reshape(-1, 3)
    in_camera = (points - camera.extrinsics.get_translation_vector()) @ (
        camera.extrinsics.get_rotation_matrix().T
    )
    if (in_camera[:, 2] < MIN_DEPTH_M).any():
        return None
    intrinsics = camera.intrinsics
    normalized = in_camera[:, :2] / in_camera[:, 2:3]
    focal = np.array([intrinsics.focal_length_x, intrinsics.focal_length_y])
    centre = np.array([intrinsics.principal_point_x, intrinsics.principal_point_y])
    return np.asarray(normalized * focal + centre)


def tight_box_2d(
    box: BoundingBox2D, pixels: npt.NDArray[np.float64], camera: Camera
) -> Optional[BoundingBox2D]:
    """``box`` with its extent replaced by the projected vertices' extent, clipped to
    the image; ``None`` if nothing of the object is inside the image."""
    width, height = camera.intrinsics.width, camera.intrinsics.height
    x_min, y_min = np.clip(pixels.min(axis=0), 0.0, [width, height])
    x_max, y_max = np.clip(pixels.max(axis=0), 0.0, [width, height])
    if x_max <= x_min or y_max <= y_min:
        return None
    return replace(
        box, x_min=float(x_min), y_min=float(y_min), x_max=float(x_max), y_max=float(y_max)
    )


def silhouette_polygon(pixels: npt.NDArray[np.float64]) -> Optional[npt.NDArray[np.float64]]:
    """Convex hull of the projected vertices (counter-clockwise), or ``None`` if degenerate."""
    try:
        hull = ConvexHull(pixels)
    except QhullError:
        return None
    return np.asarray(pixels[hull.vertices], dtype=np.float64)


def refine_with_meshes(
    camera: Camera,
    boxes_2d: List[BoundingBox2D],
    meshes: Dict[int, npt.NDArray[np.float64]],
) -> Tuple[List[BoundingBox2D], Dict[int, npt.NDArray[np.float64]]]:
    """Replace the box-derived 2D box of every object that has a mesh with the tight
    box of its projected mesh; return the new boxes and the objects' silhouettes.

    Objects whose mesh cannot be projected keep their box-derived label; objects whose
    mesh lies entirely outside the image are dropped.
    """
    refined: List[BoundingBox2D] = []
    silhouettes: Dict[int, npt.NDArray[np.float64]] = {}
    for box in boxes_2d:
        soup = meshes.get(box.object_id)
        pixels = None if soup is None else project_vertices(camera, soup)
        if pixels is None:
            refined.append(box)
            continue
        tight = tight_box_2d(box, pixels, camera)
        if tight is None:
            continue  # the object's mesh lies entirely outside the image
        refined.append(tight)
        polygon = silhouette_polygon(pixels)
        if polygon is not None:
            silhouettes[box.object_id] = np.clip(
                polygon, 0.0, [camera.intrinsics.width, camera.intrinsics.height]
            )
    return refined, silhouettes
