"""Unit tests for night_lights.py: real vehicle headlight / tail-light
placement and the ``"lights"`` payload entries the UE5 plugin parses."""

import numpy as np
import pytest

from src.procedural.actor_placement import Vehicle
from src.procedural.night_lights import (
    BRAKE_LIGHT_GLOW_INTENSITY,
    BRAKE_LIGHT_INTENSITY_CD,
    GLOW_SURFACE_OUTSET_M,
    HEADLIGHT_DIP,
    HEADLIGHT_GLOW_INTENSITY,
    HEADLIGHT_HEIGHT_M,
    HEADLIGHT_OUTER_CONE_DEG,
    LAMP_OUTSET_BEYOND_BODY_M,
    RUNNING_TAILLIGHT_GLOW_INTENSITY,
    RUNNING_TAILLIGHT_INTENSITY_CD,
    TAILLIGHT_HEIGHT_M,
    vehicle_glows,
    vehicle_lights,
)


def _vehicle(heading_rad: float = 0.0, braking: bool = False) -> Vehicle:
    return Vehicle(
        vehicle_id=0,
        vehicle_type="sedan",
        asset_path="/Game/x",
        center=np.array([10.0, 20.0]),
        heading_rad=heading_rad,
        length=4.6,
        width=1.8,
        height=1.5,
        braking=braking,
    )


def test_every_vehicle_gets_two_headlight_spots_and_two_tail_points() -> None:
    """Two spots in front, two points behind -- four lights per vehicle."""
    lights = vehicle_lights(_vehicle())
    assert sorted(light.kind for light in lights) == ["point", "point", "spot", "spot"]


def test_headlights_sit_just_ahead_of_the_body_and_point_along_the_heading() -> None:
    """Heading east: both spots are `length/2 + outset` ahead of the
    center, at the real mounting height, on opposite sides, aimed east."""
    spots = [light for light in vehicle_lights(_vehicle(0.0)) if light.kind == "spot"]
    for spot in spots:
        assert spot.position[0] == pytest.approx(10.0 + 4.6 / 2.0 + LAMP_OUTSET_BEYOND_BODY_M)
        assert spot.position[2] == HEADLIGHT_HEIGHT_M
        assert spot.direction is not None
        assert spot.direction[0] == pytest.approx(1.0)
        assert spot.direction[1] == pytest.approx(0.0)
        assert spot.direction[2] < 0.0  # slight downward dip
    assert spots[0].position[1] == pytest.approx(20.0 - spots[1].position[1] + 20.0)  # mirrored


def test_tail_lights_sit_just_behind_the_body() -> None:
    """Heading north: tail lights are behind (smaller y) the rear bumper."""
    points = [light for light in vehicle_lights(_vehicle(np.pi / 2)) if light.kind == "point"]
    for point in points:
        assert point.position[1] == pytest.approx(20.0 - 4.6 / 2.0 - LAMP_OUTSET_BEYOND_BODY_M)
        assert point.position[2] == TAILLIGHT_HEIGHT_M


def test_brake_lights_are_brighter_only_when_the_vehicle_is_braking() -> None:
    """A queued (braking) vehicle's tail lights use the brake intensity; a
    moving vehicle's use the dimmer running intensity."""
    braking = [light for light in vehicle_lights(_vehicle(braking=True)) if light.kind == "point"]
    moving = [light for light in vehicle_lights(_vehicle(braking=False)) if light.kind == "point"]
    assert all(light.intensity_candela == BRAKE_LIGHT_INTENSITY_CD for light in braking)
    assert all(light.intensity_candela == RUNNING_TAILLIGHT_INTENSITY_CD for light in moving)
    assert BRAKE_LIGHT_INTENSITY_CD > RUNNING_TAILLIGHT_INTENSITY_CD


def test_to_json_matches_the_plugins_schema() -> None:
    """Spot entries carry direction + cone angles; point entries don't."""
    for light in vehicle_lights(_vehicle()):
        entry = light.to_json()
        assert {"type", "position", "color", "intensity", "attenuation_m"} <= set(entry)
        assert len(entry["position"]) == 3 and len(entry["color"]) == 3
        if light.kind == "spot":
            assert {"direction", "inner_cone_deg", "outer_cone_deg"} <= set(entry)
        else:
            assert "direction" not in entry


def test_headlight_beams_are_narrow_and_nearly_level() -> None:
    """A wide cone's lower edge lands on the road a couple of metres ahead
    and reads as two bright discs at the bumper (found live); a real low
    beam is a narrow, almost level cone. Guards that regression."""
    dip_deg = np.degrees(np.arctan(-HEADLIGHT_DIP))
    lower_edge_deg = HEADLIGHT_OUTER_CONE_DEG + dip_deg
    metres_ahead_where_beam_reaches_road = HEADLIGHT_HEIGHT_M / np.tan(np.radians(lower_edge_deg))
    assert metres_ahead_where_beam_reaches_road > 3.0


def test_glowing_lenses_sit_on_the_body_surface_with_brake_glow_only_when_braking() -> None:
    """Four glowing lenses per vehicle, right at the bumper surface; a
    braking vehicle's tail lenses are brighter than a moving one's."""
    moving = vehicle_glows(_vehicle(0.0, braking=False))
    braking = vehicle_glows(_vehicle(0.0, braking=True))
    assert len(moving) == 4
    front = [g for g in moving if g.intensity == HEADLIGHT_GLOW_INTENSITY]
    assert len(front) == 2
    for glow in front:
        assert glow.position[0] == pytest.approx(10.0 + 4.6 / 2.0 + GLOW_SURFACE_OUTSET_M)
    assert sorted(g.intensity for g in braking)[-2:] == [HEADLIGHT_GLOW_INTENSITY] * 2
    tail_moving = [g for g in moving if g.position[0] < 10.0]
    tail_braking = [g for g in braking if g.position[0] < 10.0]
    assert all(g.intensity == RUNNING_TAILLIGHT_GLOW_INTENSITY for g in tail_moving)
    assert all(g.intensity == BRAKE_LIGHT_GLOW_INTENSITY for g in tail_braking)
    assert set(vehicle_glows(_vehicle())[0].to_json()) == {
        "position",
        "color",
        "radius_m",
        "intensity",
    }
