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

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

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
    color_gain: Optional[Tuple[float, float, float]] = None
    ground_half_extent_m: float = 3000.0
    ground_uv_tile_m: float = 2.0
    ground_z_m: float = -0.02

    def to_json(self) -> Dict[str, Any]:
        """The ``"environment"`` object the UE5 loader parses."""
        sun: Dict[str, Any] = {"pitch_deg": self.sun_pitch_deg, "yaw_deg": self.sun_yaw_deg}
        if self.sun_temperature_k is not None:
            sun["temperature_k"] = self.sun_temperature_k
        post_process: Dict[str, Any] = {
            "exposure_bias": self.exposure_bias,
            "saturation": self.saturation,
        }
        if self.color_gain is not None:
            post_process["gain"] = list(self.color_gain)
        return {
            "hide_template_terrain": self.hide_template_terrain,
            "sun": sun,
            "fog": {
                "density": self.fog_density,
                "height_falloff": self.fog_height_falloff,
                "start_distance_m": self.fog_start_distance_m,
            },
            "post_process": post_process,
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
