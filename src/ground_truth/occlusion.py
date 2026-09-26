"""Occlusion-aware visibility for 3D ground-truth boxes.

``BoundingBox2D.visibility`` only says how much of a box lies inside the image;
it cannot tell that a car is hidden behind a truck. This module measures that.

Method (area-weighted): a grid of pixels is laid over the object's projected
silhouette and a camera ray is cast through each pixel. Rays that hit the
object's box give the surface point the camera would see there; that point is
then tested for a clear line of sight, blocked when the segment from the camera
crosses any other object's box (shrunk to 95% so boxes that merely touch do not
block each other), tested exactly with the slab method in each occluder's own
rotated frame. The visible fraction is the share of hit pixels whose surface
point is unblocked, i.e. an estimate of the visible share of the object's
on-screen area. Weighting by screen area matters: a far car seen over the top
of a truck at a grazing angle shows a sliver of roof, not a third of the car.

Every occluder is treated as its full box, which is larger than the real
vehicle, so the fraction under-reports visibility.

Checked against live UE5 renders (a sedan 7 m behind a box truck, shifted
sideways; visible fraction measured from silhouette pixels, sedan alone minus
the truck's pixels, against predicted by this module):

    sideways shift (m)   0.0   2.5   3.5   4.5   5.5   7.0
    measured             0.07  0.69  0.96  1.00  1.00  1.00
    predicted            0.00  0.31  0.71  0.95  1.00  1.00

Both ends agree and the order is right; the middle is pessimistic, as the box
occluder predicts, so mid-range values are not a calibrated visibility.
``MIN_VISIBLE_FRACTION`` is a design choice: at 0.1 only objects that are
essentially completely hidden (or a sliver of roof) are dropped.
"""

from dataclasses import replace
from typing import Dict, List, Tuple

import numpy as np
import numpy.typing as npt

from src.ground_truth.bbox_2d import BoundingBox2D
from src.ground_truth.bbox_3d import BoundingBox3D
from src.sensors.camera_model import Camera

GRID_SIZE = 16
OCCLUDER_SHRINK = 0.95
MIN_VISIBLE_FRACTION = 0.1


def _to_local(
    offset: npt.NDArray[np.float64], headings: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
    """Rotate world offsets (M, ..., 3) into each box's own frame (inverse heading about z)."""
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


def _slab_interval(
    start: npt.NDArray[np.float64], delta: npt.NDArray[np.float64], half: npt.NDArray[np.float64]
) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Entry and exit parameters of ``start + t * delta`` through a centred box of ``half`` extents.

    ``start`` and ``half`` broadcast against ``delta`` (last axis is x, y, z).
    """
    delta = np.where(np.abs(delta) < 1e-9, 1e-9, delta)
    first, second = (-half - start) / delta, (half - start) / delta
    return np.minimum(first, second).max(axis=-1), np.maximum(first, second).min(axis=-1)


def _blocked_by_any(
    origin: npt.NDArray[np.float64],
    points: npt.NDArray[np.float64],
    occluders: List[BoundingBox3D],
) -> npt.NDArray[np.bool_]:
    """Which origin-to-point segments cross at least one occluder box."""
    centers = np.array([box.center for box in occluders])
    halves = np.array([box.dimensions for box in occluders]) / 2.0 * OCCLUDER_SHRINK
    headings = np.array([box.heading_rad for box in occluders])
    start = _to_local(origin[None, :] - centers, headings)  # (M, 3)
    end = _to_local(points[None, :, :] - centers[:, None, :], headings)  # (M, N, 3)
    enter, leave = _slab_interval(start[:, None, :], end - start[:, None, :], halves[:, None, :])
    return np.asarray(((enter <= leave) & (leave > 0.0) & (enter < 1.0)).any(axis=0))


def _pixel_window(camera: Camera, box: BoundingBox3D) -> Tuple[float, float, float, float]:
    """Pixel bounds (u0, v0, u1, v1) to scan for ``box``: its projected corners, clipped
    to the image; the whole image if any corner is behind the camera."""
    width, height = camera.intrinsics.width, camera.intrinsics.height
    pixels = []
    for corner in box.corners():
        pixel, _ = camera.project(corner)
        if pixel is None:
            return 0.0, 0.0, float(width), float(height)
        pixels.append(pixel)
    array = np.array(pixels)
    return (
        float(np.clip(array[:, 0].min(), 0, width)),
        float(np.clip(array[:, 1].min(), 0, height)),
        float(np.clip(array[:, 0].max(), 0, width)),
        float(np.clip(array[:, 1].max(), 0, height)),
    )


def _pixel_rays(
    camera: Camera, window: Tuple[float, float, float, float]
) -> npt.NDArray[np.float64]:
    """World-space ray directions through a GRID_SIZE x GRID_SIZE pixel grid over ``window``."""
    u0, v0, u1, v1 = window
    us = u0 + (np.arange(GRID_SIZE) + 0.5) / GRID_SIZE * (u1 - u0)
    vs = v0 + (np.arange(GRID_SIZE) + 0.5) / GRID_SIZE * (v1 - v0)
    grid_u, grid_v = np.meshgrid(us, vs)
    pixels = np.column_stack([grid_u.ravel(), grid_v.ravel(), np.ones(grid_u.size)])
    rays_camera = pixels @ np.linalg.inv(camera.intrinsics.get_intrinsic_matrix()).T
    return np.asarray(rays_camera @ camera.extrinsics.get_rotation_matrix())  # R^T d per row


def _surface_hits(camera: Camera, box: BoundingBox3D) -> npt.NDArray[np.float64]:
    """World points where camera rays through ``box``'s silhouette first hit the box."""
    window = _pixel_window(camera, box)
    if window[2] <= window[0] or window[3] <= window[1]:
        return np.empty((0, 3))
    rays = _pixel_rays(camera, window)
    origin = camera.extrinsics.get_translation_vector()
    headings = np.array([box.heading_rad])
    start = _to_local((origin - box.center)[None, None, :], headings)[0, 0]
    enter, leave = _slab_interval(
        start, _to_local(rays[None, :, :], headings)[0], box.dimensions / 2.0
    )
    hit = (enter <= leave) & (enter > 0.0)
    return np.asarray(origin + enter[hit, None] * rays[hit])


def _nearby_occluders(
    origin: npt.NDArray[np.float64], hits: npt.NDArray[np.float64], others: List[BoundingBox3D]
) -> List[BoundingBox3D]:
    """Occluders that can lie between the camera and ``hits`` (bounding-sphere test)."""
    centre = hits.mean(axis=0)
    hit_radius = float(np.linalg.norm(hits - centre, axis=1).max())
    axis = centre - origin
    axis_length = float(np.linalg.norm(axis))
    unit = axis / max(axis_length, 1e-9)
    kept = []
    for other in others:
        offset = other.center - origin
        along = float(offset @ unit)
        radius = float(np.linalg.norm(other.dimensions)) / 2.0
        across = float(np.linalg.norm(offset - along * unit))
        if along - radius < axis_length + hit_radius and across < radius + hit_radius:
            kept.append(other)
    return kept


def visible_fraction(camera: Camera, box: BoundingBox3D, occluders: List[BoundingBox3D]) -> float:
    """Estimated visible share of ``box``'s on-screen area from ``camera``.

    ``occluders`` may include ``box`` itself (it is skipped by ``object_id``).
    Returns 0.0 when no camera ray through the silhouette hits the box.
    """
    hits = _surface_hits(camera, box)
    if len(hits) == 0:
        return 0.0
    origin = camera.extrinsics.get_translation_vector()
    others = _nearby_occluders(origin, hits, [o for o in occluders if o.object_id != box.object_id])
    if not others:
        return 1.0
    return float(1.0 - _blocked_by_any(origin, hits, others).mean())


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
