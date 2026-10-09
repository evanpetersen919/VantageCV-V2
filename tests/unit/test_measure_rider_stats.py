"""Rider-vehicle pairing and class statistics of the BDD100K rider measurement."""

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List

SPEC = importlib.util.spec_from_file_location(
    "measure_rider_stats", Path(__file__).resolve().parents[2] / "bin" / "measure_rider_stats.py"
)
assert SPEC is not None and SPEC.loader is not None
STATS = importlib.util.module_from_spec(SPEC)
sys.modules["measure_rider_stats"] = STATS
SPEC.loader.exec_module(STATS)


def _image(time: str, objects: List[Any]) -> Dict[str, Any]:
    return {"time": time, "weather": "clear", "objects": objects}


def test_overlap_over_min_is_one_for_contained_boxes_and_zero_for_disjoint() -> None:
    """A rider box inside a bike box scores 1; boxes apart score 0."""
    assert STATS.overlap_over_min((10, 10, 20, 30), (0, 0, 100, 100)) == 1.0
    assert STATS.overlap_over_min((0, 0, 10, 10), (50, 50, 60, 60)) == 0.0


def test_match_riders_is_one_to_one_by_largest_overlap() -> None:
    """Two riders on one bike pair only one of them; the other has no vehicle."""
    riders = [(10, 10, 30, 60), (12, 10, 32, 60)]
    vehicles = [(0, 30, 50, 80)]
    assert len(STATS.match_riders(riders, vehicles, 0.3)) == 1
    assert STATS.vehicle_rider_counts(riders, vehicles, 0.3) == [2]


def test_threshold_decides_whether_a_grazing_rider_pairs() -> None:
    """A rider that only touches the vehicle corner pairs at a low threshold, not a high one."""
    riders = [(0, 0, 10, 10)]
    vehicles = [(8, 8, 40, 40)]
    assert STATS.match_riders(riders, vehicles, 0.01) == [(0, 0)]
    assert STATS.match_riders(riders, vehicles, 0.3) == []


def test_pairing_statistics_counts_unridden_bikes_and_pillions() -> None:
    """One ridden bike, one parked bike and a motor with two riders."""
    objects = [
        ("rider", (10, 10, 30, 60), False, False),
        ("bike", (0, 30, 50, 80), True, False),
        ("bike", (200, 30, 250, 80), False, False),
        ("rider", (500, 10, 520, 60), False, False),
        ("rider", (502, 10, 522, 60), False, False),
        ("motor", (490, 30, 540, 90), False, True),
    ]
    stats = STATS.pairing_statistics([_image("daytime", objects)])["overlap_over_min>=0.3"]
    assert stats["riders"] == 3
    assert stats["bike_boxes"] == 2 and stats["bike_with_rider"] == 1
    assert stats["bike_unridden_fraction"] == 0.5
    assert stats["motor_with_rider"] == 1
    assert stats["vehicles_with_two_or_more_riders_overlapping"] == {"motor": 1}
    assert stats["riders_without_vehicle"] == 1


def test_class_statistics_rates_by_time_of_day() -> None:
    """Instances, images with the class, and occlusion are counted per scope."""
    day = _image("daytime", [("rider", (0, 0, 10, 40), True, False)])
    night = _image("night", [])
    stats = STATS.class_statistics([day, night], "rider")
    assert stats["all"]["instances"] == 1 and stats["all"]["images"] == 2
    assert stats["all"]["p_at_least_1"] == 0.5
    assert stats["daytime"]["occluded_rate"] == 1.0
    assert stats["night"]["instances"] == 0
    assert stats["daytime"]["height_px"]["p50"] == 40.0


def test_markdown_tables_carry_the_measured_numbers() -> None:
    """The rendered tables hold the counts and pairing fractions that were measured."""
    objects = [
        ("rider", (10, 10, 30, 60), True, False),
        ("bike", (0, 30, 50, 80), True, False),
        ("person", (300, 10, 320, 70), False, False),
        ("car", (400, 100, 500, 160), False, False),
    ]
    data = STATS.measure([_image("daytime", objects), _image("night", [])])
    text = STATS.render_markdown(data, data)
    assert "| rider | train | 1 | 1 (50.0%)" in text
    assert "| 0.3 | 100.0% | 0.0% |" in text
