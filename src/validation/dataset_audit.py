"""Automatic checks over a finished live dataset (its COCO file and images).

Hard checks (errors) find labels that are simply invalid: a box outside its image,
a non-positive size, a duplicate id, an unknown class, a missing or wrongly sized image,
a polygon outside the image. Statistical checks (warnings) flag things worth a look:
images with no annotations, abnormal brightness, per-class box shapes far outside the
rest of that class, and annotation counts far from the dataset's typical frame.
"""

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import numpy as np
from PIL import Image

MIN_MEAN_LUMINANCE = 20.0
MAX_MEAN_LUMINANCE = 235.0
IQR_FENCE = 3.0
COUNT_SIGMA = 3.0


@dataclass
class Finding:
    """One problem: which image or annotation, and why."""

    severity: str
    image_id: int
    annotation_id: int
    message: str


@dataclass
class AuditReport:
    """Everything the audit found and measured."""

    findings: List[Finding] = field(default_factory=list)
    images: int = 0
    annotations: int = 0
    class_counts: Dict[str, int] = field(default_factory=dict)
    condition_counts: Dict[str, Dict[str, int]] = field(default_factory=dict)
    box_height_percentiles: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    annotations_per_image: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    def errors(self) -> List[Finding]:
        """The hard failures."""
        return [finding for finding in self.findings if finding.severity == "error"]

    def warnings(self) -> List[Finding]:
        """The things worth a look."""
        return [finding for finding in self.findings if finding.severity == "warning"]


def _check_annotation(
    annotation: Dict[str, Any], image: Dict[str, Any], valid_categories: Set[int]
) -> List[str]:
    """Reasons ``annotation`` is invalid for its image (empty if it is fine)."""
    problems = []
    x, y, width, height = annotation["bbox"]
    if width <= 0 or height <= 0:
        problems.append(f"non-positive box size {width:.1f}x{height:.1f}")
    if (
        x < -1e-6
        or y < -1e-6
        or x + width > image["width"] + 1e-6
        or y + height > image["height"] + 1e-6
    ):
        problems.append("box outside the image")
    if annotation["category_id"] not in valid_categories:
        problems.append(f"unknown category {annotation['category_id']}")
    if not 0.0 <= annotation.get("visibility_fraction", 1.0) <= 1.0:
        problems.append("visibility_fraction outside [0, 1]")
    if not 0.0 <= annotation.get("truncation", 0.0) <= 1.0:
        problems.append("truncation outside [0, 1]")
    for polygon in annotation.get("segmentation", []):
        points = np.array(polygon).reshape(-1, 2)
        if (
            points[:, 0].min() < -1e-6
            or points[:, 1].min() < -1e-6
            or points[:, 0].max() > image["width"] + 1e-6
            or points[:, 1].max() > image["height"] + 1e-6
        ):
            problems.append("segmentation polygon outside the image")
    return problems


def _iqr_outliers(values: np.ndarray) -> np.ndarray:  # type: ignore[type-arg]
    """Boolean mask of values beyond ``IQR_FENCE`` interquartile ranges of the quartiles."""
    if len(values) < 8:
        return np.zeros(len(values), dtype=bool)
    low, high = np.percentile(values, [25, 75])
    spread = high - low
    return np.asarray((values < low - IQR_FENCE * spread) | (values > high + IQR_FENCE * spread))


def audit_dataset(root: Path) -> AuditReport:  # pylint: disable=too-many-locals
    """Audit ``root/annotations.json`` and the images beside it."""
    coco = json.loads((root / "annotations.json").read_text(encoding="utf-8"))
    report = AuditReport(images=len(coco["images"]), annotations=len(coco["annotations"]))
    categories = {category["id"]: category["name"] for category in coco["categories"]}
    images = {image["id"]: image for image in coco["images"]}

    _check_ids(coco, report)
    counts: Counter = Counter()  # type: ignore[type-arg]
    for annotation in coco["annotations"]:
        image = images.get(annotation["image_id"])
        if image is None:
            report.findings.append(
                Finding(
                    "error",
                    annotation["image_id"],
                    annotation["id"],
                    "annotation of a missing image",
                )
            )
            continue
        counts[annotation["image_id"]] += 1
        for problem in _check_annotation(annotation, image, set(categories)):
            report.findings.append(Finding("error", image["id"], annotation["id"], problem))
    _check_images(root, coco, counts, report)
    _statistics(coco, categories, counts, report)
    return report


def _check_ids(coco: Dict[str, Any], report: AuditReport) -> None:
    """Annotation and image ids must be unique."""
    for name, items in (("annotation", coco["annotations"]), ("image", coco["images"])):
        ids = [item["id"] for item in items]
        for duplicate in sorted({i for i in ids if ids.count(i) > 1}):
            report.findings.append(Finding("error", -1, duplicate, f"duplicate {name} id"))


def _check_images(
    root: Path, coco: Dict[str, Any], counts: "Counter[int]", report: AuditReport
) -> None:
    """Every image exists with the recorded size, is not too dark or bright, and has labels."""
    for image in coco["images"]:
        path = root / image["file_name"]
        if not path.exists():
            report.findings.append(Finding("error", image["id"], -1, f"missing file {path.name}"))
            continue
        with Image.open(path) as picture:
            if picture.size != (image["width"], image["height"]):
                report.findings.append(
                    Finding(
                        "error",
                        image["id"],
                        -1,
                        f"image is {picture.size}, recorded as "
                        f"{(image['width'], image['height'])}",
                    )
                )
            luminance = float(np.asarray(picture.convert("L"), dtype=float).mean())
        if not MIN_MEAN_LUMINANCE <= luminance <= MAX_MEAN_LUMINANCE:
            report.findings.append(
                Finding("warning", image["id"], -1, f"mean luminance {luminance:.0f}")
            )
        if counts[image["id"]] == 0:
            report.findings.append(Finding("warning", image["id"], -1, "no annotations"))


def _statistics(  # pylint: disable=too-many-locals
    coco: Dict[str, Any], categories: Dict[int, str], counts: "Counter[int]", report: AuditReport
) -> None:
    """Class balance, conditions, size and count distributions, and their outliers."""
    report.class_counts = dict(
        Counter(categories.get(a["category_id"], "?") for a in coco["annotations"])
    )
    for key in ("time_of_day", "weather", "season", "view"):
        report.condition_counts[key] = dict(
            Counter(image.get(key, "?") for image in coco["images"])
        )
    heights = np.array([a["bbox"][3] for a in coco["annotations"]])
    if len(heights):
        low, median, high = (float(v) for v in np.percentile(heights, [10, 50, 90]))
        report.box_height_percentiles = (low, median, high)
    per_image = np.array([counts[image["id"]] for image in coco["images"]], dtype=float)
    if len(per_image):
        report.annotations_per_image = (
            float(per_image.min()),
            float(np.median(per_image)),
            float(per_image.max()),
        )
        spread = per_image.std()
        for image, count in zip(coco["images"], per_image):
            if spread > 0 and abs(count - per_image.mean()) > COUNT_SIGMA * spread:
                report.findings.append(
                    Finding(
                        "warning", image["id"], -1, f"{int(count)} annotations, far from typical"
                    )
                )
    for category_id, name in categories.items():
        group = [a for a in coco["annotations"] if a["category_id"] == category_id]
        if not group:
            continue
        boxes = np.array([a["bbox"] for a in group], dtype=float)
        aspect = np.log(np.maximum(boxes[:, 2], 1e-6) / np.maximum(boxes[:, 3], 1e-6))
        for annotation, outlier in zip(group, _iqr_outliers(aspect)):
            if outlier:
                width, height = annotation["bbox"][2], annotation["bbox"][3]
                report.findings.append(
                    Finding(
                        "warning",
                        annotation["image_id"],
                        annotation["id"],
                        f"{name} box {width:.0f}x{height:.0f} px has an unusual shape",
                    )
                )
