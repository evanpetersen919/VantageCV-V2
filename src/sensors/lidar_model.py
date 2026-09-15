"""LiDAR simulation via ray-casting against generated mesh geometry.

Implements MASTER_PROMPT Section 3.6's "LiDAR ray-casting implementation"
bullet, informed by QOL_RESEARCH_CHECKLIST.md Section E.2's test
requirements (points within max range, count vs. resolution, no
duplicates, azimuth/elevation coverage).

Unlike UE5-dependent phases, this is real physics simulation against the
same ``Mesh`` triangle buffers ``mesh_factory.py`` already produces for
roads and buildings -- ray-triangle intersection (Moeller-Trumbore) is
pure geometry, fully testable without any UE5 install.

Spatial acceleration: ``closest_hit_distance`` (brute-force, tests every
triangle of every mesh) is kept as the simple/reference implementation,
but ``LidarSensor.scan`` and ``depth_map.render_depth_map`` both instead
build one ``TriangleGrid`` per scene and reuse it across every ray of the
sweep/image -- closing KNOWN_GAPS_AND_ISSUES.md's "no spatial
acceleration structure" gap, which previously forced both modules' own
tests to keep scenes artificially tiny. ``TriangleGrid`` is an *exact*
acceleration structure (Amanatides & Woo's 1987 uniform-grid voxel
traversal algorithm), not an approximation -- every query is verified
(directly, in tests) to return bit-identical results to
``closest_hit_distance`` on the same scene, just without testing
triangles the ray's own cell-by-cell path never actually passes near.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

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
    range_noise_std_m : float
        Standard deviation (meters) of zero-mean Gaussian noise added to
        each hit's measured range, modeling real rangefinder measurement
        error. Default 0.0 (no noise, exact geometric hits) -- every
        pre-existing caller/test keeps behaving exactly as before.
    """

    channels: int
    horizontal_resolution_deg: float
    vertical_fov_deg: Tuple[float, float]
    max_range_m: float
    range_noise_std_m: float = 0.0

    def __post_init__(self) -> None:
        if self.channels <= 0:
            raise ValueError("channels must be positive")
        if self.horizontal_resolution_deg <= 0:
            raise ValueError("horizontal_resolution_deg must be positive")
        if self.max_range_m <= 0:
            raise ValueError("max_range_m must be positive")
        if self.vertical_fov_deg[0] > self.vertical_fov_deg[1]:
            raise ValueError("vertical_fov_deg must satisfy min <= max")
        if self.range_noise_std_m < 0:
            raise ValueError("range_noise_std_m must be non-negative")

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


Triangle = Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]
Cell = Tuple[int, int, int]

# Degenerate-direction-component threshold for the grid traversal's own
# axis stepping (below this, a ray is treated as never crossing a cell
# boundary along that axis -- same rationale/scale as _EPSILON above).
_DIRECTION_EPSILON = 1e-12

# A flat/degenerate scene (all triangles coplanar on one axis) would
# otherwise produce a zero-extent grid dimension; expanded to this
# minimum so cell-size computation never divides by zero.
_MIN_GRID_EXTENT_M = 1e-6


class TriangleGrid:  # pylint: disable=too-few-public-methods
    """Uniform-grid spatial index over a scene's triangles, for
    accelerated nearest-ray-hit queries -- see this module's own
    docstring for the algorithm and why it exists.

    Exposes a single public entry point (``closest_hit``) by design; the
    rest of the class is private implementation detail of that operation.
    """

    def __init__(  # pylint: disable=too-many-locals
        self, meshes: List[Mesh], target_triangles_per_cell: float = 4.0
    ) -> None:
        """Bin every triangle of every mesh into a uniform 3D grid.

        Parameters
        ----------
        meshes : List[Mesh]
            Scene geometry. Built once per scene, then queried many times
            (one ``TriangleGrid`` per LiDAR sweep or depth-map render,
            not one per ray).
        target_triangles_per_cell : float
            Grid resolution is chosen so each cell holds roughly this
            many triangles on average (via ``cell_size = (scene_volume /
            (triangle_count / target)) ** (1/3)``) -- a standard
            triangle-density heuristic; smaller values mean finer cells
            (more cells to traverse, fewer triangles tested per cell).
        """
        self._triangles: List[Triangle] = [
            (
                mesh.vertices[mesh.triangles[i]],
                mesh.vertices[mesh.triangles[i + 1]],
                mesh.vertices[mesh.triangles[i + 2]],
            )
            for mesh in meshes
            for i in range(0, len(mesh.triangles), 3)
        ]
        if not self._triangles:
            return

        all_vertices = np.array([vertex for triangle in self._triangles for vertex in triangle])
        self._bbox_min: npt.NDArray[np.float64] = all_vertices.min(axis=0)
        bbox_max: npt.NDArray[np.float64] = all_vertices.max(axis=0)
        extent = np.maximum(bbox_max - self._bbox_min, _MIN_GRID_EXTENT_M)

        target_cells = max(1.0, len(self._triangles) / target_triangles_per_cell)
        volume = float(extent[0] * extent[1] * extent[2])
        cell_size = (volume / target_cells) ** (1.0 / 3.0) if volume > 0 else float(extent.max())
        self._cell_size = max(cell_size, _MIN_GRID_EXTENT_M)

        self._dims: Tuple[int, int, int] = tuple(  # type: ignore[assignment]
            max(1, int(np.ceil(extent[axis] / self._cell_size))) for axis in range(3)
        )

        self._cells: Dict[Cell, List[int]] = {}
        for index, (v0, v1, v2) in enumerate(self._triangles):
            cell_min = self._to_cell(np.minimum(np.minimum(v0, v1), v2))
            cell_max = self._to_cell(np.maximum(np.maximum(v0, v1), v2))
            for cx in range(cell_min[0], cell_max[0] + 1):
                for cy in range(cell_min[1], cell_max[1] + 1):
                    for cz in range(cell_min[2], cell_max[2] + 1):
                        self._cells.setdefault((cx, cy, cz), []).append(index)

    def _to_cell(self, point: npt.NDArray[np.float64]) -> Cell:
        relative = (point - self._bbox_min) / self._cell_size
        return (
            int(np.clip(np.floor(relative[0]), 0, self._dims[0] - 1)),
            int(np.clip(np.floor(relative[1]), 0, self._dims[1] - 1)),
            int(np.clip(np.floor(relative[2]), 0, self._dims[2] - 1)),
        )

    def _ray_aabb_intersect(
        self, origin: npt.NDArray[np.float64], direction: npt.NDArray[np.float64]
    ) -> Optional[Tuple[float, float]]:
        """Slab-method ray/grid-bounding-box intersection. Returns the
        ``(t_min, t_max)`` interval where the ray is inside the grid's
        overall bounding box, or ``None`` if it never enters."""
        t_min, t_max = -np.inf, np.inf
        bbox_max = self._bbox_min + np.array(self._dims) * self._cell_size
        for axis in range(3):
            if abs(direction[axis]) < _DIRECTION_EPSILON:
                if not self._bbox_min[axis] <= origin[axis] <= bbox_max[axis]:
                    return None
                continue
            t1 = (self._bbox_min[axis] - origin[axis]) / direction[axis]
            t2 = (bbox_max[axis] - origin[axis]) / direction[axis]
            if t1 > t2:
                t1, t2 = t2, t1
            t_min, t_max = max(t_min, t1), min(t_max, t2)
        if t_min > t_max:
            return None
        return t_min, t_max

    def closest_hit(  # pylint: disable=too-many-locals,too-many-branches
        self,
        origin: npt.NDArray[np.float64],
        direction: npt.NDArray[np.float64],
        max_distance: Optional[float] = None,
    ) -> Optional[float]:
        """The distance to the nearest ray-triangle intersection in this
        scene, or ``None`` if the ray hits nothing (within
        ``max_distance``, if given) -- exact same contract as
        ``closest_hit_distance(origin, direction, meshes)``, just walking
        only the grid cells the ray actually passes through instead of
        testing every triangle.

        Parameters
        ----------
        origin, direction : npt.NDArray[np.float64]
            Same convention as ``ray_triangle_intersect``.
        max_distance : Optional[float]
            If given, hits beyond this distance are treated as misses --
            lets a caller that already has its own range cutoff (e.g.
            ``LidarConfig.max_range_m``) skip searching cells beyond it
            entirely, rather than finding a far hit and discarding it.
        """
        if not self._triangles:
            return None

        interval = self._ray_aabb_intersect(origin, direction)
        if interval is None:
            return None
        t_min, t_max = interval
        if max_distance is not None:
            t_max = min(t_max, max_distance)
        if t_max < max(t_min, 0.0):
            return None

        entry_point = origin + max(t_min, 0.0) * direction
        cell = list(self._to_cell(entry_point))

        step = [0, 0, 0]
        t_delta = [np.inf, np.inf, np.inf]
        t_max_axis = [np.inf, np.inf, np.inf]
        for axis in range(3):
            if direction[axis] > _DIRECTION_EPSILON:
                step[axis] = 1
                boundary = self._bbox_min[axis] + (cell[axis] + 1) * self._cell_size
                t_max_axis[axis] = (boundary - origin[axis]) / direction[axis]
                t_delta[axis] = self._cell_size / direction[axis]
            elif direction[axis] < -_DIRECTION_EPSILON:
                step[axis] = -1
                boundary = self._bbox_min[axis] + cell[axis] * self._cell_size
                t_max_axis[axis] = (boundary - origin[axis]) / direction[axis]
                t_delta[axis] = self._cell_size / -direction[axis]

        best_hit: Optional[float] = None
        tested: Set[int] = set()
        while True:
            current_cell: Cell = (cell[0], cell[1], cell[2])
            for triangle_index in self._cells.get(current_cell, []):
                if triangle_index in tested:
                    continue
                tested.add(triangle_index)
                v0, v1, v2 = self._triangles[triangle_index]
                hit = ray_triangle_intersect(origin, direction, v0, v1, v2)
                if hit is not None and hit <= t_max and (best_hit is None or hit < best_hit):
                    best_hit = hit

            cell_exit_t = min(t_max_axis)
            if best_hit is not None and best_hit <= cell_exit_t:
                break
            if cell_exit_t > t_max:
                break

            axis = t_max_axis.index(cell_exit_t)
            if step[axis] == 0:
                break
            cell[axis] += step[axis]
            if not 0 <= cell[axis] < self._dims[axis]:
                break
            t_max_axis[axis] += t_delta[axis]

        return best_hit


class LidarSensor:  # pylint: disable=too-few-public-methods
    """Simulate one LiDAR sweep via ray-casting against a scene's meshes.

    Exposes a single public entry point (``scan``) by design; the rest of
    the class is private implementation detail of that operation.
    """

    def __init__(self, config: LidarConfig, seed: Optional[int] = None) -> None:
        if config.range_noise_std_m > 0 and seed is None:
            raise ValueError(
                "config.range_noise_std_m > 0 requires an explicit seed for deterministic noise"
            )
        self.config = config
        # Constructed unconditionally (even with seed=None) to keep `rng`
        # a plain Generator rather than Optional[Generator] -- it's only
        # ever read when range_noise_std_m > 0, which __init__ already
        # guarantees means a real seed was given.
        self.rng = np.random.Generator(np.random.PCG64(seed))

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
            report a point for a miss either). If ``config
            .range_noise_std_m > 0``, each hit's measured range has
            zero-mean Gaussian noise added before the ``max_range_m``
            check -- a genuine hit can therefore be dropped (noise pushed
            it past max range or negative) exactly as a real noisy sensor
            would drop it.
        """
        azimuths = np.radians(np.linspace(0, 360, self.config.horizontal_samples, endpoint=False))
        elevations = np.radians(
            np.linspace(
                self.config.vertical_fov_deg[0],
                self.config.vertical_fov_deg[1],
                self.config.channels,
            )
        )
        grid = TriangleGrid(meshes)
        # Only bound the grid search by max_range_m when there's no noise:
        # with range_noise_std_m > 0, a *true* hit just beyond max_range_m
        # can still be reported if noise happens to pull it back within
        # range (a real noisy sensor could do the same), so the search
        # must not be cut off there in that case -- see the noise
        # docstring note below.
        search_limit = None if self.config.range_noise_std_m > 0 else self.config.max_range_m

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
                distance = grid.closest_hit(origin, direction, max_distance=search_limit)
                if distance is None:
                    continue

                if self.config.range_noise_std_m > 0:
                    distance += float(self.rng.normal(0.0, self.config.range_noise_std_m))

                if 0 < distance <= self.config.max_range_m:
                    points.append(direction * distance)

        if not points:
            return np.zeros((0, 3))
        return np.array(points)
