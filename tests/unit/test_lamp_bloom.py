"""Lamp glare: only lamps the depth map shows are lit; brake lamps glare more; hood is kept."""

# pylint: disable=missing-function-docstring

import numpy as np

from src.orchestration.lamp_bloom import BloomParams, add_glare, visible_lamps
from src.procedural import night_lights
from src.sensors.camera_model import Camera, CameraExtrinsics, CameraIntrinsics

WIDTH, HEIGHT = 200, 120


def _camera() -> Camera:
    extrinsics = CameraExtrinsics.looking_at(np.array([0.0, 0.0, 1.0]), np.array([0.0, 10.0, 1.0]))
    return Camera(CameraIntrinsics.from_fov(90.0, WIDTH, HEIGHT), extrinsics)


def _glow(y: float, intensity: float, colour=(1.0, 0.04, 0.02)):
    return {
        "position": [0.0, y, 1.0],
        "color": list(colour),
        "semi_axes_m": [0.1, 0.12, 0.1],
        "intensity": intensity,
    }


def _depth(value: float) -> np.ndarray:
    return np.full((HEIGHT, WIDTH), value, dtype=np.float32)


def test_a_visible_tail_lamp_gets_a_red_glare_centred_on_it() -> None:
    lamps = visible_lamps(
        [_glow(10.0, night_lights.BRAKE_LIGHT_GLOW_INTENSITY)], _camera(), _depth(10.0)
    )
    assert len(lamps) == 1
    picture = add_glare(np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8), lamps)
    centre = picture[HEIGHT // 2, WIDTH // 2].astype(int)
    assert centre[0] > 200 and centre[0] > centre[1] > 0  # bright and red, not white
    halo = picture[HEIGHT // 2, WIDTH // 2 + 3].astype(int)
    assert halo[0] > halo[1] and 0 < halo[0] < centre[0]  # a red halo that falls off
    assert picture[0, 0].tolist() == [0, 0, 0]  # far away: untouched


def test_a_lamp_the_depth_map_does_not_show_adds_nothing() -> None:
    hidden = visible_lamps(
        [_glow(10.0, 12.0)], _camera(), _depth(4.0)
    )  # something 4 m away covers it
    behind = visible_lamps([_glow(-5.0, 12.0)], _camera(), _depth(10.0))
    sky = visible_lamps([_glow(10.0, 12.0)], _camera(), _depth(0.0))
    assert not hidden and not behind and not sky


def test_brake_lamps_glare_more_than_running_lamps_and_headlamps_are_white() -> None:
    camera, depth = _camera(), _depth(10.0)
    brake = visible_lamps([_glow(10.0, night_lights.BRAKE_LIGHT_GLOW_INTENSITY)], camera, depth)
    running = visible_lamps(
        [_glow(10.0, night_lights.RUNNING_TAILLIGHT_GLOW_INTENSITY)], camera, depth
    )
    head = visible_lamps([_glow(10.0, 14.0, (1.0, 0.95, 0.82))], camera, depth)
    assert brake[0].peak > running[0].peak
    black = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    white = add_glare(black, head)[HEIGHT // 2, WIDTH // 2].astype(int)
    assert min(white) > 150  # a headlamp is white-ish, not red


def test_pixels_marked_keep_are_unchanged() -> None:
    lamps = visible_lamps([_glow(10.0, 12.0)], _camera(), _depth(10.0), BloomParams())
    image = np.full((HEIGHT, WIDTH, 3), 20, dtype=np.uint8)
    keep = np.zeros((HEIGHT, WIDTH), dtype=bool)
    keep[HEIGHT // 2 :] = True
    result = add_glare(image, lamps, keep=keep)
    assert (result[HEIGHT // 2 :] == 20).all()
    assert (result[: HEIGHT // 2] != 20).any()
