"""Unit tests for 3D bounding box extraction."""

import numpy as np
import pytest

from src.ground_truth.bbox_3d import (
    BoundingBox3D,
    extract_bbox_3d,
    extract_bbox_3d_pedestrian,
    extract_bbox_3d_vehicle,
    extract_bboxes_3d,
    extract_bboxes_3d_pedestrians,
    extract_bboxes_3d_vehicles,
)
from src.ground_truth.categories import BUILDING, BUS, PEDESTRIAN, SEDAN, SUV, TRUCK
from src.procedural.actor_placement import Pedestrian, Vehicle
from src.procedural.building_placement import Building
from src.procedural.city_sample_assets import PEDESTRIAN_ASSET_PATHS


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


def test_extract_bbox_3d_default_category_is_building() -> None:
    """A building's extracted box defaults to the BUILDING category."""
    building = Building(
        building_id=0, center=np.array([0.0, 0.0]), width=5.0, depth=5.0, height=10.0
    )
    assert extract_bbox_3d(building).category_id == BUILDING


def test_corners_heading_zero_matches_axis_aligned_formula() -> None:
    """heading_rad=0.0 (buildings' only value) reproduces the exact
    min/max axis-aligned corners as before rotation support existed."""
    center = np.array([5.0, -2.0, 3.0])
    dimensions = np.array([4.0, 6.0, 8.0])
    bbox = BoundingBox3D(object_id=0, center=center, dimensions=dimensions, heading_rad=0.0)
    corners = bbox.corners()

    half = dimensions / 2.0
    assert np.allclose(corners.min(axis=0), center - half)
    assert np.allclose(corners.max(axis=0), center + half)


def test_corners_heading_quarter_turn_swaps_length_and_width_extents() -> None:
    """A pi/2 heading rotates the footprint 90 degrees, so the box's
    world-space x/y extents swap relative to its (length, width)."""
    center = np.array([0.0, 0.0, 0.0])
    dimensions = np.array([10.0, 4.0, 2.0])  # length=10, width=4
    bbox = BoundingBox3D(object_id=0, center=center, dimensions=dimensions, heading_rad=np.pi / 2)
    corners = bbox.corners()

    x_extent = corners[:, 0].max() - corners[:, 0].min()
    y_extent = corners[:, 1].max() - corners[:, 1].min()
    assert np.isclose(x_extent, 4.0)  # width, now along world x
    assert np.isclose(y_extent, 10.0)  # length, now along world y


def _sample_vehicle(vehicle_type: str = "sedan") -> Vehicle:
    return Vehicle(
        vehicle_id=3,
        vehicle_type=vehicle_type,
        asset_path="/Game/Vehicle/vehCar_vehicle02/BP_vehCar_vehicle02_Sandbox",
        center=np.array([10.0, -5.0]),
        heading_rad=np.pi / 4,
        length=4.6,
        width=1.8,
        height=1.5,
    )


@pytest.mark.parametrize(
    "vehicle_type,expected_category",
    [("sedan", SEDAN), ("suv", SUV), ("truck", TRUCK), ("bus", BUS)],
)
def test_extract_bbox_3d_vehicle_category_matches_type(vehicle_type, expected_category) -> None:
    """Each vehicle type maps to its own category via VEHICLE_TYPE_TO_CATEGORY."""
    bbox = extract_bbox_3d_vehicle(_sample_vehicle(vehicle_type))
    assert bbox.category_id == expected_category


def test_extract_bbox_3d_vehicle_geometry_matches_vehicle() -> None:
    """Extracted center/dimensions/heading match the source vehicle."""
    vehicle = _sample_vehicle()
    bbox = extract_bbox_3d_vehicle(vehicle)

    assert bbox.object_id == vehicle.vehicle_id
    assert np.allclose(bbox.dimensions, [vehicle.length, vehicle.width, vehicle.height])
    assert np.allclose(bbox.center[:2], vehicle.center)
    assert np.isclose(bbox.center[2], vehicle.height / 2.0)
    assert bbox.heading_rad == vehicle.heading_rad


def test_extract_bbox_3d_vehicle_id_offset() -> None:
    """id_offset shifts object_id, disambiguating from other object
    kinds' own 0-based counters when combined into one scenario."""
    bbox = extract_bbox_3d_vehicle(_sample_vehicle(), id_offset=100)
    assert bbox.object_id == 103


def test_extract_bboxes_3d_vehicles_preserves_count_and_offset() -> None:
    """extract_bboxes_3d_vehicles produces one box per vehicle, offset IDs."""
    vehicles = [
        Vehicle(
            vehicle_id=i,
            vehicle_type="sedan",
            asset_path="/Game/Vehicle/vehCar_vehicle02/BP_vehCar_vehicle02_Sandbox",
            center=np.array([float(i), 0.0]),
            heading_rad=0.0,
            length=4.6,
            width=1.8,
            height=1.5,
        )
        for i in range(3)
    ]
    bboxes = extract_bboxes_3d_vehicles(vehicles, id_offset=10)
    assert {b.object_id for b in bboxes} == {10, 11, 12}


def test_extract_bboxes_3d_vehicles_empty_input() -> None:
    """An empty vehicle list produces an empty box list."""
    assert extract_bboxes_3d_vehicles([]) == []


def _sample_pedestrian() -> Pedestrian:
    return Pedestrian(
        pedestrian_id=2,
        center=np.array([1.0, 2.0]),
        heading_rad=np.pi / 3,
        asset_path=PEDESTRIAN_ASSET_PATHS[0],
    )


def test_extract_bbox_3d_pedestrian_category_is_pedestrian() -> None:
    """Every pedestrian's extracted box uses the PEDESTRIAN category."""
    bbox = extract_bbox_3d_pedestrian(_sample_pedestrian())
    assert bbox.category_id == PEDESTRIAN


def test_extract_bbox_3d_pedestrian_geometry_matches_pedestrian() -> None:
    """Extracted center/dimensions/heading match the source pedestrian."""
    pedestrian = _sample_pedestrian()
    bbox = extract_bbox_3d_pedestrian(pedestrian)

    assert bbox.object_id == pedestrian.pedestrian_id
    assert np.allclose(bbox.dimensions, [pedestrian.depth, pedestrian.width, pedestrian.height])
    assert np.allclose(bbox.center[:2], pedestrian.center)
    assert np.isclose(bbox.center[2], pedestrian.height / 2.0)
    assert bbox.heading_rad == pedestrian.heading_rad


def test_extract_bbox_3d_pedestrian_id_offset() -> None:
    """id_offset shifts object_id, same rationale as the vehicle case."""
    bbox = extract_bbox_3d_pedestrian(_sample_pedestrian(), id_offset=200)
    assert bbox.object_id == 202


def test_extract_bboxes_3d_pedestrians_preserves_count_and_offset() -> None:
    """extract_bboxes_3d_pedestrians produces one box per pedestrian, offset IDs."""
    pedestrians = [
        Pedestrian(
            pedestrian_id=i,
            center=np.array([float(i), 0.0]),
            heading_rad=0.0,
            asset_path=PEDESTRIAN_ASSET_PATHS[0],
        )
        for i in range(3)
    ]
    bboxes = extract_bboxes_3d_pedestrians(pedestrians, id_offset=20)
    assert {b.object_id for b in bboxes} == {20, 21, 22}


def test_extract_bboxes_3d_pedestrians_empty_input() -> None:
    """An empty pedestrian list produces an empty box list."""
    assert extract_bboxes_3d_pedestrians([]) == []
