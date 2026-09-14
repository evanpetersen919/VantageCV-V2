"""Unit tests for depth map rendering.

Covers MASTER_PROMPT Section 3.6's own "Depth map resolution validation"
test bullet, plus basic geometric correctness.

Test images are kept small (see depth_map.py module docstring): rendering
is O(width * height * triangles) with no spatial acceleration structure.
"""

import numpy as np

from src.ground_truth.depth_map import render_depth_map
from src.procedural.mesh_factory import Mesh
from src.sensors.camera_model import Camera, CameraExtrinsics, CameraIntrinsics


def _small_camera() -> Camera:
    intrinsics = CameraIntrinsics(50.0, 50.0, 16.0, 12.0, 32, 24)
    extrinsics = CameraExtrinsics(rotation=np.eye(3), translation=np.zeros(3))
    return Camera(intrinsics, extrinsics)


def _frontal_wall_mesh(z: float = 10.0, half_extent: float = 50.0) -> Mesh:
    """A large flat quad facing the camera at a fixed depth, so every
    pixel's ray should hit it."""
    vertices = np.array(
        [
            [-half_extent, -half_extent, z],
            [half_extent, -half_extent, z],
            [half_extent, half_extent, z],
            [-half_extent, half_extent, z],
        ]
    )
    triangles = np.array([0, 1, 2, 0, 2, 3], dtype=np.int64)
    return Mesh(vertices=vertices, triangles=triangles, uvs=np.zeros((4, 2)), material="asphalt")


def test_depth_map_resolution_matches_camera() -> None:
    """The depth map's shape matches the camera's (height, width)."""
    camera = _small_camera()
    depth = render_depth_map(camera, [_frontal_wall_mesh()])
    assert depth.shape == (camera.intrinsics.height, camera.intrinsics.width)


def test_depth_map_empty_scene_is_all_infinite() -> None:
    """With no geometry, every pixel is the explicit inf "no hit" marker."""
    camera = _small_camera()
    depth = render_depth_map(camera, [])
    assert np.isinf(depth).all()


def test_depth_map_frontal_wall_gives_uniform_depth() -> None:
    """A flat wall perpendicular to the optical axis at depth z produces
    (near-)uniform depth z across every pixel that hits it."""
    camera = _small_camera()
    depth = render_depth_map(camera, [_frontal_wall_mesh(z=10.0)])

    assert np.isfinite(depth).all()
    assert np.allclose(depth, 10.0, atol=1e-6)


def test_depth_map_center_pixel_matches_expected_distance() -> None:
    """The center pixel's depth for a wall at z=15 is exactly 15 (the
    optical-axis ray hits it head-on, no obliqueness)."""
    camera = _small_camera()
    depth = render_depth_map(camera, [_frontal_wall_mesh(z=15.0)])

    center_row = int(camera.intrinsics.principal_point_y)
    center_col = int(camera.intrinsics.principal_point_x)
    assert np.isclose(depth[center_row, center_col], 15.0, atol=1e-6)


def test_depth_map_nearer_object_occludes_farther_one() -> None:
    """A small near object in front of a far wall produces a lower depth
    value at the pixels it covers than the wall's own depth."""
    camera = _small_camera()
    near_patch = Mesh(
        vertices=np.array([[-1.0, -1.0, 5.0], [1.0, -1.0, 5.0], [1.0, 1.0, 5.0], [-1.0, 1.0, 5.0]]),
        triangles=np.array([0, 1, 2, 0, 2, 3], dtype=np.int64),
        uvs=np.zeros((4, 2)),
        material="concrete",
    )
    depth = render_depth_map(camera, [_frontal_wall_mesh(z=20.0), near_patch])

    center_row = int(camera.intrinsics.principal_point_y)
    center_col = int(camera.intrinsics.principal_point_x)
    assert np.isclose(depth[center_row, center_col], 5.0, atol=1e-6)


def test_depth_map_no_negative_or_nan_values() -> None:
    """No finite depth value is negative or NaN."""
    camera = _small_camera()
    depth = render_depth_map(camera, [_frontal_wall_mesh()])

    finite = depth[np.isfinite(depth)]
    assert not np.isnan(finite).any()
    assert (finite >= 0).all()
