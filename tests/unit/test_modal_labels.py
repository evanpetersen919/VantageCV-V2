"""Visible-part ("modal") boxes: the mesh refinement must not overwrite the occlusion shrink."""

from types import SimpleNamespace
from typing import Any

import numpy as np

from src.ground_truth.bbox_2d import BoundingBox2D
from src.ground_truth.mesh_labels import project_vertices, refine_with_meshes, tight_box_2d
from src.orchestration.live_render import ue_camera

CAMERA: Any = SimpleNamespace(intrinsics=SimpleNamespace(width=1920, height=1080))
# A mesh whose projection spans x 100..300, y 400..500.
PIXELS = np.array([[100.0, 400.0], [300.0, 400.0], [300.0, 500.0], [100.0, 500.0]])


def _box(visible_fraction: float, x_min: float = 100.0, x_max: float = 300.0) -> BoundingBox2D:
    return BoundingBox2D(1, x_min, 380.0, x_max, 520.0, 1.0, visible_fraction)


def test_default_box_is_the_whole_mesh_extent_even_when_occluded() -> None:
    """The unchanged (v6) behavior: the occlusion shrink is overwritten."""
    box = tight_box_2d(_box(0.5, x_min=200.0), PIXELS, CAMERA)
    assert box is not None and (box.x_min, box.x_max) == (100.0, 300.0)


def test_modal_box_keeps_only_the_visible_part() -> None:
    """With modal, a half-hidden object's box is cut to the already-shrunken visible region."""
    box = tight_box_2d(_box(0.5, x_min=200.0), PIXELS, CAMERA, modal=True)
    assert box is not None
    assert (box.x_min, box.x_max, box.y_min, box.y_max) == (200.0, 300.0, 400.0, 500.0)


def test_modal_box_of_a_fully_visible_object_is_the_mesh_extent() -> None:
    """The loose projected-corner box of an unoccluded object must not widen or crop it."""
    box = tight_box_2d(_box(1.0, x_min=50.0, x_max=400.0), PIXELS, CAMERA, modal=True)
    assert box is not None and (box.x_min, box.x_max) == (100.0, 300.0)


def test_modal_box_falls_back_to_the_mesh_when_the_regions_do_not_meet() -> None:
    """A visible region that misses the mesh extent entirely cannot erase the label."""
    box = tight_box_2d(_box(0.4, x_min=600.0, x_max=700.0), PIXELS, CAMERA, modal=True)
    assert box is not None and (box.x_min, box.x_max) == (100.0, 300.0)


def test_occlusion_is_not_counted_as_truncation() -> None:
    """Truncation stays the share of the object outside the image, with or without modal."""
    plain = tight_box_2d(_box(0.5, x_min=200.0), PIXELS, CAMERA)
    modal = tight_box_2d(_box(0.5, x_min=200.0), PIXELS, CAMERA, modal=True)
    assert plain is not None and modal is not None and plain.truncation == modal.truncation == 0.0


def test_silhouette_follows_the_visible_box_in_modal_mode() -> None:
    """The segmentation polygon is cut to the same visible rectangle."""
    camera = ue_camera(np.array([0.0, 0.0, 1.5]), np.array([30.0, 0.0, 1.5]), 1920, 1080)
    # A 4 m wide, 1.5 m tall plate 12 m ahead (two triangles).
    corners = np.array([[12.0, -2.0, 0.5], [12.0, 2.0, 0.5], [12.0, 2.0, 2.0], [12.0, -2.0, 2.0]])
    soup = corners[[0, 1, 2, 0, 2, 3]].reshape(2, 3, 3)
    pixels = project_vertices(camera, soup)
    assert pixels is not None
    middle = float(pixels[:, 0].mean())
    box = BoundingBox2D(
        1,
        middle,
        float(pixels[:, 1].min()),
        float(pixels[:, 0].max()) + 5.0,
        float(pixels[:, 1].max()),
        1.0,
        0.5,
    )
    boxes, silhouettes = refine_with_meshes(camera, [box], {1: soup}, modal=True)
    assert abs(boxes[0].x_min - middle) < 1e-6 and abs(silhouettes[1][:, 0].min() - middle) < 1e-6
    plain_boxes, plain = refine_with_meshes(camera, [box], {1: soup})
    assert plain_boxes[0].x_min < middle and plain[1][:, 0].min() < middle
