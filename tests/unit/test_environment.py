"""Unit tests for the scene environment (ground plane + UE5 settings)."""

import json

import numpy as np

from src.orchestration.dataset_generator import generate_scenario
from src.orchestration.scenario_serializer import serialize_scenario
from src.procedural.environment import DEFAULT_ENVIRONMENT, EnvironmentConfig, build_ground_mesh


def test_ground_mesh_is_a_single_upward_facing_quad_below_the_roads() -> None:
    """One quad, wound counter-clockwise seen from above, at the
    configured z (just below the z=0 road strips) with the ground tag."""
    env = EnvironmentConfig(ground_half_extent_m=500.0, ground_z_m=-0.05)
    mesh = build_ground_mesh(env)

    assert mesh.material == "ground"
    assert mesh.vertices.shape == (4, 3)
    assert np.allclose(mesh.vertices[:, 2], -0.05)
    assert len(mesh.triangles) == 6
    for first in range(0, 6, 3):
        a, b, c = (mesh.vertices[i] for i in mesh.triangles[first : first + 3])
        normal_z = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        assert normal_z > 0  # counter-clockwise from above => faces up


def test_ground_uvs_are_metres_divided_by_tile_size() -> None:
    """UVs tile the material once per ground_uv_tile_m metres."""
    env = EnvironmentConfig(ground_half_extent_m=100.0, ground_uv_tile_m=4.0)
    mesh = build_ground_mesh(env)

    assert np.allclose(mesh.uvs, mesh.vertices[:, :2] / 4.0)


def test_environment_json_has_the_fields_the_ue5_loader_reads() -> None:
    """Keys must match ProceduralScenarioLoader::ApplyEnvironment."""
    payload = DEFAULT_ENVIRONMENT.to_json()

    assert payload["hide_template_terrain"] is True
    assert set(payload["sun"]) == {"pitch_deg", "yaw_deg"}
    assert set(payload["fog"]) == {"density", "height_falloff", "start_distance_m"}
    assert set(payload["post_process"]) == {"exposure_bias", "saturation"}
    json.dumps(payload)


def test_serialize_scenario_adds_ground_and_environment_only_when_asked(
    urban_config, bounds
) -> None:
    """Without an environment the payload is just the scenario; with one,
    a ground mesh is appended and an "environment" object is added."""
    scenario = generate_scenario(42, urban_config, bounds, "env_test")

    plain = serialize_scenario(scenario)
    dressed = serialize_scenario(scenario, DEFAULT_ENVIRONMENT)

    assert "environment" not in plain
    assert len(dressed["meshes"]) == len(plain["meshes"]) + 1
    assert dressed["meshes"][-1]["material"] == "ground"
    assert dressed["environment"] == DEFAULT_ENVIRONMENT.to_json()
    json.dumps(dressed)
