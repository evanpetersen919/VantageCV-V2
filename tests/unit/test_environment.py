"""Unit tests for the scene environment (ground plane + UE5 settings)."""

import json

import numpy as np

from src.orchestration.dataset_generator import generate_scenario
from src.orchestration.scenario_serializer import serialize_scenario
from src.procedural.environment import (
    DEFAULT_ENVIRONMENT,
    EnvironmentConfig,
    Season,
    TimeOfDay,
    build_ground_mesh,
    scenario_environment,
    season_environment,
    season_has_trees,
)


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
    the ground mesh, the block paving, the intersection paving and the
    roof slabs are appended and an "environment" object is added."""
    scenario = generate_scenario(42, urban_config, bounds, "env_test")

    plain = serialize_scenario(scenario)
    dressed = serialize_scenario(scenario, DEFAULT_ENVIRONMENT)

    assert "environment" not in plain
    extra = dressed["meshes"][len(plain["meshes"]) :]
    assert extra[0]["material"] == "ground"
    assert len(extra) > 1  # the block/intersection paving follows the ground
    materials = {mesh["material"] for mesh in extra[1:]}
    assert "pavement" in materials
    assert "asphalt" in materials  # the paved intersection surfaces
    assert materials - {"pavement", "asphalt"} <= {"roof_0", "roof_1", "roof_2", "roof_3"}
    assert dressed["environment"] == DEFAULT_ENVIRONMENT.to_json()
    json.dumps(dressed)


def test_every_season_has_a_preset_and_the_two_leafless_seasons_keep_trees() -> None:
    """Each season maps to an environment; only winter and fall have street
    trees (Epic's trees are bare skeletons, so leafy seasons omit them)."""
    for season in Season:
        assert isinstance(season_environment(season), EnvironmentConfig)
    assert {s for s in Season if season_has_trees(s)} == {Season.WINTER, Season.FALL}


def test_season_presets_differ_in_sun_and_fog_and_winter_is_lowest_and_coolest() -> None:
    """Presets are distinct, winter has the lowest sun and the coolest
    light, and the optional sun temperature and colour gain reach the JSON."""
    presets = {s: season_environment(s) for s in Season}

    assert len({(p.sun_pitch_deg, p.fog_density, p.saturation) for p in presets.values()}) == 4
    assert presets[Season.WINTER].sun_pitch_deg == max(p.sun_pitch_deg for p in presets.values())
    assert presets[Season.SUMMER].sun_pitch_deg == min(p.sun_pitch_deg for p in presets.values())
    winter_json = presets[Season.WINTER].to_json()
    assert winter_json["sun"]["temperature_k"] == presets[Season.WINTER].sun_temperature_k
    assert winter_json["post_process"]["gain"] == list(presets[Season.WINTER].color_gain or ())
    assert "temperature_k" not in DEFAULT_ENVIRONMENT.to_json()["sun"]
    assert "gain" not in DEFAULT_ENVIRONMENT.to_json()["post_process"]


def _birches(result) -> list:
    """The street-birch pieces of a generated scenario."""
    return [p for p in result.street_furniture_pieces if "/Kit_Tree_Birch/" in p.asset_path]


def test_scenario_season_drives_trees_and_is_seeded(urban_config, bounds) -> None:
    """A fixed season decides whether trees appear; with no season the seed
    picks one deterministically, and earlier style draws are unaffected."""
    winter = generate_scenario(5, urban_config, bounds, "w", season=Season.WINTER)
    summer = generate_scenario(5, urban_config, bounds, "s", season=Season.SUMMER)
    auto_a = generate_scenario(5, urban_config, bounds, "a")
    auto_b = generate_scenario(5, urban_config, bounds, "b")

    assert winter.season is Season.WINTER and _birches(winter)
    assert summer.season is Season.SUMMER and not _birches(summer)
    assert auto_a.season is auto_b.season
    assert [p.asset_path for p in winter.road_edge_pieces] == [
        p.asset_path for p in summer.road_edge_pieces
    ]
    assert {generate_scenario(s, urban_config, bounds, "x").season for s in range(12)} == set(
        Season
    )


def test_day_uses_the_seasons_own_environment() -> None:
    """By day the scenario environment is exactly the season preset."""
    for season in Season:
        assert scenario_environment(season, TimeOfDay.DAY) == season_environment(season)


def test_night_environment_is_season_independent_and_moonlit() -> None:
    """Night is one preset regardless of season, keeps a light source
    ABOVE the horizon (a sun below it left the scene unlit, all black --
    found live), and is much darker than any daytime preset."""
    night = scenario_environment(Season.SUMMER, TimeOfDay.NIGHT)
    assert all(scenario_environment(season, TimeOfDay.NIGHT) == night for season in Season)
    assert night.sun_pitch_deg < 0.0  # light stays above the horizon
    assert all(night.exposure_bias < season_environment(season).exposure_bias for season in Season)
