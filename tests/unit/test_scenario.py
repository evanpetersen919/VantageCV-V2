"""Unit tests for ScenarioTypeConfig validation."""

import pytest
from pydantic import ValidationError

from src.procedural.scenario import ScenarioType, ScenarioTypeConfig


def _base_kwargs() -> dict:
    """Baseline valid kwargs for constructing a ScenarioTypeConfig.

    Deliberately mirrors the urban_config fixture in tests/conftest.py:
    this module tests ScenarioTypeConfig's own field validators (range
    ordering, density bounds, vehicle_mix sum), which requires constructing
    variations the shared fixture can't parameterize.
    """
    return {
        "scenario_type": ScenarioType.URBAN_DENSE,
        "avg_block_size": (100.0, 150.0),
        "avg_road_width": 12.0,
        "num_intersections": (4, 9),
        "intersection_types": ["4way", "3way"],
        "building_density": 0.8,
        "building_heights": (20.0, 40.0),
        "traffic_density": (0.6, 1.0),
        "vehicle_mix": {"sedan": 0.6, "suv": 0.25, "truck": 0.1, "bus": 0.05},
        "complexity_score": 80,
    }


def test_valid_config_constructs() -> None:
    """A well-formed config constructs without error."""
    config = ScenarioTypeConfig(**_base_kwargs())
    assert config.scenario_type == ScenarioType.URBAN_DENSE
    assert config.avg_block_size == (100.0, 150.0)


def test_scenario_type_accepts_string_value() -> None:
    """Pydantic coerces the raw string to the ScenarioType enum member."""
    kwargs = _base_kwargs()
    kwargs["scenario_type"] = "urban_dense"
    config = ScenarioTypeConfig(**kwargs)
    assert config.scenario_type == ScenarioType.URBAN_DENSE


def test_invalid_scenario_type_rejected() -> None:
    """An unknown scenario_type string is rejected."""
    kwargs = _base_kwargs()
    kwargs["scenario_type"] = "not_a_real_type"
    with pytest.raises(ValidationError):
        ScenarioTypeConfig(**kwargs)


@pytest.mark.parametrize("field_name", ["avg_block_size", "building_heights", "traffic_density"])
def test_inverted_range_rejected(field_name: str) -> None:
    """(max, min) ordering is rejected for every range-typed field."""
    kwargs = _base_kwargs()
    kwargs[field_name] = (100.0, 50.0)
    with pytest.raises(ValidationError):
        ScenarioTypeConfig(**kwargs)


def test_inverted_num_intersections_rejected() -> None:
    """num_intersections must satisfy min <= max."""
    kwargs = _base_kwargs()
    kwargs["num_intersections"] = (9, 4)
    with pytest.raises(ValidationError):
        ScenarioTypeConfig(**kwargs)


@pytest.mark.parametrize("bad_density", [-0.1, 1.1])
def test_building_density_out_of_range_rejected(bad_density: float) -> None:
    """building_density outside [0, 1] is rejected."""
    kwargs = _base_kwargs()
    kwargs["building_density"] = bad_density
    with pytest.raises(ValidationError):
        ScenarioTypeConfig(**kwargs)


@pytest.mark.parametrize("boundary_density", [0.0, 1.0])
def test_building_density_boundary_accepted(boundary_density: float) -> None:
    """building_density exactly 0.0 or 1.0 is accepted (inclusive bounds)."""
    kwargs = _base_kwargs()
    kwargs["building_density"] = boundary_density
    config = ScenarioTypeConfig(**kwargs)
    assert config.building_density == boundary_density


def test_vehicle_mix_not_summing_to_one_rejected() -> None:
    """vehicle_mix fractions summing far from 1.0 are rejected."""
    kwargs = _base_kwargs()
    kwargs["vehicle_mix"] = {"sedan": 0.5, "suv": 0.1}
    with pytest.raises(ValidationError):
        ScenarioTypeConfig(**kwargs)


def test_vehicle_mix_within_float_tolerance_accepted() -> None:
    """vehicle_mix fractions summing to 0.999 (float rounding) are accepted."""
    kwargs = _base_kwargs()
    kwargs["vehicle_mix"] = {"sedan": 0.6, "suv": 0.25, "truck": 0.1, "bus": 0.049}
    config = ScenarioTypeConfig(**kwargs)
    assert config.vehicle_mix["bus"] == 0.049
