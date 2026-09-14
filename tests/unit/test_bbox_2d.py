"""Unit tests for 3D-to-2D bounding box projection.

Covers QOL_RESEARCH_CHECKLIST.md Section F.1: 2D boxes within image
bounds, correct corner ordering, and visibility flag behavior.
"""

import numpy as np
import pytest

from src.ground_truth.bbox_2d import BoundingBox2D, project_bbox_3d_to_2d, project_bboxes_3d_to_2d
from src.ground_truth.bbox_3d import BoundingBox3D
from src.sensors.camera_model import Camera, CameraExtrinsics, CameraIntrinsics


def _default_camera() -> Camera:
    intrinsics = CameraIntrinsics(500.0, 500.0, 320.0, 240.0, 640, 480)
    extrinsics = CameraExtrinsics(rotation=np.eye(3), translation=np.zeros(3))
    return Camera(intrinsics, extrinsics)


def test_bounding_box_2d_rejects_inverted_x() -> None:
    """x_min >= x_max is rejected at construction."""
    with pytest.raises(ValueError, match="x_min"):
        BoundingBox2D(object_id=0, x_min=10.0, y_min=0.0, x_max=5.0, y_max=10.0, visibility=1.0)


def test_bounding_box_2d_rejects_inverted_y() -> None:
    """y_min >= y_max is rejected at construction."""
    with pytest.raises(ValueError, match="y_min"):
        BoundingBox2D(object_id=0, x_min=0.0, y_min=10.0, x_max=10.0, y_max=5.0, visibility=1.0)


def test_bounding_box_2d_rejects_visibility_out_of_range() -> None:
    """visibility outside [0, 1] is rejected."""
    with pytest.raises(ValueError, match="visibility"):
        BoundingBox2D(object_id=0, x_min=0.0, y_min=0.0, x_max=10.0, y_max=10.0, visibility=1.5)


def test_bounding_box_2d_area() -> None:
    """area computes width * height."""
    box = BoundingBox2D(object_id=0, x_min=0.0, y_min=0.0, x_max=10.0, y_max=5.0, visibility=1.0)
    assert box.area == 50.0


def test_project_box_directly_ahead_is_fully_visible() -> None:
    """A small box centered on the optical axis, well within frame,
    projects to a valid 2D box with full visibility."""
    camera = _default_camera()
    bbox_3d = BoundingBox3D(
        object_id=1, center=np.array([0.0, 0.0, 20.0]), dimensions=np.array([2.0, 2.0, 2.0])
    )

    bbox_2d = project_bbox_3d_to_2d(camera, bbox_3d)

    assert bbox_2d is not None
    assert bbox_2d.object_id == 1
    assert bbox_2d.visibility == 1.0
    assert bbox_2d.x_min >= 0 and bbox_2d.x_max <= camera.intrinsics.width
    assert bbox_2d.y_min >= 0 and bbox_2d.y_max <= camera.intrinsics.height


def test_project_box_behind_camera_returns_none() -> None:
    """A box entirely behind the camera has nothing to project."""
    camera = _default_camera()
    bbox_3d = BoundingBox3D(
        object_id=1, center=np.array([0.0, 0.0, -20.0]), dimensions=np.array([2.0, 2.0, 2.0])
    )

    assert project_bbox_3d_to_2d(camera, bbox_3d) is None


def test_project_box_far_off_axis_returns_none() -> None:
    """A box far outside the camera's field of view (all corners project
    outside image bounds) returns None."""
    camera = _default_camera()
    bbox_3d = BoundingBox3D(
        object_id=1, center=np.array([10000.0, 10000.0, 20.0]), dimensions=np.array([2.0, 2.0, 2.0])
    )

    assert project_bbox_3d_to_2d(camera, bbox_3d) is None


def test_project_box_partially_in_frame_has_partial_visibility() -> None:
    """A box straddling the edge of the frame has visibility strictly
    between 0 and 1 (some corners in bounds, some not)."""
    camera = _default_camera()
    # Large box centered near the right edge of frame; far enough off-axis
    # that some corners land outside the 640px-wide image, others inside.
    bbox_3d = BoundingBox3D(
        object_id=1, center=np.array([13.0, 0.0, 20.0]), dimensions=np.array([2.0, 2.0, 2.0])
    )

    bbox_2d = project_bbox_3d_to_2d(camera, bbox_3d)

    assert bbox_2d is not None
    assert 0.0 < bbox_2d.visibility < 1.0


def test_project_bboxes_3d_to_2d_filters_invisible_boxes() -> None:
    """project_bboxes_3d_to_2d omits boxes with nothing visible, keeping
    only genuinely visible ones -- QOL_RESEARCH_CHECKLIST.md Section
    F.1's 'Box count matches objects' (only visible objects)."""
    camera = _default_camera()
    visible_box = BoundingBox3D(
        object_id=1, center=np.array([0.0, 0.0, 20.0]), dimensions=np.array([2.0, 2.0, 2.0])
    )
    behind_box = BoundingBox3D(
        object_id=2, center=np.array([0.0, 0.0, -20.0]), dimensions=np.array([2.0, 2.0, 2.0])
    )
    far_off_axis_box = BoundingBox3D(
        object_id=3, center=np.array([10000.0, 0.0, 20.0]), dimensions=np.array([2.0, 2.0, 2.0])
    )

    result = project_bboxes_3d_to_2d(camera, [visible_box, behind_box, far_off_axis_box])

    assert len(result) == 1
    assert result[0].object_id == 1


def test_project_bboxes_3d_to_2d_empty_input() -> None:
    """An empty box list produces an empty result."""
    camera = _default_camera()
    assert project_bboxes_3d_to_2d(camera, []) == []
