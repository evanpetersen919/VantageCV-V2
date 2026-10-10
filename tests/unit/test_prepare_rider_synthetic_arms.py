"""Tests for the rider study's arm builder (``bin/prepare_rider_synthetic_arms.py``)."""

import importlib.util
import json
from pathlib import Path
from typing import Dict, Set

import pytest

SPEC = importlib.util.spec_from_file_location(
    "prepare_rider_synthetic_arms",
    Path(__file__).resolve().parents[2] / "bin" / "prepare_rider_synthetic_arms.py",
)
arms = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(arms)  # type: ignore[union-attr]


def _base() -> Dict[str, Set[str]]:
    """100 images: 4 with a rider, 10 with a bike (one with both), none with a motor."""
    base: Dict[str, Set[str]] = {f"img{i:03d}": set() for i in range(100)}
    for i in range(4):
        base[f"img{i:03d}"].add("rider")
    for i in range(3, 13):
        base[f"img{i:03d}"].add("bike")
    return base


def test_rarest_class_repeated_three_times_and_others_less() -> None:
    """Rarest class repeated three times and others less."""
    counts = arms.repeat_counts(_base(), ("rider", "bike", "motor"), 9.0, seed=0)
    # f_rider 0.04, f_bike 0.10, t = 0.36: r_rider = 3, r_bike = sqrt(3.6) = 1.9
    assert all(counts[f"img{i:03d}"] == 3 for i in range(4))
    assert all(counts[f"img{i:03d}"] in (1, 2) for i in range(4, 13))
    assert all(counts[f"img{i:03d}"] == 1 for i in range(13, 100))


def test_repeat_counts_are_deterministic() -> None:
    """Repeat counts are deterministic."""
    first = arms.repeat_counts(_base(), ("rider", "bike"), 9.0, seed=7)
    assert first == arms.repeat_counts(_base(), ("rider", "bike"), 9.0, seed=7)


def test_repeat_counts_with_no_rare_images_are_all_one() -> None:
    """Repeat counts with no rare images are all one."""
    counts = arms.repeat_counts({"a": set(), "b": set()}, ("rider",), 9.0, seed=0)
    assert counts == {"a": 1, "b": 1}


def test_pick_synthetic_only_rider_or_bike_images() -> None:
    """Pick synthetic only rider or bike images."""
    coco = {
        "images": [{"id": i} for i in range(6)],
        "annotations": [
            {"image_id": 0, "category_id": 10},
            {"image_id": 1, "category_id": 2},
            {"image_id": 2, "category_id": 3},
            {"image_id": 3, "category_id": 1},
        ],
    }
    picked = arms.pick_synthetic(coco, 2, seed=0)
    assert {i["id"] for i in picked} == {0, 1}
    assert [i["id"] for i in picked] == [i["id"] for i in arms.pick_synthetic(coco, 2, seed=0)]
    with pytest.raises(ValueError):
        arms.pick_synthetic(coco, 3, seed=0)


def test_import_synthetic_copies_images_and_writes_labels(tmp_path: Path) -> None:
    """Import synthetic copies images and writes labels."""
    synthetic, bundle = tmp_path / "syn", tmp_path / "bundle"
    (synthetic / "images").mkdir(parents=True)
    (synthetic / "images" / "f0.jpg").write_bytes(b"x")
    coco = {
        "images": [{"id": 0, "file_name": "images/f0.jpg", "width": 100, "height": 50}],
        "annotations": [
            {"id": 1, "image_id": 0, "category_id": 10, "bbox": [10, 5, 20, 40], "iscrowd": 0}
        ],
        "categories": [],
    }
    (synthetic / "annotations.json").write_text(json.dumps(coco), encoding="utf-8")
    lines = arms.import_synthetic(synthetic, bundle, seed=0, count=1)
    assert len(lines) == 1 and Path(lines[0]).is_file()
    label = (bundle / "labels" / "synthetic" / "images_f0.txt").read_text(encoding="utf-8")
    assert label.split()[0] == "6"  # rider is the last class of the riders order
