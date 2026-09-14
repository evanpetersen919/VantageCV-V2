"""Unit tests for LiDAR ray-casting.

Covers QOL_RESEARCH_CHECKLIST.md Section E.2: points within max range, no
duplicate points, and ray-triangle intersection correctness directly.

Test LiDAR configs use small channel counts / coarse resolution
deliberately: LidarSensor.scan is brute-force O(rays * triangles) with no
spatial acceleration structure (see lidar_model.py module docstring and
KNOWN_GAPS_AND_ISSUES.md) -- a config matching a real sensor (e.g. 64
channels x ~2000 azimuth samples) against even a modest scene would be
far too slow for a unit test.
"""

import numpy as np
import pytest

from src.procedural.mesh_factory import Mesh
from src.sensors.lidar_model import LidarConfig, LidarSensor, ray_triangle_intersect


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

    assert len(points) > 0
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
