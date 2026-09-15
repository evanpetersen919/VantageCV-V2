"""Unit tests for LiDAR ray-casting.

Covers QOL_RESEARCH_CHECKLIST.md Section E.2: points within max range, no
duplicate points, and ray-triangle intersection correctness directly.

Test LiDAR configs still use small channel counts / coarse resolution:
even with TriangleGrid's spatial acceleration (see lidar_model.py module
docstring), many rays against a real-sensor-scale scan (e.g. 64 channels
x ~2000 azimuth samples) is still real work a unit test shouldn't pay for.
"""

import numpy as np
import pytest

from src.procedural.mesh_factory import Mesh
from src.sensors.lidar_model import (
    LidarConfig,
    LidarSensor,
    TriangleGrid,
    closest_hit_distance,
    ray_triangle_intersect,
)


def _ground_plane_mesh(half_extent: float = 50.0) -> Mesh:
    """A single large quad (2 triangles) lying flat at z=0, big enough
    that every downward-ish ray in these tests hits it."""
    vertices = np.array(
        [
            [-half_extent, -half_extent, 0.0],
            [half_extent, -half_extent, 0.0],
            [half_extent, half_extent, 0.0],
            [-half_extent, half_extent, 0.0],
        ]
    )
    triangles = np.array([0, 1, 2, 0, 2, 3], dtype=np.int64)
    return Mesh(vertices=vertices, triangles=triangles, uvs=np.zeros((4, 2)), material="asphalt")


def test_ray_triangle_intersect_hits_center() -> None:
    """A ray straight down through a triangle's centroid hits it at the
    expected distance."""
    origin = np.array([0.25, 0.25, 5.0])
    direction = np.array([0.0, 0.0, -1.0])
    v0 = np.array([0.0, 0.0, 0.0])
    v1 = np.array([1.0, 0.0, 0.0])
    v2 = np.array([0.0, 1.0, 0.0])

    t = ray_triangle_intersect(origin, direction, v0, v1, v2)

    assert t is not None
    assert np.isclose(t, 5.0)


def test_ray_triangle_intersect_misses_outside_triangle() -> None:
    """A ray that passes outside the triangle's edges returns None."""
    origin = np.array([10.0, 10.0, 5.0])
    direction = np.array([0.0, 0.0, -1.0])
    v0 = np.array([0.0, 0.0, 0.0])
    v1 = np.array([1.0, 0.0, 0.0])
    v2 = np.array([0.0, 1.0, 0.0])

    assert ray_triangle_intersect(origin, direction, v0, v1, v2) is None


def test_ray_triangle_intersect_misses_parallel_ray() -> None:
    """A ray parallel to the triangle's plane (never converges) returns
    None rather than dividing by ~zero."""
    origin = np.array([0.25, 0.25, 5.0])
    direction = np.array([1.0, 0.0, 0.0])
    v0 = np.array([0.0, 0.0, 0.0])
    v1 = np.array([1.0, 0.0, 0.0])
    v2 = np.array([0.0, 1.0, 0.0])

    assert ray_triangle_intersect(origin, direction, v0, v1, v2) is None


def test_ray_triangle_intersect_misses_behind_origin() -> None:
    """A triangle behind the ray's origin (negative t) is not reported as
    a hit."""
    origin = np.array([0.25, 0.25, -5.0])
    direction = np.array([0.0, 0.0, -1.0])
    v0 = np.array([0.0, 0.0, 0.0])
    v1 = np.array([1.0, 0.0, 0.0])
    v2 = np.array([0.0, 1.0, 0.0])

    assert ray_triangle_intersect(origin, direction, v0, v1, v2) is None


def test_lidar_config_rejects_invalid_values() -> None:
    """LidarConfig validates channels, resolution, range, and FOV
    ordering."""
    with pytest.raises(ValueError):
        LidarConfig(0, 10.0, (-10.0, 10.0), 100.0)
    with pytest.raises(ValueError):
        LidarConfig(16, 0.0, (-10.0, 10.0), 100.0)
    with pytest.raises(ValueError):
        LidarConfig(16, 10.0, (-10.0, 10.0), 0.0)
    with pytest.raises(ValueError):
        LidarConfig(16, 10.0, (10.0, -10.0), 100.0)


def test_lidar_horizontal_samples_computed_from_resolution() -> None:
    """horizontal_samples derives correctly from resolution."""
    config = LidarConfig(
        channels=4, horizontal_resolution_deg=10.0, vertical_fov_deg=(-5.0, 5.0), max_range_m=100.0
    )
    assert config.horizontal_samples == 36


def test_lidar_points_within_max_range() -> None:
    """Every reported hit point's distance from the sensor is <= max_range."""
    config = LidarConfig(
        channels=4, horizontal_resolution_deg=15.0, vertical_fov_deg=(-30.0, -5.0), max_range_m=20.0
    )
    sensor = LidarSensor(config)
    points = sensor.scan(np.array([0.0, 0.0, 5.0]), [_ground_plane_mesh()])

    assert len(points) > 0
    distances = np.linalg.norm(points, axis=1)
    assert (distances <= config.max_range_m + 1e-9).all()


def test_lidar_no_duplicate_points() -> None:
    """No two hit points coincide (within a small tolerance)."""
    config = LidarConfig(
        channels=3,
        horizontal_resolution_deg=20.0,
        vertical_fov_deg=(-30.0, -10.0),
        max_range_m=20.0,
    )
    sensor = LidarSensor(config)
    points = sensor.scan(np.array([0.0, 0.0, 5.0]), [_ground_plane_mesh()])

    for i, p1 in enumerate(points):
        for p2 in points[i + 1 :]:
            assert np.linalg.norm(p1 - p2) > 1e-6


def test_lidar_points_finite() -> None:
    """No NaN/Inf in any returned point."""
    config = LidarConfig(
        channels=4, horizontal_resolution_deg=15.0, vertical_fov_deg=(-30.0, -5.0), max_range_m=20.0
    )
    sensor = LidarSensor(config)
    points = sensor.scan(np.array([0.0, 0.0, 5.0]), [_ground_plane_mesh()])

    assert np.isfinite(points).all()


def test_lidar_empty_scene_returns_no_points() -> None:
    """Raycasting against an empty scene (no meshes) returns an empty
    array, not an error."""
    config = LidarConfig(
        channels=4, horizontal_resolution_deg=30.0, vertical_fov_deg=(-10.0, 10.0), max_range_m=50.0
    )
    sensor = LidarSensor(config)
    points = sensor.scan(np.array([0.0, 0.0, 5.0]), [])

    assert points.shape == (0, 3)


def test_lidar_upward_rays_miss_ground_plane() -> None:
    """Rays pointed above the horizon (positive elevation) never hit a
    ground plane at z=0 when the sensor is above it -- confirms rays
    genuinely respect direction, not just distance-to-plane."""
    config = LidarConfig(
        channels=2, horizontal_resolution_deg=90.0, vertical_fov_deg=(20.0, 40.0), max_range_m=100.0
    )
    sensor = LidarSensor(config)
    points = sensor.scan(np.array([0.0, 0.0, 5.0]), [_ground_plane_mesh()])

    assert len(points) == 0


def test_lidar_hit_points_lie_on_ground_plane() -> None:
    """Every hit point's world z-coordinate (sensor z + point z) is
    (near) 0, confirming intersections are geometrically correct, not
    just present."""
    origin = np.array([0.0, 0.0, 5.0])
    config = LidarConfig(
        channels=3,
        horizontal_resolution_deg=45.0,
        vertical_fov_deg=(-45.0, -20.0),
        max_range_m=50.0,
    )
    sensor = LidarSensor(config)
    points = sensor.scan(origin, [_ground_plane_mesh()])

    assert len(points) == config.channels * config.horizontal_samples
    world_z = origin[2] + points[:, 2]
    assert np.allclose(world_z, 0.0, atol=1e-6)


def test_range_noise_std_must_be_non_negative() -> None:
    """A negative range_noise_std_m is rejected at construction."""
    with pytest.raises(ValueError, match="non-negative"):
        LidarConfig(
            channels=1,
            horizontal_resolution_deg=90.0,
            vertical_fov_deg=(0.0, 0.0),
            max_range_m=50.0,
            range_noise_std_m=-1.0,
        )


def test_range_noise_requires_seed() -> None:
    """Constructing a LidarSensor with range_noise_std_m > 0 but no seed
    is rejected -- deterministic noise needs a real seed, not silent
    OS-entropy randomness."""
    config = LidarConfig(
        channels=1,
        horizontal_resolution_deg=90.0,
        vertical_fov_deg=(0.0, 0.0),
        max_range_m=50.0,
        range_noise_std_m=0.5,
    )
    with pytest.raises(ValueError, match="requires an explicit seed"):
        LidarSensor(config)


def test_range_noise_perturbs_hit_distances() -> None:
    """With range_noise_std_m > 0, hit distances differ from the noiseless
    (range_noise_std_m=0) scan of the same scene."""
    origin = np.array([0.0, 0.0, 5.0])
    base_kwargs = {
        "channels": 4,
        "horizontal_resolution_deg": 15.0,
        "vertical_fov_deg": (-30.0, -5.0),
        "max_range_m": 20.0,
    }
    clean_config = LidarConfig(**base_kwargs)
    noisy_config = LidarConfig(**base_kwargs, range_noise_std_m=0.3)

    clean_points = LidarSensor(clean_config).scan(origin, [_ground_plane_mesh()])
    noisy_points = LidarSensor(noisy_config, seed=7).scan(origin, [_ground_plane_mesh()])

    clean_distances = np.sort(np.linalg.norm(clean_points, axis=1))
    noisy_distances = np.sort(np.linalg.norm(noisy_points, axis=1))
    assert len(clean_distances) == len(noisy_distances)
    assert not np.allclose(clean_distances, noisy_distances)


def test_range_noise_is_deterministic_for_same_seed() -> None:
    """Same seed produces identical noisy output; a different seed
    doesn't."""
    origin = np.array([0.0, 0.0, 5.0])
    config = LidarConfig(
        channels=4,
        horizontal_resolution_deg=15.0,
        vertical_fov_deg=(-30.0, -5.0),
        max_range_m=20.0,
        range_noise_std_m=0.3,
    )

    points_a = LidarSensor(config, seed=42).scan(origin, [_ground_plane_mesh()])
    points_b = LidarSensor(config, seed=42).scan(origin, [_ground_plane_mesh()])
    points_c = LidarSensor(config, seed=43).scan(origin, [_ground_plane_mesh()])

    assert np.array_equal(points_a, points_b)
    assert not np.array_equal(points_a, points_c)


def test_range_noise_can_drop_hits_near_max_range() -> None:
    """Noise can push a near-boundary hit's measured range past
    max_range_m, correctly dropping it -- exactly what a real noisy
    sensor would do, not an artifact to special-case around."""
    origin = np.array([0.0, 0.0, 5.0])
    # Ground plane is exactly max_range_m away at nadir; large noise std
    # guarantees some rays get pushed over the boundary.
    config_clean = LidarConfig(
        channels=1,
        horizontal_resolution_deg=360.0,
        vertical_fov_deg=(-90.0, -90.0),
        max_range_m=5.0,
    )
    config_noisy = LidarConfig(
        channels=1,
        horizontal_resolution_deg=360.0,
        vertical_fov_deg=(-90.0, -90.0),
        max_range_m=5.0,
        range_noise_std_m=10.0,
    )
    clean_points = LidarSensor(config_clean).scan(origin, [_ground_plane_mesh()])
    noisy_points = LidarSensor(config_noisy, seed=1).scan(origin, [_ground_plane_mesh()])

    assert len(clean_points) == 1
    assert len(noisy_points) == 0


def _random_triangle_mesh(rng: np.random.Generator, num_triangles: int) -> Mesh:
    """A mesh of ``num_triangles`` unrelated triangles scattered across a
    -20..20 cube, for randomized TriangleGrid-vs-brute-force comparison."""
    vertices = []
    triangles = []
    for i in range(num_triangles):
        base = rng.uniform(-20.0, 20.0, size=3)
        for _ in range(3):
            vertices.append(base + rng.uniform(-5.0, 5.0, size=3))
        triangles.extend([3 * i, 3 * i + 1, 3 * i + 2])
    return Mesh(
        vertices=np.array(vertices),
        triangles=np.array(triangles, dtype=np.int64),
        uvs=np.zeros((len(vertices), 2)),
        material="test",
    )


def test_triangle_grid_matches_brute_force_on_random_scenes() -> None:
    """TriangleGrid.closest_hit is an *exact* acceleration structure: for
    many random scenes and rays, it returns bit-identical results (within
    floating tolerance) to the brute-force closest_hit_distance, with and
    without a max_distance cutoff."""
    rng = np.random.default_rng(0)
    mismatches = 0

    for _ in range(15):
        mesh = _random_triangle_mesh(rng, num_triangles=int(rng.integers(1, 20)))
        grid = TriangleGrid([mesh], target_triangles_per_cell=2.0)

        for _ in range(15):
            origin = rng.uniform(-30.0, 30.0, size=3)
            direction = rng.normal(size=3)
            direction = direction / np.linalg.norm(direction)
            max_distance = rng.choice([None, float(rng.uniform(1.0, 50.0))])

            expected = closest_hit_distance(origin, direction, [mesh])
            if expected is not None and max_distance is not None and expected > max_distance:
                expected = None
            actual = grid.closest_hit(origin, direction, max_distance=max_distance)

            if expected is None and actual is None:
                continue
            if expected is None or actual is None or not np.isclose(expected, actual, atol=1e-6):
                mismatches += 1

    assert mismatches == 0


def test_triangle_grid_matches_brute_force_for_axis_aligned_rays() -> None:
    """Axis-aligned ray directions (a zero component) are a documented
    special case in the grid traversal's own stepping logic -- verified
    directly against brute force."""
    triangles = [
        (np.array([0.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])),
        (np.array([5.0, 5.0, -1.0]), np.array([6.0, 5.0, -1.0]), np.array([5.0, 6.0, -1.0])),
    ]
    vertices = np.array([v for tri in triangles for v in tri])
    mesh = Mesh(
        vertices=vertices,
        triangles=np.arange(6, dtype=np.int64),
        uvs=np.zeros((6, 2)),
        material="test",
    )
    grid = TriangleGrid([mesh], target_triangles_per_cell=1.0)

    directions = [
        np.array([0.0, 0.0, -1.0]),
        np.array([0.0, 0.0, 1.0]),
        np.array([1.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
    ]
    origins = [
        np.array([0.25, 0.25, 5.0]),
        np.array([0.25, 0.25, -5.0]),
        np.array([5.5, 5.5, 0.0]),
        np.array([-10.0, 0.25, 0.1]),
    ]

    for direction in directions:
        for origin in origins:
            expected = closest_hit_distance(origin, direction, [mesh])
            actual = grid.closest_hit(origin, direction)
            if expected is None:
                assert actual is None
            else:
                assert actual is not None
                assert np.isclose(expected, actual, atol=1e-6)


def test_triangle_grid_empty_scene_returns_none() -> None:
    """A grid built from no meshes at all returns None for every query,
    not an error."""
    grid = TriangleGrid([])
    assert grid.closest_hit(np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.0, -1.0])) is None


def test_triangle_grid_ray_missing_grid_bbox_entirely() -> None:
    """A ray that never enters the grid's own bounding box at all (not
    just missing individual triangles) returns None -- the fast-reject
    path in _ray_aabb_intersect."""
    grid = TriangleGrid([_ground_plane_mesh(half_extent=1.0)], target_triangles_per_cell=1.0)
    origin = np.array([1000.0, 1000.0, 1000.0])
    direction = np.array([1.0, 0.0, 0.0])
    assert grid.closest_hit(origin, direction) is None


def test_triangle_grid_respects_max_distance() -> None:
    """A hit that exists but lies beyond max_distance is reported as a
    miss, exactly like the caller's own post-hoc max_range_m filtering
    would do -- but found via a bounded search, not a full one."""
    grid = TriangleGrid([_ground_plane_mesh()])
    origin = np.array([0.0, 0.0, 5.0])
    direction = np.array([0.0, 0.0, -1.0])

    assert grid.closest_hit(origin, direction) == pytest.approx(5.0)
    assert grid.closest_hit(origin, direction, max_distance=4.0) is None
    assert grid.closest_hit(origin, direction, max_distance=5.5) == pytest.approx(5.0)


def test_triangle_grid_finds_hits_grazing_flat_scene_boundary() -> (
    None
):  # pylint: disable=duplicate-code
    """Regression test for a real bug found via CI (passed on Windows,
    failed on Linux -- see KNOWN_GAPS_AND_ISSUES.md): a flat mesh (every
    vertex at the same z) makes the grid's own z-extent collapse to a
    single thin cell, so the geometry sits exactly on that cell's
    boundary. A ray grazing that boundary can compute a hit distance via
    Moeller-Trumbore that's a few ULPs *greater* than the grid's own
    AABB-slab-derived traversal bound for the same geometric point (two
    different formulas for what should be the same number) -- rejecting
    such a hit against that self-referential bound would silently drop a
    real, exact hit. `closest_hit` must accept it (checked only against
    the caller's own `max_distance`, never the grid's internal traversal
    bound) exactly like `closest_hit_distance` (brute force) does.

    This specific config (channels=3, 45-degree azimuth step, -45..-20
    degree elevation, over a huge flat ground plane) is the exact one
    that exposed the bug in CI."""
    mesh = _ground_plane_mesh()
    grid = TriangleGrid([mesh])
    origin = np.array([0.0, 0.0, 5.0])
    config = LidarConfig(
        channels=3,
        horizontal_resolution_deg=45.0,
        vertical_fov_deg=(-45.0, -20.0),
        max_range_m=50.0,
    )

    azimuths = np.radians(np.linspace(0, 360, config.horizontal_samples, endpoint=False))
    elevations = np.radians(np.linspace(*config.vertical_fov_deg, config.channels))
    for elevation in elevations:
        for azimuth in azimuths:
            direction = np.array(
                [
                    np.cos(elevation) * np.cos(azimuth),
                    np.cos(elevation) * np.sin(azimuth),
                    np.sin(elevation),
                ]
            )
            expected = closest_hit_distance(origin, direction, [mesh])
            actual = grid.closest_hit(origin, direction, max_distance=config.max_range_m)
            assert expected is not None, "test setup should guarantee every ray hits"
            assert actual is not None, f"grid missed a real hit for direction {direction}"
            assert actual == pytest.approx(expected)


def test_lidar_sensor_scan_matches_brute_force_reference() -> (
    None
):  # pylint: disable=duplicate-code
    """LidarSensor.scan's grid-accelerated output matches a direct
    brute-force reimplementation of the same sweep -- confirms the
    TriangleGrid integration, not just the grid in isolation. The
    direction-computation loop below is a deliberate independent
    reimplementation of scan()'s own (to avoid testing the real code
    tautologically against itself), not an accidental duplicate."""
    config = LidarConfig(
        channels=3,
        horizontal_resolution_deg=30.0,
        vertical_fov_deg=(-40.0, -10.0),
        max_range_m=30.0,
    )
    origin = np.array([0.0, 0.0, 5.0])
    meshes = [_ground_plane_mesh()]

    actual_points = LidarSensor(config).scan(origin, meshes)

    azimuths = np.radians(np.linspace(0, 360, config.horizontal_samples, endpoint=False))
    elevations = np.radians(np.linspace(*config.vertical_fov_deg, config.channels))
    expected_points = []
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
            if distance is not None and distance <= config.max_range_m:
                expected_points.append(direction * distance)

    assert np.allclose(np.sort(actual_points, axis=0), np.sort(np.array(expected_points), axis=0))
