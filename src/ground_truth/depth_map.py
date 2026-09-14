"""Depth map rendering via per-pixel ray-casting.

Implements MASTER_PROMPT Section 3.6's "Depth map rendering" bullet and
its own "Depth map resolution validation" test bullet.

Reuses the same ray-triangle intersection primitive as
``lidar_model.py``: for each pixel, cast a ray from the camera through
that pixel (inverse pinhole projection) and record the distance to the
nearest mesh hit, exactly like a LiDAR sweep but with rays arranged in a
camera's regular pixel grid instead of a rotating sensor's angular grid.

Performance: O(width * height * triangles), same brute-force
no-acceleration-structure caveat as ``lidar_model.py`` -- see that
module's docstring and KNOWN_GAPS_AND_ISSUES.md. Test images are kept
small for the same reason.
"""

from typing import List

import numpy as np
import numpy.typing as npt

from src.procedural.mesh_factory import Mesh
from src.sensors.camera_model import Camera
from src.sensors.lidar_model import closest_hit_distance


def render_depth_map(camera: Camera, meshes: List[Mesh]) -> npt.NDArray[np.float64]:
    """Render a per-pixel depth map for ``camera``'s full image.

    Parameters
    ----------
    camera : Camera
    meshes : List[Mesh]
        Scene geometry to raycast against.

    Returns
    -------
    npt.NDArray[np.float64]
        [height, width] array of camera-frame z distances (matching
        ``Camera.project``'s own depth convention). Pixels whose ray hits
        nothing are ``np.inf`` -- a real, explicit "no data" marker
        rather than an arbitrary sentinel like 0 or -1 that could be
        mistaken for a valid (very close, or behind-camera) depth.
    """
    width, height = camera.intrinsics.width, camera.intrinsics.height
    k_inverse = np.linalg.inv(camera.intrinsics.get_intrinsic_matrix())
    origin = camera.extrinsics.get_translation_vector()
    rotation = camera.extrinsics.get_rotation_matrix()

    depth_map = np.full((height, width), np.inf)

    for row in range(height):
        for col in range(width):
            pixel_homogeneous = np.array([col + 0.5, row + 0.5, 1.0])
            # K^-1 @ [u, v, 1] = [(u-cx)/fx, (v-cy)/fy, 1] -- the z
            # component is always exactly 1 by construction (K is upper
            # triangular with a 1 in the bottom-right, so is K^-1). That
            # makes `distance` (from closest_hit_distance, in units of
            # this direction vector's own length) numerically identical
            # to the hit point's camera-frame z -- i.e. exactly
            # Camera.project's own depth convention, with no extra scale
            # factor needed.
            camera_frame_direction = k_inverse @ pixel_homogeneous
            # World-frame direction: undo the world-to-camera rotation
            # (rotation is orthogonal, so its inverse is its transpose).
            world_direction = rotation.T @ camera_frame_direction

            distance = closest_hit_distance(origin, world_direction, meshes)
            if distance is not None:
                depth_map[row, col] = distance

    return depth_map
