"""Tests for measured pedestrian boxes and their elliptic-cylinder 2D labels."""

import numpy as np
import pytest

from src.ground_truth.bbox_2d import BoundingBox2D
from src.ground_truth.bbox_3d import BoundingBox3D
from src.ground_truth.categories import PEDESTRIAN
from src.ground_truth.mesh_labels import refine_with_meshes
from src.ground_truth.proxy_shapes import RING_POINTS, elliptic_cylinder_triangles
from src.orchestration.live_render import ue_camera
from src.procedural.pedestrian_bounds import PEDESTRIAN_HEAD_HEIGHTS, PEDESTRIAN_POSE_EXTENTS
from src.procedural.pedestrian_boxes import character_id, interpolate_extents, pedestrian_box

FACE = "/Game/Crowd/VAT/Meshes/SM_f_004_nrw_FaceMesh"
ROWS = (
    (0.0, -0.2, 0.2, -0.3, 0.3),
    (10.0, -0.4, 0.4, -0.25, 0.25),
    (310.0, -0.1, 0.1, -0.2, 0.2),
    (320.0, -0.5, 0.5, -0.4, 0.4),
    (330.0, -0.6, 0.6, -0.45, 0.45),
)


def test_character_id_is_read_from_the_face_path() -> None:
    """The character number is the third underscore-separated token."""
    assert character_id(FACE) == "004"


def test_interpolation_is_linear_within_a_clip() -> None:
    """Between two measured frames the extents are interpolated linearly."""
    assert interpolate_extents(ROWS, 5.0) == pytest.approx((-0.3, 0.3, -0.275, 0.275))


def test_interpolation_never_crosses_the_clip_boundary() -> None:
    """Frame 315 lies in the walk clip, so it holds at frame 310 instead of blending toward 320."""
    assert interpolate_extents(ROWS, 315.0) == pytest.approx((-0.1, 0.1, -0.2, 0.2))
    assert interpolate_extents(ROWS, 325.0) == pytest.approx((-0.55, 0.55, -0.425, 0.425))


def test_measured_box_uses_the_characters_head_height() -> None:
    """A pedestrian's height is its character's measured head top, hair included."""
    box = pedestrian_box("f", "nrw", FACE, 20.0)
    assert box is not None
    assert box.height == PEDESTRIAN_HEAD_HEIGHTS["f_004"]
    assert box.length > 0 and box.width > 0


def test_unknown_body_or_face_has_no_measured_box() -> None:
    """Anything that was not measured falls back to the caller's default."""
    assert pedestrian_box("x", "nrw", FACE, 0.0) is None
    assert pedestrian_box("f", "nrw", "/Game/Crowd/VAT/Meshes/SM_f_999_nrw_FaceMesh", 0.0) is None


def test_measured_tables_are_plausible() -> None:
    """Heights are human, extents are narrower than a metre, every body has 43 frames."""
    assert all(1.6 < height < 1.95 for height in PEDESTRIAN_HEAD_HEIGHTS.values())
    for rows in PEDESTRIAN_POSE_EXTENTS.values():
        assert len(rows) == 43
        assert all(0.1 < row[2] - row[1] < 1.0 and 0.3 < row[4] - row[3] < 1.0 for row in rows)


def test_cylinder_rings_lie_on_the_ellipse_and_span_the_height() -> None:
    """Both rings are on the ellipse with the box's axes, at the box's bottom and top."""
    box = BoundingBox3D(
        1, np.array([2.0, 3.0, 0.9]), np.array([0.8, 0.4, 1.8]), np.pi / 2, PEDESTRIAN
    )
    points = elliptic_cylinder_triangles(box).reshape(-1, 3)
    assert len(points) == 2 * RING_POINTS
    assert points[:, 2].min() == pytest.approx(0.0) and points[:, 2].max() == pytest.approx(1.8)
    # heading +y: the 0.8 m axis runs along y, the 0.4 m axis along x
    assert points[:, 1].max() - points[:, 1].min() == pytest.approx(0.8, abs=0.02)
    assert points[:, 0].max() - points[:, 0].min() == pytest.approx(0.4, abs=0.02)


def test_pedestrian_2d_box_is_tighter_than_the_box_corners() -> None:
    """Viewed diagonally, the cylinder's 2D box is narrower than the corner hull of its box."""
    camera = ue_camera(np.array([-8.0, -8.0, 1.0]), np.array([0.0, 0.0, 0.9]), 1920, 1080)
    box_3d = BoundingBox3D(1, np.array([0.0, 0.0, 0.9]), np.array([0.7, 0.5, 1.8]), 0.0, PEDESTRIAN)
    columns = [camera.project(corner)[0][0] for corner in box_3d.corners()]  # type: ignore[index]
    corner_width = max(columns) - min(columns)
    placeholder = BoundingBox2D(1, 0.0, 0.0, 10.0, 10.0, 1.0)
    boxes, silhouettes = refine_with_meshes(
        camera, [placeholder], {1: elliptic_cylinder_triangles(box_3d)}
    )
    assert boxes[0].x_max - boxes[0].x_min < corner_width * 0.95
    assert 1 in silhouettes
