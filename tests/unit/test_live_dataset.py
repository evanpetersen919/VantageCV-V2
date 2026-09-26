"""Tests for per-scenario condition draws and per-image metadata."""

import numpy as np

from src.export.coco_exporter import CocoFrame, export_coco
from src.orchestration.live_dataset import NIGHT_SHARE, draw_conditions
from src.orchestration.live_render import ue_camera
from src.procedural.environment import TimeOfDay, Weather


def test_conditions_are_deterministic() -> None:
    """The same seed always gives the same time of day and weather."""
    assert draw_conditions(123) == draw_conditions(123)


def test_night_only_takes_clear_or_rain() -> None:
    """Night keeps its own sky, so only clear or rain is drawn with it."""
    for seed in range(400):
        time_of_day, weather = draw_conditions(seed)
        if time_of_day == TimeOfDay.NIGHT:
            assert weather in (Weather.CLEAR, Weather.RAIN)


def test_night_share_matches_the_configured_share() -> None:
    """About NIGHT_SHARE of seeds are at night."""
    nights = sum(draw_conditions(seed)[0] == TimeOfDay.NIGHT for seed in range(3000))
    assert abs(nights / 3000 - NIGHT_SHARE) < 0.03


def test_frame_metadata_is_written_but_cannot_overwrite_core_fields() -> None:
    """Extra image fields reach the COCO images entry, but id and size stay authoritative."""
    camera = ue_camera(np.zeros(3), np.array([1.0, 0.0, 0.0]), 640, 480)
    frame = CocoFrame(
        image_id=5,
        file_name="a.png",
        camera=camera,
        bboxes_2d=[],
        metadata={"weather": "rain", "id": 99, "width": 1},
    )
    image = export_coco([frame])["images"][0]
    assert image["weather"] == "rain"
    assert image["id"] == 5
    assert image["width"] == 640
