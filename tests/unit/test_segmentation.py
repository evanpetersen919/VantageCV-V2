"""Unit tests for instance segmentation mask generation.

Covers QOL_RESEARCH_CHECKLIST.md Section F.2: no empty masks, instance
masks don't overlap, plus occlusion-ordering correctness specific to
this module's painter's-algorithm design.
"""

import numpy as np
from matplotlib.path import Path

from src.ground_truth.bbox_3d import BoundingBox3D
from src.ground_truth.segmentation import (
    _paint_silhouette,
    compute_silhouette,
    rasterize_instance_masks,
)
from src.sensors.camera_model import Camera, CameraExtrinsics, CameraIntrinsics


def _small_camera() -> Camera:
    """A small image (64x48) keeps per-test rasterization fast."""
    intrinsics = CameraIntrinsics(50.0, 50.0, 32.0, 24.0, 64, 48)
    extrinsics = CameraExtrinsics(rotation=np.eye(3), translation=np.zeros(3))
    return Camera(intrinsics, extrinsics)


def test_compute_silhouette_returns_convex_hull_points() -> None:
    """A box facing the camera head-on produces a silhouette with at
    least 3 vertices, all finite."""
    camera = _small_camera()
    bbox = BoundingBox3D(
        object_id=1, center=np.array([0.0, 0.0, 20.0]), dimensions=np.array([2.0, 2.0, 2.0])
    )

    silhouette = compute_silhouette(camera, bbox)

    assert silhouette is not None
    assert silhouette.shape[0] >= 3
    assert np.isfinite(silhouette).all()


def test_compute_silhouette_triangle_when_exactly_3_corners_visible() -> None:
    """When exactly 3 of a box's 8 corners project in front of the camera
    (found via search: a camera positioned/oriented so most of the box is
    behind it), the silhouette is exactly those 3 points -- the shortcut
    path that skips ConvexHull for an already-trivial triangle."""
    intrinsics = CameraIntrinsics(50.0, 50.0, 32.0, 24.0, 64, 48)
    extrinsics = CameraExtrinsics.looking_at(
        camera_position=np.array([-0.01565181, 0.8368351, 9.21150764]),
        target=np.array([-2.17859837, 1.9327064, 8.13908747]),
    )
    camera = Camera(intrinsics, extrinsics)
    bbox = BoundingBox3D(
        object_id=1, center=np.array([0.0, 0.0, 10.0]), dimensions=np.array([4.0, 4.0, 4.0])
    )

    corners = bbox.corners()
    visible_count = sum(1 for c in corners if camera.project(c)[1] > 0)
    assert visible_count == 3, "test setup assumption broken: expected exactly 3 visible corners"

    silhouette = compute_silhouette(camera, bbox)
    assert silhouette is not None
    assert silhouette.shape == (3, 2)


def test_compute_silhouette_none_when_fully_behind_camera() -> None:
    """A box entirely behind the camera has no silhouette."""
    camera = _small_camera()
    bbox = BoundingBox3D(
        object_id=1, center=np.array([0.0, 0.0, -20.0]), dimensions=np.array([2.0, 2.0, 2.0])
    )

    assert compute_silhouette(camera, bbox) is None


def test_rasterize_single_object_produces_nonempty_mask() -> None:
    """A single visible object produces a non-empty mask, keyed by its
    object_id."""
    camera = _small_camera()
    bbox = BoundingBox3D(
        object_id=42, center=np.array([0.0, 0.0, 20.0]), dimensions=np.array([2.0, 2.0, 2.0])
    )

    masks = rasterize_instance_masks(camera, [bbox])

    assert 42 in masks
    assert masks[42].any()
    assert masks[42].shape == (camera.intrinsics.height, camera.intrinsics.width)


def test_rasterize_no_empty_masks_returned() -> None:
    """Every mask returned has at least one True pixel (fully-occluded or
    out-of-frame objects are simply absent from the result, never present
    with zero pixels)."""
    camera = _small_camera()
    visible = BoundingBox3D(
        object_id=1, center=np.array([0.0, 0.0, 20.0]), dimensions=np.array([2.0, 2.0, 2.0])
    )
    behind = BoundingBox3D(
        object_id=2, center=np.array([0.0, 0.0, -20.0]), dimensions=np.array([2.0, 2.0, 2.0])
    )

    masks = rasterize_instance_masks(camera, [visible, behind])

    assert 2 not in masks
    for mask in masks.values():
        assert mask.any()


def test_rasterize_instance_masks_never_overlap() -> None:
    """No pixel is True in more than one object's mask (each pixel has a
    single owner by construction)."""
    camera = _small_camera()
    # A large near box and a large-but-farther, laterally-offset box:
    # enough lateral offset that each keeps some unoccluded silhouette,
    # while still overlapping in the middle (so this test actually
    # exercises overlap resolution, not just two disjoint objects).
    near = BoundingBox3D(
        object_id=1, center=np.array([-1.0, 0.0, 15.0]), dimensions=np.array([3.0, 3.0, 3.0])
    )
    far = BoundingBox3D(
        object_id=2, center=np.array([1.0, 0.0, 15.0]), dimensions=np.array([3.0, 3.0, 3.0])
    )

    masks = rasterize_instance_masks(camera, [near, far])

    assert len(masks) == 2
    combined = np.zeros((camera.intrinsics.height, camera.intrinsics.width), dtype=int)
    for mask in masks.values():
        combined += mask.astype(int)
    assert (combined <= 1).all()


def test_nearer_object_occludes_farther_object_in_overlap_region() -> None:
    """Where two objects' silhouettes overlap, the nearer one wins --
    painter's algorithm correctness, not just non-overlap."""
    camera = _small_camera()
    near = BoundingBox3D(
        object_id=1, center=np.array([0.0, 0.0, 15.0]), dimensions=np.array([4.0, 4.0, 4.0])
    )
    far = BoundingBox3D(
        object_id=2, center=np.array([0.0, 0.0, 25.0]), dimensions=np.array([4.0, 4.0, 4.0])
    )

    masks_near_first = rasterize_instance_masks(camera, [near, far])
    masks_far_first = rasterize_instance_masks(camera, [far, near])

    # Order of the input list must not matter -- depth alone decides.
    assert set(masks_near_first.keys()) == set(masks_far_first.keys())
    for object_id, mask in masks_near_first.items():
        assert np.array_equal(mask, masks_far_first[object_id])

    # The near object, being larger on screen and in front, should own
    # strictly more pixels than the far, mostly-occluded one.
    assert masks_near_first[1].sum() > masks_near_first.get(2, np.zeros((1, 1))).sum()


def test_rasterize_empty_input_returns_empty_dict() -> None:
    """No objects at all produces an empty result."""
    camera = _small_camera()
    assert not rasterize_instance_masks(camera, [])


def test_rasterize_mask_shape_matches_camera_resolution() -> None:
    """Every mask's shape matches the camera's (height, width)."""
    camera = _small_camera()
    bbox = BoundingBox3D(
        object_id=1, center=np.array([0.0, 0.0, 20.0]), dimensions=np.array([2.0, 2.0, 2.0])
    )
    masks = rasterize_instance_masks(camera, [bbox])
    assert masks[1].shape == (48, 64)


def _brute_force_inside_mask(silhouette: np.ndarray, width: int, height: int) -> np.ndarray:
    """Reference implementation: full-image point-in-polygon test, no
    bounding-box clipping -- what rasterize_instance_masks's own
    per-object painting used to do before it was accelerated."""
    xx, yy = np.meshgrid(np.arange(width) + 0.5, np.arange(height) + 0.5)
    pixel_centers = np.column_stack([xx.ravel(), yy.ravel()])
    path = Path(silhouette)
    return path.contains_points(pixel_centers).reshape(height, width)


def test_bbox_clipped_rasterization_matches_brute_force_full_image() -> None:
    """The bounding-box-clipped rasterization used internally by
    rasterize_instance_masks produces bit-identical results to a
    brute-force full-image point-in-polygon test, across many randomized
    convex polygon shapes and positions (including partially/fully
    outside the image) -- confirms the optimization is exact, not an
    approximation."""
    rng = np.random.default_rng(0)
    width, height = 64, 48
    mismatches = 0

    for _ in range(100):
        num_vertices = int(rng.integers(3, 8))
        center_x = rng.uniform(-30.0, width + 30.0)
        center_y = rng.uniform(-30.0, height + 30.0)
        radius = rng.uniform(1.0, 60.0)
        angles = np.sort(rng.uniform(0.0, 2.0 * np.pi, num_vertices))
        silhouette = np.column_stack(
            [center_x + radius * np.cos(angles), center_y + radius * np.sin(angles)]
        )

        expected = _brute_force_inside_mask(silhouette, width, height)

        owner = np.full((height, width), -1, dtype=np.int64)
        _paint_silhouette(owner, silhouette, 1, width, height)
        actual = owner == 1

        if not np.array_equal(expected, actual):
            mismatches += 1

    assert mismatches == 0


def test_silhouette_entirely_outside_image_produces_no_pixels() -> None:
    """A silhouette whose bounding box never overlaps the image at all
    (the x_min >= x_max / y_min >= y_max early-return path) contributes
    no pixels, not an error."""
    silhouette = np.array([[1000.0, 1000.0], [1010.0, 1000.0], [1010.0, 1010.0]])
    owner = np.full((48, 64), -1, dtype=np.int64)
    _paint_silhouette(owner, silhouette, 1, 64, 48)
    assert (owner == 1).sum() == 0


def test_rasterize_object_partially_outside_frame_still_correct() -> None:
    """An object whose silhouette extends past the image edge still
    produces a correctly-clipped mask -- the bbox-clip optimization must
    not lose pixels that are legitimately inside both the polygon and the
    image."""
    camera = _small_camera()
    # A large box near the camera, offset so its silhouette spills off
    # the right/bottom edges of the small (64x48) image.
    bbox = BoundingBox3D(
        object_id=1, center=np.array([3.0, 2.0, 5.0]), dimensions=np.array([6.0, 6.0, 6.0])
    )

    masks = rasterize_instance_masks(camera, [bbox])

    assert 1 in masks
    assert masks[1].any()
    # Confirms the silhouette really does spill past at least one edge
    # (otherwise this test isn't exercising the clipping path at all).
    silhouette = compute_silhouette(camera, bbox)
    assert silhouette is not None
    assert (
        silhouette[:, 0].min() < 0
        or silhouette[:, 0].max() > camera.intrinsics.width
        or silhouette[:, 1].min() < 0
        or silhouette[:, 1].max() > camera.intrinsics.height
    )
