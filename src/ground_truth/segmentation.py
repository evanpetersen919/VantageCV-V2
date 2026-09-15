"""Instance segmentation mask generation from generated buildings.

Implements MASTER_PROMPT Section 3.6's "Segmentation mask generation"
bullet, informed by QOL_RESEARCH_CHECKLIST.md Section F.2 (no empty
masks, instance masks don't overlap, mask-annotation alignment).

Silhouette: a building is a convex box (see ``building_placement.py``,
``mesh_factory.py``), and the perspective projection of a convex
polyhedron's silhouette is exactly the convex hull of its projected
vertices -- a real geometric fact, not an approximation, for this
specific (box) shape. So each object's on-screen silhouette is computed
as the convex hull of its 8 projected corners, then rasterized.

Occlusion: resolved via a painter's algorithm -- objects are rasterized
farthest-to-nearest by center depth, with each subsequent (nearer)
object's pixels overwriting any farther object already assigned there.
This is only correct because every object here is convex and axis-
aligned-box-shaped; occlusion *within* an object's own silhouette (e.g. a
building blocking part of itself from certain angles) doesn't arise for
a convex shape, so per-object center-depth ordering is sufficient --
that would not hold for concave geometry.

Performance: each object's point-in-polygon test (via
``matplotlib.path.Path.contains_points``) only runs over its own
projected silhouette's pixel bounding box, clipped to the image -- not
the full ``width * height`` image, since every pixel outside that box is
trivially outside the (convex) silhouette too. An *exact* optimization,
not an approximation (verified directly against a brute-force
full-image reference in tests): for a small object in a large frame this
is a two-to-three-order-of-magnitude reduction in points tested, closing
the gap KNOWN_GAPS_AND_ISSUES.md flagged here (this was previously one
full-image pass per object regardless of how much screen space it
actually covered).
"""

from typing import Dict, List, Optional

import numpy as np
import numpy.typing as npt
from matplotlib.path import Path
from scipy.spatial import ConvexHull, QhullError  # pylint: disable=no-name-in-module

from src.ground_truth.bbox_3d import BoundingBox3D
from src.sensors.camera_model import Camera


def compute_silhouette(camera: Camera, bbox_3d: BoundingBox3D) -> Optional[npt.NDArray[np.float64]]:
    """Compute the 2D convex-hull silhouette of a 3D box's projection.

    Returns
    -------
    Optional[npt.NDArray[np.float64]]
        [K, 2] convex hull vertices in pixel coordinates, or ``None`` if
        fewer than 3 corners project in front of the camera (no
        well-defined 2D silhouette), or if the projected points are
        degenerate (collinear -- zero-area hull).
    """
    corners = bbox_3d.corners()
    projected: List[npt.NDArray[np.float64]] = []
    for corner in corners:
        pixel, depth = camera.project(corner)
        if pixel is not None and depth > 0:
            projected.append(pixel)

    if len(projected) < 3:
        return None

    points = np.array(projected)
    if len(points) == 3:
        return points

    try:
        hull = ConvexHull(points)
    except QhullError:
        return None
    return np.asarray(points[hull.vertices], dtype=np.float64)


def _paint_silhouette(
    owner: npt.NDArray[np.int64],
    silhouette: npt.NDArray[np.float64],
    object_id: int,
    width: int,
    height: int,
) -> None:
    """Assign ``object_id`` into ``owner`` (in place) at every pixel
    inside ``silhouette``, testing only ``silhouette``'s own projected
    pixel bounding box (clipped to the image) rather than every pixel of
    the full image -- every point outside that box is trivially outside
    a convex silhouette too, so this is exact, not approximate (see
    module docstring)."""
    x_min = max(0, int(np.floor(silhouette[:, 0].min())))
    x_max = min(width, int(np.ceil(silhouette[:, 0].max())))
    y_min = max(0, int(np.floor(silhouette[:, 1].min())))
    y_max = min(height, int(np.ceil(silhouette[:, 1].max())))
    if x_min >= x_max or y_min >= y_max:
        return  # silhouette's bbox doesn't overlap the image at all

    xx, yy = np.meshgrid(np.arange(x_min, x_max) + 0.5, np.arange(y_min, y_max) + 0.5)
    pixel_centers = np.column_stack([xx.ravel(), yy.ravel()])

    path = Path(silhouette)
    inside = path.contains_points(pixel_centers).reshape(y_max - y_min, x_max - x_min)
    owner[y_min:y_max, x_min:x_max][inside] = object_id


def rasterize_instance_masks(  # pylint: disable=too-many-locals
    camera: Camera, bboxes_3d: List[BoundingBox3D]
) -> Dict[int, npt.NDArray[np.bool_]]:
    """Rasterize per-object instance segmentation masks with occlusion.

    Parameters
    ----------
    camera : Camera
    bboxes_3d : List[BoundingBox3D]

    Returns
    -------
    ``Dict[int, npt.NDArray[np.bool_]]``
        ``object_id -> [height, width]`` boolean mask, one entry per
        object with at least one visible pixel after occlusion
        resolution. Objects fully occluded or entirely out of frame are
        omitted (never an empty-but-present mask -- see module
        docstring's QOL Section F.2 reference).
    """
    width, height = camera.intrinsics.width, camera.intrinsics.height

    objects_with_depth = []
    for bbox in bboxes_3d:
        silhouette = compute_silhouette(camera, bbox)
        if silhouette is None:
            continue
        _, center_depth = camera.project(bbox.center)
        objects_with_depth.append((center_depth, bbox.object_id, silhouette))

    # Farthest first, so a nearer object's assignment (processed later)
    # overwrites a farther object already painted at the same pixel.
    objects_with_depth.sort(key=lambda entry: -entry[0])

    owner = np.full((height, width), -1, dtype=np.int64)
    for _, object_id, silhouette in objects_with_depth:
        _paint_silhouette(owner, silhouette, object_id, width, height)

    masks: Dict[int, npt.NDArray[np.bool_]] = {}
    for _, object_id, _ in objects_with_depth:
        mask = owner == object_id
        if mask.any():
            masks[object_id] = mask

    return masks
