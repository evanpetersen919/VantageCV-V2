"""Scenario taxonomy and per-scenario-type configuration.

Defines the six scenario categories from MASTER_PROMPT Section 1.3 and the
configuration schema that parameterizes procedural generation for each of
them. Values are validated with pydantic so a malformed YAML template fails
fast at load time rather than producing a silently-invalid scenario.
"""

from enum import Enum
from typing import Dict, List, Tuple

from pydantic import BaseModel, field_validator


class ScenarioType(str, Enum):
    """Scenario taxonomy category. See MASTER_PROMPT Section 1.3."""

    URBAN_DENSE = "urban_dense"
    URBAN_SPARSE = "urban_sparse"
    HIGHWAY = "highway"
    MIXED_URBAN_HIGHWAY = "mixed_urban_highway"
    PARKING_LOT = "parking_lot"
    ROUNDABOUT = "roundabout"


class ScenarioTypeConfig(BaseModel):
    """Parameters governing procedural generation for one scenario type.

    Attributes
    ----------
    scenario_type : ScenarioType
        Which taxonomy category this configuration parameterizes.
    avg_block_size : Tuple[float, float]
        (min, max) meters. Grid spacing for road network generation is
        sampled uniformly from this range (MASTER_PROMPT Section 3.2.1).
    avg_road_width : float
        Meters, used as the default road width before per-edge overrides.
    num_intersections : Tuple[int, int]
        (min, max) expected intersection count, informational/validation use.
    intersection_types : List[str]
        Allowed intersection topologies (e.g. "4way", "3way").
    building_density : float
        Coverage ratio in [0, 1].
    building_heights : Tuple[float, float]
        (min, max) meters.
    traffic_density : Tuple[float, float]
        (min, max) fraction of spawn slots occupied, in [0, 1].
    vehicle_mix : Dict[str, float]
        Vehicle type name -> fraction of population. Must sum to ~1.0.
    complexity_score : int
        Informational relative complexity metric in [0, 100].
    road_setback_meters : float
        Minimum clearance (meters) a building must keep from every road,
        beyond the road's own half-width -- read by
        ``BuildingPlacementGenerator``. Defaults to 2.0 (real-world
        minimum sidewalk width guidance), matching the fixed constant
        this field replaces (see KNOWN_GAPS_AND_ISSUES.md).
    """

    scenario_type: ScenarioType
    avg_block_size: Tuple[float, float]
    avg_road_width: float
    num_intersections: Tuple[int, int]
    intersection_types: List[str]
    building_density: float
    building_heights: Tuple[float, float]
    traffic_density: Tuple[float, float]
    vehicle_mix: Dict[str, float]
    complexity_score: int
    road_setback_meters: float = 2.0

    @field_validator("avg_block_size", "building_heights", "traffic_density")
    @classmethod
    def _validate_range_ordering(cls, value: Tuple[float, float]) -> Tuple[float, float]:
        low, high = value
        if low > high:
            raise ValueError(f"Range must satisfy min <= max, got ({low}, {high})")
        return value

    @field_validator("num_intersections")
    @classmethod
    def _validate_intersection_range(cls, value: Tuple[int, int]) -> Tuple[int, int]:
        low, high = value
        if low > high:
            raise ValueError(f"num_intersections must satisfy min <= max, got ({low}, {high})")
        return value

    @field_validator("building_density")
    @classmethod
    def _validate_density(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"building_density must be in [0, 1], got {value}")
        return value

    @field_validator("vehicle_mix")
    @classmethod
    def _validate_vehicle_mix_sums_to_one(cls, value: Dict[str, float]) -> Dict[str, float]:
        total = sum(value.values())
        if not 0.99 <= total <= 1.01:
            raise ValueError(f"vehicle_mix fractions must sum to ~1.0, got {total}")
        return value

    @field_validator("road_setback_meters")
    @classmethod
    def _validate_road_setback(cls, value: float) -> float:
        if value < 0.0:
            raise ValueError(f"road_setback_meters must be non-negative, got {value}")
        return value
