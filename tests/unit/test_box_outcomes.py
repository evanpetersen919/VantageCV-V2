# pylint: disable=missing-function-docstring
"""The per-box outcome rules: found, mislabelled, found only at low confidence, missed."""

from src.evaluation.box_outcomes import box_outcomes, iou_xywh, size_bin, summarise
from src.evaluation.class_maps import BUS, CAR, TRUCK


def _truck(x: float = 100.0, image: int = 1) -> dict:
    return {"image_id": image, "category_id": TRUCK, "bbox": [x, 100.0, 100.0, 100.0], "iscrowd": 0}


def _detection(category: int, score: float, x: float = 100.0, image: int = 1) -> dict:
    return {
        "image_id": image,
        "category_id": category,
        "bbox": [x, 100.0, 100.0, 100.0],
        "score": score,
    }


def _outcome(detections: list, confidence: float = 0.25) -> str:
    return box_outcomes([_truck()], detections, [TRUCK], confidence)[0]["outcome"]


def test_iou_and_size_bins() -> None:
    assert iou_xywh([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    assert iou_xywh([0, 0, 10, 10], [20, 20, 10, 10]) == 0.0
    assert abs(iou_xywh([0, 0, 10, 10], [5, 0, 10, 10]) - 1 / 3) < 1e-9
    assert [size_bin(a) for a in (31.0**2, 32.0**2, 95.0**2, 96.0**2)] == [
        "small",
        "medium",
        "medium",
        "large",
    ]


def test_a_confident_right_class_box_is_correct() -> None:
    assert _outcome([_detection(TRUCK, 0.9)]) == "correct"


def test_the_best_scoring_overlapping_box_decides_the_class() -> None:
    """A truck found at 0.5 and also called a car at 0.9: the detector's answer is car."""
    record = box_outcomes([_truck()], [_detection(TRUCK, 0.5), _detection(CAR, 0.9)], [TRUCK])[0]
    assert (record["outcome"], record["confused_as"]) == ("wrong_class", CAR)


def test_right_class_only_below_the_threshold_is_low_confidence() -> None:
    assert _outcome([_detection(TRUCK, 0.1)]) == "low_confidence"
    assert _outcome([_detection(TRUCK, 0.1)], confidence=0.05) == "correct"


def test_wrong_class_below_the_threshold_or_far_away_is_a_miss() -> None:
    assert (
        _outcome([_detection(CAR, 0.1)]) == "missed"
    )  # nothing confident, and not the right class
    assert _outcome([_detection(TRUCK, 0.9, x=500.0)]) == "missed"  # does not overlap
    assert _outcome([_detection(TRUCK, 0.0005)]) == "missed"  # under the floor
    assert _outcome([]) == "missed"


def test_other_classes_ignore_regions_and_other_images_are_skipped() -> None:
    annotations = [
        {"image_id": 1, "category_id": CAR, "bbox": [0, 0, 50, 50], "iscrowd": 0},
        {"image_id": 1, "category_id": TRUCK, "bbox": [0, 0, 50, 50], "iscrowd": 1},
        _truck(image=2),
    ]
    records = box_outcomes(annotations, [_detection(TRUCK, 0.9, image=1)], [TRUCK])
    assert len(records) == 1 and records[0]["image_id"] == 2 and records[0]["outcome"] == "missed"


def test_summary_counts_by_class_size_and_condition() -> None:
    annotations = [
        {"image_id": 1, "category_id": BUS, "bbox": [0, 0, 20, 20], "iscrowd": 0},
        {"image_id": 2, "category_id": BUS, "bbox": [0, 0, 120, 120], "iscrowd": 0},
    ]
    detections = [
        {"image_id": 1, "category_id": TRUCK, "bbox": [0, 0, 20, 20], "score": 0.8},
        {"image_id": 2, "category_id": BUS, "bbox": [0, 0, 120, 120], "score": 0.8},
    ]
    summary = summarise(box_outcomes(annotations, detections, [BUS]), {1: "night", 2: "daytime"})
    assert summary["bus"]["all"]["boxes"] == 2
    assert summary["bus"]["small"]["wrong_class"] == 1 and summary["bus"]["small"][
        "confused_as"
    ] == {"truck": 1}
    assert summary["bus"]["large"]["correct"] == 1
    assert summary["bus"]["night"]["wrong_class"] == 1 and summary["bus"]["daytime"]["correct"] == 1
