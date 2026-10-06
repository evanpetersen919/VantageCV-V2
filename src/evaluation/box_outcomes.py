"""What happens to each real truck and bus box: found, mislabelled, found only at low confidence,
missed.

AP summarises a detector in one number. This asks the question underneath it for chosen classes:
for every ground-truth box of that class, taking the detections above a confidence threshold, did
the detector

* ``correct``: report a box of the right class that overlaps it (IoU >= ``iou_threshold``);
* ``wrong_class``: report overlapping boxes, the best-scoring of which has another class (recorded
  as ``confused_as``: car, bus, truck, person);
* ``low_confidence``: report nothing above the threshold, but a right-class box overlapping it
  exists below the threshold (the detector found it and was not sure);
* ``missed``: report nothing that overlaps it at all.

Boxes are bucketed by COCO's area sizes (small below 32 x 32, medium below 96 x 96, large above).
Each ground-truth box is judged on its own (no one-to-one assignment), so one detection can serve
two neighbouring boxes; that is the usual simplification for a diagnostic and does not change the
picture. Ignore regions (``iscrowd``) are skipped.
"""

from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.evaluation.class_maps import OUR_CLASSES

SIZE_EDGES: Tuple[Tuple[str, float], ...] = (("small", 32.0**2), ("medium", 96.0**2))
OUTCOMES = ("correct", "wrong_class", "low_confidence", "missed")


def size_bin(area: float) -> str:
    """COCO's size bucket of a box of ``area`` square pixels."""
    for name, limit in SIZE_EDGES:
        if area < limit:
            return name
    return "large"


def iou_xywh(first: Sequence[float], second: Sequence[float]) -> float:
    """Intersection over union of two boxes given as x, y, width, height."""
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right = min(first[0] + first[2], second[0] + second[2])
    bottom = min(first[1] + first[3], second[1] + second[3])
    inter = max(0.0, right - left) * max(0.0, bottom - top)
    union = first[2] * first[3] + second[2] * second[3] - inter
    return inter / union if union > 0.0 else 0.0


def judge_box(  # pylint: disable=too-many-arguments
    box: Sequence[float],
    category: int,
    detections: Iterable[Dict[str, Any]],
    confidence: float,
    iou_threshold: float,
    floor: float,
) -> Tuple[str, int]:
    """(outcome, confused_as) of one ground-truth box; ``confused_as`` is 0 unless wrong_class."""
    best_score, best_category = -1.0, 0
    low_right_class = False
    for detection in detections:
        score = detection["score"]
        if score < floor or iou_xywh(box, detection["bbox"]) < iou_threshold:
            continue
        if score >= confidence:
            if score > best_score:
                best_score, best_category = score, detection["category_id"]
        elif detection["category_id"] == category:
            low_right_class = True
    if best_score >= 0.0:
        return ("correct", 0) if best_category == category else ("wrong_class", best_category)
    return ("low_confidence", 0) if low_right_class else ("missed", 0)


def box_outcomes(  # pylint: disable=too-many-arguments
    annotations: Iterable[Dict[str, Any]],
    detections: Iterable[Dict[str, Any]],
    targets: Sequence[int],
    confidence: float = 0.25,
    iou_threshold: float = 0.5,
    floor: float = 0.001,
) -> List[Dict[str, Any]]:
    """One record per scored ground-truth box of the ``targets`` classes (COCO category ids)."""
    by_image: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for detection in detections:
        by_image[detection["image_id"]].append(detection)
    records = []
    for annotation in annotations:
        if annotation.get("iscrowd") or annotation["category_id"] not in targets:
            continue
        outcome, confused_as = judge_box(
            annotation["bbox"],
            annotation["category_id"],
            by_image.get(annotation["image_id"], ()),
            confidence,
            iou_threshold,
            floor,
        )
        records.append(
            {
                "image_id": annotation["image_id"],
                "category_id": annotation["category_id"],
                "size": size_bin(annotation["bbox"][2] * annotation["bbox"][3]),
                "outcome": outcome,
                "confused_as": confused_as,
            }
        )
    return records


def _tally(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Boxes per outcome, and which classes the wrong_class ones were called."""
    counts = Counter(r["outcome"] for r in rows)
    confused = Counter(OUR_CLASSES.get(r["confused_as"], "other") for r in rows if r["confused_as"])
    return {
        "boxes": len(rows),
        **{o: counts.get(o, 0) for o in OUTCOMES},
        "confused_as": dict(confused),
    }


def summarise(
    records: Sequence[Dict[str, Any]], image_conditions: Optional[Dict[int, str]] = None
) -> Dict[str, Any]:
    """Counts per class: overall, by size, and by condition when ``image_conditions`` is given."""
    summary: Dict[str, Any] = {}
    for category, name in OUR_CLASSES.items():
        mine = [r for r in records if r["category_id"] == category]
        if not mine:
            continue
        entry: Dict[str, Any] = {"all": _tally(mine)}
        for size in ("small", "medium", "large"):
            entry[size] = _tally([r for r in mine if r["size"] == size])
        for condition in sorted(set((image_conditions or {}).values())):
            entry[condition] = _tally(
                [r for r in mine if (image_conditions or {}).get(r["image_id"]) == condition]
            )
        summary[name] = entry
    return summary
