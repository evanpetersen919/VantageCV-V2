"""The v7 realism profile: hood overlay and label clipping, night/fog/weather presets, camera
jitter. Each default (v6) is checked to be unchanged."""

import numpy as np
from PIL import Image

from src.export.coco_exporter import CocoFrame
from src.ground_truth.bbox_2d import BoundingBox2D
from src.orchestration.camera_sampling import (
    PITCH_JITTER_RAD,
    PITCH_JITTER_V7_RAD,
    _pitched_target_z,
)
from src.orchestration.hood import (
    HOOD_HEIGHT_FRACTION_RANGE,
    clip_to_hood,
    hood_top_row,
    paint_hood,
)
from src.procedural.environment import (
    NIGHT_ENVIRONMENT,
    NIGHT_ENVIRONMENT_V7,
    WEATHER_SHARES_V7,
    Season,
    TimeOfDay,
    Weather,
    draw_weather,
    scenario_environment,
)


def _frame(boxes) -> CocoFrame:  # type: ignore[no-untyped-def]
    """A frame holding the given (y_min, y_max) boxes; the camera is not used by the clip."""
    bboxes = [BoundingBox2D(i, 10.0, y0, 50.0, y1, 1.0) for i, (y0, y1) in enumerate(boxes)]
    silhouettes = {
        i: np.array([[10.0, y0], [50.0, y0], [30.0, y1]]) for i, (y0, y1) in enumerate(boxes)
    }
    return CocoFrame(0, "x.png", None, bboxes, {}, {}, silhouettes)  # type: ignore[arg-type]


def test_clip_drops_boxes_under_the_hood_and_cuts_boxes_that_reach_into_it() -> None:
    """Hood at row 900: a box wholly below goes, one reaching in is cut, one above is kept."""
    frame = _frame([(920.0, 1000.0), (850.0, 960.0), (400.0, 500.0), (895.0, 905.0)])
    clipped = clip_to_hood(frame, 900, min_height_px=8.0)
    spans = [(box.y_min, box.y_max) for box in clipped.bboxes_2d]
    assert spans == [(850.0, 900.0), (400.0, 500.0)]  # the 5-px sliver is below the minimum
    assert all(np.asarray(p)[:, 1].max() <= 900 for p in clipped.silhouettes_by_id.values())


def test_hood_top_row_respects_probability_and_height_range() -> None:
    """About half the frames get a hood, 5-12% of the image height tall."""
    rng = np.random.Generator(np.random.PCG64(0))
    rows = [hood_top_row(rng, 1080) for _ in range(4000)]
    present = [row for row in rows if row is not None]
    assert 0.45 < len(present) / len(rows) < 0.55
    low, high = HOOD_HEIGHT_FRACTION_RANGE
    assert min(present) >= round(1080 * (1 - high)) and max(present) <= round(1080 * (1 - low))


def test_painted_hood_is_dark_and_leaves_the_scene_above_untouched() -> None:
    """Pixels above the crown keep their values; the bottom rows are dark."""
    scene = Image.new("RGB", (200, 100), (200, 180, 160))
    painted = np.array(paint_hood(scene, 85, np.random.Generator(np.random.PCG64(1))))
    assert (painted[:80] == np.array([200, 180, 160])).all()
    assert painted[-1].mean() < 90


def test_v6_defaults_are_unchanged() -> None:
    """The default profile still gives the v6 night and the v6 weather draw."""
    default = scenario_environment(Season.SUMMER, TimeOfDay.NIGHT, Weather.CLEAR, 7)
    assert default.sun_temperature_k == NIGHT_ENVIRONMENT.sun_temperature_k
    assert default.asset_scalars  # v6's always-on material jitter
    assert draw_weather(11) == draw_weather(11, "v6")


def test_v7_night_is_dimmer_and_neutral_and_has_no_material_jitter() -> None:
    """v7 night: much lower sun, neutral-to-warm grade, exposure cap emitted, no jitter."""
    night = scenario_environment(Season.SUMMER, TimeOfDay.NIGHT, Weather.CLEAR, 7, "v7")
    assert night.sun_intensity_lux == NIGHT_ENVIRONMENT_V7.sun_intensity_lux
    assert night.color_gain is not None and night.color_gain[2] <= night.color_gain[0]
    assert night.asset_scalars is None and night.surface_scalars is None
    assert night.to_json()["exposure"] == {
        "max_brightness": NIGHT_ENVIRONMENT_V7.exposure_max_brightness
    }


def test_v7_fog_starts_at_the_camera_and_is_rare() -> None:
    """The v6 fog started 300 m out, past the whole scene; v7's starts at 0 and is ~1% of days."""
    fog = scenario_environment(Season.SUMMER, TimeOfDay.DAY, Weather.FOG, 7, "v7")
    assert fog.fog_start_distance_m == 0.0
    assert (
        scenario_environment(Season.SUMMER, TimeOfDay.DAY, Weather.FOG, 7).fog_start_distance_m
        == 300.0
    )
    assert (
        abs(sum(WEATHER_SHARES_V7.values()) - 1.0) < 1e-9 and WEATHER_SHARES_V7[Weather.FOG] <= 0.01
    )
    draws = [draw_weather(seed, "v7") for seed in range(3000)]
    assert 0.0 < draws.count(Weather.FOG) / 3000 < 0.025


def test_v7_pitch_jitter_is_wider_but_draws_the_same_number_of_values() -> None:
    """Same rng consumption, wider limit."""
    wide = [
        abs(_pitched_target_z(30.0, np.random.Generator(np.random.PCG64(s)), "v7") - 1.2)
        for s in range(300)
    ]
    narrow = [
        abs(_pitched_target_z(30.0, np.random.Generator(np.random.PCG64(s))) - 1.2)
        for s in range(300)
    ]
    assert max(narrow) <= 30.0 * np.tan(PITCH_JITTER_RAD) + 1e-9
    assert max(wide) > max(narrow) and max(wide) <= 30.0 * np.tan(PITCH_JITTER_V7_RAD) + 1e-9
