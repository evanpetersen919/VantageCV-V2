"""Tests for the live-render camera model and calibration measurement."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.orchestration.live_render import (
    CALIBRATION_CAMERA,
    CALIBRATION_SQUARE_CENTRES,
    LiveRenderer,
    ue_camera,
    vertical_fov_deg,
)
from src.ue5.backend import _as_text


def test_vertical_fov_is_the_engine_default_at_four_by_three() -> None:
    """The engine default of 90 degrees is defined at 4:3, i.e. 73.74 degrees vertical."""
    assert vertical_fov_deg() == pytest.approx(73.74, abs=0.01)


def test_horizontal_fov_follows_the_aspect_ratio() -> None:
    """The vertical FOV is fixed, so a wider image sees a wider horizontal angle."""
    narrow = ue_camera(np.zeros(3), np.array([1.0, 0.0, 0.0]), 640, 480).intrinsics
    wide = ue_camera(np.zeros(3), np.array([1.0, 0.0, 0.0]), 1920, 1080).intrinsics
    assert narrow.focal_length_x == pytest.approx(320.0, abs=0.01)  # 90 deg horizontal at 4:3
    assert wide.focal_length_y == pytest.approx(1080 / 2 / np.tan(np.radians(73.74 / 2)), abs=0.1)
    assert wide.focal_length_x == wide.focal_length_y


def test_point_ahead_projects_to_the_image_centre() -> None:
    """A point on the optical axis lands on the principal point."""
    camera = ue_camera(np.array([0.0, 0.0, 2.0]), np.array([30.0, 0.0, 2.0]), 1920, 1080)
    pixel, depth = camera.project(np.array([20.0, 0.0, 2.0]))
    assert pixel is not None
    assert pixel == pytest.approx([960.0, 540.0], abs=1e-6)
    assert depth == pytest.approx(20.0)


def _calibration_picture(path: Path, shift_px: float) -> None:
    """A black frame with a white square at each projected calibration square, shifted."""
    camera = ue_camera(*CALIBRATION_CAMERA, 1920, 1080)
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    for x, y in CALIBRATION_SQUARE_CENTRES:
        pixel, _ = camera.project(np.array([x, y, 0.02]))
        assert pixel is not None
        column, row = int(pixel[0] + shift_px), int(pixel[1])
        image[row - 12 : row + 12, column - 12 : column + 12] = 255
    Image.fromarray(image).save(path)


def _error(path: Path) -> float:
    """The calibration error of the picture at ``path`` for the calibration camera."""
    camera = ue_camera(*CALIBRATION_CAMERA, 1920, 1080)
    return LiveRenderer._measure_error(path, camera)  # pylint: disable=protected-access


def test_calibration_error_is_zero_for_a_perfect_render(tmp_path: Path) -> None:
    """Squares exactly where the camera model puts them give about zero error."""
    path = tmp_path / "perfect.png"
    _calibration_picture(path, 0.0)
    assert _error(path) < 2.0  # the picture is drawn on whole pixels


def test_calibration_error_reports_a_shift(tmp_path: Path) -> None:
    """A render shifted by 10 px reads as about 10 px of error."""
    path = tmp_path / "shifted.png"
    _calibration_picture(path, 10.0)
    assert _error(path) == pytest.approx(10.0, abs=1.0)


def test_calibration_error_is_infinite_when_squares_are_missing(tmp_path: Path) -> None:
    """A black frame has no squares to match."""
    path = tmp_path / "empty.png"
    Image.fromarray(np.zeros((1080, 1920, 3), dtype=np.uint8)).save(path)
    assert _error(path) == float("inf")


def test_websocket_messages_decode_from_text_or_bytes() -> None:
    """The server may answer with text or bytes."""
    assert _as_text('{"a": 1}') == '{"a": 1}'
    assert _as_text(b'{"a": 1}') == '{"a": 1}'
