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
from src.procedural.vehicle_lamp_geometry import VEHICLE_LAMP_GEOMETRY, LampGeometry

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

HEADLIGHT_INTENSITY = 6.0
HEADLIGHT_ATTENUATION_M = 40.0
# Headlights use a flat (non-inverse-square) falloff: an inverse-square
# light 0.7 m off the road is orders of magnitude brighter close in than
# far out, so it blew the pavement just ahead of the bumper out to two
# hard white ovals (found live); a flat falloff washes the road evenly
# out to the attenuation radius instead. Intensity is then unitless.
HEADLIGHT_FALLOFF_EXPONENT = 2.0
HEADLIGHT_INNER_CONE_DEG = 4.0
HEADLIGHT_OUTER_CONE_DEG = 16.0
# Real US low-beam cutoff is about 1 degree below level (FMVSS 108); a
# little more than that so the beam reads on the road at this scale. The
# cone is deliberately narrow: a wide cone's lower edge lands on the road
# a couple of metres ahead and reads as two bright discs at the bumper
# (found live), not a beam streaking down the road.
HEADLIGHT_DIP = -0.01

RUNNING_TAILLIGHT_INTENSITY_CD = 12.0
RUNNING_TAILLIGHT_ATTENUATION_M = 3.0
BRAKE_LIGHT_INTENSITY_CD = 50.0
BRAKE_LIGHT_ATTENUATION_M = 4.0

# Visible glowing lenses (see ``SceneGlow``): a light actor casts light but
# is itself invisible, so each measured lamp also gets an unlit, additive
# emissive ellipsoid the size of the real lens mesh that blooms. Sizes and
# intensities tuned by eye.
HEADLIGHT_GLOW_INTENSITY = 14.0
RUNNING_TAILLIGHT_GLOW_INTENSITY = 3.0
BRAKE_LIGHT_GLOW_INTENSITY = 12.0
# A measured lens's own front/rear face is where its light sits, plus a hair.
LIGHT_OUTSET_BEYOND_LENS_M = 0.10


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
    inverse_squared: bool = True
    falloff_exponent: float = 2.0

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
        if not self.inverse_squared:
            entry["inverse_squared"] = False
            entry["falloff_exponent"] = self.falloff_exponent
        return entry


@dataclass(frozen=True)
class SceneGlow:
    """One visible glowing lens: an emissive ellipsoid the size of the
    real lens mesh, in the scenario's own right-handed meters frame."""

    position: Tuple[float, float, float]
    color: Tuple[float, float, float]
    semi_axes_m: Tuple[float, float, float]  # (forward, lateral, vertical)
    rotation_rad: float  # the vehicle's heading
    intensity: float

    def to_json(self) -> Dict[str, Any]:
        """The ``"glows"`` entry the UE5 loader parses."""
        return {
            "position": list(self.position),
            "color": list(self.color),
            "semi_axes_m": list(self.semi_axes_m),
            "rotation_rad": self.rotation_rad,
            "intensity": self.intensity,
        }


def _vehicle_folder(vehicle: Vehicle) -> str:
    """The City Sample vehicle folder (e.g. ``vehCar_vehicle02``) that
    ``VEHICLE_LAMP_GEOMETRY`` is keyed by."""
    return vehicle.asset_path.split("/")[3]


def _lamp_world_positions(
    vehicle: Vehicle, forward_m: float, lateral_m: float, height_m: float
) -> List[Tuple[float, float, float]]:
    """A symmetric lamp pair's two world positions: ``forward_m`` along
    the heading and ``+-lateral_m`` off the centreline, from the mesh
    origin (which is exactly ``Vehicle.center``)."""
    forward = np.array([np.cos(vehicle.heading_rad), np.sin(vehicle.heading_rad)])
    left = np.array([-forward[1], forward[0]])
    center = np.asarray(vehicle.center, dtype=np.float64)
    positions = []
    for side in (-1.0, 1.0):
        point = center + forward * forward_m + left * side * lateral_m
        positions.append((float(point[0]), float(point[1]), height_m))
    return positions


def _glows_for(
    vehicle: Vehicle, lamp: LampGeometry, color: Tuple[float, float, float], intensity: float
) -> List[SceneGlow]:
    return [
        SceneGlow(position, color, lamp.half_extents_m, float(vehicle.heading_rad), intensity)
        for position in _lamp_world_positions(
            vehicle, lamp.forward_m, lamp.lateral_m, lamp.height_m
        )
    ]


def vehicle_glows(vehicle: Vehicle) -> List[SceneGlow]:
    """Glowing headlight and tail/brake lenses at the vehicle model's own
    measured lamp positions, sized like the real lens meshes. A model with
    no measured lamps (see ``vehicle_lamp_geometry.py``) gets none: a glow
    at a guessed spot floats off the body (found live), while an
    unmeasured model's lights still work without one."""
    geometry = VEHICLE_LAMP_GEOMETRY.get(_vehicle_folder(vehicle))
    if geometry is None:
        return []
    tail_intensity = (
        BRAKE_LIGHT_GLOW_INTENSITY if vehicle.braking else RUNNING_TAILLIGHT_GLOW_INTENSITY
    )
    return _glows_for(vehicle, geometry.headlight, HEADLIGHT_COLOR, HEADLIGHT_GLOW_INTENSITY) + (
        _glows_for(vehicle, geometry.taillight, TAILLIGHT_COLOR, tail_intensity)
    )


def _generic_lamp_positions(
    vehicle: Vehicle,
) -> Tuple[List[Tuple[float, float, float]], List[Tuple[float, float, float]]]:
    """Headlight and tail-light positions for a model with no measured
    lamps: the generic vehicle-type length/width, just outside the body."""
    half = vehicle.length / 2.0
    heads = _lamp_world_positions(
        vehicle,
        half + LAMP_OUTSET_BEYOND_BODY_M,
        vehicle.width * HEADLIGHT_LATERAL_FRACTION_OF_WIDTH,
        HEADLIGHT_HEIGHT_M,
    )
    tails = _lamp_world_positions(
        vehicle,
        -(half + LAMP_OUTSET_BEYOND_BODY_M),
        vehicle.width * TAILLIGHT_LATERAL_FRACTION_OF_WIDTH,
        TAILLIGHT_HEIGHT_M,
    )
    return heads, tails


def vehicle_lights(vehicle: Vehicle) -> List[SceneLight]:
    """Two headlight spots and two tail/brake point lights for one
    vehicle: headlights on always at night, tail lights dim while driving
    and bright while ``vehicle.braking`` (stopped in a queue). Placed just
    in front of / behind the model's own measured lens when known, else at
    the generic type-based spot."""
    geometry = VEHICLE_LAMP_GEOMETRY.get(_vehicle_folder(vehicle))
    if geometry is None:
        heads, tails = _generic_lamp_positions(vehicle)
    else:
        head = geometry.headlight
        tail = geometry.taillight
        heads = _lamp_world_positions(
            vehicle,
            head.forward_m + head.half_extents_m[0] + LIGHT_OUTSET_BEYOND_LENS_M,
            head.lateral_m,
            head.height_m,
        )
        tails = _lamp_world_positions(
            vehicle,
            tail.forward_m - tail.half_extents_m[0] - LIGHT_OUTSET_BEYOND_LENS_M,
            tail.lateral_m,
            tail.height_m,
        )

    beam = (float(np.cos(vehicle.heading_rad)), float(np.sin(vehicle.heading_rad)), HEADLIGHT_DIP)
    braking = vehicle.braking
    lights: List[SceneLight] = [
        SceneLight(
            kind="spot",
            position=head_position,
            color=HEADLIGHT_COLOR,
            intensity_candela=HEADLIGHT_INTENSITY,
            attenuation_m=HEADLIGHT_ATTENUATION_M,
            direction=beam,
            inner_cone_deg=HEADLIGHT_INNER_CONE_DEG,
            outer_cone_deg=HEADLIGHT_OUTER_CONE_DEG,
            inverse_squared=False,
            falloff_exponent=HEADLIGHT_FALLOFF_EXPONENT,
        )
        for head_position in heads
    ]
    lights += [
        SceneLight(
            kind="point",
            position=tail_position,
            color=TAILLIGHT_COLOR,
            intensity_candela=BRAKE_LIGHT_INTENSITY_CD
            if braking
            else RUNNING_TAILLIGHT_INTENSITY_CD,
            attenuation_m=BRAKE_LIGHT_ATTENUATION_M if braking else RUNNING_TAILLIGHT_ATTENUATION_M,
        )
        for tail_position in tails
    ]
    return lights
