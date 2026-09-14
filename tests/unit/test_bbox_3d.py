"""Unit tests for 3D bounding box extraction."""

import numpy as np
import pytest

from src.ground_truth.bbox_3d import BoundingBox3D, extract_bbox_3d, extract_bboxes_3d
from src.procedural.building_placement import Building


def test_extract_bbox_3d_dimensions_match_building() -> None:
    """Extracted dimensions match the source building's footprint/height."""
    building = Building(
        building_id=7, center=np.array([10.0, -5.0]), width=6.0, depth=4.0, height=15.0
    )
    bbox = extract_bbox_3d(building)

    assert bbox.object_id == 7
    assert np.allclose(bbox.dimensions, [6.0, 4.0, 15.0])


def test_extract_bbox_3d_center_z_is_half_height() -> None:
    """The box's center z-coordinate is half the building's height (base
    at z=0, per mesh_factory.py's extrusion convention)."""
    building = Building(
        building_id=0, center=np.array([0.0, 0.0]), width=10.0, depth=10.0, height=20.0
    )
    bbox = extract_bbox_3d(building)
    assert np.isclose(bbox.center[2], 10.0)


def test_extract_bbox_3d_center_xy_matches_building_center() -> None:
    """The box's x/y center matches the building's own center."""
    building = Building(
        building_id=0, center=np.array([12.5, -3.5]), width=8.0, depth=8.0, height=10.0
    )
    bbox = extract_bbox_3d(building)
    assert np.allclose(bbox.center[:2], [12.5, -3.5])


def test_bounding_box_3d_rejects_non_positive_dimensions() -> None:
    """Zero or negative dimensions are rejected at construction."""
    with pytest.raises(ValueError):
        BoundingBox3D(object_id=0, center=np.zeros(3), dimensions=np.array([0.0, 5.0, 5.0]))
    with pytest.raises(ValueError):
        BoundingBox3D(object_id=0, center=np.zeros(3), dimensions=np.array([5.0, -1.0, 5.0]))


def test_corners_returns_8_points() -> None:
    """corners() returns exactly 8 points."""
    bbox = BoundingBox3D(object_id=0, center=np.zeros(3), dimensions=np.array([2.0, 2.0, 2.0]))
    assert bbox.corners().shape == (8, 3)


def test_corners_bound_the_declared_dimensions() -> None:
    """Every corner's coordinates fall within [center - half, center +
    half] on each axis, and the extremes are actually reached."""
    center = np.array([5.0, -2.0, 3.0])
    dimensions = np.array([4.0, 6.0, 8.0])
    bbox = BoundingBox3D(object_id=0, center=center, dimensions=dimensions)
    corners = bbox.corners()

    half = dimensions / 2.0
    assert np.allclose(corners.min(axis=0), center - half)
    assert np.allclose(corners.max(axis=0), center + half)


def test_corners_finite() -> None:
    """No NaN/Inf in the corners."""
    bbox = BoundingBox3D(
        object_id=0, center=np.array([1.0, 2.0, 3.0]), dimensions=np.array([1.0, 1.0, 1.0])
    )
    assert np.isfinite(bbox.corners()).all()


def test_extract_bboxes_3d_preserves_count_and_ids() -> None:
    """extract_bboxes_3d produces one box per building, with matching IDs."""
    buildings = [
        Building(
            building_id=i, center=np.array([float(i) * 20, 0.0]), width=5.0, depth=5.0, height=10.0
        )
        for i in range(5)
    ]
    bboxes = extract_bboxes_3d(buildings)

    assert len(bboxes) == 5
    assert {b.object_id for b in bboxes} == {0, 1, 2, 3, 4}


def test_extract_bboxes_3d_empty_input() -> None:
    """An empty building list produces an empty box list."""
    assert extract_bboxes_3d([]) == []
