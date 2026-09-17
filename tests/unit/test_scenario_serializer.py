"""Unit tests for scenario_serializer.

Regression coverage for a real gap found while planning the City Sample
asset integration work: no committed code converted a ScenarioResult into
the JSON shape UE5 actually expects before this module existed -- tonight's
real, live-UE5-verified round trip ran through an uncommitted scratchpad
script. See KNOWN_GAPS_AND_ISSUES.md.
"""

import json

from src.orchestration.dataset_generator import generate_scenario
from src.orchestration.scenario_serializer import serialize_scenario

# urban_config, bounds fixtures: see tests/conftest.py


def test_serialize_scenario_produces_meshes_and_assets_keys(urban_config, bounds) -> None:
    """A serialized scenario has exactly the top-level shape
    ProceduralScenarioLoader.cpp parses: "meshes" (populated) and
    "assets" (one entry per vehicle, as of Phase 1 of the City Sample
    integration work -- props/hero buildings still empty, added by
    later phases)."""
    scenario = generate_scenario(42, urban_config, bounds, "serializer_test")
    assert scenario.vehicles  # sanity: this config/seed places some

    payload = serialize_scenario(scenario)

    assert set(payload.keys()) == {"meshes", "assets"}
    assert len(payload["assets"]) == len(scenario.vehicles)
    assert len(payload["meshes"]) == len(scenario.meshes)


def test_serialize_scenario_preserves_vehicle_asset_data_exactly(urban_config, bounds) -> None:
    """Every vehicle's asset path, position, heading, and id survive
    into its "assets" entry exactly -- the real invariant Phase 1 of the
    City Sample integration work exists to guarantee."""
    scenario = generate_scenario(42, urban_config, bounds, "serializer_test")
    assert scenario.vehicles

    payload = serialize_scenario(scenario)

    for vehicle, asset in zip(scenario.vehicles, payload["assets"]):
        assert asset["category"] == "vehicle"
        assert asset["asset_path"] == vehicle.asset_path
        assert asset["position"] == [float(vehicle.center[0]), float(vehicle.center[1]), 0.0]
        assert asset["rotation_rad"] == float(vehicle.heading_rad)
        assert asset["id"] == vehicle.vehicle_id


def test_serialize_scenario_preserves_mesh_data_exactly(urban_config, bounds) -> None:
    """Every mesh's vertex/triangle/uv counts and material string survive
    the numpy-array-to-JSON-list conversion exactly -- the real invariant
    this module exists to guarantee."""
    scenario = generate_scenario(42, urban_config, bounds, "serializer_test")
    assert scenario.meshes  # sanity: this config/seed produces some

    payload = serialize_scenario(scenario)

    for source_mesh, serialized_mesh in zip(scenario.meshes, payload["meshes"]):
        assert len(serialized_mesh["vertices"]) == len(source_mesh.vertices)
        assert all(len(vertex) == 3 for vertex in serialized_mesh["vertices"])
        assert len(serialized_mesh["triangles"]) == len(source_mesh.triangles)
        assert len(serialized_mesh["uvs"]) == len(source_mesh.uvs)
        assert all(len(uv) == 2 for uv in serialized_mesh["uvs"])
        assert serialized_mesh["material"] == source_mesh.material


def test_serialize_scenario_is_json_serializable(urban_config, bounds) -> None:
    """json.dumps never raises on a real serialized scenario.

    Regression guard for the real, likely bug class this module's own
    docstring calls out: every Mesh field is a numpy array, whose
    elements (numpy.float64/numpy.int64) are NOT JSON-serializable
    without the explicit .tolist() conversion -- a bare
    json.dumps(mesh.vertices) would raise TypeError.
    """
    scenario = generate_scenario(42, urban_config, bounds, "serializer_test")

    payload = serialize_scenario(scenario)

    serialized = json.dumps(payload)
    round_tripped = json.loads(serialized)
    assert len(round_tripped["meshes"]) == len(scenario.meshes)


def test_serialize_scenario_handles_empty_meshes() -> None:
    """A ScenarioResult with no meshes/vehicles serializes to empty (not
    missing, not erroring) "meshes"/"assets" lists -- exercised directly
    via a minimal fake, since every real generated scenario has both."""

    class _FakeResult:  # pylint: disable=too-few-public-methods
        meshes: list = []
        vehicles: list = []

    payload = serialize_scenario(_FakeResult())  # type: ignore[arg-type]

    assert payload == {"meshes": [], "assets": []}
