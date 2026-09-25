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
    # Rain streaks drawn over the frame (see create_rain_material.py): opacity
    # (0 is none), the horizontal shear per unit height, and a pattern seed.
    # Wet walls and cars: roughness caps ("<slot pattern>|<parameter>": value)
    # and darkening factors applied to a slot's current colour.
    asset_scalars: Optional[Dict[str, float]] = None
    asset_vector_scales: Optional[Dict[str, float]] = None
    rain_intensity: Optional[float] = None
    rain_density: float = 0.5
    # Expanding rings where rain lands on flat wet ground (opacity, 0 is none,
    # and the share of ground cells that hold one).
    ripple_intensity: float = 0.6
    ripple_density: float = 0.35
    rain_slant: float = 0.12
    rain_seed: float = 1.0
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

    def _sun_json(self) -> Dict[str, Any]:
        sun: Dict[str, Any] = {"pitch_deg": self.sun_pitch_deg, "yaw_deg": self.sun_yaw_deg}
        if self.sun_temperature_k is not None:
            sun["temperature_k"] = self.sun_temperature_k
        if self.sun_intensity_lux is not None:
            sun["intensity_lux"] = self.sun_intensity_lux
        return sun

    def _fog_json(self) -> Dict[str, Any]:
        fog: Dict[str, Any] = {
            "density": self.fog_density,
            "height_falloff": self.fog_height_falloff,
            "start_distance_m": self.fog_start_distance_m,
        }
        if self.fog_color is not None:
            fog["color"] = list(self.fog_color)
        return fog

    def _post_process_json(self) -> Dict[str, Any]:
        post_process: Dict[str, Any] = {
            "exposure_bias": self.exposure_bias,
            "saturation": self.saturation,
        }
        if self.color_gain is not None:
            post_process["gain"] = list(self.color_gain)
        return post_process

    def _sky_json(self) -> Dict[str, Any]:
        """The sky light, sky atmosphere and cloud objects that are set."""
        sky: Dict[str, Any] = {}
        if self.sky_light_intensity is not None:
            sky["sky_light"] = {"intensity": self.sky_light_intensity}
        for key, fields in (
            (
                "sky_atmosphere",
                (
                    ("rayleigh_scale", self.rayleigh_scale),
                    ("mie_scale", self.mie_scale),
                    ("mie_absorption_scale", self.mie_absorption_scale),
                    ("mie_anisotropy", self.mie_anisotropy),
                ),
            ),
            (
                "clouds",
                (
                    ("extinction_scale", self.cloud_extinction_scale),
                    ("layer_bottom_km", self.cloud_layer_bottom_km),
                    ("layer_height_km", self.cloud_layer_height_km),
                ),
            ),
        ):
            values = {name: value for name, value in fields if value is not None}
            if values:
                sky[key] = values
        return sky

    def _weather_json(self) -> Dict[str, Any]:
        """The rain and wet-surface objects that are set."""
        weather: Dict[str, Any] = {}
        if self.rain_intensity is not None:
            weather["rain"] = {
                "intensity": self.rain_intensity,
                "slant": self.rain_slant,
                "seed": self.rain_seed,
                "density": self.rain_density,
                "ripple_intensity": self.ripple_intensity,
                "ripple_density": self.ripple_density,
            }
        if self.asset_scalars:
            weather["asset_scalars"] = dict(self.asset_scalars)
        if self.asset_vector_scales:
            weather["asset_vector_scales"] = dict(self.asset_vector_scales)
        if self.surface_scalars:
            weather["surface_scalars"] = {
                tag: dict(values) for tag, values in self.surface_scalars.items()
            }
        return weather

    def to_json(self) -> Dict[str, Any]:
        """The ``"environment"`` object the UE5 loader parses."""
        return {
            "hide_template_terrain": self.hide_template_terrain,
            "sun": self._sun_json(),
            "fog": self._fog_json(),
            "post_process": self._post_process_json(),
            **self._sky_json(),
            **self._weather_json(),
        }


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
# Wet walls and cars. Roughness is capped (stone and brick 0.4, painted stone
# 0.3, car paint nearly mirror-smooth) and colour is darkened (walls to 75%, car
# paint to 85%), because a wet surface is darker as well as glossier: capping
# roughness alone changed the walls by only 3-6 grey levels. Found by rendering
# 0.6 and 0.75; 0.6 read as dirty.
_WET_ASSET_SCALARS: Dict[str, float] = {
    "Bldg_block*|Roughness Max M1": 0.4,
    "Bldg_brick*|Roughness Max M1": 0.4,
    "Bldg_painted*|Roughness Max M1": 0.3,
    "veh_carPaint|Max Roughness": 0.02,
    "veh_carPaint|Min Roughness": 0.01,
}
_WET_ASSET_VECTOR_SCALES: Dict[str, float] = {
    "Bldg_block*|Color Tint M1": 0.75,
    "Bldg_brick*|Color Tint M1": 0.75,
    "Bldg_painted*|Color Tint/Mult(A) M1": 0.75,
    "veh_carPaint|BaseColor": 0.85,
}
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
        "asset_scalars": _WET_ASSET_SCALARS,
        "asset_vector_scales": _WET_ASSET_VECTOR_SCALES,
        "rain_intensity": 0.9,
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

# Night rain: the moonlit sky stays, roads and paving get wet (street lamps and
# headlights then reflect in them), a little haze, and streaks at a lower opacity
# because bright streaks over a dark scene overpower it.
_NIGHT_RAIN_OVERRIDES: Dict[str, Any] = {
    "fog_density": 0.004,
    "surface_scalars": _WET_SURFACES,
    "asset_scalars": _WET_ASSET_SCALARS,
    "asset_vector_scales": _WET_ASSET_VECTOR_SCALES,
    "rain_intensity": 0.45,
    "ripple_intensity": 0.35,
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


# Rain strengths a seeded scenario draws from: (share of streak cells, streak
# and ripple opacity scale). Light rain has fewer, fainter streaks; heavy has
# the most. The wind slant range is small because a strongly slanted streak
# would need the sky's other features to lean with it.
_RAIN_STRENGTHS: Tuple[Tuple[float, float], ...] = ((0.3, 0.75), (0.5, 1.0), (0.75, 1.0))
_RAIN_SLANT_RANGE = (-0.2, 0.2)


def _vary_rain(env: EnvironmentConfig, seed: int) -> EnvironmentConfig:
    """The rain of ``env`` with a strength, wind slant and streak pattern
    drawn from ``seed`` (its own RNG stream)."""
    rng = np.random.Generator(np.random.PCG64([seed, 0x8A17]))
    density, opacity = _RAIN_STRENGTHS[int(rng.integers(len(_RAIN_STRENGTHS)))]
    assert env.rain_intensity is not None
    return dataclasses.replace(
        env,
        rain_density=density,
        rain_intensity=env.rain_intensity * opacity,
        rain_slant=float(rng.uniform(*_RAIN_SLANT_RANGE)),
        rain_seed=float(seed % 997),
        ripple_density=0.25 + 0.2 * density,
    )


def scenario_environment(
    season: Season,
    time_of_day: TimeOfDay,
    weather: Weather = Weather.CLEAR,
    seed: Optional[int] = None,
) -> EnvironmentConfig:
    """The environment for a scenario: the night preset at night
    (season-independent), otherwise the season's daytime preset with the
    weather's overrides on top.

    Night takes clear or rain (its own moonlit sky is kept; rain adds wet
    surfaces, a little haze and dimmer streaks). With a ``seed``, rain gets
    its own strength, wind slant and streak pattern.

    Raises
    ------
    ValueError
        If a weather other than clear or rain is combined with night.
    """
    if time_of_day == TimeOfDay.NIGHT:
        if weather == Weather.RAIN:
            night_rain = dataclasses.replace(NIGHT_ENVIRONMENT, **_NIGHT_RAIN_OVERRIDES)
            return _vary_rain(night_rain, seed) if seed is not None else night_rain
        if weather != Weather.CLEAR:
            raise ValueError(f"weather {weather.value!r} is not defined for night scenarios")
        return NIGHT_ENVIRONMENT
    env = dataclasses.replace(season_environment(season), **_WEATHER_OVERRIDES[weather])
    return _vary_rain(env, seed) if weather == Weather.RAIN and seed is not None else env


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
