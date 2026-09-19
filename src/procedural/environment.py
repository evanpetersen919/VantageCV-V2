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
from typing import Any, Dict

import numpy as np

from src.procedural.mesh_factory import Mesh


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
    ground_half_extent_m: float = 3000.0
    ground_uv_tile_m: float = 2.0
    ground_z_m: float = -0.02

    def to_json(self) -> Dict[str, Any]:
        """The ``"environment"`` object the UE5 loader parses."""
        return {
            "hide_template_terrain": self.hide_template_terrain,
            "sun": {"pitch_deg": self.sun_pitch_deg, "yaw_deg": self.sun_yaw_deg},
            "fog": {
                "density": self.fog_density,
                "height_falloff": self.fog_height_falloff,
                "start_distance_m": self.fog_start_distance_m,
            },
            "post_process": {
                "exposure_bias": self.exposure_bias,
                "saturation": self.saturation,
            },
        }


DEFAULT_ENVIRONMENT = EnvironmentConfig()


def build_ground_mesh(environment: EnvironmentConfig) -> Mesh:
    """One large square, facing up, centred on the origin, with UVs in
    metres divided by ``ground_uv_tile_m`` so the material tiles."""
    half = environment.ground_half_extent_m
    z = environment.ground_z_m
    vertices = np.array(
        [[-half, -half, z], [half, -half, z], [half, half, z], [-half, half, z]],
        dtype=np.float64,
    )
    uvs = vertices[:, :2] / environment.ground_uv_tile_m
    triangles = np.array([0, 1, 2, 0, 2, 3], dtype=np.int64)
    return Mesh(vertices=vertices, triangles=triangles, uvs=uvs, material="ground")
