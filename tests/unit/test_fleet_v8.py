"""The v8 truck and bus mix: fewer rigs, a fleet that labels some pickups and vans as trucks, and
fewer trucks and buses at night. Everything else, and every older config, must be unchanged."""

from collections import Counter
from pathlib import Path

import numpy as np

from src.procedural.actor_placement import _sample_vehicle_type
from src.procedural.city_sample_assets import RIG_SUFFIX, TRACTOR_FOLDER, fleet_models
from src.utils.config_loader import load_scenario_config

TEMPLATES = Path("configs/scenario_templates")


def _truck_shares(fleet: str) -> Counter:
    paths, weights = fleet_models(fleet, "truck")
    total = sum(weights)
    shares: Counter = Counter()
    for path, weight in zip(paths, weights):
        if path.endswith(RIG_SUFFIX):
            shares["rig"] += weight / total
        elif "vehicle11" in path:
            shares["three_axle"] += weight / total
        else:
            shares["pickup_or_van"] += weight / total
    return shares


def test_v8a_cuts_the_rig_and_keeps_the_other_truck() -> None:
    """v7 is half rigs; v8a is a tenth rigs and only the two models v7 had."""
    assert abs(_truck_shares("v7")["rig"] - 0.5) < 1e-9
    shares = _truck_shares("v8a")
    assert abs(shares["rig"] - 0.10) < 1e-9 and abs(shares["three_axle"] - 0.90) < 1e-9
    assert shares["pickup_or_van"] == 0.0


def test_v8b_labels_pickups_and_vans_as_trucks_for_a_fifth_of_them() -> None:
    """Real BDD100K labels about 15-20% of its truck boxes on pickups and vans."""
    shares = _truck_shares("v8b")
    assert abs(shares["pickup_or_van"] - 0.20) < 1e-9
    assert abs(shares["rig"] - 0.10) < 1e-9 and abs(shares["three_axle"] - 0.70) < 1e-9
    assert TRACTOR_FOLDER in "".join(fleet_models("v8b", "truck")[0])


def test_other_vehicle_types_are_the_v7_ones() -> None:
    """Only the truck list changed: sedans, SUVs and the bus draw from the same models."""
    for fleet in ("v8a", "v8b"):
        for vehicle_type in ("sedan", "suv", "bus"):
            assert fleet_models(fleet, vehicle_type) == fleet_models("v7", vehicle_type)


def test_night_scale_applies_only_at_night_and_only_to_the_listed_types() -> None:
    """``vehicle_mix_for`` scales the listed types at night and returns the mix itself by day."""
    config = load_scenario_config(TEMPLATES / "urban_dense_v8a.yaml")
    assert config.night_vehicle_scale == {"truck": 0.30, "bus": 0.36}
    assert config.vehicle_mix_for(False) is config.vehicle_mix
    night = config.vehicle_mix_for(True)
    assert abs(night["truck"] - 0.051 * 0.30) < 1e-9 and abs(night["bus"] - 0.033 * 0.36) < 1e-9
    assert (
        night["sedan"] == config.vehicle_mix["sedan"] and night["suv"] == config.vehicle_mix["suv"]
    )


def test_drawn_night_traffic_has_about_a_third_of_the_trucks_and_buses() -> None:
    """The sampler follows the scaled mix: the night/day truck rate is near the factor 0.30."""
    config = load_scenario_config(TEMPLATES / "urban_dense_v8a.yaml")
    rates = {}
    for night in (False, True):
        rng = np.random.default_rng(0)
        draws = Counter(
            _sample_vehicle_type(rng, config.vehicle_mix_for(night)) for _ in range(60000)
        )
        rates[night] = (draws["truck"] / 60000, draws["bus"] / 60000)
    # the scaled weights are renormalised, so the ratio is a little above the factor itself
    assert 0.27 < rates[True][0] / rates[False][0] < 0.35
    assert 0.32 < rates[True][1] / rates[False][1] < 0.41


def test_older_configs_are_unchanged() -> None:
    """No night scale: the mix is the very same object, so every earlier draw is unchanged."""
    for name in ("urban_dense.yaml", "urban_dense_v7.yaml", "urban_dense_v7_peds.yaml"):
        config = load_scenario_config(TEMPLATES / name)
        assert not config.night_vehicle_scale
        assert config.vehicle_mix_for(True) is config.vehicle_mix


def test_v8b_config_differs_from_v8a_only_in_the_fleet() -> None:
    """The two arms share everything but the truck list, so they can be compared directly."""
    first = load_scenario_config(TEMPLATES / "urban_dense_v8a.yaml")
    second = load_scenario_config(TEMPLATES / "urban_dense_v8b.yaml")
    assert (first.fleet, second.fleet) == ("v8a", "v8b")
    assert first.model_copy(update={"fleet": "v8b"}) == second
