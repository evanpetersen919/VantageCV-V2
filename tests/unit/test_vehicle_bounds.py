"""Unit tests for the measured vehicle boxes: table coverage and plausibility,
that placement and ground truth use it, and the box-centre geometry."""

import numpy as np
import pytest

from src.ground_truth.bbox_3d import extract_bbox_3d_vehicle
from src.orchestration.dataset_generator import generate_scenario
from src.procedural.actor_placement import VEHICLE_DIMENSIONS, Vehicle, vehicle_box
from src.procedural.city_sample_assets import VEHICLE_ASSET_PATHS
from src.procedural.vehicle_bounds import VEHICLE_MODEL_BOUNDS

SEDAN = "/Game/Vehicle/vehCar_vehicle03/Mesh/SM_Frame_vehCar_vehicle03"


def test_every_real_model_has_a_measured_box() -> None:
    """All 14 models in the asset pools have an entry, and nothing else."""
    folders = {path.split("/")[3] for paths in VEHICLE_ASSET_PATHS.values() for path in paths}
    assert len(folders) == 14
    assert set(VEHICLE_MODEL_BOUNDS) == folders


def test_measured_boxes_are_plausible() -> None:
    """Lengths, widths and heights are real-vehicle sized, the box centre is
    within a fraction of a vehicle length of the placement point (the trailer
    is the one deliberate exception) and the underside is at the ground."""
    for folder, (length, width, height, offset_x, offset_y, z_min) in VEHICLE_MODEL_BOUNDS.items():
        assert 4.0 < length < 12.0 and 1.6 < width < 3.6 and 1.3 < height < 5.1, folder
        assert length > width
        assert abs(offset_y) < 0.05 and abs(z_min) < 0.05, folder
        if "trailer" not in folder:
            assert abs(offset_x) < 0.5, folder


def test_sedan_sizes_are_no_longer_one_generic_value() -> None:
    """The five sedans differ in length, none is the old generic 4.6 m, and the
    fallback table is still there for an unknown model."""
    sedan_lengths = {
        VEHICLE_MODEL_BOUNDS[path.split("/")[3]][0] for path in VEHICLE_ASSET_PATHS["sedan"]
    }
    assert len(sedan_lengths) == 5 and 4.6 not in sedan_lengths
    assert vehicle_box("/Game/Unknown/Thing", "bus")[:3] == VEHICLE_DIMENSIONS["bus"]
    assert vehicle_box("", "sedan")[3:] == (0.0, 0.0, 0.0)


def test_box_center_turns_the_offset_with_the_heading() -> None:
    """The box centre is the placement point plus the offset rotated by the
    heading: ahead of the point along +x at heading 0, along +y at 90 degrees."""
    car = Vehicle(
        0, "sedan", SEDAN, np.array([10.0, 20.0]), 0.0, 5.0, 2.0, 1.5, box_offset=(0.3, 0.1)
    )
    assert car.box_center == pytest.approx([10.3, 20.1])
    car.heading_rad = np.pi / 2.0
    assert car.box_center == pytest.approx([9.9, 20.3])
    plain = Vehicle(1, "sedan", SEDAN, np.array([1.0, 2.0]), 0.7, 5.0, 2.0, 1.5)
    assert plain.box_center == pytest.approx([1.0, 2.0])


def test_ground_truth_box_is_the_real_box_standing_on_its_surface() -> None:
    """The label uses the model's measured size, is centred on the box centre
    (not the placement point) and rests on the surface: z centre is the surface
    height plus the underside plus half the height."""
    length, width, height, offset_x, offset_y, z_min = vehicle_box(SEDAN, "sedan")
    car = Vehicle(
        3,
        "sedan",
        SEDAN,
        np.array([5.0, 6.0]),
        0.0,
        length,
        width,
        height,
        box_offset=(offset_x, offset_y),
        box_z_min=z_min,
        surface_z=0.11,
    )
    box = extract_bbox_3d_vehicle(car)
    assert box.dimensions == pytest.approx([length, width, height])
    assert box.center[:2] == pytest.approx([5.0 + offset_x, 6.0 + offset_y])
    assert box.center[2] == pytest.approx(0.11 + z_min + height / 2.0)
    corners = box.corners()
    assert corners[:, 2].min() == pytest.approx(0.11 + z_min)


def test_generated_vehicles_carry_their_models_measured_box(urban_config, bounds) -> None:
    """Every placed vehicle, driving or parked, uses its own model's table row
    for size, offset and underside height."""
    config = urban_config.model_copy(update={"parking_lot_fraction": 0.6})
    result = generate_scenario(42, config, bounds, "x")
    assert result.vehicles
    assert any(v.parked for v in result.vehicles)
    for vehicle in result.vehicles:
        expected = VEHICLE_MODEL_BOUNDS[vehicle.asset_path.split("/")[3]]
        assert (vehicle.length, vehicle.width, vehicle.height) == expected[:3]
        assert vehicle.box_offset == expected[3:5] and vehicle.box_z_min == expected[5]
