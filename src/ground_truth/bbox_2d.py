"""2D bounding box extraction: project a 3D box into camera image space.

Implements MASTER_PROMPT Section 3.6's "Bounding Box extraction (...2D)"
bullet, informed by QOL_RESEARCH_CHECKLIST.md Section F.1's "2D boxes
within image bounds" and "Visibility flag is correct" checks.
"""

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import numpy.typing as npt

from src.ground_truth.bbox_3d import BoundingBox3D
from src.sensors.camera_model import Camera


@dataclass(frozen=True)
class BoundingBox2D:  # pylint: disable=too-many-instance-attributes
    """A 2D bounding box in image pixel coordinates.

    Attributes
    ----------
    object_id : int
        Identifies the source 3D object.
    x_min, y_min, x_max, y_max : float
        Box corners in pixels, clipped to the camera's image bounds.
        Guaranteed ``x_min < x_max`` and ``y_min < y_max``.
    visibility : float
        Fraction (0.0-1.0) of the 3D box's 8 corners that both project in
        front of the camera and land within the image bounds. This is a
        coarse, corner-sampled visibility measure -- it does not account
        for occlusion by other objects (no z-buffer/renderer exists in
        this codebase; see KNOWN_GAPS_AND_ISSUES.md) -- only for the box
        being partly or wholly outside the camera's view.
    visible_fraction : float
        Fraction (0.0-1.0) of the object that has a clear line of sight to
        the camera, accounting for occlusion by other objects (see
        ``src.ground_truth.occlusion``). 1.0 until that module has measured
        it.
    truncation : float
        Fraction (0.0-1.0) of the object's full projected extent that lies outside
        the image (0.0 when it is entirely in frame). The box itself is clipped to
        the image.
    """

    object_id: int
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    visibility: float
    visible_fraction: float = 1.0
    truncation: float = 0.0

    def __post_init__(self) -> None:
        if self.x_min >= self.x_max:
            raise ValueError(f"x_min ({self.x_min}) must be < x_max ({self.x_max})")
        if self.y_min >= self.y_max:
            raise ValueError(f"y_min ({self.y_min}) must be < y_max ({self.y_max})")
        if not 0.0 <= self.visibility <= 1.0:
            raise ValueError(f"visibility must be in [0, 1], got {self.visibility}")
        if not 0.0 <= self.visible_fraction <= 1.0:
            raise ValueError(f"visible_fraction must be in [0, 1], got {self.visible_fraction}")
        if not 0.0 <= self.truncation <= 1.0:
            raise ValueError(f"truncation must be in [0, 1], got {self.truncation}")

    @property
    def area(self) -> float:
        """The box's pixel area (width * height)."""
        return (self.x_max - self.x_min) * (self.y_max - self.y_min)


def truncation_fraction(clipped_area: float, full_area: float) -> float:
    """Share of a box's full area lost to clipping at the image edge (0.0 if it has no area)."""
    if full_area <= 0.0:
        return 0.0
    return float(min(max(1.0 - clipped_area / full_area, 0.0), 1.0))


def project_bbox_3d_to_2d(  # pylint: disable=too-many-locals
    camera: Camera, bbox_3d: BoundingBox3D
) -> Optional[BoundingBox2D]:
    """Project a 3D box's 8 corners into image space and take their
    axis-aligned enclosing rectangle, clipped to the image bounds.

    Returns
    -------
    Optional[BoundingBox2D]
        ``None`` if every corner is behind the camera (nothing to show),
        or if the corners that *are* in front all project outside the
        image bounds (the projected rectangle would have zero area after
        clipping).
    """
    corners = bbox_3d.corners()

    projected_pixels: List[npt.NDArray[np.float64]] = []
    in_bounds_count = 0

    for corner in corners:
        pixel, depth = camera.project(corner)
        if pixel is None:
            continue
        projected_pixels.append(pixel)
        if depth > 0 and camera.is_pixel_in_bounds(pixel):
            in_bounds_count += 1

    if not projected_pixels:
        return None

    visibility = in_bounds_count / len(corners)

    pixels_array = np.array(projected_pixels)
    full_area = float(np.prod(pixels_array.max(axis=0) - pixels_array.min(axis=0)))
    x_min = float(np.clip(pixels_array[:, 0].min(), 0, camera.intrinsics.width))
    x_max = float(np.clip(pixels_array[:, 0].max(), 0, camera.intrinsics.width))
    y_min = float(np.clip(pixels_array[:, 1].min(), 0, camera.intrinsics.height))
    y_max = float(np.clip(pixels_array[:, 1].max(), 0, camera.intrinsics.height))

    if x_max <= x_min or y_max <= y_min:
        return None
    truncation = truncation_fraction((x_max - x_min) * (y_max - y_min), full_area)

    return BoundingBox2D(
        object_id=bbox_3d.object_id,
        x_min=x_min,
        y_min=y_min,
        x_max=x_max,
        y_max=y_max,
        visibility=visibility,
        truncation=truncation,
    )


def project_bboxes_3d_to_2d(camera: Camera, bboxes_3d: List[BoundingBox3D]) -> List[BoundingBox2D]:
    """Project every 3D box that has any visible portion into 2D.

    Boxes entirely behind the camera or entirely outside the image bounds
    are omitted (matching QOL_RESEARCH_CHECKLIST.md Section F.1's "Box
    count matches objects" -- only *visible* objects should have
    annotations).
    """
    projected = (project_bbox_3d_to_2d(camera, bbox) for bbox in bboxes_3d)
    return [bbox_2d for bbox_2d in projected if bbox_2d is not None]
