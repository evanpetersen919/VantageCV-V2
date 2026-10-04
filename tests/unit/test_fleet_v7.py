"""The v7 fleet: pickups count as cars, models are weighted by registration share, and the
default v5 behavior is unchanged."""

from collections import Counter
from pathlib import Path

import numpy as np

from src.ground_truth.categories import COCO_PROFILE, SUV, TRUCK
from src.procedural.actor_placement import (
    ActorPlacementGenerator,
    _sample_asset_path,
    _sample_vehicle_type,
)
from src.procedural.city_sample_assets import FLEET_MODEL_WEIGHTS, VEHICLE_ASSET_PATHS, fleet_models
from src.procedural.parking_lots import PARKED_MODELS, PARKED_WEIGHTS_V7, _parked_model
from src.procedural.scenario import ScenarioTypeConfig
from src.utils.config_loader import load_scenario_config

PICKUP = "/Game/Vehicle/vehTruck_vehicle04/Mesh/SM_Frame_vehTruck_vehicle04"
TEMPLATE = Path("configs/scenario_templates/urban_dense_v7.yaml")


def test_v5_fleet_is_the_original_equal_weight_list() -> None:
    """The default fleet reproduces VEHICLE_ASSET_PATHS with equal weights."""
    for vehicle_type, paths in VEHICLE_ASSET_PATHS.items():
        assert fleet_models("v5", vehicle_type) == (list(paths), [1.0] * len(paths))


def test_v7_puts_the_pickup_under_suv_not_truck() -> None:
    """A pickup is a car in the COCO profile, so it cannot be listed under truck."""
    assert PICKUP in FLEET_MODEL_WEIGHTS["v7"]["suv"]
    assert PICKUP not in FLEET_MODEL_WEIGHTS["v7"]["truck"]
    assert COCO_PROFILE.mapping[SUV] != COCO_PROFILE.mapping[TRUCK]


def test_v7_model_shares_follow_the_registration_weights() -> None:
    """Over many draws the pickup is ~15% of vehicles and taxi/police are rare."""
    config = load_scenario_config(TEMPLATE)
    rng = np.random.Generator(np.random.PCG64(1))
    draws = Counter()
    for _ in range(40000):
        vehicle_type = _sample_vehicle_type(rng, config.vehicle_mix)
        draws[(vehicle_type, _sample_asset_path(rng, vehicle_type, "v7"))] += 1
    total = sum(draws.values())
    by_type = Counter()
    for (vehicle_type, _), count in draws.items():
        by_type[vehicle_type] += count
    assert abs(by_type["truck"] / total - 0.04) < 0.006
    assert abs(by_type["bus"] / total - 0.015) < 0.004
    pickups = draws[("suv", PICKUP)] / total
    assert 0.12 < pickups < 0.18
    taxi = draws[("suv", "/Game/Vehicle/vehCar_vehicle12/Mesh/SM_Frame_vehCar_vehicle12")] / total
    assert taxi < 0.03
    assert all(path != PICKUP for (vehicle_type, path) in draws if vehicle_type == "truck")


def test_parked_pool_v7_types_the_pickup_as_a_car() -> None:
    """In lots the single pickup is no longer labelled truck, and weights line up with models."""
    assert len(PARKED_WEIGHTS_V7) == len(PARKED_MODELS)
    rng = np.random.Generator(np.random.PCG64(3))
    types = Counter(_parked_model(rng, {}, "v7").vehicle_type for _ in range(5000))
    assert "truck" not in types
    assert 0.17 < types["suv"] / 5000 < 0.30  # pickup 1.0 + van 0.5 of 6.5 total weight


def test_parked_pool_v5_still_draws_trucks() -> None:
    """The default keeps the old flattened mix, with the pickup typed truck."""
    rng = np.random.Generator(np.random.PCG64(3))
    mix = {"sedan": 0.181, "suv": 0.614, "truck": 0.175}
    assert any(_parked_model(rng, mix).vehicle_type == "truck" for _ in range(200))


def test_v7_template_loads_with_its_fleet_and_pedestrian_range() -> None:
    """The v7 template sets the new fields; urban_dense.yaml keeps the v5 defaults."""
    v7 = load_scenario_config(TEMPLATE)
    assert (
        v7.fleet == "v7"
        and v7.pedestrian_density_fraction == (0.0, 0.45)
        and v7.pedestrian_density_skew == 3.0
    )
    v5 = load_scenario_config(Path("configs/scenario_templates/urban_dense.yaml"))
    assert v5.fleet == "v5" and v5.pedestrian_density_fraction == (0.3, 0.3)


def test_config_rejects_an_unknown_fleet_and_a_bad_density_range() -> None:
    """Typos fail at load time."""
    base = load_scenario_config(TEMPLATE).model_dump()
    for update in (
        {"fleet": "v9"},
        {"pedestrian_density_fraction": (0.2, 0.1)},
        {"pedestrian_density_skew": 0.5},
    ):
        try:
            ScenarioTypeConfig(**{**base, **update})
        except ValueError:
            continue
        raise AssertionError(f"accepted {update}")


def test_skewed_pedestrian_density_is_mostly_sparse_with_a_crowded_tail() -> (
    None
):  # pylint: disable=protected-access
    """With range (0, 0.45) and skew 3 the median scenario is sparse and the max is crowded."""
    config = load_scenario_config(TEMPLATE)
    densities = [ActorPlacementGenerator(seed, config)._pedestrian_density for seed in range(400)]
    assert 0.0 <= min(densities) and max(densities) <= 0.45
    assert np.median(densities) < 0.1 < max(densities)
    v6 = load_scenario_config(Path("configs/scenario_templates/urban_dense.yaml"))
    assert ActorPlacementGenerator(1, v6)._pedestrian_density == 0.3
