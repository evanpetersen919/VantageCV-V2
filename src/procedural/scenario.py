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
    parking_lot_fraction : float
        Share of city blocks (in expectation) that hold a surface parking
        lot instead of buildings, in [0, 1]. Defaults to 0 (no lots).
    fleet : str
        Which vehicle model weighting to use: ``"v5"`` (every model of a
        type equally likely, the pickup counted as a truck) or ``"v7"``
        (per-model weights, the pickup counted as a car); see
        ``city_sample_assets.FLEET_MODEL_WEIGHTS``.
    pedestrian_density_fraction : Tuple[float, float]
        (min, max) share of ``traffic_density`` used as a sidewalk spot's
        pedestrian occupancy; drawn once per scenario when min < max, as
        ``min + (max - min) * u ** skew`` with ``u`` uniform in [0, 1].
    pedestrian_density_skew : float
        Exponent of that draw: 1 is uniform, larger values give many sparse scenes and a few
        crowded ones (real street footage clumps; BDD100K has 3 or more people in 15-23% of
        frames but one in 32-44%).
    pedestrian_source : str
        ``"city_sample"`` (the project's original crowd characters) or ``"rocketbox"``
        (Microsoft Rocketbox avatars swapped in after generation; see
        ``rocketbox_pedestrians.py``).
    lane_markings : bool
        Paint centre lines, lane lines and stop lines on the roads (``lane_markings.py``). Off by
        default so seeds of earlier batches give the same scenes.
    signal_states : bool
        Show each signal pole's colour for its intersection's phase, and put poles only at the
        signalized intersections (``traffic_lights.py``). Off by default so seeds of earlier
        batches give the same scenes.
    foliage : bool
        Replace the bare Epic street trees with leafy procedural ones in spring, summer and fall
        (``foliage.py``). Off by default so seeds of earlier batches give the same
        scenes.
    photoreal_trees : bool
        With ``foliage``: use scanned photographic tree models (``photoreal_trees.py``) instead of
        the generated card trees. Off by default.
    paint_wear : float
        How worn the painted lines are, 0 (fresh) to 1: random chips and eroded ends
        (``lane_markings``).
    cyclists : bool
        Place riders on bicycles along the curb of the driving lanes (``cyclists.py``). Off by
        default so seeds of earlier batches give the same scenes.
    cyclist_run_probability : float
        The chance that a curb run holds a cyclist, and again for each further one (up to two).
    planting : bool
        Add grass patches, shrubs and hedges beside the curb (``planting.py``). Off by default so
        seeds of earlier batches give the same scenes.
    street_tree_spacing_m : float
        Distance between street-tree spots along a curb. The default is what Epic's own placements
        measure; a denser street needs a smaller value (see ``foliage.py``).
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
    parking_lot_fraction: float = 0.0
    fleet: str = "v5"
    # Factors applied to ``vehicle_mix`` weights at night (types not listed keep their weight): real
    # trucks and buses are far more common by day than by night, and the generator draws the same
    # mix at any hour unless this is set.
    night_vehicle_scale: Dict[str, float] = {}
    pedestrian_density_fraction: Tuple[float, float] = (0.3, 0.3)
    pedestrian_density_skew: float = 1.0
    pedestrian_source: str = "city_sample"
    lane_markings: bool = False
    signal_states: bool = False
    foliage: bool = False
    photoreal_trees: bool = False
    planting: bool = False
    cyclists: bool = False
    paint_wear: float = 0.0
    cyclist_run_probability: float = 0.6
    street_tree_spacing_m: float = 20.21

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

    @field_validator("fleet")
    @classmethod
    def _validate_fleet(cls, value: str) -> str:
        if value not in ("v5", "v7", "v8a", "v8b", "v11"):
            raise ValueError(f"fleet must be 'v5', 'v7', 'v8a' or 'v8b', got {value!r}")
        return value

    @field_validator("pedestrian_source")
    @classmethod
    def _validate_pedestrian_source(cls, value: str) -> str:
        if value not in ("city_sample", "rocketbox"):
            raise ValueError(
                f"pedestrian_source must be 'city_sample' or 'rocketbox', got {value!r}"
            )
        return value

    @field_validator("night_vehicle_scale")
    @classmethod
    def _validate_night_scale(cls, value: Dict[str, float]) -> Dict[str, float]:
        if any(factor < 0.0 for factor in value.values()):
            raise ValueError(f"night_vehicle_scale factors must be >= 0, got {value}")
        return value

    def vehicle_mix_for(self, night: bool) -> Dict[str, float]:
        """The mix to draw from: ``vehicle_mix``, with ``night_vehicle_scale`` applied at night."""
        if not night or not self.night_vehicle_scale:
            return self.vehicle_mix
        return {
            name: weight * self.night_vehicle_scale.get(name, 1.0)
            for name, weight in self.vehicle_mix.items()
        }

    @field_validator("pedestrian_density_skew")
    @classmethod
    def _validate_density_skew(cls, value: float) -> float:
        if value < 1.0:
            raise ValueError(f"pedestrian_density_skew must be >= 1, got {value}")
        return value

    @field_validator("pedestrian_density_fraction")
    @classmethod
    def _validate_pedestrian_density(cls, value: Tuple[float, float]) -> Tuple[float, float]:
        low, high = value
        if not 0.0 <= low <= high <= 1.0:
            raise ValueError(
                f"pedestrian_density_fraction must satisfy 0 <= min <= max <= 1, got {value}"
            )
        return value

    @field_validator("parking_lot_fraction")
    @classmethod
    def _validate_parking_lot_fraction(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"parking_lot_fraction must be in [0, 1], got {value}")
        return value

    @field_validator("road_setback_meters")
    @classmethod
    def _validate_road_setback(cls, value: float) -> float:
        if value < 0.0:
            raise ValueError(f"road_setback_meters must be non-negative, got {value}")
        return value
