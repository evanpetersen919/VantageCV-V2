"""Unit tests for scenario_serializer.

Regression coverage for a real gap found while planning the City Sample
asset integration work: no committed code converted a ScenarioResult into
the JSON shape UE5 actually expects before this module existed -- tonight's
real, live-UE5-verified round trip ran through an uncommitted scratchpad
script. See KNOWN_GAPS_AND_ISSUES.md.
"""

import json

import numpy as np
import pytest

from src.orchestration.dataset_generator import generate_scenario
from src.orchestration.scenario_serializer import _facade_piece_to_asset_json, serialize_scenario
from src.procedural.building_facade import FacadePiece
from src.procedural.city_sample_assets import PEDESTRIAN_MESH_FORWARD_OFFSET_RAD, VEHICLE_PART_PATHS
from src.procedural.environment import TimeOfDay
from src.procedural.street_furniture import LAMP_ASSET_PATHS, STREET_LAMP_OFF_OVERRIDES

# urban_config, bounds fixtures: see tests/conftest.py


def test_serialize_scenario_produces_meshes_and_assets_keys(urban_config, bounds) -> None:
    """A serialized scenario has exactly the top-level shape
    ProceduralScenarioLoader.cpp parses: "meshes" (populated) and
    "assets" (one entry per vehicle, per building facade piece and per
    road curb/sidewalk piece -- props still not populated, a deliberate
    later fast-follow)."""
    scenario = generate_scenario(42, urban_config, bounds, "serializer_test")
    assert scenario.vehicles  # sanity: this config/seed places some
    assert scenario.building_facade_pieces  # sanity: this config/seed places buildings

    payload = serialize_scenario(scenario)

    assert set(payload.keys()) == {"meshes", "assets"}
    assert scenario.road_edge_pieces  # sanity: the road network has edges
    assert scenario.street_furniture_pieces
    assert scenario.crosswalk_pieces
    assert scenario.traffic_light_pieces
    assert scenario.pedestrians
    assert len(payload["assets"]) == (
        len(scenario.vehicles)
        + len(scenario.building_facade_pieces)
        + len(scenario.road_edge_pieces)
        + len(scenario.street_furniture_pieces)
        + len(scenario.crosswalk_pieces)
        + len(scenario.traffic_light_pieces)
        + len(scenario.pedestrians)
    )
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


def test_serialize_scenario_populates_vehicle_part_paths(urban_config, bounds) -> None:
    """Every vehicle's "part_paths" matches VEHICLE_PART_PATHS's real
    entry for that vehicle's own folder -- the wheels/doors/glass/
    interior spawned alongside the body (see city_sample_assets.py)."""
    scenario = generate_scenario(42, urban_config, bounds, "serializer_test")
    assert scenario.vehicles

    payload = serialize_scenario(scenario)

    for vehicle, asset in zip(scenario.vehicles, payload["assets"]):
        folder = vehicle.asset_path.split("/")[3]
        assert asset["part_paths"] == VEHICLE_PART_PATHS[folder]
        assert asset["part_paths"], f"Expected real parts for {folder!r}"


def test_serialize_scenario_preserves_facade_piece_data_exactly(urban_config, bounds) -> None:
    """Every building facade piece's asset path, position, and rotation
    survive into its "assets" entry exactly, tagged "static_asset" with
    no part_paths -- the real invariant the building-facade integration
    exists to guarantee, mirroring the vehicle test above."""
    scenario = generate_scenario(42, urban_config, bounds, "serializer_test")
    assert scenario.building_facade_pieces

    payload = serialize_scenario(scenario)
    static_assets = [asset for asset in payload["assets"] if asset["category"] == "static_asset"]
    # Building facade pieces come first, then the road curb/sidewalk pieces.
    facade_assets = static_assets[: len(scenario.building_facade_pieces)]

    assert len(static_assets) == (
        len(scenario.building_facade_pieces)
        + len(scenario.road_edge_pieces)
        + len(scenario.street_furniture_pieces)
        + len(scenario.crosswalk_pieces)
        + len(scenario.traffic_light_pieces)
        + len(scenario.pedestrians)
    )
    for piece, asset in zip(scenario.building_facade_pieces, facade_assets):
        assert asset["asset_path"] == piece.asset_path
        assert asset["position"] == [
            float(piece.position[0]),
            float(piece.position[1]),
            float(piece.position[2]),
        ]
        assert asset["rotation_rad"] == float(piece.rotation_rad)
        assert asset["part_paths"] == []


def test_serialize_scenario_preserves_pedestrian_asset_data_exactly(urban_config, bounds) -> None:
    """Every pedestrian's asset path, (x, y) position, id, and real
    top/bottom/shoe/face part_paths survive into its "assets" entry
    exactly -- mirroring the vehicle test above. z is the pedestrian's
    own real ``surface_z`` (sidewalk height for a sidewalk walker, real
    road-surface height for a CROSSING pedestrian -- see
    ``Pedestrian.surface_z``'s own docstring for the real floating-on-
    the-road bug this distinction fixes), not a single hardcoded
    constant, and rotation_rad carries the real mesh-forward-axis
    correction on top of heading_rad -- see ``_pedestrian_to_asset_json``'s
    own docstring."""
    scenario = generate_scenario(42, urban_config, bounds, "serializer_test")
    assert scenario.pedestrians

    payload = serialize_scenario(scenario)
    pedestrian_assets = payload["assets"][-len(scenario.pedestrians) :]

    for pedestrian, asset in zip(scenario.pedestrians, pedestrian_assets):
        assert asset["category"] == "static_asset"
        assert asset["asset_path"] == pedestrian.asset_path
        assert asset["position"] == [
            float(pedestrian.center[0]),
            float(pedestrian.center[1]),
            pedestrian.surface_z,
        ]
        assert asset["rotation_rad"] == pytest.approx(
            float(pedestrian.heading_rad) + PEDESTRIAN_MESH_FORWARD_OFFSET_RAD
        )
        assert asset["part_paths"] == pedestrian.part_paths
        assert len(asset["part_paths"]) in (4, 5)
        assert asset["material_scalar_overrides"] == {"Frame": pedestrian.pose_frame}


def test_serialize_scenario_live_pose_preview_is_opt_in(urban_config, bounds) -> None:
    """ "enable_live_pose_preview" is ABSENT (not just false) from every
    pedestrian asset entry by default -- the real dataset-generation
    pipeline never passes this, so old payloads stay byte-identical.
    When explicitly requested, every pedestrian entry carries
    ``"enable_live_pose_preview": True`` -- an interactive QA/review aid
    only (see ``serialize_scenario``'s own docstring for why this must
    never affect the real, reproducible dataset-capture path)."""
    scenario = generate_scenario(42, urban_config, bounds, "serializer_test")
    assert scenario.pedestrians

    default_payload = serialize_scenario(scenario)
    default_pedestrian_assets = default_payload["assets"][-len(scenario.pedestrians) :]
    for asset in default_pedestrian_assets:
        assert "enable_live_pose_preview" not in asset

    preview_payload = serialize_scenario(scenario, enable_live_pose_preview=True)
    preview_pedestrian_assets = preview_payload["assets"][-len(scenario.pedestrians) :]
    for asset in preview_pedestrian_assets:
        assert asset["enable_live_pose_preview"] is True


def test_serialize_scenario_vehicle_and_facade_assets_have_no_material_overrides(
    urban_config, bounds
) -> None:
    """Only pedestrians and (by day) regular street lamps carry
    "material_scalar_overrides" -- vehicles and building facade pieces
    have nothing to override, and ApplyMaterialScalarOverrides
    (VehicleActorSpawner.cpp) is a no-op for an entry with no such key, so
    this is a real, checkable invariant, not just an implementation
    detail."""
    scenario = generate_scenario(42, urban_config, bounds, "serializer_test")
    assert scenario.vehicles
    assert scenario.buildings
    assert scenario.pedestrians  # needed for the negative-index slice below

    payload = serialize_scenario(scenario)
    non_pedestrian_assets = payload["assets"][: -len(scenario.pedestrians)]

    assert non_pedestrian_assets  # sanity: vehicles/facade pieces exist
    saw_lamp = False
    for asset in non_pedestrian_assets:
        if asset["asset_path"] in LAMP_ASSET_PATHS:
            assert asset["material_scalar_overrides"] == STREET_LAMP_OFF_OVERRIDES
            saw_lamp = True
        else:
            assert "material_scalar_overrides" not in asset
    assert saw_lamp  # sanity: this seed places street lamps


def test_street_lamps_keep_their_default_glow_at_night(urban_config, bounds) -> None:
    """The lamp-off override is a DAYTIME thing: a night payload leaves
    every street lamp's own default glow alone."""
    night = generate_scenario(42, urban_config, bounds, "night", time_of_day=TimeOfDay.NIGHT)
    lamps = [a for a in serialize_scenario(night)["assets"] if a["asset_path"] in LAMP_ASSET_PATHS]
    assert lamps
    assert all("material_scalar_overrides" not in lamp for lamp in lamps)


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
        building_facade_pieces: list = []
        road_edge_pieces: list = []
        street_furniture_pieces: list = []
        crosswalk_pieces: list = []
        traffic_light_pieces: list = []
        pedestrians: list = []
        time_of_day = TimeOfDay.DAY

    payload = serialize_scenario(_FakeResult())  # type: ignore[arg-type]

    assert payload == {"meshes": [], "assets": []}


def test_facade_piece_scale_is_serialized_only_when_set() -> None:
    """An unscaled piece's JSON has no "scale" key (existing payloads stay
    identical); a scaled one carries it as three plain floats, including a
    negative (mirroring) component."""
    unscaled = FacadePiece("/Game/Test/Piece", np.array([1.0, 2.0, 3.0]), 0.5)
    scaled = FacadePiece("/Game/Test/Piece", np.array([1.0, 2.0, 3.0]), 0.5, (1.0, -0.75, 0.75))

    assert "scale" not in _facade_piece_to_asset_json(unscaled, 0)
    entry = _facade_piece_to_asset_json(scaled, 1)
    assert entry["scale"] == [1.0, -0.75, 0.75]
    json.dumps(entry)


def test_night_payload_carries_four_real_lights_per_vehicle_and_day_carries_none(
    urban_config, bounds
) -> None:
    """A night scenario adds a top-level "lights" array (two headlight
    spots and two tail points per vehicle); a day scenario has no
    "lights" key at all, so every existing daytime payload is unchanged."""
    day = generate_scenario(42, urban_config, bounds, "day")
    night = generate_scenario(42, urban_config, bounds, "night", time_of_day=TimeOfDay.NIGHT)
    assert "lights" not in serialize_scenario(day)
    lights = serialize_scenario(night)["lights"]
    assert len(lights) == 4 * len(night.vehicles)
    assert sum(1 for light in lights if light["type"] == "spot") == 2 * len(night.vehicles)
    assert len(serialize_scenario(night)["glows"]) == 4 * len(night.vehicles)
    assert "glows" not in serialize_scenario(day)
