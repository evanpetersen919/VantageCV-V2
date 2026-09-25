"""Unit tests for vehicle_colors.py: the sourced colour shares, deterministic
per-vehicle draws, which models are recoloured and the payload entries."""

import numpy as np
import pytest

from src.orchestration.dataset_generator import generate_scenario
from src.orchestration.scenario_serializer import _vehicle_to_asset_json, serialize_scenario
from src.procedural.actor_placement import VEHICLE_DIMENSIONS, Vehicle
from src.procedural.vehicle_colors import (
    PAINT_COLORS,
    PAINT_COLORS_BY_NAME,
    PAINT_SCALE,
    PAINT_SLOT_NAME,
    RECOLORABLE_MODELS,
    assign_vehicle_paint,
    draw_paint_color,
    is_recolorable,
    paint_material_replacement,
    paint_parameter,
)

SEDAN = "/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Frame_vehCar_vehicle02"
TAXI = "/Game/Vehicle/vehCar_vehicle12/Mesh/SM_Frame_vehCar_vehicle12"
POLICE = "/Game/Vehicle/vehCar_vehicle13/Mesh/SM_Frame_vehCar_vehicle13"
BUS = "/Game/Vehicle/vehBus_vehicle10/Mesh/SM_Frame_vehBus_vehicle10"


def _vehicle(vehicle_id: int, asset_path: str) -> Vehicle:
    return Vehicle(vehicle_id, "sedan", asset_path, np.zeros(2), 0.0, *VEHICLE_DIMENSIONS["sedan"])


def test_shares_are_the_sourced_major_colours_and_sum_to_one() -> None:
    """The six named colours carry the cited iSeeCars 2025 shares; all shares
    sum to one."""
    cited = {
        "white": 0.257,
        "black": 0.234,
        "gray": 0.229,
        "silver": 0.084,
        "red": 0.070,
        "blue": 0.060,
    }
    for name, share in cited.items():
        assert PAINT_COLORS_BY_NAME[name].share == pytest.approx(share)
    assert sum(color.share for color in PAINT_COLORS) == pytest.approx(1.0)


def test_only_models_with_a_paint_copy_are_recoloured() -> None:
    """Ordinary cars are recolourable; the taxi, police car and bus keep
    their livery."""
    assert is_recolorable(SEDAN)
    assert not any(is_recolorable(path) for path in (TAXI, POLICE, BUS))
    assert paint_material_replacement(TAXI) is None
    assert paint_material_replacement(SEDAN) == {
        PAINT_SLOT_NAME: "/Game/VantageCV/VehiclePaint/vehCar_vehicle02.vehCar_vehicle02"
    }
    assert len(RECOLORABLE_MODELS) == 7


def test_draws_are_deterministic_and_follow_the_shares() -> None:
    """The same seed and vehicle id always draw the same colour, and a large
    sample matches each colour's share."""
    assert draw_paint_color(5, 9) == draw_paint_color(5, 9)
    draws = [draw_paint_color(1, vehicle_id).name for vehicle_id in range(6000)]
    for color in PAINT_COLORS:
        assert draws.count(color.name) / len(draws) == pytest.approx(color.share, abs=0.02)
    assert len({draw_paint_color(seed, 0).name for seed in range(60)}) > 1


def test_paint_parameter_is_scaled_linear_and_capped() -> None:
    """A colour's BaseColor is its linear sRGB times PAINT_SCALE, capped at
    one per channel: black stays near zero, white is capped."""
    black = paint_parameter(PAINT_COLORS_BY_NAME["black"])
    assert max(black) < 0.02
    white = paint_parameter(PAINT_COLORS_BY_NAME["white"])
    assert max(white) == 1.0
    red = paint_parameter(PAINT_COLORS_BY_NAME["red"])
    assert red[0] > 10 * red[1] and red[0] > 10 * red[2]
    assert PAINT_SCALE > 1.0


def test_assign_paint_sets_only_recolourable_vehicles() -> None:
    """Recolourable vehicles get a colour name; a taxi does not."""
    cars = [_vehicle(0, SEDAN), _vehicle(1, TAXI), _vehicle(2, SEDAN)]
    assign_vehicle_paint(cars, seed=3)
    assert cars[0].paint in PAINT_COLORS_BY_NAME and cars[2].paint in PAINT_COLORS_BY_NAME
    assert cars[1].paint is None


def test_a_painted_vehicle_payload_swaps_the_paint_and_sets_its_colours() -> None:
    """The asset entry carries the paint replacement and BaseColor plus both
    flake tints; an unpainted vehicle's entry has neither key."""
    painted = _vehicle(0, SEDAN)
    painted.paint = "red"
    entry = _vehicle_to_asset_json(painted)
    assert entry["material_replacements"][PAINT_SLOT_NAME].startswith(
        "/Game/VantageCV/VehiclePaint/"
    )
    vectors = entry["material_slot_vectors"][PAINT_SLOT_NAME]
    assert set(vectors) == {"BaseColor", "FlakeTintA", "FlakeTintB"}
    assert vectors["BaseColor"][:3] == pytest.approx(
        list(paint_parameter(PAINT_COLORS_BY_NAME["red"]))
    )
    assert vectors["BaseColor"][3] == 1.0
    plain = _vehicle_to_asset_json(_vehicle(1, SEDAN))
    assert "material_replacements" not in plain and "material_slot_vectors" not in plain


def test_generated_scenarios_paint_ordinary_cars_in_several_colours(urban_config, bounds) -> None:
    """A scenario's payload has recoloured vehicles in more than one colour
    and no livery model recoloured."""
    result = generate_scenario(42, urban_config, bounds, "x")
    painted = [v for v in result.vehicles if v.paint is not None]
    assert painted
    assert len({v.paint for v in painted}) > 2
    assert all(is_recolorable(v.asset_path) for v in painted)
    assert all(v.paint is None for v in result.vehicles if not is_recolorable(v.asset_path))
    payload = serialize_scenario(result)
    recolored = [
        a for a in payload["assets"] if a["category"] == "vehicle" and "material_slot_vectors" in a
    ]
    assert len(recolored) == len(painted)
