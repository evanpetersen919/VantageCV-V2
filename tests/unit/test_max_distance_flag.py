# pylint: disable=missing-function-docstring,protected-access
"""The ``--max-distance CLASS=METRES`` override of the annotation policy."""

import argparse
import importlib.util
from pathlib import Path

import pytest

from src.export.annotation_policy import MAX_DISTANCE_M
from src.ground_truth.categories import BUS, SEDAN, SUV, TRUCK

_SPEC = importlib.util.spec_from_file_location(
    "generate_live_dataset",
    Path(__file__).resolve().parents[2] / "bin" / "generate_live_dataset.py",
)
assert _SPEC is not None and _SPEC.loader is not None
generate = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(generate)


def _args(items: list) -> argparse.Namespace:
    return argparse.Namespace(
        classes="coco", min_box_height=8.0, min_box_width=4.0, max_distance=items
    )


def test_overrides_change_only_the_named_classes() -> None:
    policy = generate._policy(_args(["truck=95", "bus=72"]))
    assert policy.max_distance_m[TRUCK] == 95.0
    assert policy.max_distance_m[BUS] == 72.0
    assert policy.max_distance_m[SEDAN] == MAX_DISTANCE_M[SEDAN]
    assert policy.max_distance_m[SUV] == MAX_DISTANCE_M[SUV]


def test_car_sets_both_car_categories() -> None:
    policy = generate._policy(_args(["car=60"]))
    assert policy.max_distance_m[SEDAN] == policy.max_distance_m[SUV] == 60.0


def test_no_override_keeps_the_defaults_and_does_not_touch_the_module_table() -> None:
    generate._policy(_args(["truck=95"]))
    assert generate._policy(_args([])).max_distance_m == MAX_DISTANCE_M
    assert MAX_DISTANCE_M[TRUCK] == 53.0


@pytest.mark.parametrize("bad", ["truck", "truck=", "tank=50"])
def test_a_malformed_override_is_refused(bad: str) -> None:
    with pytest.raises(SystemExit):
        generate._policy(_args([bad]))
