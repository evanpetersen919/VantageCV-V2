"""LiDAR simulation via ray-casting against generated mesh geometry.

Implements MASTER_PROMPT Section 3.6's "LiDAR ray-casting implementation"
bullet, informed by QOL_RESEARCH_CHECKLIST.md Section E.2's test
requirements (points within max range, count vs. resolution, no
duplicates, azimuth/elevation coverage).

Unlike UE5-dependent phases, this is real physics simulation against the
same ``Mesh`` triangle buffers ``mesh_factory.py`` already produces for
roads and buildings -- ray-triangle intersection (Moeller-Trumbore) is
pure geometry, fully testable without any UE5 install.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import numpy.typing as npt

from src.procedural.mesh_factory import Mesh

# Degenerate-ray/triangle threshold for the Moeller-Trumbore determinant
# check (a near-zero determinant means the ray is (nearly) parallel to
# the triangle's plane -- no well-defined single intersection point).
_EPSILON = 1e-9


@dataclass(frozen=True)
class LidarConfig:
    """LiDAR sensor configuration.

    Attributes
    ----------
    channels : int
        Number of vertical scan lines (rows).
    horizontal_resolution_deg : float
        Angular spacing between consecutive azimuth samples, in degrees.
    vertical_fov_deg : Tuple[float, float]
        (min, max) elevation angle in degrees, 0 = horizontal,
        positive = up.
    max_range_m : float
        Maximum sensing range in meters; rays that don't hit anything
        within this range produce no point.
    """

    channels: int
    horizontal_resolution_deg: float
    vertical_fov_deg: Tuple[float, float]
    max_range_m: float

    def __post_init__(self) -> None:
        if self.channels <= 0:
            raise ValueError("channels must be positive")
        if self.horizontal_resolution_deg <= 0:
            raise ValueError("horizontal_resolution_deg must be positive")
        if self.max_range_m <= 0:
            raise ValueError("max_range_m must be positive")
        if self.vertical_fov_deg[0] > self.vertical_fov_deg[1]:
            raise ValueError("vertical_fov_deg must satisfy min <= max")

    @property
    def horizontal_samples(self) -> int:
        """Number of azimuth samples in a full 360-degree sweep."""
        return int(round(360.0 / self.horizontal_resolution_deg))


def ray_triangle_intersect(
    origin: npt.NDArray[np.float64],
    direction: npt.NDArray[np.float64],
    v0: npt.NDArray[np.float64],
    v1: npt.NDArray[np.float64],
    v2: npt.NDArray[np.float64],
) -> Optional[float]:
    """Moeller-Trumbore ray-triangle intersection.

    Parameters
    ----------
    origin : npt.NDArray[np.float64]
        Ray origin, [3].
    direction : npt.NDArray[np.float64]
        Ray direction, [3]. Need not be normalized; the returned distance
        ``t`` is in units of ``direction``'s own length (``origin + t *
        direction`` is the hit point either way).
    v0, v1, v2 : npt.NDArray[np.float64]
        Triangle vertices, each [3].

    Returns
    -------
    Optional[float]
        Distance ``t`` along ``direction`` to the intersection point, or
        ``None`` if the ray doesn't hit the triangle (parallel to its
        plane, intersects outside the triangle's edges, or intersects
        behind the ray origin).
    """
    edge1 = v1 - v0
    edge2 = v2 - v0
    h = np.cross(direction, edge2)
    determinant = np.dot(edge1, h)

    if abs(determinant) < _EPSILON:
        return None

    inverse_determinant = 1.0 / determinant
    s = origin - v0
    u = inverse_determinant * np.dot(s, h)
    if u < 0.0 or u > 1.0:
        return None

    q = np.cross(s, edge1)
    v = inverse_determinant * np.dot(direction, q)
    if v < 0.0 or u + v > 1.0:
        return None

    t = inverse_determinant * np.dot(edge2, q)
    if t <= _EPSILON:
        return None

    return float(t)


def closest_hit_distance(
    origin: npt.NDArray[np.float64], direction: npt.NDArray[np.float64], meshes: List[Mesh]
) -> Optional[float]:
    """The distance to the nearest ray-mesh intersection across every
    triangle of every mesh, or None if the ray hits nothing.

    Public (not module-private) because ``depth_map.py`` reuses this same
    ray-casting primitive for per-pixel depth rendering.
    """
    closest: Optional[float] = None
    for mesh in meshes:
        for i in range(0, len(mesh.triangles), 3):
            v0 = mesh.vertices[mesh.triangles[i]]
            v1 = mesh.vertices[mesh.triangles[i + 1]]
            v2 = mesh.vertices[mesh.triangles[i + 2]]
            hit = ray_triangle_intersect(origin, direction, v0, v1, v2)
            if hit is not None and (closest is None or hit < closest):
                closest = hit
    return closest


class LidarSensor:  # pylint: disable=too-few-public-methods
    """Simulate one LiDAR sweep via ray-casting against a scene's meshes.

    Exposes a single public entry point (``scan``) by design; the rest of
    the class is private implementation detail of that operation.
    """

    def __init__(self, config: LidarConfig) -> None:
        self.config = config

    def scan(self, origin: npt.NDArray[np.float64], meshes: List[Mesh]) -> npt.NDArray[np.float64]:
        """Cast one full sweep of rays from ``origin`` and collect hit
        points, in the sensor's own frame (origin-relative, not world
        coordinates -- matching how a real LiDAR reports points relative
        to itself).

        Parameters
        ----------
        origin : npt.NDArray[np.float64]
            Sensor position in world coordinates, [3].
        meshes : List[Mesh]
            Scene geometry to raycast against.

        Returns
        -------
        npt.NDArray[np.float64]
            [N, 3] array of hit points, sensor-relative. N <=
            ``channels * horizontal_samples``; rays that hit nothing
            within ``max_range_m`` produce no point (a real LiDAR doesn't
            report a point for a miss either).
        """
        azimuths = np.radians(np.linspace(0, 360, self.config.horizontal_samples, endpoint=False))
        elevations = np.radians(
            np.linspace(
                self.config.vertical_fov_deg[0],
                self.config.vertical_fov_deg[1],
                self.config.channels,
            )
        )

        points: List[npt.NDArray[np.float64]] = []
        for elevation in elevations:
            for azimuth in azimuths:
                direction = np.array(
                    [
                        np.cos(elevation) * np.cos(azimuth),
                        np.cos(elevation) * np.sin(azimuth),
                        np.sin(elevation),
                    ]
                )
                distance = closest_hit_distance(origin, direction, meshes)
                if distance is not None and distance <= self.config.max_range_m:
                    points.append(direction * distance)

        if not points:
            return np.zeros((0, 3))
        return np.array(points)
