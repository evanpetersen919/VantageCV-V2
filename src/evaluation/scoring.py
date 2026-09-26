"""Score detections against an ``EvalSet`` with the standard COCO evaluation.

This is pycocotools' ``COCOeval`` (bbox, IoU 0.50:0.95, 100 detections per image), the code
published detection numbers are computed with, so results are comparable with the literature.
Ignore regions are COCO ``iscrowd`` regions. On top of the overall AP, results are given per
class, per COCO size bucket (small < 32^2 px, medium < 96^2, large), and per image condition
(BDD100K's weather and time of day), which is what shows *where* synthetic training helps.
"""

import contextlib
import copy
import io
import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval

from src.evaluation import class_maps
from src.evaluation.loaders import EvalSet

STAT_NAMES = ("ap", "ap50", "ap75", "ap_small", "ap_medium", "ap_large")
ALL_AREAS, MAX_DETECTIONS = 0, 2  # indices into COCOeval's precision array
DEFAULT_CONDITIONS = ("timeofday", "weather")
UNDEFINED_VALUES = ("undefined", "")


@dataclass
class Scores:
    """The scores of one image subset. Undefined values (no ground truth) are NaN."""

    images: int
    overall: Dict[str, float]
    per_class_ap: Dict[str, float]
    per_class_ap50: Dict[str, float]
    ground_truth_boxes: Dict[str, int]


@dataclass
class ScoreReport:
    """Scores over the whole set, and over each condition subset large enough to score."""

    overall: Scores
    by_condition: Dict[str, Scores] = field(default_factory=dict)


def remap_coco80(detections: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detections from a COCO-pretrained detector (0-based COCO-80 class indices) in our ids.

    Predictions of any class we do not model are dropped.
    """
    remapped = []
    for detection in detections:
        category = class_maps.COCO80_INDEX_TO_OURS.get(detection["category_id"])
        if category is not None:
            remapped.append({**detection, "category_id": category})
    return remapped


def _nan_if_undefined(value: float) -> float:
    """COCOeval marks an undefined statistic as -1."""
    return float("nan") if value < 0 else float(value)


def _mean_precision(precision: np.ndarray) -> float:  # type: ignore[type-arg]
    """Mean of the defined entries of a precision slice, NaN if none are defined."""
    defined = precision[precision > -1]
    return float(defined.mean()) if defined.size else float("nan")


def _ground_truth_counts(gt: COCO, image_ids: Sequence[int]) -> Dict[str, int]:
    """Scored (non-ignore) ground-truth boxes per class over ``image_ids``."""
    counts = {name: 0 for name in class_maps.OUR_CLASSES.values()}
    wanted = set(image_ids)
    for annotation in gt.dataset["annotations"]:
        if annotation["image_id"] in wanted and not annotation["iscrowd"]:
            counts[class_maps.OUR_CLASSES[annotation["category_id"]]] += 1
    return counts


def _per_class_precision(
    evaluator: COCOeval,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Per-class AP (IoU 0.50:0.95) and AP50 from an evaluated ``COCOeval``."""
    precision = evaluator.eval["precision"]  # [IoU, recall, class, area, max detections]
    per_class, per_class_50 = {}, {}
    for index, category_id in enumerate(evaluator.params.catIds):
        name = class_maps.OUR_CLASSES[category_id]
        per_class[name] = _mean_precision(precision[:, :, index, ALL_AREAS, MAX_DETECTIONS])
        per_class_50[name] = _mean_precision(precision[0, :, index, ALL_AREAS, MAX_DETECTIONS])
    return per_class, per_class_50


def _score_subset(gt: COCO, detections: List[Dict[str, Any]], image_ids: Sequence[int]) -> Scores:
    """COCO evaluation restricted to ``image_ids``."""
    wanted = set(image_ids)
    kept = [
        d
        for d in detections
        if d["image_id"] in wanted and d["category_id"] in class_maps.OUR_CLASSES
    ]
    counts = _ground_truth_counts(gt, image_ids)
    names = list(class_maps.OUR_CLASSES.values())
    if not kept:
        zero = {name: (0.0 if counts[name] else float("nan")) for name in names}
        overall = {stat: (0.0 if any(counts.values()) else float("nan")) for stat in STAT_NAMES}
        return Scores(len(image_ids), overall, zero, dict(zero), counts)
    evaluator = COCOeval(gt, gt.loadRes(copy.deepcopy(kept)), "bbox")
    evaluator.params.imgIds = list(image_ids)
    with contextlib.redirect_stdout(io.StringIO()):
        evaluator.evaluate()
        evaluator.accumulate()
        evaluator.summarize()
    per_class, per_class_50 = _per_class_precision(evaluator)
    overall = {
        stat: _nan_if_undefined(evaluator.stats[position])
        for position, stat in enumerate(STAT_NAMES)
    }
    return Scores(len(image_ids), overall, per_class, per_class_50, counts)


def score(
    eval_set: EvalSet,
    detections: Sequence[Dict[str, Any]],
    conditions: Sequence[str] = DEFAULT_CONDITIONS,
    min_images: int = 20,
) -> ScoreReport:
    """Score ``detections`` (COCO result dicts in our class ids) on ``eval_set``.

    ``conditions`` are image attribute keys (BDD100K: ``timeofday``, ``weather``, ``scene``);
    each value with at least ``min_images`` images is scored separately as ``key=value``.
    """
    gt = COCO()
    gt.dataset = copy.deepcopy(eval_set.coco)
    with contextlib.redirect_stdout(io.StringIO()):
        gt.createIndex()
    all_ids = [image["id"] for image in eval_set.coco["images"]]
    listed = list(detections)
    report = ScoreReport(overall=_score_subset(gt, listed, all_ids))
    for key in conditions:
        groups: Dict[str, List[int]] = {}
        for image in eval_set.coco["images"]:
            value = image.get("attributes", {}).get(key)
            if value is not None and value not in UNDEFINED_VALUES:
                groups.setdefault(str(value), []).append(image["id"])
        for value, ids in sorted(groups.items()):
            if len(ids) >= min_images:
                report.by_condition[f"{key}={value}"] = _score_subset(gt, listed, ids)
    return report


def format_report(report: ScoreReport) -> str:
    """A plain-text table of the report."""

    def cell(value: float) -> str:
        return "  n/a" if math.isnan(value) else f"{100.0 * value:5.1f}"

    names = list(class_maps.OUR_CLASSES.values())
    header = "subset                     images   AP  AP50  " + "  ".join(f"{n:>6s}" for n in names)
    lines = [header]
    rows = [("all", report.overall)] + list(report.by_condition.items())
    for label, scores in rows:
        classes = "  ".join(f"{cell(scores.per_class_ap[n]):>6s}" for n in names)
        lines.append(
            f"{label:26s} {scores.images:6d} {cell(scores.overall['ap'])} "
            f"{cell(scores.overall['ap50'])}  {classes}"
        )
    return "\n".join(lines)
