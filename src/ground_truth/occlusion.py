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

Objects with a real mesh (vehicles: ``vehicle_meshes.py``, the render triangles
dumped from the game) are measured and occlude by their actual shape; everything
else (pedestrians, buildings) still counts as its full box, which is larger than
the real thing, so those fractions under-report visibility. The engine's own
line traces were tried first and rejected: vehicle collision here is a few
convex hulls (trace flag "simple as complex"), no better than boxes.

Checked against live UE5 renders (a sedan 7 m behind a semi-tractor, shifted
sideways). "Pixels" is the share of the sedan's pixels that keep their colour
when the truck is added to the scene:

    sideways shift (m)   0.0    2.5   3.5   4.5   5.5   7.0
    pixels               0.13*  0.98  1.00  1.00  1.00  1.00
    boxes only           0.00   0.31  0.71  0.95  1.00  1.00
    real meshes          0.01   0.72  1.00  1.00  1.00  1.00

(* the colour test is fooled by two whitish surfaces; the render shows the sedan
completely hidden.) At 2.5 m the render shows the sedan roughly 90% visible, so
the mesh value is still somewhat low, mostly the truck's wide mirrors and doors.
``MIN_VISIBLE_FRACTION`` is a design choice: at 0.1 only objects that are
essentially completely hidden (or a sliver of roof) are dropped.
"""

from dataclasses import replace
from typing import Dict, List, Optional, Tuple

import numpy as np
import numpy.typing as npt

from src.ground_truth.bbox_2d import BoundingBox2D
from src.ground_truth.bbox_3d import BoundingBox3D
from src.sensors.camera_model import Camera

GRID_SIZE = 16
MIN_GRID_SIZE = 4
PIXELS_PER_RAY = 16.0
OCCLUDER_SHRINK = 0.95
MIN_VISIBLE_FRACTION = 0.1
TRIANGLE_CHUNK = 512
WINDOW_MARGIN = 0.05
MESH_CANDIDATE_SHRINK = 1.05
SEGMENT_END_MARGIN = 0.99


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
    shrink: float = OCCLUDER_SHRINK,
) -> npt.NDArray[np.bool_]:
    """Which origin-to-point segments cross at least one occluder box."""
    centers = np.array([box.center for box in occluders])
    halves = np.array([box.dimensions for box in occluders]) / 2.0 * shrink
    headings = np.array([box.heading_rad for box in occluders])
    start = _to_local(origin[None, :] - centers, headings)  # (M, 3)
    end = _to_local(points[None, :, :] - centers[:, None, :], headings)  # (M, N, 3)
    enter, leave = _slab_interval(start[:, None, :], end - start[:, None, :], halves[:, None, :])
    return np.asarray(((enter <= leave) & (leave > 0.0) & (enter < 1.0)).any(axis=0))


def pixel_window(camera: Camera, box: BoundingBox3D) -> Tuple[float, float, float, float]:
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
    """World-space ray directions through a square pixel grid over ``window``.

    The grid has about one ray per PIXELS_PER_RAY pixels of window area, between
    MIN_GRID_SIZE and GRID_SIZE rays per side, so small distant objects are cheap.
    """
    u0, v0, u1, v1 = window
    size = int(np.clip(np.sqrt((u1 - u0) * (v1 - v0) / PIXELS_PER_RAY), MIN_GRID_SIZE, GRID_SIZE))
    us = u0 + (np.arange(size) + 0.5) / size * (u1 - u0)
    vs = v0 + (np.arange(size) + 0.5) / size * (v1 - v0)
    grid_u, grid_v = np.meshgrid(us, vs)
    pixels = np.column_stack([grid_u.ravel(), grid_v.ravel(), np.ones(grid_u.size)])
    rays_camera = pixels @ np.linalg.inv(camera.intrinsics.get_intrinsic_matrix()).T
    return np.asarray(rays_camera @ camera.extrinsics.get_rotation_matrix())  # R^T d per row


def _chunk_hit_parameters(
    origin: npt.NDArray[np.float64],
    directions: npt.NDArray[np.float64],
    chunk: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Smallest positive hit parameter per ray against one chunk of triangles (inf if none)."""
    corner, edge_1, edge_2 = chunk[:, 0], chunk[:, 1] - chunk[:, 0], chunk[:, 2] - chunk[:, 0]
    pvec = np.cross(directions[:, None, :], edge_2[None, :, :])
    det = np.einsum("tk,rtk->rt", edge_1, pvec)
    safe = np.where(np.abs(det) < 1e-12, 1.0, det)
    tvec = origin[None, :] - corner
    u_coord = np.einsum("tk,rtk->rt", tvec, pvec) / safe
    qvec = np.cross(tvec, edge_1)
    v_coord = np.einsum("rk,tk->rt", directions, qvec) / safe
    t_hit = np.einsum("tk,tk->t", edge_2, qvec)[None, :] / safe
    valid = (
        (np.abs(det) >= 1e-12)
        & (u_coord >= 0.0)
        & (v_coord >= 0.0)
        & (u_coord + v_coord <= 1.0)
        & (t_hit > 1e-6)
    )
    return np.asarray(np.where(valid, t_hit, np.inf).min(axis=1))


def _first_hit_parameter(
    origin: npt.NDArray[np.float64],
    directions: npt.NDArray[np.float64],
    triangles: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Smallest t > 0 with ``origin + t * direction`` on a triangle, per ray (inf if none).

    Moller-Trumbore, two-sided, vectorised over rays and chunks of triangles.
    """
    nearest = np.full(len(directions), np.inf)
    for start in range(0, len(triangles), TRIANGLE_CHUNK):
        chunk = triangles[start : start + TRIANGLE_CHUNK]
        nearest = np.minimum(nearest, _chunk_hit_parameters(origin, directions, chunk))
    return nearest


def _segments_hit_triangles(
    origin: npt.NDArray[np.float64],
    points: npt.NDArray[np.float64],
    triangles: npt.NDArray[np.float64],
) -> npt.NDArray[np.bool_]:
    """Which origin-to-point segments cross the triangle soup."""
    reach = _first_hit_parameter(origin, points - origin, triangles)
    return np.asarray(reach < SEGMENT_END_MARGIN)


def _surface_hits(
    camera: Camera, box: BoundingBox3D, triangles: Optional[npt.NDArray[np.float64]] = None
) -> npt.NDArray[np.float64]:
    """World points where camera rays through ``box``'s silhouette first hit the box."""
    window = pixel_window(camera, box)
    if window[2] <= window[0] or window[3] <= window[1]:
        return np.empty((0, 3))
    origin = camera.extrinsics.get_translation_vector()
    if triangles is not None:
        grow_u, grow_v = WINDOW_MARGIN * (window[2] - window[0]), WINDOW_MARGIN * (
            window[3] - window[1]
        )
        window = (window[0] - grow_u, window[1] - grow_v, window[2] + grow_u, window[3] + grow_v)
        rays = _pixel_rays(camera, window)
        reach = _first_hit_parameter(origin, rays, triangles)
        found = np.isfinite(reach)
        return np.asarray(origin + reach[found, None] * rays[found])
    rays = _pixel_rays(camera, window)
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
    if not others:
        return []
    centre = hits.mean(axis=0)
    hit_radius = float(np.linalg.norm(hits - centre, axis=1).max())
    axis = centre - origin
    axis_length = float(np.linalg.norm(axis))
    unit = axis / max(axis_length, 1e-9)
    offsets = np.array([other.center for other in others]) - origin
    radii = np.linalg.norm(np.array([other.dimensions for other in others]), axis=1) / 2.0
    along = offsets @ unit
    across = np.linalg.norm(offsets - along[:, None] * unit, axis=1)
    keep = (along - radii < axis_length + hit_radius) & (across < radii + hit_radius)
    return [other for other, kept in zip(others, keep) if kept]


def _blocked_mask(
    origin: npt.NDArray[np.float64],
    hits: npt.NDArray[np.float64],
    others: List[BoundingBox3D],
    meshes: Dict[int, npt.NDArray[np.float64]],
) -> npt.NDArray[np.bool_]:
    """Which segments origin->hit are blocked by ``others``.

    An occluder with a real mesh blocks only where a triangle is crossed (its
    box just selects the candidate segments); one without blocks by its box.
    """
    blocked = np.zeros(len(hits), dtype=bool)
    boxes_only = [other for other in others if other.object_id not in meshes]
    if boxes_only:
        blocked |= _blocked_by_any(origin, hits, boxes_only)
    for other in others:
        soup = meshes.get(other.object_id)
        if soup is None:
            continue
        candidates = _blocked_by_any(origin, hits, [other], MESH_CANDIDATE_SHRINK) & ~blocked
        if candidates.any():
            blocked[candidates] = _segments_hit_triangles(origin, hits[candidates], soup)
    return blocked


def visible_fraction(
    camera: Camera,
    box: BoundingBox3D,
    occluders: List[BoundingBox3D],
    meshes: Optional[Dict[int, npt.NDArray[np.float64]]] = None,
) -> float:
    """Estimated visible share of ``box``'s on-screen area from ``camera``.

    ``occluders`` may include ``box`` itself (it is skipped by ``object_id``).
    ``meshes`` maps an ``object_id`` to its world-space triangles (T, 3, 3); those
    objects are tested against their real shape instead of their box, both as
    the object being measured and as occluders. Returns 0.0 when no camera ray
    through the silhouette hits the object.
    """
    meshes = meshes or {}
    hits = _surface_hits(camera, box, meshes.get(box.object_id))
    if len(hits) == 0:
        return 0.0
    origin = camera.extrinsics.get_translation_vector()
    others = _nearby_occluders(origin, hits, [o for o in occluders if o.object_id != box.object_id])
    if not others:
        return 1.0
    return float(1.0 - _blocked_mask(origin, hits, others, meshes).mean())


def filter_occluded(
    camera: Camera,
    bboxes_2d: List[BoundingBox2D],
    bboxes_3d_by_id: Dict[int, BoundingBox3D],
    minimum: float = MIN_VISIBLE_FRACTION,
    meshes: Optional[Dict[int, npt.NDArray[np.float64]]] = None,
) -> List[BoundingBox2D]:
    """Stamp each 2D box with its occlusion-aware visible fraction and drop the
    boxes below ``minimum`` (objects effectively hidden behind others).

    Every box in ``bboxes_3d_by_id`` counts as a potential occluder, whether or
    not it has a 2D box of its own; ``meshes`` gives some of them a real shape.
    """
    occluders = list(bboxes_3d_by_id.values())
    kept: List[BoundingBox2D] = []
    for bbox_2d in bboxes_2d:
        bbox_3d = bboxes_3d_by_id.get(bbox_2d.object_id)
        if bbox_3d is None:
            kept.append(bbox_2d)
            continue
        fraction = visible_fraction(camera, bbox_3d, occluders, meshes)
        if fraction >= minimum:
            kept.append(replace(bbox_2d, visible_fraction=fraction))
    return kept
