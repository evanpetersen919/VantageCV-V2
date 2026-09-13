"""Shared pytest configuration and fixtures."""

from typing import Tuple

import pytest

from src.procedural.scenario import ScenarioType, ScenarioTypeConfig


@pytest.fixture(name="urban_config")
def urban_config_fixture() -> ScenarioTypeConfig:
    """Urban dense scenario configuration, shared across road-network
    unit and integration tests."""
    return ScenarioTypeConfig(
        scenario_type=ScenarioType.URBAN_DENSE,
        avg_block_size=(100.0, 150.0),
        avg_road_width=12.0,
        num_intersections=(4, 9),
        intersection_types=["4way", "3way"],
        building_density=0.8,
        building_heights=(20.0, 40.0),
        traffic_density=(0.6, 1.0),
        vehicle_mix={"sedan": 0.6, "suv": 0.25, "truck": 0.1, "bus": 0.05},
        complexity_score=80,
    )


@pytest.fixture(name="bounds")
def bounds_fixture() -> Tuple[float, float, float, float]:
    """Standard test bounds (500m x 500m)."""
    return (-250.0, -250.0, 250.0, 250.0)
