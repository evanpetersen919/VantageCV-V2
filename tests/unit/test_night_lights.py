"""Unit tests for night_lights.py: real vehicle headlight / tail-light
placement (at each model's own measured lamp positions when known) and
the ``"lights"`` / ``"glows"`` payload entries the UE5 plugin parses."""

import numpy as np
import pytest

from src.procedural.actor_placement import Vehicle
from src.procedural.night_lights import (
    BRAKE_LIGHT_GLOW_INTENSITY,
    BRAKE_LIGHT_INTENSITY_CD,
    HEADLIGHT_DIP,
    HEADLIGHT_GLOW_INTENSITY,
    HEADLIGHT_HEIGHT_M,
    HEADLIGHT_OUTER_CONE_DEG,
    LAMP_OUTSET_BEYOND_BODY_M,
    LIGHT_OUTSET_BEYOND_LENS_M,
    RUNNING_TAILLIGHT_GLOW_INTENSITY,
    RUNNING_TAILLIGHT_INTENSITY_CD,
    TAILLIGHT_HEIGHT_M,
    vehicle_glows,
    vehicle_lights,
)
from src.procedural.vehicle_lamp_geometry import VEHICLE_LAMP_GEOMETRY

MEASURED = "/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Frame_vehCar_vehicle02"
UNMEASURED = "/Game/Vehicle/vehCar_vehicle03/Mesh/SM_Frame_vehCar_vehicle03"


def _vehicle(
    heading_rad: float = 0.0, braking: bool = False, asset_path: str = MEASURED
) -> Vehicle:
    return Vehicle(
        vehicle_id=0,
        vehicle_type="sedan",
        asset_path=asset_path,
        center=np.array([10.0, 20.0]),
        heading_rad=heading_rad,
        length=4.6,
        width=1.8,
        height=1.5,
        braking=braking,
    )


def test_lamp_geometry_table_is_physically_sensible() -> None:
    """Every measured model has headlights ahead of the origin, tail
    lights behind it, both off the centreline and off the ground."""
    assert VEHICLE_LAMP_GEOMETRY
    for geometry in VEHICLE_LAMP_GEOMETRY.values():
        assert geometry.headlight.forward_m > 0.0 > geometry.taillight.forward_m
        assert geometry.headlight.lateral_m > 0.0 and geometry.taillight.lateral_m > 0.0
        assert geometry.headlight.height_m > 0.0 and geometry.taillight.height_m > 0.0


def test_every_vehicle_gets_two_headlight_spots_and_two_tail_points() -> None:
    """Two spots in front, two points behind -- four lights per vehicle,
    measured or not."""
    for asset_path in (MEASURED, UNMEASURED):
        lights = vehicle_lights(_vehicle(asset_path=asset_path))
        assert sorted(light.kind for light in lights) == ["point", "point", "spot", "spot"]


def test_measured_headlights_sit_just_in_front_of_the_real_lens() -> None:
    """Heading east, on a measured model: each spot is at the real lens's
    own forward position plus its half-depth plus the small outset, at the
    real lens height and lateral spacing -- not a generic guess."""
    lamp = VEHICLE_LAMP_GEOMETRY["vehCar_vehicle02"].headlight
    spots = [light for light in vehicle_lights(_vehicle(0.0)) if light.kind == "spot"]
    for spot in spots:
        assert spot.position[0] == pytest.approx(
            10.0 + lamp.forward_m + lamp.half_extents_m[0] + LIGHT_OUTSET_BEYOND_LENS_M
        )
        assert spot.position[2] == pytest.approx(lamp.height_m)
        assert spot.direction is not None
        assert spot.direction[0] == pytest.approx(1.0, abs=1e-3)
        assert spot.direction[2] < 0.0  # slight downward dip
    assert sorted(spot.position[1] for spot in spots) == pytest.approx(
        [20.0 - lamp.lateral_m, 20.0 + lamp.lateral_m]
    )


def test_unmeasured_models_fall_back_to_generic_placement_and_get_no_glow() -> None:
    """A model with no measured lamp meshes places its lights from the
    generic vehicle-type length just outside the body, and gets no glowing
    lens (a glow at a guessed spot floats off the body -- found live)."""
    vehicle = _vehicle(0.0, asset_path=UNMEASURED)
    spots = [light for light in vehicle_lights(vehicle) if light.kind == "spot"]
    for spot in spots:
        assert spot.position[0] == pytest.approx(10.0 + 4.6 / 2.0 + LAMP_OUTSET_BEYOND_BODY_M)
        assert spot.position[2] == HEADLIGHT_HEIGHT_M
    points = [light for light in vehicle_lights(vehicle) if light.kind == "point"]
    for point in points:
        assert point.position[0] == pytest.approx(10.0 - 4.6 / 2.0 - LAMP_OUTSET_BEYOND_BODY_M)
        assert point.position[2] == TAILLIGHT_HEIGHT_M
    assert not vehicle_glows(vehicle)


def test_measured_tail_lights_sit_just_behind_the_real_lens() -> None:
    """Heading north on a measured model: tail lights are behind (smaller
    y) the real tail lens by its half-depth plus the small outset."""
    lamp = VEHICLE_LAMP_GEOMETRY["vehCar_vehicle02"].taillight
    points = [light for light in vehicle_lights(_vehicle(np.pi / 2)) if light.kind == "point"]
    for point in points:
        assert point.position[1] == pytest.approx(
            20.0 + lamp.forward_m - lamp.half_extents_m[0] - LIGHT_OUTSET_BEYOND_LENS_M
        )
        assert point.position[2] == pytest.approx(lamp.height_m)


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


def test_glowing_lenses_sit_on_the_real_lens_and_are_sized_like_it() -> None:
    """A measured model gets four glowing lenses centred on its real lamp
    meshes, each an ellipsoid with the real lens's own half-extents,
    rotated to the vehicle's heading; a braking vehicle's tail lenses are
    brighter than a moving one's."""
    geometry = VEHICLE_LAMP_GEOMETRY["vehCar_vehicle02"]
    moving = vehicle_glows(_vehicle(0.0, braking=False))
    braking = vehicle_glows(_vehicle(0.0, braking=True))
    assert len(moving) == 4

    heads = [g for g in moving if g.intensity == HEADLIGHT_GLOW_INTENSITY]
    tails_moving = [g for g in moving if g.position[0] < 10.0]
    tails_braking = [g for g in braking if g.position[0] < 10.0]
    assert len(heads) == 2
    for glow in heads:
        assert glow.position[0] == pytest.approx(10.0 + geometry.headlight.forward_m)
        assert glow.position[2] == pytest.approx(geometry.headlight.height_m)
        assert glow.semi_axes_m == geometry.headlight.half_extents_m
        assert glow.rotation_rad == 0.0
    for glow in tails_moving:
        assert glow.position[0] == pytest.approx(10.0 + geometry.taillight.forward_m)
        assert glow.semi_axes_m == geometry.taillight.half_extents_m
        assert glow.intensity == RUNNING_TAILLIGHT_GLOW_INTENSITY
    assert all(g.intensity == BRAKE_LIGHT_GLOW_INTENSITY for g in tails_braking)
    assert set(heads[0].to_json()) == {
        "position",
        "color",
        "semi_axes_m",
        "rotation_rad",
        "intensity",
    }
