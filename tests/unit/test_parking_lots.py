"""Unit tests for parking_lots.py: stall/aisle geometry from the cited US
dimensions, parked cars sitting inside their stalls, building keep-out and
the night-lights and default-off behaviour."""

import numpy as np
import pytest

from src.orchestration.dataset_generator import generate_scenario
from src.orchestration.scenario_serializer import serialize_scenario
from src.procedural.actor_placement import VEHICLE_DIMENSIONS, Vehicle
from src.procedural.environment import TimeOfDay
from src.procedural.night_lights import vehicle_glows, vehicle_lights
from src.procedural.parking_lots import (
    AISLE_OVERHANG_M,
    AISLE_WIDTH_M,
    LOT_SURFACE_Z_M,
    MIN_STALLS_PER_ROW,
    PARKED_MIX_EXPONENT,
    PARKED_MODELS,
    PARKED_VEHICLE_TYPES,
    STALL_LENGTH_M,
    STALL_WIDTH_M,
    layout_lot,
    parked_vehicles,
    parking_lot_meshes,
    plan_parking_lots,
)

FEET = 0.3048
# A pickup may stand a few centimetres over its stall's length, like a real one.
PICKUP_OVERHANG_M = 0.1


def _config(urban_config, fraction: float):
    return urban_config.model_copy(update={"parking_lot_fraction": fraction})


def _nearest_stall(stalls, car):
    """The stall whose center is closest to ``car``."""
    return min(stalls, key=lambda s: np.hypot(*(np.array(s.center) - car.center)))


def test_stall_and_aisle_are_the_cited_us_dimensions() -> None:
    """9 x 18 ft stalls and a 24 ft two-way aisle, in metres."""
    assert STALL_WIDTH_M == pytest.approx(9 * FEET)
    assert STALL_LENGTH_M == pytest.approx(18 * FEET)
    assert AISLE_WIDTH_M == pytest.approx(24 * FEET)


def test_a_double_loaded_lot_has_the_expected_stall_count_and_geometry() -> None:
    """A lot exactly one module (two rows + aisle) deep and 20 stalls long
    (plus edge margins) holds 2 rows x 20 stalls, every stall inside the
    bounds, and evenly spaced by one stall width."""
    depth = 2 * STALL_LENGTH_M + AISLE_WIDTH_M + 2.0
    length = 20 * STALL_WIDTH_M + 2.0
    lot = layout_lot(0, (0.0, 0.0, length, depth))
    assert len(lot.stalls) == 40
    x_min, y_min, x_max, y_max = lot.bounds
    for stall in lot.stalls:
        cx, cy = stall.center
        assert x_min <= cx - stall.width / 2 and cx + stall.width / 2 <= x_max
        assert y_min <= cy - stall.length / 2 and cy + stall.length / 2 <= y_max
    rows = sorted({round(stall.center[1], 6) for stall in lot.stalls})
    assert len(rows) == 2
    assert rows[1] - rows[0] == pytest.approx(STALL_LENGTH_M + AISLE_WIDTH_M)
    row_one = sorted(s.center[0] for s in lot.stalls if round(s.center[1], 6) == rows[0])
    assert np.diff(row_one) == pytest.approx(STALL_WIDTH_M)


def test_stalls_face_away_from_their_aisle() -> None:
    """The lower row's head-in heading points to -y, the upper row's to
    +y (aisle along x)."""
    depth = 2 * STALL_LENGTH_M + AISLE_WIDTH_M + 2.0
    lot = layout_lot(0, (0.0, 0.0, 12 * STALL_WIDTH_M + 2.0, depth))
    mid_y = (lot.bounds[1] + lot.bounds[3]) / 2.0
    for stall in lot.stalls:
        expected = np.pi / 2 if stall.center[1] > mid_y else -np.pi / 2
        assert stall.head_heading_rad == pytest.approx(expected)


def test_a_lot_too_small_for_an_aisle_and_row_is_empty() -> None:
    """Shorter than one aisle plus a row, or too short for the minimum
    stalls per row, yields no stalls."""
    assert not layout_lot(0, (0.0, 0.0, 60.0, STALL_LENGTH_M + AISLE_WIDTH_M)).stalls
    assert not layout_lot(0, (0.0, 0.0, MIN_STALLS_PER_ROW * STALL_WIDTH_M, 40.0)).stalls


def test_a_lot_whose_long_side_is_y_runs_its_aisles_along_y() -> None:
    """Rotating the lot swaps the axes: headings point along +-x."""
    lot = layout_lot(0, (0.0, 0.0, 2 * STALL_LENGTH_M + AISLE_WIDTH_M + 2.0, 50.0))
    assert lot.stalls
    assert all(abs(np.cos(s.head_heading_rad)) == pytest.approx(1.0) for s in lot.stalls)


def test_default_config_plans_no_lots(urban_config, bounds) -> None:
    """parking_lot_fraction defaults to 0, so existing scenarios are unchanged."""
    assert urban_config.parking_lot_fraction == 0.0
    assert not generate_scenario(42, urban_config, bounds, "x").parking_lots


def test_lots_are_deterministic_and_inside_bounds(urban_config, bounds) -> None:
    """Same seed, same lots; every lot is inside the scenario bounds."""
    config = _config(urban_config, 0.6)
    first = generate_scenario(42, config, bounds, "a")
    again = generate_scenario(42, config, bounds, "b")
    assert first.parking_lots
    assert [lot.bounds for lot in first.parking_lots] == [lot.bounds for lot in again.parking_lots]
    for lot in first.parking_lots:
        assert lot.bounds[0] >= bounds[0] and lot.bounds[2] <= bounds[2]
        assert lot.bounds[1] >= bounds[1] and lot.bounds[3] <= bounds[3]


def test_no_building_overlaps_a_lot(urban_config, bounds) -> None:
    """Buildings keep out of every lot."""
    result = generate_scenario(42, _config(urban_config, 0.6), bounds, "x")
    for building in result.buildings:
        b = building.aabb
        for lot in result.parking_lots:
            x0, y0, x1, y1 = lot.bounds
            assert b[2] <= x0 or b[0] >= x1 or b[3] <= y0 or b[1] >= y1


def test_parked_cars_sit_inside_their_stalls_without_overlapping(  # pylint: disable=too-many-locals
    urban_config, bounds
) -> None:
    """Every parked car is a sedan or SUV on the lot surface, marked parked,
    inside its own stall's painted lines, and no two cars' boxes overlap."""
    result = generate_scenario(42, _config(urban_config, 0.6), bounds, "x")
    parked = [v for v in result.vehicles if v.parked]
    assert parked
    stalls = [s for lot in result.parking_lots for s in lot.stalls]
    for car in parked:
        assert car.vehicle_type in PARKED_VEHICLE_TYPES
        assert car.surface_z == LOT_SURFACE_Z_M
        nearest = _nearest_stall(stalls, car)
        along = np.array([np.cos(nearest.head_heading_rad), np.sin(nearest.head_heading_rad)])
        lateral = np.array([-along[1], along[0]])
        offset = car.center - np.array(nearest.center)
        yaw = abs(((car.heading_rad - nearest.head_heading_rad + np.pi / 2) % np.pi) - np.pi / 2)
        half_along = (car.length * np.cos(yaw) + car.width * np.sin(yaw)) / 2
        half_lateral = (car.length * np.sin(yaw) + car.width * np.cos(yaw)) / 2
        assert offset @ along + half_along <= nearest.length / 2 + 1e-6
        assert (
            -(offset @ along) + half_along
            <= nearest.length / 2 + AISLE_OVERHANG_M + PICKUP_OVERHANG_M
        )
        assert abs(offset @ lateral) + half_lateral <= nearest.width / 2 + 1e-6
    ids = [v.vehicle_id for v in result.vehicles]
    assert len(ids) == len(set(ids))
    boxes = [v.aabb for v in parked]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]


def test_parked_vehicle_types_follow_the_flattened_class_mix(urban_config) -> None:
    """Only sedans, SUVs and pickups park, in the class mix raised to
    PARKED_MIX_EXPONENT."""
    config = _config(urban_config, 1.0)
    lot = layout_lot(0, (0.0, 0.0, 60 * STALL_WIDTH_M, 2 * STALL_LENGTH_M + AISLE_WIDTH_M + 2.0))
    cars = parked_vehicles([lot] * 8, config, seed=3, first_vehicle_id=100)
    types = [c.vehicle_type for c in cars]
    assert set(types) <= set(PARKED_VEHICLE_TYPES)
    weights = {t: urban_config.vehicle_mix[t] ** PARKED_MIX_EXPONENT for t in PARKED_VEHICLE_TYPES}
    for vehicle_type, weight in weights.items():
        expected = weight / sum(weights.values())
        assert abs(types.count(vehicle_type) / len(types) - expected) < 0.06
    assert cars[0].vehicle_id == 100


def test_lot_meshes_are_a_surface_and_one_stripe_mesh_per_lot(urban_config, bounds) -> None:
    """Each lot yields an asphalt surface and a paint_white stripe mesh."""
    result = generate_scenario(42, _config(urban_config, 0.6), bounds, "x")
    meshes = parking_lot_meshes(result.parking_lots)
    assert [m.material for m in meshes].count("asphalt") == len(result.parking_lots)
    assert [m.material for m in meshes].count("paint_white") == len(result.parking_lots)
    for mesh in meshes:
        assert np.allclose(mesh.vertices[:, 2], mesh.vertices[0, 2])


def test_plan_needs_edges_and_positive_fraction(urban_config) -> None:
    """No edges plans nothing."""
    assert not plan_parking_lots({}, {}, _config(urban_config, 1.0), 1)


def test_parked_cars_have_no_lights_at_night_and_stand_on_the_lot(urban_config, bounds) -> None:
    """Parked cars add no headlights/glows, and their asset z is the lot
    surface height."""
    night = generate_scenario(
        42, _config(urban_config, 0.6), bounds, "n", time_of_day=TimeOfDay.NIGHT
    )
    parked = [v for v in night.vehicles if v.parked]
    moving = [v for v in night.vehicles if not v.parked]
    assert parked and moving
    assert all(not vehicle_lights(v) and not vehicle_glows(v) for v in parked)
    payload = serialize_scenario(night)
    assert len(payload["lights"]) == 4 * len(moving)
    zs = {a["id"]: a["position"][2] for a in payload["assets"] if a["category"] == "vehicle"}
    assert all(zs[v.vehicle_id] == LOT_SURFACE_Z_M for v in parked)
    assert all(zs[v.vehicle_id] == 0.0 for v in moving)


def test_parked_models_are_only_ordinary_cars_that_fit_a_stall() -> None:
    """Every allowed model is a sedan, SUV or pickup that fits a stall (a
    pickup may overhang by a few centimetres), and the taxi, police car, box
    van, other trucks and bus are excluded."""
    assert {m.vehicle_type for m in PARKED_MODELS} == set(PARKED_VEHICLE_TYPES)
    for model in PARKED_MODELS:
        assert model.length <= STALL_LENGTH_M + PICKUP_OVERHANG_M
        assert model.width <= STALL_WIDTH_M - 0.5
    excluded = (
        "vehicle12",
        "vehicle13",
        "vehVan_vehicle09",
        "vehTruck_vehicle08",
        "vehTruck_vehicle11",
        "trailer",
        "vehBus",
    )
    assert not any(name in m.asset_path for m in PARKED_MODELS for name in excluded)


def test_vehicle_defaults_are_unparked_on_the_road() -> None:
    """A plain Vehicle is not parked and stands at z 0."""
    car = Vehicle(0, "sedan", "/p", np.zeros(2), 0.0, *VEHICLE_DIMENSIONS["sedan"])
    assert not car.parked and car.surface_z == 0.0
