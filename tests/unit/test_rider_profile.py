"""The rider profile scores rider, bike and motor as classes; the default profile is unchanged."""

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.evaluation import class_maps
from src.evaluation.class_maps import DEFAULT_PROFILE, RIDER_PROFILE
from src.evaluation.detections import boxes_to_detections
from src.evaluation.loaders import _cityscapes_mapping, load_bdd100k
from src.evaluation.portable import data_yaml
from src.evaluation.scoring import format_report, score

RIDER, BIKE, MOTOR = class_maps.RIDER, class_maps.BIKE, class_maps.MOTOR


def _labels(tmp_path: Path) -> Path:
    """A BDD100K label list with a rider on a bike, a parked motor, a car and a train."""
    objects: List[Dict[str, Any]] = [
        {"category": "rider", "box2d": {"x1": 100, "y1": 100, "x2": 140, "y2": 200}},
        {"category": "bike", "box2d": {"x1": 90, "y1": 150, "x2": 160, "y2": 220}},
        {"category": "motor", "box2d": {"x1": 400, "y1": 300, "x2": 480, "y2": 380}},
        {"category": "car", "box2d": {"x1": 600, "y1": 300, "x2": 700, "y2": 360}},
        {"category": "train", "box2d": {"x1": 800, "y1": 100, "x2": 1000, "y2": 300}},
    ]
    path = tmp_path / "labels.json"
    path.write_text(
        json.dumps([{"name": "a.jpg", "attributes": {"timeofday": "daytime"}, "labels": objects}]),
        encoding="utf-8",
    )
    return path


def test_default_profile_still_ignores_riders_and_drops_bikes(tmp_path: Path) -> None:
    """The four-class profile is as before: rider is ignored and bike and motor are dropped."""
    eval_set = load_bdd100k(_labels(tmp_path), tmp_path)
    scored = {a["category_id"] for a in eval_set.coco["annotations"] if not a["iscrowd"]}
    assert scored == {class_maps.CAR}
    assert eval_set.notes["profile"] == "default"


def test_rider_profile_scores_rider_bike_and_motor(tmp_path: Path) -> None:
    """Rider, bike and motor become scored classes; the train stays an ignore region."""
    eval_set = load_bdd100k(_labels(tmp_path), tmp_path, profile=RIDER_PROFILE)
    counts = eval_set.counts()
    assert counts["rider"] == 1 and counts["bike"] == 1 and counts["motor"] == 1
    assert (
        counts["car"] == 1 and counts["ignore_regions"] == 2
    )  # the train, once per class it hides
    assert {c["name"] for c in eval_set.coco["categories"]} == set(RIDER_PROFILE.classes.values())


def test_rider_profile_class_order_and_ids() -> None:
    """Bike and motor take COCO's bicycle and motorcycle ids, rider its own; YOLO order is by id."""
    assert (BIKE, MOTOR, RIDER) == (2, 4, 10)
    assert RIDER_PROFILE.class_order == (1, 2, 3, 4, 6, 8, 10)
    assert [RIDER_PROFILE.classes[i] for i in RIDER_PROFILE.class_order] == [
        "person",
        "bike",
        "car",
        "motor",
        "bus",
        "truck",
        "rider",
    ]


def test_cityscapes_labels_map_to_the_rider_classes() -> None:
    """Bicycle and motorcycle are classes, their groups are ignore regions for the same class."""
    assert _cityscapes_mapping("bicycle", RIDER_PROFILE) == (BIKE, ())
    assert _cityscapes_mapping("motorcycle", RIDER_PROFILE) == (MOTOR, ())
    assert _cityscapes_mapping("rider", RIDER_PROFILE) == (RIDER, ())
    assert _cityscapes_mapping("bicyclegroup", RIDER_PROFILE) == (None, (BIKE,))
    assert _cityscapes_mapping("rider", DEFAULT_PROFILE) == (None, (class_maps.PERSON,))


def test_detections_map_coco_bicycle_and_motorcycle_but_have_no_rider() -> None:
    """A COCO detector's bicycle and motorcycle become bike and motor; nothing becomes rider."""
    boxes = [[0, 0, 10, 10]] * 3
    found = boxes_to_detections(1, boxes, [0.9] * 3, [1, 3, 0], "coco80", RIDER_PROFILE)
    assert [d["category_id"] for d in found] == [BIKE, MOTOR, class_maps.PERSON]
    assert RIDER not in RIDER_PROFILE.coco80_to_ours.values()


def test_trained_model_indices_follow_the_profile_order() -> None:
    """A model trained on the rider export predicts index 6 for rider and 1 for bike."""
    boxes = [[0, 0, 10, 10]] * 2
    found = boxes_to_detections(1, boxes, [0.9, 0.9], [6, 1], "ours", RIDER_PROFILE)
    assert [d["category_id"] for d in found] == [RIDER, BIKE]


def test_scoring_reports_the_profile_classes(tmp_path: Path) -> None:
    """A perfect bike detection scores AP 1 for bike, and the report lists every profile class."""
    eval_set = load_bdd100k(_labels(tmp_path), tmp_path, profile=RIDER_PROFILE)
    perfect = [
        {"image_id": 1, "category_id": a["category_id"], "bbox": a["bbox"], "score": 0.99}
        for a in eval_set.coco["annotations"]
        if not a["iscrowd"]
    ]
    report = score(eval_set, perfect, min_images=1)
    assert report.overall.per_class_ap["bike"] == pytest.approx(1.0)
    assert report.overall.per_class_ap["rider"] == pytest.approx(1.0)
    assert set(report.overall.per_class_ap) == set(RIDER_PROFILE.classes.values())
    assert "rider" in format_report(report)


def test_data_yaml_names_follow_the_profile() -> None:
    """The training yaml lists the rider classes in YOLO order when given them."""
    names = {i: RIDER_PROFILE.classes[c] for i, c in enumerate(RIDER_PROFILE.class_order)}
    text = data_yaml([Path("/d/a.txt")], Path("/d/val.txt"), names)
    assert "  6: rider" in text and "  1: bike" in text
