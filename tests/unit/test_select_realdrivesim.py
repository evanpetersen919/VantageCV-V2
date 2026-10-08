"""The RealDriveSim selection: class mapping, box rules, YOLO conversion, night rule, matcher."""

# pylint: disable=missing-function-docstring,duplicate-code

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

_SPEC = importlib.util.spec_from_file_location(
    "select_realdrivesim", Path(__file__).resolve().parents[2] / "bin" / "select_realdrivesim.py"
)
assert _SPEC is not None and _SPEC.loader is not None
sel = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sel)


def _annotation(
    class_id: int, w: int = 40, h: int = 30, visibility: float = 0.8, iscrowd: bool = False
) -> dict:
    return {
        "class_id": class_id,
        "iscrowd": iscrowd,
        "box": {"x": 100, "y": 100, "w": w, "h": h},
        "attributes": {"user_data": json.dumps({"visibility": visibility, "truncation": 0.0})},
    }


@pytest.mark.parametrize(
    "class_id, expected",
    [(22, 0), (5, 1), (103, 1), (4, 2), (47, 2), (36, 3), (104, 3)],
)
def test_the_official_ids_map_to_the_four_classes(class_id: int, expected: int) -> None:
    assert sel.object_class(_annotation(class_id)) == expected


@pytest.mark.parametrize("class_id", [0, 1, 2, 6, 7, 13, 14, 18, 32, 35, 39, 17, 24, 37, 255])
def test_riders_motorcycles_rvs_and_scenery_are_dropped(class_id: int) -> None:
    assert sel.object_class(_annotation(class_id)) is None


def test_size_visibility_and_crowd_rules() -> None:
    assert sel.object_class(_annotation(5, h=7)) is None  # under 8 px high
    assert sel.object_class(_annotation(5, h=8)) == 1
    assert sel.object_class(_annotation(5, w=3)) is None  # under 4 px wide
    assert sel.object_class(_annotation(5, visibility=0.0999)) is None
    assert sel.object_class(_annotation(5, visibility=0.1)) == 1
    assert sel.object_class(_annotation(5, iscrowd=True)) is None


def test_an_annotation_without_visibility_is_dropped_not_guessed() -> None:
    broken = _annotation(5)
    broken["attributes"]["user_data"] = "{}"
    assert sel.object_class(broken) is None


def test_yolo_line_is_normalised_and_clipped_to_the_image() -> None:
    line = sel.yolo_line(1, {"x": 0, "y": 0, "w": 2048, "h": 1024})
    assert line == "1 0.500000 0.500000 1.000000 1.000000"
    clipped = sel.yolo_line(0, {"x": 2000, "y": 1000, "w": 200, "h": 100})
    parts = clipped.split()
    assert float(parts[3]) == pytest.approx(48 / 2048, abs=1e-5)
    assert float(parts[4]) == pytest.approx(24 / 1024, abs=1e-5)
    assert sel.yolo_line(0, {"x": 3000, "y": 10, "w": 20, "h": 20}) is None  # entirely outside


def test_brightness_orders_dark_and_light_frames_and_ignores_the_bottom() -> None:
    dark = Image.new("RGB", (160, 80), (20, 20, 20))
    light = Image.new("RGB", (160, 80), (200, 200, 200))
    assert sel.brightness(dark) < sel.brightness(light)
    bottom_bright = Image.new("RGB", (160, 80), (20, 20, 20))
    bottom_bright.paste((255, 255, 255), (0, 64, 160, 80))  # the lowest 20%
    assert sel.brightness(bottom_bright) == pytest.approx(sel.brightness(dark), abs=1.0)


def test_night_threshold_separates_a_clean_set() -> None:
    values = [10, 20, 30, 40, 100, 110, 120, 130]
    night = [True, True, True, True, False, False, False, False]
    threshold, accuracy = sel.fit_night_threshold(values, night)
    assert 40 < threshold < 100 and accuracy == 1.0


def test_matcher_reaches_counts_and_night_share_when_the_pool_allows_it() -> None:
    rng = np.random.default_rng(1)
    counts = rng.integers(0, 8, size=(2000, 4))
    night = rng.random(2000) < 0.25
    totals = counts[:512].sum(axis=0)  # a target that certainly exists in the pool
    picked, within = sel.choose_matched(
        counts, night, totals, 0.39, 512, seed=0, iterations=120_000
    )
    assert within
    assert len(set(picked)) == 512
    assert (np.abs(counts[picked].sum(axis=0) / totals - 1.0) <= 0.1).all()
    assert abs(night[picked].mean() - 0.39) <= 0.05


def test_matcher_reports_failure_when_the_target_cannot_be_reached() -> None:
    counts = np.ones((600, 4), dtype=int)
    night = np.zeros(600, dtype=bool)
    _, within = sel.choose_matched(
        counts, night, [5000, 5000, 5000, 5000], 0.5, 512, seed=0, iterations=2000
    )
    assert not within
