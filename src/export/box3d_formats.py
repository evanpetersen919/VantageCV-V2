"""3D boxes in the camera frame, and the KITTI label and calibration text built from them.

This project's camera frame (``src/sensors/camera_model.py``: x right, y down, z forward,
``p_cam = R (p_world - t)``) is KITTI's camera frame, so the conversion is exact geometry:

* ``location`` is the bottom centre of the box (KITTI's y axis points down, so the bottom face has
  the larger y);
* ``dimensions_hwl`` are height, width, length (KITTI's order; this project stores length, width,
  height);
* ``rotation_y`` is the heading about the camera's down axis. An object whose forward direction is
  the camera's forward direction (it drives away along the line of sight) has
  ``rotation_y = -pi/2``;
* ``alpha`` is the observation angle, ``rotation_y - atan2(x, z)`` wrapped to [-pi, pi].

KITTI assumes a level camera, so labels are written in the *level* camera frame: the camera's own
frame turned about its right axis (and rolled) until its down axis is gravity, keeping its yaw and
position. For a level camera this is the camera's own frame. For a pitched one the projection
matrix carries the rotation back, ``P = K R R_level^T``, so ``P`` applied to a label-frame point
gives its true pixel: the labels stay exact (``rotation_y`` is a rotation about the vertical) and
the round trip through ``P`` is exact. The cost is that ``P`` is not of the pure ``[K | 0]`` form
for a pitched camera.
"""

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np
import numpy.typing as npt

from src.ground_truth.bbox_3d import BoundingBox3D
from src.sensors.camera_model import Camera

# Which KITTI type each of this project's COCO class names becomes. KITTI has no bus class.
KITTI_TYPES = {"car": "Car", "truck": "Truck", "bus": "Misc", "person": "Pedestrian"}


@dataclass(frozen=True)
class CameraBox3D:
    """One 3D box in the camera frame, in KITTI's conventions."""

    location: Tuple[float, float, float]  # bottom centre, metres
    dimensions_hwl: Tuple[float, float, float]  # height, width, length, metres
    rotation_y: float  # radians, [-pi, pi]
    alpha: float  # radians, [-pi, pi]

    def to_dict(self) -> Dict[str, Any]:
        """Plain values for JSON."""
        return {k: (list(v) if isinstance(v, tuple) else v) for k, v in asdict(self).items()}


def _wrap(angle: float) -> float:
    """``angle`` wrapped to [-pi, pi]."""
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


MIN_HORIZONTAL_FORWARD = 0.1  # a camera tilted more than about 84 degrees has no usable level frame


def has_level_frame(camera: Camera) -> bool:
    """False for cameras that look (almost) straight up or down, such as an overview camera."""
    forward = camera.extrinsics.get_rotation_matrix()[2]
    return float(np.hypot(forward[0], forward[1])) >= MIN_HORIZONTAL_FORWARD


def level_rotation(camera: Camera) -> npt.NDArray[np.float64]:
    """World-to-label-frame rotation: rows are right, down (gravity), forward (the heading)."""
    forward = camera.extrinsics.get_rotation_matrix()[2].copy()  # camera forward, in world axes
    horizontal = np.array([forward[0], forward[1], 0.0])
    norm = np.linalg.norm(horizontal)
    if norm < 1e-9:
        raise ValueError("the camera looks straight up or down; there is no level frame")
    horizontal /= norm
    down = np.array([0.0, 0.0, -1.0])
    right = np.cross(horizontal, -down)  # forward x up
    return np.vstack([right, down, horizontal])


def camera_box(camera: Camera, box: BoundingBox3D) -> CameraBox3D:
    """``box`` (world frame) as a KITTI-convention box in ``camera``'s level frame."""
    length, width, height = (float(v) for v in box.dimensions)
    bottom_world = np.array([box.center[0], box.center[1], box.center[2] - height / 2.0])
    rotation = level_rotation(camera)
    x, y, z = (
        float(v) for v in rotation @ (bottom_world - camera.extrinsics.get_translation_vector())
    )
    forward_world = np.array([math.cos(box.heading_rad), math.sin(box.heading_rad), 0.0])
    forward_cam = rotation @ forward_world
    rotation_y = math.atan2(-forward_cam[2], forward_cam[0])
    alpha = _wrap(rotation_y - math.atan2(x, z))
    return CameraBox3D(
        location=(x, y, z),
        dimensions_hwl=(height, width, length),
        rotation_y=rotation_y,
        alpha=alpha,
    )


def projection_matrix(camera: Camera) -> npt.NDArray[np.float64]:
    """KITTI's 3x4 projection matrix ``P`` for label-frame points: ``K R R_level^T`` with a zero
    fourth column (for a level camera, exactly ``K``)."""
    matrix = np.zeros((3, 4))
    back = camera.extrinsics.get_rotation_matrix() @ level_rotation(camera).T
    matrix[:, :3] = camera.intrinsics.get_intrinsic_matrix() @ back
    return matrix


def _row(values: npt.NDArray[np.float64]) -> str:
    return " ".join(f"{v:.12e}" for v in values.reshape(-1))


def kitti_calibration(camera: Camera) -> str:
    """The text of one KITTI ``calib`` file for ``camera`` (see ``calibration_text``)."""
    return calibration_text(projection_matrix(camera))


def calibration_text(projection: npt.NDArray[np.float64]) -> str:
    """The text of a KITTI ``calib`` file for a 3x4 ``projection``.

    ``P0``-``P3`` are all that matrix (no stereo rig), ``R0_rect`` is the identity, and the two
    ``Tr`` matrices are identity placeholders (no LiDAR is generated).
    """
    p_row = f"{_row(projection)}"
    identity_rect = _row(np.eye(3))
    identity_tr = _row(np.hstack([np.eye(3), np.zeros((3, 1))]))
    return (
        "\n".join(
            [
                f"P0: {p_row}",
                f"P1: {p_row}",
                f"P2: {p_row}",
                f"P3: {p_row}",
                f"R0_rect: {identity_rect}",
                f"Tr_velo_to_cam: {identity_tr}",
                f"Tr_imu_to_velo: {identity_tr}",
            ]
        )
        + "\n"
    )


def occluded_level(visibility_fraction: float) -> int:
    """KITTI occlusion level from the visible fraction: 0 above 0.9, 1 above 0.6, else 2."""
    if visibility_fraction > 0.9:
        return 0
    if visibility_fraction > 0.6:
        return 1
    return 2


def kitti_label_line(  # pylint: disable=too-many-arguments
    kitti_type: str,
    truncated: float,
    visibility_fraction: float,
    bbox_xywh: Tuple[float, float, float, float],
    box: CameraBox3D,
    score: Optional[float] = None,
) -> str:
    """One line of a KITTI ``label_2`` file (15 fields, 16 with a detection ``score``)."""
    x1, y1 = bbox_xywh[0], bbox_xywh[1]
    x2, y2 = x1 + bbox_xywh[2], y1 + bbox_xywh[3]
    fields = [
        kitti_type,
        f"{min(max(truncated, 0.0), 1.0):.2f}",
        str(occluded_level(visibility_fraction)),
        f"{box.alpha:.2f}",
        f"{x1:.2f}",
        f"{y1:.2f}",
        f"{x2:.2f}",
        f"{y2:.2f}",
        *(f"{v:.2f}" for v in box.dimensions_hwl),
        *(f"{v:.2f}" for v in box.location),
        f"{box.rotation_y:.2f}",
    ]
    if score is not None:
        fields.append(f"{score:.2f}")
    return " ".join(fields)
