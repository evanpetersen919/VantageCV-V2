"""Pinhole camera model: intrinsics, extrinsics, and world-to-image projection.

Implements MASTER_PROMPT Section 3.6's "Camera projection matrix
computation" bullet. As with prior phases, MASTER_PROMPT gives no
formulas for this phase; the standard pinhole camera model below is
informed directly by QOL_RESEARCH_CHECKLIST.md Section E.1's own test
signatures (``get_intrinsic_matrix``, ``get_rotation_matrix``, a
translation vector, and a ``project`` operation).

Coordinate conventions
-----------------------
World frame: the same [x, y] ground-plane frame used throughout
``src/procedural/`` (x right, y "up" on the ground plane, i.e. what a
top-down map would call north), extended with z as height above ground
(matching ``mesh_factory.py``'s z=0 road plane / z=height building tops).

Camera frame: standard computer-vision convention -- +x right, +y down,
+z forward (out of the lens, into the scene). A world point is visible
only if its camera-frame z > 0 (in front of the camera); this is checked
explicitly rather than assumed, since perspective division by a
non-positive z is meaningless.

Lens distortion: ``CameraIntrinsics.distortion_coeffs`` (Brown-Conrady,
the model ``configs/sensor_profiles/camera_front.yaml``/``camera_rear
.yaml`` declare -- see KNOWN_GAPS_AND_ISSUES.md) is optional and defaults
to ``None`` (no distortion), so every pre-existing caller/test keeps
behaving exactly as before. Every real sensor profile shipped in this
repo happens to use all-zero coefficients anyway (a genuinely undistorted
lens is a reasonable default, not a placeholder this module is hiding),
so this only changes behavior for a caller that explicitly opts in with
nonzero coefficients.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import numpy.typing as npt

# Brown-Conrady distortion coefficients, in OpenCV's own (k1, k2, p1, p2,
# k3) order: k1/k2/k3 are radial terms, p1/p2 are tangential terms.
DistortionCoeffs = Tuple[float, float, float, float, float]


def _apply_distortion(
    normalized: npt.NDArray[np.float64], coeffs: DistortionCoeffs
) -> npt.NDArray[np.float64]:
    """Apply Brown-Conrady distortion to a normalized (pre-intrinsics)
    image-plane point ``[x, y] = point_camera[:2] / depth``.

    Standard OpenCV formulation::

        r2 = x^2 + y^2
        radial = 1 + k1*r2 + k2*r2^2 + k3*r2^3
        x' = x*radial + 2*p1*x*y + p2*(r2 + 2*x^2)
        y' = y*radial + p1*(r2 + 2*y^2) + 2*p2*x*y
    """
    k1, k2, p1, p2, k3 = coeffs
    x, y = normalized[0], normalized[1]
    r2 = x * x + y * y
    radial = 1.0 + k1 * r2 + k2 * r2**2 + k3 * r2**3

    x_distorted = x * radial + 2.0 * p1 * x * y + p2 * (r2 + 2.0 * x * x)
    y_distorted = y * radial + p1 * (r2 + 2.0 * y * y) + 2.0 * p2 * x * y
    return np.array([x_distorted, y_distorted])


@dataclass(frozen=True)
class CameraIntrinsics:
    """Pinhole camera intrinsic parameters.

    Attributes
    ----------
    focal_length_x, focal_length_y : float
        Focal length in pixels along each axis. Equal for square pixels
        (the common case, and what QOL_RESEARCH_CHECKLIST.md Section
        E.1's own test checks for).
    principal_point_x, principal_point_y : float
        Principal point in pixels, normally near the image center.
    width, height : int
        Image resolution in pixels.
    distortion_coeffs : Optional[DistortionCoeffs]
        Brown-Conrady (k1, k2, p1, p2, k3) lens distortion coefficients,
        or ``None`` (default) for an ideal undistorted pinhole lens.
    """

    focal_length_x: float
    focal_length_y: float
    principal_point_x: float
    principal_point_y: float
    width: int
    height: int
    distortion_coeffs: Optional[DistortionCoeffs] = None

    def __post_init__(self) -> None:
        if self.focal_length_x <= 0 or self.focal_length_y <= 0:
            raise ValueError("Focal length must be positive")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Image width/height must be positive")

    def get_intrinsic_matrix(self) -> npt.NDArray[np.float64]:
        """The 3x3 intrinsic matrix K, standard pinhole form::

        [fx   0  cx]
        [ 0  fy  cy]
        [ 0   0   1]
        """
        return np.array(
            [
                [self.focal_length_x, 0.0, self.principal_point_x],
                [0.0, self.focal_length_y, self.principal_point_y],
                [0.0, 0.0, 1.0],
            ]
        )

    @classmethod
    def from_fov(
        cls,
        horizontal_fov_deg: float,
        width: int,
        height: int,
        distortion_coeffs: Optional[DistortionCoeffs] = None,
    ) -> "CameraIntrinsics":
        """Construct intrinsics from a horizontal field of view, assuming
        square pixels and a centered principal point.

        Mathematical formula::

            fx = (width / 2) / tan(hfov / 2)
            fy = fx  (square pixels)
        """
        half_fov_rad = np.radians(horizontal_fov_deg) / 2.0
        focal_length = (width / 2.0) / np.tan(half_fov_rad)
        return cls(
            focal_length_x=focal_length,
            focal_length_y=focal_length,
            principal_point_x=width / 2.0,
            principal_point_y=height / 2.0,
            width=width,
            height=height,
            distortion_coeffs=distortion_coeffs,
        )


@dataclass(frozen=True)
class CameraExtrinsics:
    """Camera pose: rotation and translation from world frame to camera frame.

    A world point p_world maps to camera frame via
    ``p_camera = R @ (p_world - t)``, i.e. ``t`` is the camera's position
    in world coordinates and ``R`` rotates world-aligned axes into the
    camera's own (right, down, forward) axes.
    """

    rotation: npt.NDArray[np.float64]  # [3, 3]
    translation: npt.NDArray[np.float64]  # [3]

    def __post_init__(self) -> None:
        if self.rotation.shape != (3, 3):
            raise ValueError(f"rotation must be 3x3, got shape {self.rotation.shape}")
        if self.translation.shape != (3,):
            raise ValueError(f"translation must be length 3, got shape {self.translation.shape}")
        should_be_identity = self.rotation @ self.rotation.T
        if not np.allclose(should_be_identity, np.eye(3), atol=1e-6):
            raise ValueError("rotation is not orthogonal (R @ R.T != I)")
        determinant = np.linalg.det(self.rotation)
        if not np.isclose(determinant, 1.0, atol=1e-6):
            raise ValueError(f"rotation is not a proper rotation (det={determinant}, expected 1)")

    def get_rotation_matrix(self) -> npt.NDArray[np.float64]:
        """The 3x3 world-to-camera rotation matrix."""
        return self.rotation

    def get_translation_vector(self) -> npt.NDArray[np.float64]:
        """The camera's position in world coordinates."""
        return self.translation

    def world_to_camera(self, point_world: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Transform a single [x, y, z] world point into camera frame."""
        return self.rotation @ (point_world - self.translation)

    @classmethod
    def looking_at(
        cls,
        camera_position: npt.NDArray[np.float64],
        target: npt.NDArray[np.float64],
        world_up: npt.NDArray[np.float64] = np.array([0.0, 0.0, 1.0]),
    ) -> "CameraExtrinsics":
        """Construct extrinsics for a camera at ``camera_position`` looking
        toward ``target``, with camera-frame +z pointing at the target.

        Standard look-at construction: forward = normalize(target - eye),
        right = normalize(forward x world_up), down = forward x right
        (already unit since forward/right are orthonormal).
        """
        forward = target - camera_position
        forward_norm = np.linalg.norm(forward)
        if forward_norm < 1e-9:
            raise ValueError("camera_position and target must not coincide")
        forward = forward / forward_norm

        right = np.cross(forward, world_up)
        right_norm = np.linalg.norm(right)
        if right_norm < 1e-9:
            raise ValueError("forward direction is parallel to world_up; ambiguous orientation")
        right = right / right_norm

        down = np.cross(forward, right)

        rotation = np.vstack([right, down, forward])
        return cls(rotation=rotation, translation=camera_position)


class Camera:
    """A camera combining intrinsics and extrinsics, with world-to-image
    projection."""

    def __init__(self, intrinsics: CameraIntrinsics, extrinsics: CameraExtrinsics) -> None:
        self.intrinsics = intrinsics
        self.extrinsics = extrinsics

    def project(
        self, point_world: npt.NDArray[np.float64]
    ) -> Tuple[Optional[npt.NDArray[np.float64]], float]:
        """Project a single world point into image pixel coordinates.

        Returns
        -------
        pixel, depth : Tuple[Optional[npt.NDArray[np.float64]], float]
            ``pixel`` is the [u, v] image coordinate, or ``None`` if the
            point is behind the camera (camera-frame z <= 0), where
            projection is undefined. ``depth`` is the camera-frame z
            (distance along the optical axis), always returned (even when
            ``pixel`` is None) since callers may want it for occlusion
            reasoning regardless.
        """
        point_camera = self.extrinsics.world_to_camera(point_world)
        depth = float(point_camera[2])

        if depth <= 0:
            return None, depth

        normalized = point_camera[:2] / depth
        if self.intrinsics.distortion_coeffs is not None:
            normalized = _apply_distortion(normalized, self.intrinsics.distortion_coeffs)

        k = self.intrinsics.get_intrinsic_matrix()
        pixel_homogeneous = k @ np.array([normalized[0], normalized[1], 1.0])
        pixel = pixel_homogeneous[:2]

        return pixel, depth

    def is_pixel_in_bounds(self, pixel: npt.NDArray[np.float64]) -> bool:
        """True if ``pixel`` falls within the camera's image dimensions."""
        return bool(
            0 <= pixel[0] <= self.intrinsics.width and 0 <= pixel[1] <= self.intrinsics.height
        )
