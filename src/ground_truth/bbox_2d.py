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
class BoundingBox2D:
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
    """

    object_id: int
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    visibility: float

    def __post_init__(self) -> None:
        if self.x_min >= self.x_max:
            raise ValueError(f"x_min ({self.x_min}) must be < x_max ({self.x_max})")
        if self.y_min >= self.y_max:
            raise ValueError(f"y_min ({self.y_min}) must be < y_max ({self.y_max})")
        if not 0.0 <= self.visibility <= 1.0:
            raise ValueError(f"visibility must be in [0, 1], got {self.visibility}")

    @property
    def area(self) -> float:
        """The box's pixel area (width * height)."""
        return (self.x_max - self.x_min) * (self.y_max - self.y_min)


def project_bbox_3d_to_2d(camera: Camera, bbox_3d: BoundingBox3D) -> Optional[BoundingBox2D]:
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
    x_min = float(np.clip(pixels_array[:, 0].min(), 0, camera.intrinsics.width))
    x_max = float(np.clip(pixels_array[:, 0].max(), 0, camera.intrinsics.width))
    y_min = float(np.clip(pixels_array[:, 1].min(), 0, camera.intrinsics.height))
    y_max = float(np.clip(pixels_array[:, 1].max(), 0, camera.intrinsics.height))

    if x_max <= x_min or y_max <= y_min:
        return None

    return BoundingBox2D(
        object_id=bbox_3d.object_id,
        x_min=x_min,
        y_min=y_min,
        x_max=x_max,
        y_max=y_max,
        visibility=visibility,
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
