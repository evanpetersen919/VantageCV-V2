# pylint: disable=missing-function-docstring
"""The v11 fleet adds the box truck to v8a's truck pool and changes nothing else."""

from src.procedural.actor_placement import vehicle_box
from src.procedural.city_sample_assets import BOXTRUCK_BODY, FLEET_MODEL_WEIGHTS, fleet_models
from src.procedural.vehicle_bounds import VEHICLE_MODEL_BOUNDS


def test_v11_truck_pool_is_v8a_with_30_percent_box_truck() -> None:
    weights = FLEET_MODEL_WEIGHTS["v11"]["truck"]
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert weights[BOXTRUCK_BODY] == 0.30
    v8a = FLEET_MODEL_WEIGHTS["v8a"]["truck"]
    rig = next(path for path in v8a if path.endswith("+trailer"))
    assert weights[rig] == v8a[rig]


def test_v11_other_types_equal_v8a() -> None:
    for vehicle_type in ("sedan", "suv", "bus"):
        assert FLEET_MODEL_WEIGHTS["v11"][vehicle_type] == FLEET_MODEL_WEIGHTS["v8a"][vehicle_type]


def test_older_fleets_never_draw_the_box_truck() -> None:
    for fleet in ("v5", "v7", "v8a", "v8b"):
        for vehicle_type in ("sedan", "suv", "truck", "bus"):
            assert BOXTRUCK_BODY not in fleet_models(fleet, vehicle_type)[0]


def test_box_truck_has_a_measured_box() -> None:
    length, width, height, _, _, z_min = vehicle_box(BOXTRUCK_BODY, "truck")
    assert (length, width, height) == VEHICLE_MODEL_BOUNDS["Meshes"][:3]
    assert 5.0 < length < 6.0 and 2.5 < width < 3.0 and 2.5 < height < 3.2
    assert abs(z_min) < 0.05
