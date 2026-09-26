"""Tests for occlusion-aware visibility with hand-built, known geometry."""

from typing import Tuple

import numpy as np
import pytest

from src.ground_truth.bbox_2d import BoundingBox2D, project_bboxes_3d_to_2d
from src.ground_truth.bbox_3d import BoundingBox3D
from src.ground_truth.categories import SEDAN
from src.ground_truth.occlusion import _surface_hits, filter_occluded, visible_fraction
from src.sensors.camera_model import Camera, CameraExtrinsics, CameraIntrinsics


def _camera() -> Camera:
    """Camera at the origin, 2 m up, looking along +x."""
    intrinsics = CameraIntrinsics.from_fov(90.0, 1280, 720)
    position = np.array([0.0, 0.0, 2.0])
    return Camera(intrinsics, CameraExtrinsics.looking_at(position, np.array([50.0, 0.0, 2.0])))


def _box(
    object_id: int, x: float, y: float, size: Tuple[float, float, float], heading: float = 0.0
) -> BoundingBox3D:
    length, width, height = size
    return BoundingBox3D(
        object_id,
        np.array([x, y, height / 2.0]),
        np.array([length, width, height]),
        heading_rad=heading,
        category_id=SEDAN,
    )


CAR = (4.5, 1.9, 1.5)
TRUCK_SIZE = (8.0, 2.5, 4.0)


def test_surface_hits_lie_on_the_box_surface_facing_the_camera() -> None:
    """Every ray hit is on the box boundary and on the side nearest the camera."""
    box = _box(1, 10.0, 3.0, CAR, heading=0.7)
    camera = _camera()
    hits = _surface_hits(camera, box)
    assert len(hits) > 50
    cos_h, sin_h = np.cos(-0.7), np.sin(-0.7)
    offset = hits - box.center
    local = np.column_stack(
        [
            offset[:, 0] * cos_h - offset[:, 1] * sin_h,
            offset[:, 0] * sin_h + offset[:, 1] * cos_h,
            offset[:, 2],
        ]
    )
    on_surface = np.isclose(np.abs(local) / (box.dimensions / 2.0), 1.0, atol=1e-6).any(axis=1)
    assert on_surface.all()
    to_hits = np.linalg.norm(hits - camera.extrinsics.translation, axis=1)
    assert to_hits.mean() < np.linalg.norm(box.center - camera.extrinsics.translation)


def test_unobstructed_box_is_fully_visible() -> None:
    """Unobstructed box is fully visible."""
    car = _box(1, 20.0, 0.0, CAR)
    assert visible_fraction(_camera(), car, [car]) == 1.0


def test_car_directly_behind_a_truck_is_hidden() -> None:
    """Car directly behind a truck is hidden."""
    car = _box(1, 30.0, 0.0, CAR)
    truck = _box(2, 15.0, 0.0, TRUCK_SIZE)
    assert visible_fraction(_camera(), car, [car, truck]) == 0.0


def test_car_beside_a_truck_is_fully_visible() -> None:
    """Car beside a truck is fully visible."""
    car = _box(1, 30.0, 12.0, CAR)
    truck = _box(2, 15.0, 0.0, TRUCK_SIZE)
    assert visible_fraction(_camera(), car, [car, truck]) == 1.0


def test_car_half_behind_a_truck_is_partly_visible() -> None:
    """Car half behind a truck is partly visible."""
    truck = _box(2, 15.0, 0.0, (8.0, 2.5, 4.0))
    car = _box(1, 30.0, 2.6, CAR, heading=np.pi / 2)
    fraction = visible_fraction(_camera(), car, [car, truck])
    assert 0.2 < fraction < 0.8


def test_a_box_never_occludes_itself() -> None:
    """A box never occludes itself."""
    car = _box(1, 20.0, 0.0, CAR, heading=0.4)
    assert visible_fraction(_camera(), car, [car]) == 1.0


def test_rotated_occluder_uses_its_own_frame() -> None:
    """Rotated occluder uses its own frame."""
    wall = _box(2, 15.0, 0.0, (10.0, 0.3, 4.0), heading=np.pi / 2)
    car = _box(1, 30.0, 0.0, CAR)
    assert visible_fraction(_camera(), car, [car, wall]) == 0.0
    along_sight_line = _box(3, 15.0, 0.0, (10.0, 0.3, 4.0))
    partly = visible_fraction(_camera(), car, [car, along_sight_line])
    assert 0.3 < partly < 0.95
    off_to_the_side = _box(4, 15.0, 6.0, (10.0, 0.3, 4.0))
    assert visible_fraction(_camera(), car, [car, off_to_the_side]) == 1.0


def test_object_behind_the_camera_has_no_visible_fraction() -> None:
    """Object behind the camera has no visible fraction."""
    car = _box(1, -20.0, 0.0, CAR)
    assert visible_fraction(_camera(), car, [car]) == 0.0


def test_filter_drops_hidden_and_stamps_the_rest() -> None:
    """A hidden car is dropped; the truck and the free car keep a stamped fraction."""
    camera = _camera()
    front = _box(2, 15.0, 0.0, TRUCK_SIZE)
    hidden = _box(1, 30.0, 0.0, CAR)
    clear = _box(3, 30.0, 12.0, CAR)
    boxes = {box.object_id: box for box in (hidden, front, clear)}
    projected = project_bboxes_3d_to_2d(camera, list(boxes.values()))
    kept = filter_occluded(camera, projected, boxes)
    assert sorted(box.object_id for box in kept) == [2, 3]
    assert all(box.visible_fraction == 1.0 for box in kept)


def test_visible_fraction_is_validated() -> None:
    """A fraction outside [0, 1] is rejected."""
    with pytest.raises(ValueError):
        BoundingBox2D(1, 0.0, 0.0, 10.0, 10.0, 1.0, visible_fraction=1.5)


def test_far_car_seen_only_over_a_trucks_roof_is_not_counted_visible() -> None:
    """Grazing view over a tall truck: a sliver of roof, not a third of the car."""
    high_camera = Camera(
        CameraIntrinsics.from_fov(90.0, 1280, 720),
        CameraExtrinsics.looking_at(np.array([0.0, 0.0, 4.5]), np.array([60.0, 0.0, 1.0])),
    )
    truck = _box(2, 6.0, 0.0, (8.0, 2.5, 4.4))
    car = _box(1, 90.0, 0.0, CAR)
    assert visible_fraction(high_camera, car, [car, truck]) < 0.1
