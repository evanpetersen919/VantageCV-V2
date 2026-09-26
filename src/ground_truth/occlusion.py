"""Occlusion-aware visibility for 3D ground-truth boxes.

``BoundingBox2D.visibility`` only says how much of a box lies inside the image;
it cannot tell that a car is hidden behind a truck. This module measures that.

Method: 27 sample points on a 3x3x3 grid just inside the object's box (at 90%
of its half-extents) are tested for a clear line of sight to the camera. A
sight line is blocked when it crosses any other object's box (shrunk to 95% so
boxes that merely touch do not block each other), tested exactly with the slab
method in each occluder's own rotated frame. Only sample points that project
inside the image count, so an object cut by the frame edge is judged on the
part that is in frame. The visible fraction is the share of those points with
a clear line.

Every occluder is treated as its full box, which is larger than the real
vehicle, so the fraction under-reports visibility (it errs toward calling
things hidden, never toward keeping a hidden object).

Checked against live UE5 renders (a sedan 7 m behind a box truck, shifted
sideways; visible fraction measured from silhouette pixels, sedan alone minus
the truck's pixels, against predicted by this module):

    sideways shift (m)   0.0   2.5   3.5   4.5   5.5   7.0
    measured             0.07  0.69  0.96  1.00  1.00  1.00
    predicted            0.00  0.22  0.56  0.89  1.00  1.00

Both ends agree and the order is right; the middle is pessimistic, as the box
occluder predicts. ``MIN_VISIBLE_FRACTION`` is a design choice: at 0.1 only
objects that are essentially completely hidden are dropped (nuScenes' lowest
visibility bin is 0-40%, so 10% keeps well within what detectors are trained on).
"""

from dataclasses import replace
from typing import Dict, List

import numpy as np
import numpy.typing as npt

from src.ground_truth.bbox_2d import BoundingBox2D
from src.ground_truth.bbox_3d import BoundingBox3D
from src.sensors.camera_model import Camera

SAMPLE_INSET = 0.9
OCCLUDER_SHRINK = 0.95
MIN_VISIBLE_FRACTION = 0.1


def sample_points(box: BoundingBox3D) -> npt.NDArray[np.float64]:
    """The 27 world-space sample points just inside ``box``."""
    steps = np.array([-SAMPLE_INSET, 0.0, SAMPLE_INSET])
    grid = np.array(np.meshgrid(steps, steps, steps)).reshape(3, -1).T * (box.dimensions / 2.0)
    cos_h, sin_h = np.cos(box.heading_rad), np.sin(box.heading_rad)
    rotation = np.array([[cos_h, -sin_h], [sin_h, cos_h]])
    world = np.column_stack([grid[:, :2] @ rotation.T, grid[:, 2]])
    return np.asarray(world + box.center)


def _to_local(
    offset: npt.NDArray[np.float64], headings: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
    """Rotate world offsets (M, ..., 3) into each occluder's own frame (inverse heading about z)."""
    shape = (-1,) + (1,) * (offset.ndim - 2)
    cos_b, sin_b = np.cos(headings).reshape(shape), np.sin(headings).reshape(shape)
    return np.stack(
        [
            offset[..., 0] * cos_b + offset[..., 1] * sin_b,
            -offset[..., 0] * sin_b + offset[..., 1] * cos_b,
            offset[..., 2],
        ],
        axis=-1,
    )


def _blocked_by_any(
    origin: npt.NDArray[np.float64],
    points: npt.NDArray[np.float64],
    occluders: List[BoundingBox3D],
) -> npt.NDArray[np.bool_]:
    """Which origin-to-point segments cross at least one occluder box.

    Vectorised over occluders and points: every segment is moved into each
    occluder's rotated frame and clipped against its slab extents.
    """
    centers = np.array([box.center for box in occluders])
    halves = np.array([box.dimensions for box in occluders]) / 2.0 * OCCLUDER_SHRINK
    headings = np.array([box.heading_rad for box in occluders])
    start = _to_local(origin[None, :] - centers, headings)  # (M, 3)
    end = _to_local(points[None, :, :] - centers[:, None, :], headings)  # (M, N, 3)
    delta = end - start[:, None, :]
    delta = np.where(np.abs(delta) < 1e-9, 1e-9, delta)
    first = (-halves[:, None, :] - start[:, None, :]) / delta
    second = (halves[:, None, :] - start[:, None, :]) / delta
    enter = np.minimum(first, second).max(axis=2)
    leave = np.maximum(first, second).min(axis=2)
    return np.asarray(((enter <= leave) & (leave > 0.0) & (enter < 1.0)).any(axis=0))


def visible_fraction(camera: Camera, box: BoundingBox3D, occluders: List[BoundingBox3D]) -> float:
    """Share of ``box``'s in-frame sample points with a clear line to ``camera``.

    ``occluders`` may include ``box`` itself (it is skipped by ``object_id``).
    Returns 0.0 when no sample point is in frame.
    """
    points = sample_points(box)
    in_frame = np.zeros(len(points), dtype=bool)
    for index, point in enumerate(points):
        pixel, _ = camera.project(point)
        in_frame[index] = pixel is not None and camera.is_pixel_in_bounds(pixel)
    if not in_frame.any():
        return 0.0
    others = [other for other in occluders if other.object_id != box.object_id]
    counted = points[in_frame]
    if not others:
        return 1.0
    blocked = _blocked_by_any(camera.extrinsics.get_translation_vector(), counted, others)
    return float(1.0 - blocked.mean())


def filter_occluded(
    camera: Camera,
    bboxes_2d: List[BoundingBox2D],
    bboxes_3d_by_id: Dict[int, BoundingBox3D],
    minimum: float = MIN_VISIBLE_FRACTION,
) -> List[BoundingBox2D]:
    """Stamp each 2D box with its occlusion-aware visible fraction and drop the
    boxes below ``minimum`` (objects effectively hidden behind others).

    Every box in ``bboxes_3d_by_id`` counts as a potential occluder, whether or
    not it has a 2D box of its own.
    """
    occluders = list(bboxes_3d_by_id.values())
    kept: List[BoundingBox2D] = []
    for bbox_2d in bboxes_2d:
        bbox_3d = bboxes_3d_by_id.get(bbox_2d.object_id)
        if bbox_3d is None:
            kept.append(bbox_2d)
            continue
        fraction = visible_fraction(camera, bbox_3d, occluders)
        if fraction >= minimum:
            kept.append(replace(bbox_2d, visible_fraction=fraction))
    return kept
