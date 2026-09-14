"""Unit tests for dataset sanity checks.

Covers QOL_RESEARCH_CHECKLIST.md Section H.2: annotation count variation
sensible, plus this module's building-height distribution analogue.
"""

import numpy as np

from src.export.coco_exporter import CocoFrame
from src.ground_truth.bbox_2d import BoundingBox2D
from src.sensors.camera_model import Camera, CameraExtrinsics, CameraIntrinsics
from src.validation.sanity_checker import (
    check_annotation_count_consistency,
    check_building_height_distribution,
    check_vehicle_class_distribution,
)

# urban_config fixture: see tests/conftest.py


def _default_camera() -> Camera:
    intrinsics = CameraIntrinsics(500.0, 500.0, 320.0, 240.0, 640, 480)
    extrinsics = CameraExtrinsics(rotation=np.eye(3), translation=np.zeros(3))
    return Camera(intrinsics, extrinsics)


def _frame_with_n_boxes(image_id: int, n: int) -> CocoFrame:
    boxes = [
        BoundingBox2D(object_id=i, x_min=0.0, y_min=0.0, x_max=10.0, y_max=10.0, visibility=1.0)
        for i in range(n)
    ]
    return CocoFrame(
        image_id=image_id, file_name=f"f{image_id}.png", camera=_default_camera(), bboxes_2d=boxes
    )


def test_annotation_count_consistency_no_outliers() -> None:
    """Frames with similar annotation counts produce a healthy report."""
    frames = [_frame_with_n_boxes(i, n=5) for i in range(10)]
    report = check_annotation_count_consistency(frames)

    assert report.is_healthy
    assert report.num_frames == 10
    assert report.num_annotations == 50


def test_annotation_count_consistency_detects_outlier() -> None:
    """A frame with a wildly different annotation count is flagged."""
    frames = [_frame_with_n_boxes(i, n=5) for i in range(20)]
    frames.append(_frame_with_n_boxes(999, n=500))

    report = check_annotation_count_consistency(frames)

    assert not report.is_healthy
    assert 999 in report.outlier_frame_ids


def test_annotation_count_consistency_empty_dataset() -> None:
    """No frames at all produces a trivially healthy, zeroed report."""
    report = check_annotation_count_consistency([])

    assert report.is_healthy
    assert report.num_frames == 0
    assert report.num_annotations == 0


def test_annotation_count_consistency_uniform_zero_std() -> None:
    """When every frame has the exact same count (std=0), no frame is
    ever flagged as an outlier (avoids a 0/0 division)."""
    frames = [_frame_with_n_boxes(i, n=3) for i in range(5)]
    report = check_annotation_count_consistency(frames)

    assert report.std_annotations_per_frame == 0.0
    assert report.is_healthy


def test_building_height_distribution_within_range_passes(urban_config) -> None:
    """Heights matching the configured uniform distribution pass."""
    rng = np.random.default_rng(42)
    heights = rng.uniform(20.0, 40.0, size=1000).tolist()

    assert check_building_height_distribution(heights, urban_config)


def test_building_height_distribution_out_of_range_fails(urban_config) -> None:
    """A height outside [min, max] fails the check."""
    heights = [25.0, 30.0, 100.0]  # 100.0 is out of the configured range

    assert not check_building_height_distribution(heights, urban_config)


def test_building_height_distribution_skewed_mean_fails(urban_config) -> None:
    """Heights all clustered at one extreme (valid range, but mean far
    from the expected uniform-distribution mean) fail the tolerance
    check."""
    heights = [20.0] * 100  # always the minimum, never near the 30.0 mean

    assert not check_building_height_distribution(heights, urban_config)


def test_building_height_distribution_empty_list_passes(urban_config) -> None:
    """No buildings at all trivially passes (nothing to violate)."""
    assert check_building_height_distribution([], urban_config)


def test_vehicle_class_distribution_matching_mix_passes(urban_config) -> None:
    """Vehicle types sampled at exactly config.vehicle_mix's own
    fractions pass."""
    rng = np.random.default_rng(42)
    types = list(urban_config.vehicle_mix.keys())
    weights = list(urban_config.vehicle_mix.values())
    vehicle_types = rng.choice(types, size=5000, p=weights).tolist()

    assert check_vehicle_class_distribution(vehicle_types, urban_config)


def test_vehicle_class_distribution_skewed_fails(urban_config) -> None:
    """Every vehicle being the same type, when config.vehicle_mix expects
    a spread across 4 types, fails the tolerance check."""
    vehicle_types = ["sedan"] * 100

    assert not check_vehicle_class_distribution(vehicle_types, urban_config)


def test_vehicle_class_distribution_missing_type_fails(urban_config) -> None:
    """A configured type that never appears at all (0% vs. its expected
    fraction) fails, as long as its expected fraction exceeds tolerance."""
    # urban_config expects bus: 0.05 -- well within tolerance even at 0%,
    # but sedan: 0.6 is not.
    vehicle_types = ["bus"] * 20 + ["suv"] * 20 + ["truck"] * 20  # no sedan at all

    assert not check_vehicle_class_distribution(vehicle_types, urban_config)


def test_vehicle_class_distribution_empty_list_passes(urban_config) -> None:
    """No vehicles at all trivially passes (nothing to violate)."""
    assert check_vehicle_class_distribution([], urban_config)
