"""Scene environment for rendered scenarios: the ground plane plus the sun,
fog and colour grade the UE5 plugin applies (see ``ProceduralScenarioLoader
::ApplyEnvironment``).

Without this the engine template's checkerboard floor and bare desert
hills fill every frame. Values start from Epic's City Sample levels
(height-fog falloff 0.07 and start distance in the hundreds of metres, a
low warm sun, a slightly desaturated grade) and were then tuned by eye
against our own scene, because City Sample's exact values (exposure bias
-1.0, sun temperature 4500K, green-tinted gain) gave a dark teal cast
under our lighting. Every field is a plain number so it can later be
randomized per scenario (time of day, haze) as a domain-randomization
knob.

The ground is a single large quad built through the normal mesh path with
the ``"ground"`` material tag (City Sample's matte parking-lot asphalt,
already migrated), sitting just below the road strips (z=0) so nothing
z-fights. UVs run in metres divided by ``ground_uv_tile_m``.
"""

import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

import numpy as np

from src.procedural.mesh_factory import Mesh, flat_quad_mesh


@dataclass(frozen=True)
class EnvironmentConfig:  # pylint: disable=too-many-instance-attributes
    """Everything the plugin needs to dress a scenario's surroundings."""

    hide_template_terrain: bool = True
    sun_pitch_deg: float = -40.0
    sun_yaw_deg: float = 150.0
    fog_density: float = 0.004
    fog_height_falloff: float = 0.07
    fog_start_distance_m: float = 300.0
    exposure_bias: float = 0.0
    saturation: float = 0.95
    sun_temperature_k: Optional[float] = None
    # Optional lighting and sky controls; None leaves the map's own value.
    sun_intensity_lux: Optional[float] = None
    sky_light_intensity: Optional[float] = None
    # Sky atmosphere scattering: a large Mie scale with little Rayleigh washes
    # the blue out of the sky to a grey-white overcast.
    # Scalar overrides per procedural-mesh material tag ("asphalt", "ground",
    # "pavement"): how wet the roads and paving look.
    surface_scalars: Optional[Dict[str, Dict[str, float]]] = None
    rayleigh_scale: Optional[float] = None
    mie_scale: Optional[float] = None
    mie_absorption_scale: Optional[float] = None
    mie_anisotropy: Optional[float] = None
    cloud_extinction_scale: Optional[float] = None
    cloud_layer_bottom_km: Optional[float] = None
    cloud_layer_height_km: Optional[float] = None
    fog_color: Optional[Tuple[float, float, float]] = None
    color_gain: Optional[Tuple[float, float, float]] = None
    ground_half_extent_m: float = 3000.0
    ground_uv_tile_m: float = 2.0
    ground_z_m: float = -0.02

    def to_json(self) -> Dict[str, Any]:
        """The ``"environment"`` object the UE5 loader parses."""
        sun: Dict[str, Any] = {"pitch_deg": self.sun_pitch_deg, "yaw_deg": self.sun_yaw_deg}
        if self.sun_temperature_k is not None:
            sun["temperature_k"] = self.sun_temperature_k
        if self.sun_intensity_lux is not None:
            sun["intensity_lux"] = self.sun_intensity_lux
        post_process: Dict[str, Any] = {
            "exposure_bias": self.exposure_bias,
            "saturation": self.saturation,
        }
        if self.color_gain is not None:
            post_process["gain"] = list(self.color_gain)
        fog: Dict[str, Any] = {
            "density": self.fog_density,
            "height_falloff": self.fog_height_falloff,
            "start_distance_m": self.fog_start_distance_m,
        }
        if self.fog_color is not None:
            fog["color"] = list(self.fog_color)
        result: Dict[str, Any] = {
            "hide_template_terrain": self.hide_template_terrain,
            "sun": sun,
            "fog": fog,
            "post_process": post_process,
        }
        if self.surface_scalars:
            result["surface_scalars"] = {
                tag: dict(values) for tag, values in self.surface_scalars.items()
            }
        if self.sky_light_intensity is not None:
            result["sky_light"] = {"intensity": self.sky_light_intensity}
        atmosphere = {
            key: value
            for key, value in (
                ("rayleigh_scale", self.rayleigh_scale),
                ("mie_scale", self.mie_scale),
                ("mie_absorption_scale", self.mie_absorption_scale),
                ("mie_anisotropy", self.mie_anisotropy),
            )
            if value is not None
        }
        if atmosphere:
            result["sky_atmosphere"] = atmosphere
        clouds: Dict[str, Any] = {}
        if self.cloud_extinction_scale is not None:
            clouds["extinction_scale"] = self.cloud_extinction_scale
        if self.cloud_layer_bottom_km is not None:
            clouds["layer_bottom_km"] = self.cloud_layer_bottom_km
        if self.cloud_layer_height_km is not None:
            clouds["layer_height_km"] = self.cloud_layer_height_km
        if clouds:
            result["clouds"] = clouds
        return result


DEFAULT_ENVIRONMENT = EnvironmentConfig()


class Season(str, Enum):
    """The scenario's season: a preset of the environment numbers plus
    whether street trees appear."""

    WINTER = "winter"
    SPRING = "spring"
    SUMMER = "summer"
    FALL = "fall"


# Season presets. Every field is a plain number the plugin already applies.
# The values are tuned by eye against this project's own scene (City
# Sample's exact grade gave a dark teal cast under our lighting), not
# measured: a low sun and warm colour for fall, a low cool sun with a muted
# grade and heavier haze for winter, a higher brighter sun for summer and a
# hazier, softer light for spring.
_SEASON_ENVIRONMENTS: Dict[Season, EnvironmentConfig] = {
    Season.SUMMER: EnvironmentConfig(
        sun_pitch_deg=-58.0, fog_density=0.003, exposure_bias=0.15, saturation=1.05
    ),
    Season.SPRING: EnvironmentConfig(
        sun_pitch_deg=-45.0,
        sun_temperature_k=6800.0,
        fog_density=0.006,
        fog_start_distance_m=250.0,
        saturation=1.0,
    ),
    Season.FALL: EnvironmentConfig(
        sun_pitch_deg=-24.0,
        sun_temperature_k=4600.0,
        fog_density=0.006,
        exposure_bias=-0.1,
        saturation=0.9,
        color_gain=(1.0, 0.95, 0.88),
    ),
    Season.WINTER: EnvironmentConfig(
        sun_pitch_deg=-16.0,
        sun_temperature_k=8500.0,
        fog_density=0.010,
        fog_start_distance_m=200.0,
        exposure_bias=-0.15,
        saturation=0.6,
        color_gain=(0.93, 0.98, 1.05),
    ),
}


class TimeOfDay(str, Enum):
    """Whether the scenario is lit by day or at night. Independent of
    season: night is a moonlit preset (see ``NIGHT_ENVIRONMENT``) that
    replaces the season's daytime sun, and also switches on vehicle
    lights (see ``city_sample_assets.VEHICLE_NIGHT_LIGHT_OVERRIDES``)."""

    DAY = "day"
    NIGHT = "night"


# Night preset, tuned by eye against this project's own scene like the
# season presets above (not measured). Sun BELOW the horizon left nothing
# lighting the scene at all (only emissives showed, a black void), so
# night keeps a low light source ABOVE the horizon as a cool "moon",
# with exposure pulled far down, a cool tint, and almost no fog.
NIGHT_ENVIRONMENT = EnvironmentConfig(
    sun_pitch_deg=-22.0,
    sun_temperature_k=10000.0,
    exposure_bias=-3.0,
    saturation=0.7,
    color_gain=(0.6, 0.8, 1.3),
    fog_density=0.001,
)


class Weather(str, Enum):
    """The scenario's daytime weather or light: a preset of overrides applied
    on top of the season's environment. Only daytime scenarios take a
    non-clear weather (night has its own lighting)."""

    CLEAR = "clear"
    OVERCAST = "overcast"
    RAIN = "rain"
    FOG = "fog"
    GOLDEN_HOUR = "golden_hour"
    SUNSET = "sunset"
    DAWN_HAZE = "dawn_haze"


# Weather presets: the values were found by rendering each on this project's own
# scene (seed 456, one street view and one skyline view) and keeping the ones
# that read as the named condition, not measured. Overcast comes from the sky
# atmosphere (almost no Rayleigh scattering, a lot of Mie), because the volumetric
# cloud layer's coverage cannot be raised through its material parameters, and
# because lowering the sun alone is cancelled by auto-exposure. Fog is denser
# height fog with a grey colour. The low-sun presets are sun angle, colour
# temperature and intensity.
_FOG_GREY = (0.4, 0.42, 0.45)
# Wet roads and paving: puddle depth up, roughness down, more specular. Found by
# rendering two strengths; a stronger one made the road a perfect mirror. Only the
# generated road, ground and paving meshes get it; curbs, walls and props keep
# their own dry materials.
_WET_SURFACES: Dict[str, Dict[str, float]] = {
    "asphalt": {
        "Roughness MFPD": 0.03,
        "Puddle Height MFPD": 0.9,
        "BaseRoughnessMult": 0.25,
        "Specular MFPD": 0.6,
    },
    "ground": {"Roughness MFPD": 0.03, "BaseRoughnessMult": 0.25},
    "pavement": {"Roughness MFPD": 0.03, "Puddle Height MFPD": 0.9, "Specular MFPD": 0.6},
}
_WEATHER_OVERRIDES: Dict[Weather, Dict[str, Any]] = {
    Weather.CLEAR: {},
    Weather.OVERCAST: {
        "sun_intensity_lux": 2.0,
        "rayleigh_scale": 0.05,
        "mie_scale": 12.0,
        "mie_anisotropy": 0.3,
        "fog_density": 0.01,
        "fog_color": _FOG_GREY,
    },
    Weather.RAIN: {
        "sun_intensity_lux": 1.5,
        "rayleigh_scale": 0.05,
        "mie_scale": 12.0,
        "mie_anisotropy": 0.3,
        "fog_density": 0.012,
        "fog_color": _FOG_GREY,
        "surface_scalars": _WET_SURFACES,
    },
    Weather.FOG: {"sun_intensity_lux": 1.5, "fog_density": 0.05, "fog_color": _FOG_GREY},
    Weather.GOLDEN_HOUR: {
        "sun_pitch_deg": -9.0,
        "sun_temperature_k": 4300.0,
        "sun_intensity_lux": 6.0,
    },
    Weather.SUNSET: {
        "sun_pitch_deg": -4.0,
        "sun_temperature_k": 3400.0,
        "sun_intensity_lux": 5.0,
    },
    Weather.DAWN_HAZE: {
        "sun_pitch_deg": -6.0,
        "sun_temperature_k": 4800.0,
        "sun_intensity_lux": 3.0,
        "fog_density": 0.012,
        "fog_color": (0.55, 0.5, 0.45),
    },
}

# How often each weather is drawn when a dataset picks one at random. These
# shares are this project's own choice (no source was used): mostly clear or
# overcast, with the rarer conditions kept in.
WEATHER_SHARES: Dict[Weather, float] = {
    Weather.CLEAR: 0.35,
    Weather.OVERCAST: 0.20,
    Weather.RAIN: 0.15,
    Weather.FOG: 0.07,
    Weather.GOLDEN_HOUR: 0.10,
    Weather.SUNSET: 0.05,
    Weather.DAWN_HAZE: 0.08,
}


def draw_weather(seed: int) -> Weather:
    """A weather for ``seed`` by ``WEATHER_SHARES``, from its own RNG stream
    (so no other draw in a scenario changes)."""
    rng = np.random.Generator(np.random.PCG64([seed, 0x9E47]))
    weathers = list(WEATHER_SHARES)
    shares = np.array([WEATHER_SHARES[weather] for weather in weathers])
    return weathers[int(rng.choice(len(weathers), p=shares / shares.sum()))]


def scenario_environment(
    season: Season, time_of_day: TimeOfDay, weather: Weather = Weather.CLEAR
) -> EnvironmentConfig:
    """The environment for a scenario: the night preset at night
    (season-independent), otherwise the season's daytime preset with the
    weather's overrides on top.

    Raises
    ------
    ValueError
        If a non-clear ``weather`` is combined with night.
    """
    if time_of_day == TimeOfDay.NIGHT:
        if weather != Weather.CLEAR:
            raise ValueError(f"weather {weather.value!r} is only defined for daytime scenarios")
        return NIGHT_ENVIRONMENT
    return dataclasses.replace(season_environment(season), **_WEATHER_OVERRIDES[weather])


# Epic's tree kits are bare branch skeletons (no leaves, see
# KNOWN_GAPS_AND_ISSUES.md), so trees only suit the leafless seasons; spring
# and summer streets have none rather than dead-looking ones.
_SEASONS_WITH_TREES = frozenset({Season.WINTER, Season.FALL})


def season_environment(season: Season) -> EnvironmentConfig:
    """The environment preset for ``season``."""
    return _SEASON_ENVIRONMENTS[season]


def season_has_trees(season: Season) -> bool:
    """Whether street trees appear in ``season``."""
    return season in _SEASONS_WITH_TREES


def build_ground_mesh(environment: EnvironmentConfig) -> Mesh:
    """One large square, facing up, centred on the origin, with UVs in
    metres divided by ``ground_uv_tile_m`` so the material tiles."""
    half = environment.ground_half_extent_m
    return flat_quad_mesh(
        -half,
        -half,
        half,
        half,
        environment.ground_z_m,
        environment.ground_uv_tile_m,
        "ground",
    )
