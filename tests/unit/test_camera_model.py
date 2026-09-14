"""Unit tests for the pinhole camera model.

Covers QOL_RESEARCH_CHECKLIST.md Section E.1: intrinsics validity,
extrinsics rigid-transformation validity, and projected points landing
within (or correctly outside) image bounds.
"""

import numpy as np
import pytest

from src.sensors.camera_model import Camera, CameraExtrinsics, CameraIntrinsics


def test_intrinsics_focal_length_positive() -> None:
    """Focal length must be positive; construction rejects non-positive."""
    with pytest.raises(ValueError):
        CameraIntrinsics(0.0, 100.0, 320.0, 240.0, 640, 480)
    with pytest.raises(ValueError):
        CameraIntrinsics(100.0, -1.0, 320.0, 240.0, 640, 480)


def test_intrinsics_dimensions_positive() -> None:
    """Width/height must be positive."""
    with pytest.raises(ValueError):
        CameraIntrinsics(500.0, 500.0, 320.0, 240.0, 0, 480)


def test_intrinsic_matrix_shape_and_values() -> None:
    """get_intrinsic_matrix() returns the standard 3x3 pinhole form."""
    intrinsics = CameraIntrinsics(500.0, 500.0, 320.0, 240.0, 640, 480)
    k = intrinsics.get_intrinsic_matrix()

    assert k.shape == (3, 3)
    assert k[0, 0] > 0 and k[1, 1] > 0
    assert 0 <= k[0, 2] <= intrinsics.width
    assert 0 <= k[1, 2] <= intrinsics.height
    assert np.abs(k[0, 0] - k[1, 1]) < 1.0


def test_intrinsics_from_fov() -> None:
    """from_fov constructs sensible, square-pixel intrinsics."""
    intrinsics = CameraIntrinsics.from_fov(90.0, 640, 480)
    assert intrinsics.focal_length_x == intrinsics.focal_length_y
    assert intrinsics.focal_length_x > 0
    assert intrinsics.principal_point_x == 320.0
    assert intrinsics.principal_point_y == 240.0


def test_extrinsics_identity_is_valid() -> None:
    """Identity rotation + zero translation is a trivially valid pose."""
    extrinsics = CameraExtrinsics(rotation=np.eye(3), translation=np.zeros(3))
    r = extrinsics.get_rotation_matrix()
    assert np.allclose(r @ r.T, np.eye(3), atol=1e-6)
    assert np.isclose(np.linalg.det(r), 1.0, atol=1e-6)


def test_extrinsics_rejects_non_orthogonal_rotation() -> None:
    """A non-orthogonal matrix is rejected as an invalid rotation."""
    bad_rotation = np.array([[1.0, 0.5, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    with pytest.raises(ValueError, match="not orthogonal"):
        CameraExtrinsics(rotation=bad_rotation, translation=np.zeros(3))


def test_extrinsics_rejects_reflection() -> None:
    """An orthogonal matrix with det=-1 (a reflection, not a rotation) is
    rejected."""
    reflection = np.diag([1.0, 1.0, -1.0])
    with pytest.raises(ValueError, match="not a proper rotation"):
        CameraExtrinsics(rotation=reflection, translation=np.zeros(3))


def test_extrinsics_rejects_wrong_shapes() -> None:
    """Malformed rotation/translation shapes are rejected explicitly."""
    with pytest.raises(ValueError, match="3x3"):
        CameraExtrinsics(rotation=np.eye(2), translation=np.zeros(3))
    with pytest.raises(ValueError, match="length 3"):
        CameraExtrinsics(rotation=np.eye(3), translation=np.zeros(2))


def test_looking_at_produces_valid_rotation() -> None:
    """looking_at constructs a valid (orthogonal, det=1) rotation for a
    typical camera pose."""
    extrinsics = CameraExtrinsics.looking_at(
        camera_position=np.array([0.0, 0.0, 5.0]), target=np.array([10.0, 0.0, 0.0])
    )
    r = extrinsics.rotation
    assert np.allclose(r @ r.T, np.eye(3), atol=1e-6)
    assert np.isclose(np.linalg.det(r), 1.0, atol=1e-6)


def test_looking_at_rejects_coincident_position_and_target() -> None:
    """Camera position equal to target has no defined forward direction."""
    with pytest.raises(ValueError, match="must not coincide"):
        CameraExtrinsics.looking_at(
            camera_position=np.array([1.0, 2.0, 3.0]), target=np.array([1.0, 2.0, 3.0])
        )


def test_looking_at_rejects_forward_parallel_to_up() -> None:
    """Looking straight up/down (forward parallel to world_up) has no
    unique right vector and is rejected rather than silently returning
    garbage."""
    with pytest.raises(ValueError, match="parallel to world_up"):
        CameraExtrinsics.looking_at(
            camera_position=np.array([0.0, 0.0, 10.0]), target=np.array([0.0, 0.0, 0.0])
        )


def test_project_point_directly_ahead_lands_near_principal_point() -> None:
    """A world point directly along the optical axis projects near the
    principal point."""
    intrinsics = CameraIntrinsics(500.0, 500.0, 320.0, 240.0, 640, 480)
    extrinsics = CameraExtrinsics(rotation=np.eye(3), translation=np.zeros(3))
    camera = Camera(intrinsics, extrinsics)

    pixel, depth = camera.project(np.array([0.0, 0.0, 10.0]))

    assert pixel is not None
    assert np.allclose(pixel, [320.0, 240.0], atol=1e-6)
    assert depth == 10.0


def test_project_point_behind_camera_returns_none_pixel() -> None:
    """A point behind the camera (camera-frame z <= 0) has no valid pixel,
    but depth is still returned for occlusion reasoning."""
    intrinsics = CameraIntrinsics(500.0, 500.0, 320.0, 240.0, 640, 480)
    extrinsics = CameraExtrinsics(rotation=np.eye(3), translation=np.zeros(3))
    camera = Camera(intrinsics, extrinsics)

    pixel, depth = camera.project(np.array([0.0, 0.0, -5.0]))

    assert pixel is None
    assert depth == -5.0


def test_project_offset_point_moves_away_from_principal_point() -> None:
    """A point offset to the +x side of the optical axis projects to a
    pixel with u > principal_point_x."""
    intrinsics = CameraIntrinsics(500.0, 500.0, 320.0, 240.0, 640, 480)
    extrinsics = CameraExtrinsics(rotation=np.eye(3), translation=np.zeros(3))
    camera = Camera(intrinsics, extrinsics)

    pixel, _ = camera.project(np.array([2.0, 0.0, 10.0]))

    assert pixel is not None
    assert pixel[0] > intrinsics.principal_point_x


def test_is_pixel_in_bounds() -> None:
    """is_pixel_in_bounds correctly classifies in/out-of-frame pixels."""
    intrinsics = CameraIntrinsics(500.0, 500.0, 320.0, 240.0, 640, 480)
    extrinsics = CameraExtrinsics(rotation=np.eye(3), translation=np.zeros(3))
    camera = Camera(intrinsics, extrinsics)

    assert camera.is_pixel_in_bounds(np.array([320.0, 240.0]))
    assert camera.is_pixel_in_bounds(np.array([0.0, 0.0]))
    assert camera.is_pixel_in_bounds(np.array([640.0, 480.0]))
    assert not camera.is_pixel_in_bounds(np.array([-1.0, 240.0]))
    assert not camera.is_pixel_in_bounds(np.array([320.0, 481.0]))


def test_get_translation_vector() -> None:
    """get_translation_vector returns the camera's world position."""
    extrinsics = CameraExtrinsics(rotation=np.eye(3), translation=np.array([1.0, 2.0, 3.0]))
    assert np.array_equal(extrinsics.get_translation_vector(), np.array([1.0, 2.0, 3.0]))


def test_world_to_camera_translation_applied_correctly() -> None:
    """A camera translated away from the origin correctly re-centers
    world points into its own frame."""
    extrinsics = CameraExtrinsics(rotation=np.eye(3), translation=np.array([5.0, 0.0, 0.0]))
    point_camera = extrinsics.world_to_camera(np.array([5.0, 0.0, 10.0]))
    assert np.allclose(point_camera, [0.0, 0.0, 10.0])
