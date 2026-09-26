"""Tests for the real-benchmark loaders, the COCO scorer and the scenario-level split."""

import json
import math
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.evaluation import class_maps
from src.evaluation.loaders import load_bdd100k, load_cityscapes
from src.evaluation.scoring import format_report, remap_coco80, score
from src.evaluation.split import split_scenarios, write_split

PERSON, CAR, BUS, TRUCK = class_maps.PERSON, class_maps.CAR, class_maps.BUS, class_maps.TRUCK


def _bdd_frame(name: str, timeofday: str, labels: List[Dict[str, Any]]) -> Dict[str, Any]:
    """One BDD100K label entry in the published format."""
    return {
        "name": name,
        "attributes": {"weather": "clear", "scene": "city street", "timeofday": timeofday},
        "labels": labels,
    }


def _bdd_label(category: str, x1: float, y1: float, x2: float, y2: float) -> Dict[str, Any]:
    """One BDD100K box label."""
    return {"category": category, "box2d": {"x1": x1, "y1": y1, "x2": x2, "y2": y2}}


def _write_bdd(tmp_path: Path, frames: List[Dict[str, Any]]) -> Path:
    """A BDD100K label file."""
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(frames), encoding="utf-8")
    return path


def test_bdd100k_maps_classes_ignores_and_drops(tmp_path: Path) -> None:
    """Positives map to our ids; a rider becomes a person-ignore region; signs are dropped."""
    labels = [
        _bdd_label("car", 100, 100, 200, 160),
        _bdd_label("person", 300, 100, 330, 190),
        _bdd_label("rider", 400, 100, 430, 190),
        _bdd_label("train", 500, 100, 700, 200),
        _bdd_label("traffic sign", 10, 10, 40, 40),
        _bdd_label("bike", 600, 300, 650, 350),
        {"category": "lane", "poly2d": []},
    ]
    eval_set = load_bdd100k(
        _write_bdd(tmp_path, [_bdd_frame("a.jpg", "daytime", labels)]), tmp_path
    )
    by = [(a["category_id"], a["iscrowd"]) for a in eval_set.coco["annotations"]]
    assert by == [(CAR, 0), (PERSON, 0), (PERSON, 1), (BUS, 1), (TRUCK, 1)]
    assert eval_set.counts() == {
        "person": 1,
        "car": 1,
        "bus": 0,
        "truck": 0,
        "ignore_regions": 3,
    }
    assert eval_set.coco["images"][0]["attributes"]["timeofday"] == "daytime"


def test_objects_below_the_size_floor_become_ignore_regions(tmp_path: Path) -> None:
    """A car 6 px tall was never in the training labels, so it is ignored, not scored."""
    labels = [_bdd_label("car", 100, 100, 130, 106), _bdd_label("car", 200, 100, 260, 130)]
    eval_set = load_bdd100k(
        _write_bdd(tmp_path, [_bdd_frame("a.jpg", "daytime", labels)]), tmp_path
    )
    assert [a["iscrowd"] for a in eval_set.coco["annotations"]] == [1, 0]


def test_boxes_are_clipped_to_the_image_and_empty_ones_dropped(tmp_path: Path) -> None:
    """A box hanging off the frame is clipped; one wholly outside is discarded."""
    labels = [_bdd_label("car", 1200, 600, 1400, 800), _bdd_label("car", 1300, 100, 1400, 200)]
    eval_set = load_bdd100k(
        _write_bdd(tmp_path, [_bdd_frame("a.jpg", "daytime", labels)]), tmp_path
    )
    (only,) = eval_set.coco["annotations"]
    assert only["bbox"] == [1200, 600, 80, 120]


def test_bdd100k_per_image_json_directory_layout(tmp_path: Path) -> None:
    """The "Labels" download: one JSON per image (``frames[].objects``); image is ``<name>.jpg``."""
    folder = tmp_path / "labels" / "val"
    folder.mkdir(parents=True)
    entry = {
        "name": "abc-123",
        "attributes": {"weather": "rainy", "scene": "highway", "timeofday": "night"},
        "frames": [
            {
                "timestamp": 10000,
                "objects": [
                    {
                        "category": "car",
                        "id": 0,
                        "box2d": {"x1": 10, "y1": 20, "x2": 110, "y2": 90},
                    },
                    {
                        "category": "rider",
                        "id": 1,
                        "box2d": {"x1": 300, "y1": 20, "x2": 340, "y2": 110},
                    },
                    {"category": "drivable area", "id": 2, "poly2d": []},
                ],
            }
        ],
    }
    (folder / "abc-123.json").write_text(json.dumps(entry), encoding="utf-8")
    (folder / "def-456.json").write_text(
        json.dumps({"name": "def-456", "frames": [{"objects": []}]}), encoding="utf-8"
    )
    images = tmp_path / "images"
    images.mkdir()
    (images / "abc-123.jpg").write_bytes(b"x")
    eval_set = load_bdd100k(folder, images)
    assert [i["file_name"] for i in eval_set.coco["images"]] == ["abc-123.jpg", "def-456.jpg"]
    assert eval_set.coco["images"][0]["attributes"]["weather"] == "rainy"
    assert [(a["category_id"], a["iscrowd"]) for a in eval_set.coco["annotations"]] == [
        (CAR, 0),
        (PERSON, 1),
    ]
    assert eval_set.missing_images() == ["def-456.jpg"]
    assert eval_set.missing_images(limit=1) == []


def test_empty_bdd100k_directory_raises(tmp_path: Path) -> None:
    """A folder with no per-image JSON files is an error, not an empty benchmark."""
    with pytest.raises(FileNotFoundError):
        load_bdd100k(tmp_path, tmp_path)


def _write_cityscapes(root: Path) -> None:
    """One Cityscapes-format image with a car, a person group, a rider and a road."""
    folder = root / "gtFine" / "val" / "berlin"
    folder.mkdir(parents=True)

    def box(label: str, x1: int, y1: int, x2: int, y2: int) -> Dict[str, Any]:
        return {"label": label, "polygon": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]}

    data = {
        "imgWidth": 2048,
        "imgHeight": 1024,
        "objects": [
            box("car", 100, 400, 300, 500),
            box("persongroup", 600, 400, 700, 500),
            box("rider", 800, 400, 850, 500),
            box("road", 0, 600, 2048, 1024),
            box("trailer", 1000, 400, 1200, 500),
            box("bicycle", 1300, 450, 1350, 500),
        ],
    }
    (folder / "berlin_000001_000019_gtFine_polygons.json").write_text(
        json.dumps(data), encoding="utf-8"
    )


def test_cityscapes_boxes_come_from_polygon_extents_with_group_ignores(tmp_path: Path) -> None:
    """Instances map to boxes; group labels ignore their own class; stuff and bikes are dropped."""
    _write_cityscapes(tmp_path)
    eval_set = load_cityscapes(tmp_path)
    by = [(a["category_id"], a["iscrowd"]) for a in eval_set.coco["annotations"]]
    assert by == [(CAR, 0), (PERSON, 1), (PERSON, 1), (TRUCK, 1)]
    image = eval_set.coco["images"][0]
    assert image["file_name"] == "leftImg8bit/val/berlin/berlin_000001_000019_leftImg8bit.png"
    assert image["attributes"] == {"city": "berlin"}
    assert eval_set.coco["annotations"][0]["bbox"] == [100, 400, 200, 100]


def test_missing_cityscapes_files_raise(tmp_path: Path) -> None:
    """A wrong root fails loudly instead of returning an empty benchmark."""
    with pytest.raises(FileNotFoundError):
        load_cityscapes(tmp_path)


def _detection(
    image_id: int, category: int, box: List[float], confidence: float = 0.9
) -> Dict[str, Any]:
    """One COCO-format detection."""
    return {"image_id": image_id, "category_id": category, "bbox": box, "score": confidence}


def _two_image_set(tmp_path: Path) -> Any:
    """Two BDD images (day and night) with one car and one person each."""
    frames = [
        _bdd_frame(
            "day.jpg",
            "daytime",
            [_bdd_label("car", 100, 100, 220, 180), _bdd_label("person", 400, 100, 430, 190)],
        ),
        _bdd_frame(
            "night.jpg",
            "night",
            [_bdd_label("car", 100, 100, 220, 180), _bdd_label("person", 400, 100, 430, 190)],
        ),
    ]
    return load_bdd100k(_write_bdd(tmp_path, frames), tmp_path)


PERFECT = [
    _detection(1, CAR, [100, 100, 120, 80]),
    _detection(1, PERSON, [400, 100, 30, 90]),
    _detection(2, CAR, [100, 100, 120, 80]),
    _detection(2, PERSON, [400, 100, 30, 90]),
]


def test_perfect_detections_score_100(tmp_path: Path) -> None:
    """Every ground truth found exactly gives AP 1.0, overall and per class."""
    report = score(_two_image_set(tmp_path), PERFECT, min_images=1)
    assert report.overall.overall["ap"] == pytest.approx(1.0)
    assert report.overall.per_class_ap["car"] == pytest.approx(1.0)
    assert report.overall.per_class_ap["person"] == pytest.approx(1.0)
    assert math.isnan(report.overall.per_class_ap["bus"])  # no bus ground truth
    assert report.overall.ground_truth_boxes["car"] == 2


def test_missing_a_class_lowers_only_that_class(tmp_path: Path) -> None:
    """Dropping every person detection leaves car AP at 1 and person AP at 0."""
    detections = [d for d in PERFECT if d["category_id"] == CAR]
    report = score(_two_image_set(tmp_path), detections, min_images=1)
    assert report.overall.per_class_ap["car"] == pytest.approx(1.0)
    assert report.overall.per_class_ap["person"] == pytest.approx(0.0)
    assert report.overall.overall["ap"] == pytest.approx(0.5)


def test_no_detections_at_all_scores_zero(tmp_path: Path) -> None:
    """An empty detection list is AP 0 for classes that have ground truth."""
    report = score(_two_image_set(tmp_path), [], min_images=1)
    assert report.overall.overall["ap"] == 0.0
    assert report.overall.per_class_ap["car"] == 0.0
    assert math.isnan(report.overall.per_class_ap["truck"])


def test_conditions_are_scored_separately(tmp_path: Path) -> None:
    """Perfect on day, nothing on night: the breakdown separates them."""
    detections = [d for d in PERFECT if d["image_id"] == 1]
    report = score(_two_image_set(tmp_path), detections, min_images=1)
    assert report.by_condition["timeofday=daytime"].overall["ap"] == pytest.approx(1.0)
    assert report.by_condition["timeofday=night"].overall["ap"] == pytest.approx(0.0)
    # Half the ground truth found perfectly: COCO's 101 recall thresholds (0.00 .. 1.00) put 51
    # of them at or below recall 0.5, so AP is 51/101, not 0.5.
    assert report.overall.overall["ap"] == pytest.approx(51.0 / 101.0)


def test_small_condition_groups_are_not_scored(tmp_path: Path) -> None:
    """A condition with fewer than ``min_images`` images gets no (noisy) score."""
    report = score(_two_image_set(tmp_path), PERFECT, min_images=5)
    assert report.by_condition == {}


def test_a_detection_on_an_ignore_region_is_not_a_false_positive(tmp_path: Path) -> None:
    """A person detected on a rider (an ignore region) costs nothing; on empty road it does."""
    labels = [_bdd_label("person", 100, 100, 130, 190), _bdd_label("rider", 400, 100, 430, 190)]
    eval_set = load_bdd100k(
        _write_bdd(tmp_path, [_bdd_frame("a.jpg", "daytime", labels)]), tmp_path
    )
    found = _detection(1, PERSON, [100, 100, 30, 90])
    on_rider = _detection(1, PERSON, [400, 100, 30, 90], 0.95)
    on_road = _detection(1, PERSON, [800, 300, 30, 90], 0.95)
    with_rider = score(eval_set, [found, on_rider], min_images=1).overall.per_class_ap["person"]
    with_road = score(eval_set, [found, on_road], min_images=1).overall.per_class_ap["person"]
    assert with_rider == pytest.approx(1.0)
    assert with_road < 1.0


def test_scoring_does_not_modify_the_benchmark(tmp_path: Path) -> None:
    """The ground truth is copied before pycocotools annotates it."""
    eval_set = _two_image_set(tmp_path)
    before = json.dumps(eval_set.coco, sort_keys=True)
    score(eval_set, PERFECT, min_images=1)
    assert json.dumps(eval_set.coco, sort_keys=True) == before


def test_coco80_detections_are_remapped_to_our_ids() -> None:
    """A COCO-pretrained detector's person/car/bus/truck map over; other classes are dropped."""
    raw = [_detection(1, index, [0, 0, 10, 10]) for index in (0, 2, 5, 7, 16, 62)]
    assert [d["category_id"] for d in remap_coco80(raw)] == [PERSON, CAR, BUS, TRUCK]


def test_format_report_lists_every_subset(tmp_path: Path) -> None:
    """The text table has a row for the whole set and each scored condition."""
    text = format_report(score(_two_image_set(tmp_path), PERFECT, min_images=1))
    assert "all" in text and "timeofday=night" in text and "person" in text


def _write_dataset(root: Path) -> None:
    """A dataset with 10 scenarios of 2 frames each."""
    images, annotations = [], []
    for scenario in range(10):
        for view in range(2):
            image_id = scenario * 100 + view
            images.append(
                {
                    "id": image_id,
                    "scenario_id": f"live_{scenario:04d}",
                    "file_name": f"images/{image_id}.png",
                    "time_of_day": "night" if scenario % 5 == 0 else "day",
                    "weather": "clear",
                    "view": "ego",
                }
            )
            annotations.append({"id": image_id + 1, "image_id": image_id, "category_id": CAR})
    coco = {"images": images, "annotations": annotations, "categories": [{"id": CAR}]}
    (root / "annotations.json").write_text(json.dumps(coco), encoding="utf-8")


def test_split_never_puts_a_scenario_on_both_sides(tmp_path: Path) -> None:
    """Whole scenarios go to one side, each image to exactly one, sizes follow the fraction."""
    _write_dataset(tmp_path)
    summary = write_split(tmp_path, val_fraction=0.2, seed=3)
    train = json.loads((tmp_path / "train.json").read_text(encoding="utf-8"))
    val = json.loads((tmp_path / "val.json").read_text(encoding="utf-8"))
    train_scenarios = {i["scenario_id"] for i in train["images"]}
    val_scenarios = {i["scenario_id"] for i in val["images"]}
    assert not train_scenarios & val_scenarios
    assert len(train["images"]) + len(val["images"]) == 20
    assert len(val_scenarios) == 2 and len(train_scenarios) == 8
    assert summary["val"]["images"] == 4
    assert {a["image_id"] for a in val["annotations"]} == {i["id"] for i in val["images"]}


def test_split_is_deterministic_and_seed_dependent() -> None:
    """The same seed gives the same split; another seed a different one."""
    ids = [f"s{i}" for i in range(50)]
    assert split_scenarios(ids, 0.1, 1) == split_scenarios(ids, 0.1, 1)
    assert split_scenarios(ids, 0.1, 1) != split_scenarios(ids, 0.1, 2)
    train, val = split_scenarios(ids, 0.1, 1)
    assert len(val) == 5 and len(train) == 45 and not set(train) & set(val)


def test_split_rejects_bad_fractions_and_unlabelled_scenarios(tmp_path: Path) -> None:
    """A fraction outside (0, 1) and images without a scenario id are errors."""
    with pytest.raises(ValueError):
        split_scenarios(["a", "b"], 1.0, 0)
    (tmp_path / "annotations.json").write_text(
        json.dumps({"images": [{"id": 1}], "annotations": [], "categories": []}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="scenario_id"):
        write_split(tmp_path)
