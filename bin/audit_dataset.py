"""Audit a finished live dataset: hard label checks, statistics and flagged crops.

    PYTHONPATH=. python bin/audit_dataset.py live_dataset/audit50

Prints the class balance, conditions, size and count distributions and every finding,
writes ``audit_report.json`` next to the dataset, and saves ``flagged.png``: crops from
the QA overlays of the annotations flagged as unusual, for a quick look.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image

from src.validation.dataset_audit import AuditReport, audit_dataset

SHEET_COLUMNS = 6
SHEET_CELL = 240
CROP_PAD = 0.3
MAX_CROPS = 24


def _print(report: AuditReport) -> None:
    """The report as text."""
    print(f"{report.images} images, {report.annotations} annotations")
    print("classes:", report.class_counts)
    for key, counts in report.condition_counts.items():
        print(f"{key}:", counts)
    low, median, high = report.box_height_percentiles
    print(f"box height px p10 {low:.0f}  median {median:.0f}  p90 {high:.0f}")
    smallest, typical, largest = report.annotations_per_image
    print(f"annotations per image: min {smallest:.0f}  median {typical:.0f}  max {largest:.0f}")
    print(f"{len(report.errors())} errors, {len(report.warnings())} warnings")
    for finding in report.findings:
        print(
            f"  {finding.severity:7s} image {finding.image_id} annotation {finding.annotation_id}: "
            f"{finding.message}"
        )


def _flagged_sheet(root: Path, report: AuditReport) -> None:  # pylint: disable=too-many-locals
    """Crops of the flagged annotations from their QA overlays."""
    coco = json.loads((root / "annotations.json").read_text(encoding="utf-8"))
    by_id: Dict[int, Dict[str, Any]] = {a["id"]: a for a in coco["annotations"]}
    files = {image["id"]: image["file_name"] for image in coco["images"]}
    crops: List[Image.Image] = []
    for finding in report.findings:
        annotation = by_id.get(finding.annotation_id)
        if annotation is None or len(crops) >= MAX_CROPS:
            continue
        qa = root / "qa" / Path(files[finding.image_id]).name
        if not qa.exists():
            continue
        x, y, width, height = annotation["bbox"]
        pad_x, pad_y = width * CROP_PAD + 20, height * CROP_PAD + 20
        with Image.open(qa) as picture:
            crop = picture.convert("RGB").crop(
                (int(x - pad_x), int(y - pad_y), int(x + width + pad_x), int(y + height + pad_y))
            )
        crops.append(crop.resize((SHEET_CELL, SHEET_CELL)))
    if not crops:
        return
    rows = (len(crops) + SHEET_COLUMNS - 1) // SHEET_COLUMNS
    sheet = Image.new("RGB", (SHEET_COLUMNS * SHEET_CELL, rows * SHEET_CELL))
    for index, crop in enumerate(crops):
        sheet.paste(
            crop, ((index % SHEET_COLUMNS) * SHEET_CELL, (index // SHEET_COLUMNS) * SHEET_CELL)
        )
    sheet.save(root / "flagged.png")
    print(f"wrote {root / 'flagged.png'} ({len(crops)} crops)")


def main() -> None:
    """Parse arguments, audit, report."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("root", type=Path)
    root = parser.parse_args().root
    report = audit_dataset(root)
    _print(report)
    (root / "audit_report.json").write_text(
        json.dumps(
            {
                "images": report.images,
                "annotations": report.annotations,
                "classes": report.class_counts,
                "conditions": report.condition_counts,
                "findings": [vars(finding) for finding in report.findings],
            }
        ),
        encoding="utf-8",
    )
    _flagged_sheet(root, report)


if __name__ == "__main__":
    main()
