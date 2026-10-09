"""Arm selection of the rider headroom check (``bin/prepare_rider_headroom.py``)."""

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

SPEC = importlib.util.spec_from_file_location(
    "prepare_rider_headroom",
    Path(__file__).resolve().parents[2] / "bin" / "prepare_rider_headroom.py",
)
assert SPEC is not None and SPEC.loader is not None
HEADROOM = importlib.util.module_from_spec(SPEC)
sys.modules["prepare_rider_headroom"] = HEADROOM
SPEC.loader.exec_module(HEADROOM)


def _order_and_flags(total: int, rare_every: int) -> Tuple[List[str], Dict[str, bool]]:
    """Names ``n0..`` in a fixed order; every ``rare_every``-th one is rare."""
    order: List[str] = [f"n{i:04d}" for i in range(total)]
    return order, {name: i % rare_every == 0 for i, name in enumerate(order)}


def test_shuffle_is_sorted_then_seeded_and_reproducible() -> None:
    """The same names and seed always give the same order, whatever order the names arrive in."""
    names = [f"img{i}" for i in range(50)]
    first = HEADROOM.shuffled_names(names, 0)
    assert first == HEADROOM.shuffled_names(list(reversed(names)), 0)
    assert first != HEADROOM.shuffled_names(names, 1)
    assert sorted(first) == sorted(names)


def test_arms_share_the_base_and_the_validation_list_is_disjoint() -> None:
    """Every arm starts with the same base set; extras never touch the base or validation images."""
    order, rare = _order_and_flags(2000, 8)
    chosen = HEADROOM.select_arms(order, rare, 400, 50)
    base, validation = chosen["arms"]["A"], set(chosen["validation"])
    assert base == order[:400] and len(validation) == 50 and not validation & set(base)
    for arm, items in chosen["arms"].items():
        assert items[:400] == base
        assert not set(items[400:]) & (set(base) | validation), arm


def test_rare_arms_double_and_quadruple_the_rare_images_and_random_arms_match_the_size() -> None:
    """rare2 / rare4 hold 2x / 4x the base's rare images; rand arms add as many images."""
    order, rare = _order_and_flags(2000, 8)
    chosen = HEADROOM.select_arms(order, rare, 400, 50)
    r0 = chosen["r0"]
    assert r0 == sum(rare[n] for n in order[:400])
    arms = chosen["arms"]

    def rare_count(arm: str) -> int:
        return sum(rare[n] for n in arms[arm])

    assert rare_count("rare2") == 2 * r0 and rare_count("rare4") == 4 * r0
    assert len(arms["rare2"]) == len(arms["rand2"]) == 400 + r0
    assert len(arms["rare4"]) == len(arms["rand4"]) == 400 + 3 * r0
    assert set(arms["rare2"]) <= set(arms["rare4"]) and set(arms["rand2"]) <= set(arms["rand4"])


def test_random_arms_follow_the_natural_rare_rate_not_the_rare_arms() -> None:
    """The random extras are the pool's first images, so they are not selected for rarity."""
    order, rare = _order_and_flags(2000, 8)
    arms = HEADROOM.select_arms(order, rare, 400, 50)["arms"]
    extra = arms["rand4"][400:]
    assert extra == order[450 : 450 + len(extra)]


def test_not_enough_rare_images_in_the_pool_is_an_error() -> None:
    """A pool with too few rare images stops the build."""
    order, rare = _order_and_flags(500, 2)
    with pytest.raises(ValueError):
        HEADROOM.select_arms(order, rare, 400, 50)


def test_instance_counts_ignore_regions_and_name_classes() -> None:
    """Counts are per class name over the chosen images, without ignore regions."""
    coco: Dict[str, Any] = {
        "images": [{"id": 1, "file_name": "a.jpg"}, {"id": 2, "file_name": "b.jpg"}],
        "categories": [{"id": 10, "name": "rider"}, {"id": 2, "name": "bike"}],
        "annotations": [
            {"image_id": 1, "category_id": 10, "iscrowd": 0},
            {"image_id": 1, "category_id": 2, "iscrowd": 1},
            {"image_id": 2, "category_id": 10, "iscrowd": 0},
        ],
    }
    eval_set = HEADROOM.EvalSet("t", coco, Path("."))
    assert HEADROOM.instance_counts(eval_set, ["a"]) == {"rider": 1, "bike": 0}
