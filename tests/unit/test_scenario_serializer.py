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
    "assets" (present, empty -- populated by later City Sample
    integration phases, not yet)."""
    scenario = generate_scenario(42, urban_config, bounds, "serializer_test")

    payload = serialize_scenario(scenario)

    assert set(payload.keys()) == {"meshes", "assets"}
    assert not payload["assets"]
    assert len(payload["meshes"]) == len(scenario.meshes)


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
    """A ScenarioResult with no meshes serializes to an empty (not
    missing, not erroring) "meshes" list -- exercised directly via a
    minimal fake, since every real generated scenario has meshes."""

    class _FakeResult:  # pylint: disable=too-few-public-methods
        meshes: list = []

    payload = serialize_scenario(_FakeResult())  # type: ignore[arg-type]

    assert payload == {"meshes": [], "assets": []}
