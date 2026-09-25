"""Real light sources for a night scenario: vehicle headlights and
tail/brake lights, sent to the UE5 plugin as the payload's top-level
``"lights"`` array (one real point or spot light actor per entry -- see
``ProceduralScenarioLoader::SpawnLights``). A daytime scenario simply
carries no lights.

Why real light actors instead of the vehicle materials' own emissive
parameters: City Sample's vehicle light materials expose headlight and
brake scalars (``Headlight Amt LE`` / ``Brake Amt LE``), but overriding
them per vehicle had no visible effect in a controlled with/without
comparison (even at 40,000x brightness), for a reason not yet found. A
light actor also does something an emissive texture never can: it lights
the road and the cars ahead.

Real mounting geometry, from FMVSS 108 (US lamp mounting-height rules):
headlamps 22-54 in (0.56-1.37 m) above the road, taillamps 15-72 in
(0.38-1.83 m). Lateral spacing (a fraction of the vehicle's own width) and
every intensity/cone below are tuned by eye against this project's own
scene, not measured -- they only need to read correctly, and live in this
one module so they can be retuned without touching the plugin.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.procedural.actor_placement import Vehicle

HEADLIGHT_HEIGHT_M = 0.7  # inside FMVSS 108's 0.56-1.37 m range
TAILLIGHT_HEIGHT_M = 0.9  # inside FMVSS 108's 0.38-1.83 m range
HEADLIGHT_LATERAL_FRACTION_OF_WIDTH = 0.35
# Lamps sit just OUTSIDE the bodywork: unshadowed lights placed inside the
# body flood the car's own surface (found live -- brake lights turned the
# whole rear panel pink).
LAMP_OUTSET_BEYOND_BODY_M = 0.25
TAILLIGHT_LATERAL_FRACTION_OF_WIDTH = 0.38

HEADLIGHT_COLOR = (1.0, 0.95, 0.82)
TAILLIGHT_COLOR = (1.0, 0.04, 0.02)

HEADLIGHT_INTENSITY_CD = 9000.0
HEADLIGHT_ATTENUATION_M = 22.0
HEADLIGHT_INNER_CONE_DEG = 14.0
HEADLIGHT_OUTER_CONE_DEG = 40.0
HEADLIGHT_DIP = -0.06  # slight downward tilt of the beam's z component

RUNNING_TAILLIGHT_INTENSITY_CD = 12.0
RUNNING_TAILLIGHT_ATTENUATION_M = 3.0
BRAKE_LIGHT_INTENSITY_CD = 50.0
BRAKE_LIGHT_ATTENUATION_M = 4.0


@dataclass(frozen=True)
class SceneLight:  # pylint: disable=too-many-instance-attributes
    """One real light source, in the scenario's own right-handed meters
    frame (the plugin applies the same Y mirror it applies to every
    other spawned asset)."""

    kind: str  # "point" or "spot"
    position: Tuple[float, float, float]
    color: Tuple[float, float, float]
    intensity_candela: float
    attenuation_m: float
    direction: Optional[Tuple[float, float, float]] = None
    inner_cone_deg: float = 0.0
    outer_cone_deg: float = 0.0

    def to_json(self) -> Dict[str, Any]:
        """The ``"lights"`` entry the UE5 loader parses."""
        entry: Dict[str, Any] = {
            "type": self.kind,
            "position": list(self.position),
            "color": list(self.color),
            "intensity": self.intensity_candela,
            "attenuation_m": self.attenuation_m,
        }
        if self.kind == "spot":
            entry["direction"] = list(self.direction or (1.0, 0.0, 0.0))
            entry["inner_cone_deg"] = self.inner_cone_deg
            entry["outer_cone_deg"] = self.outer_cone_deg
        return entry


def vehicle_lights(vehicle: Vehicle) -> List[SceneLight]:
    """Two headlight spots and two tail/brake point lights for one
    vehicle: headlights on always at night, tail lights dim while
    driving and bright while ``vehicle.braking`` (stopped in a queue)."""
    forward = np.array([np.cos(vehicle.heading_rad), np.sin(vehicle.heading_rad)])
    left = np.array([-forward[1], forward[0]])
    center = np.asarray(vehicle.center, dtype=np.float64)
    front = center + forward * (vehicle.length / 2.0 + LAMP_OUTSET_BEYOND_BODY_M)
    rear = center - forward * (vehicle.length / 2.0 + LAMP_OUTSET_BEYOND_BODY_M)

    beam = (float(forward[0]), float(forward[1]), HEADLIGHT_DIP)
    brake = vehicle.braking
    lights: List[SceneLight] = []
    for side in (-1.0, 1.0):
        head = front + left * (side * vehicle.width * HEADLIGHT_LATERAL_FRACTION_OF_WIDTH)
        lights.append(
            SceneLight(
                kind="spot",
                position=(float(head[0]), float(head[1]), HEADLIGHT_HEIGHT_M),
                color=HEADLIGHT_COLOR,
                intensity_candela=HEADLIGHT_INTENSITY_CD,
                attenuation_m=HEADLIGHT_ATTENUATION_M,
                direction=beam,
                inner_cone_deg=HEADLIGHT_INNER_CONE_DEG,
                outer_cone_deg=HEADLIGHT_OUTER_CONE_DEG,
            )
        )
        tail = rear + left * (side * vehicle.width * TAILLIGHT_LATERAL_FRACTION_OF_WIDTH)
        lights.append(
            SceneLight(
                kind="point",
                position=(float(tail[0]), float(tail[1]), TAILLIGHT_HEIGHT_M),
                color=TAILLIGHT_COLOR,
                intensity_candela=BRAKE_LIGHT_INTENSITY_CD
                if brake
                else RUNNING_TAILLIGHT_INTENSITY_CD,
                attenuation_m=BRAKE_LIGHT_ATTENUATION_M
                if brake
                else RUNNING_TAILLIGHT_ATTENUATION_M,
            )
        )
    return lights
