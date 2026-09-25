"""Unit tests for the weather presets in environment.py: overrides layered on
the season, the night restriction, the seeded draw and the payload keys."""

import pytest

from src.procedural.environment import (
    NIGHT_ENVIRONMENT,
    WEATHER_SHARES,
    Season,
    TimeOfDay,
    Weather,
    draw_weather,
    scenario_environment,
    season_environment,
)


def test_clear_weather_changes_nothing() -> None:
    """Clear is exactly the season's own environment, for every season."""
    for season in Season:
        assert scenario_environment(season, TimeOfDay.DAY) == season_environment(season)
        assert scenario_environment(season, TimeOfDay.DAY, Weather.CLEAR) == season_environment(
            season
        )


def test_overcast_washes_the_sky_and_flattens_the_sun() -> None:
    """Overcast drops the sun, kills Rayleigh scattering and raises Mie
    (grey sky), and adds haze; the season's other fields survive."""
    base = season_environment(Season.SUMMER)
    env = scenario_environment(Season.SUMMER, TimeOfDay.DAY, Weather.OVERCAST)
    assert env.sun_intensity_lux == 2.0
    assert env.rayleigh_scale < 0.1 < 1.0 < env.mie_scale
    assert env.fog_density > base.fog_density
    assert env.sun_pitch_deg == base.sun_pitch_deg
    assert env.saturation == base.saturation


def test_low_sun_presets_are_lower_and_warmer_than_the_season() -> None:
    """Golden hour, sunset and dawn put the sun lower than summer's and set a
    warm colour temperature; sunset is the lowest and warmest."""
    summer = season_environment(Season.SUMMER)
    golden = scenario_environment(Season.SUMMER, TimeOfDay.DAY, Weather.GOLDEN_HOUR)
    sunset = scenario_environment(Season.SUMMER, TimeOfDay.DAY, Weather.SUNSET)
    dawn = scenario_environment(Season.SUMMER, TimeOfDay.DAY, Weather.DAWN_HAZE)
    for env in (golden, sunset, dawn):
        assert env.sun_pitch_deg > summer.sun_pitch_deg
        assert env.sun_temperature_k is not None and env.sun_temperature_k < 5500.0
    assert sunset.sun_pitch_deg > golden.sun_pitch_deg
    assert sunset.sun_temperature_k < golden.sun_temperature_k
    assert dawn.fog_density > summer.fog_density


def test_rain_is_overcast_light_with_wet_surfaces_and_only_rain_is_wet() -> None:
    """Rain has the overcast sky and lower roughness and deeper puddles on the
    road, ground and paving meshes; no other weather sets surface scalars."""
    rain = scenario_environment(Season.SUMMER, TimeOfDay.DAY, Weather.RAIN)
    overcast = scenario_environment(Season.SUMMER, TimeOfDay.DAY, Weather.OVERCAST)
    assert rain.mie_scale == overcast.mie_scale and rain.rayleigh_scale == overcast.rayleigh_scale
    assert set(rain.surface_scalars) == {"asphalt", "ground", "pavement"}
    assert rain.surface_scalars["asphalt"]["Roughness MFPD"] < 0.05
    assert rain.surface_scalars["asphalt"]["Puddle Height MFPD"] > 0.5
    for weather in Weather:
        env = scenario_environment(Season.SUMMER, TimeOfDay.DAY, weather)
        assert (env.surface_scalars is not None) == (weather == Weather.RAIN)
    assert rain.asset_vector_scales["Bldg_block*|Color Tint M1"] == 0.75
    assert rain.asset_scalars["veh_carPaint|Max Roughness"] < 0.05
    for weather in Weather:
        env = scenario_environment(Season.SUMMER, TimeOfDay.DAY, weather)
        assert (env.asset_scalars is not None) == (weather == Weather.RAIN)
        assert (env.asset_vector_scales is not None) == (weather == Weather.RAIN)
    payload = rain.to_json()["surface_scalars"]
    assert payload["asphalt"]["BaseRoughnessMult"] == 0.25
    assert "surface_scalars" not in overcast.to_json()


def test_fog_is_denser_than_overcast_haze() -> None:
    """The fog preset has the densest fog of all weathers."""
    densities = {
        weather: scenario_environment(Season.SUMMER, TimeOfDay.DAY, weather).fog_density
        for weather in Weather
    }
    assert max(densities, key=densities.get) == Weather.FOG


def test_night_takes_clear_or_rain_and_rejects_the_rest() -> None:
    """Night keeps its moonlit sky, allows rain (wet surfaces and dimmer
    streaks on top of it) and rejects every other weather."""
    assert scenario_environment(Season.SUMMER, TimeOfDay.NIGHT) is NIGHT_ENVIRONMENT
    night_rain = scenario_environment(Season.SUMMER, TimeOfDay.NIGHT, Weather.RAIN)
    assert night_rain.exposure_bias == NIGHT_ENVIRONMENT.exposure_bias
    assert night_rain.color_gain == NIGHT_ENVIRONMENT.color_gain
    assert night_rain.sun_temperature_k == NIGHT_ENVIRONMENT.sun_temperature_k
    assert night_rain.mie_scale is None
    assert set(night_rain.surface_scalars) == {"asphalt", "ground", "pavement"}
    day_rain = scenario_environment(Season.SUMMER, TimeOfDay.DAY, Weather.RAIN)
    assert 0.0 < night_rain.rain_intensity < day_rain.rain_intensity
    for weather in Weather:
        if weather not in (Weather.CLEAR, Weather.RAIN):
            with pytest.raises(ValueError):
                scenario_environment(Season.SUMMER, TimeOfDay.NIGHT, weather)


def test_rain_streaks_are_in_the_payload_only_for_rain() -> None:
    """Only rain adds a "rain" object (intensity, slant, seed)."""
    rain = scenario_environment(Season.SUMMER, TimeOfDay.DAY, Weather.RAIN).to_json()
    assert rain["rain"] == {"intensity": 0.9, "slant": 0.12, "seed": 1.0, "density": 0.5}
    assert rain["asset_vector_scales"]["veh_carPaint|BaseColor"] == 0.85
    for weather in Weather:
        if weather != Weather.RAIN:
            assert (
                "rain" not in scenario_environment(Season.SUMMER, TimeOfDay.DAY, weather).to_json()
            )
    assert scenario_environment(Season.SUMMER, TimeOfDay.NIGHT).to_json().get("rain") is None


def test_json_carries_only_the_fields_a_weather_sets() -> None:
    """A clear environment has no sky-atmosphere, sky-light, cloud or fog
    colour keys; overcast has the atmosphere and fog colour."""
    clear = scenario_environment(Season.SUMMER, TimeOfDay.DAY).to_json()
    assert "sky_atmosphere" not in clear and "sky_light" not in clear and "clouds" not in clear
    assert "color" not in clear["fog"] and "intensity_lux" not in clear["sun"]
    overcast = scenario_environment(Season.SUMMER, TimeOfDay.DAY, Weather.OVERCAST).to_json()
    assert overcast["sky_atmosphere"] == {
        "rayleigh_scale": 0.05,
        "mie_scale": 12.0,
        "mie_anisotropy": 0.3,
    }
    assert overcast["fog"]["color"] == [0.4, 0.42, 0.45]
    assert overcast["sun"]["intensity_lux"] == 2.0


def test_shares_sum_to_one_and_the_draw_is_seeded_and_follows_them() -> None:
    """Shares are a distribution; the draw repeats for a seed and a big sample
    matches each weather's share."""
    assert sum(WEATHER_SHARES.values()) == pytest.approx(1.0)
    assert draw_weather(7) == draw_weather(7)
    draws = [draw_weather(seed) for seed in range(6000)]
    for weather, share in WEATHER_SHARES.items():
        assert draws.count(weather) / len(draws) == pytest.approx(share, abs=0.02)
