"""Tests for the automatic dataset audit."""

import json
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image

from src.validation.dataset_audit import audit_dataset

CATEGORIES = [{"id": 1, "name": "person"}, {"id": 3, "name": "car"}]


def _annotation(
    annotation_id: int, image_id: int, bbox: List[float], category: int = 3
) -> Dict[str, Any]:
    """A minimal valid annotation."""
    return {
        "id": annotation_id,
        "image_id": image_id,
        "category_id": category,
        "bbox": bbox,
        "area": bbox[2] * bbox[3],
        "segmentation": [],
        "visibility_fraction": 1.0,
        "truncation": 0.0,
    }


def _write(root: Path, annotations: List[Dict[str, Any]], brightness: int = 120) -> None:
    """A one-image dataset (image 0, 200x100) with the given annotations."""
    (root / "images").mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (200, 100), (brightness,) * 3).save(root / "images" / "a.png")
    coco = {
        "images": [{"id": 0, "file_name": "images/a.png", "width": 200, "height": 100}],
        "annotations": annotations,
        "categories": CATEGORIES,
    }
    (root / "annotations.json").write_text(json.dumps(coco), encoding="utf-8")


def test_a_clean_dataset_has_no_errors(tmp_path: Path) -> None:
    """Valid labels on an image of normal brightness give no errors."""
    _write(tmp_path, [_annotation(1, 0, [10, 10, 40, 20]), _annotation(2, 0, [100, 30, 30, 60], 1)])
    report = audit_dataset(tmp_path)
    assert report.errors() == []
    assert report.class_counts == {"car": 1, "person": 1}


def test_boxes_outside_the_image_or_without_size_are_errors(tmp_path: Path) -> None:
    """A box past the edge, a zero-size box and an unknown class are all errors."""
    _write(
        tmp_path,
        [
            _annotation(1, 0, [180, 10, 40, 20]),
            _annotation(2, 0, [10, 10, 0, 20]),
            _annotation(3, 0, [10, 10, 20, 20], 99),
        ],
    )
    messages = " | ".join(f.message for f in audit_dataset(tmp_path).errors())
    assert "outside the image" in messages
    assert "non-positive" in messages
    assert "unknown category 99" in messages


def test_duplicate_ids_and_missing_images_are_errors(tmp_path: Path) -> None:
    """Two annotations with one id, and an image file that is gone."""
    _write(tmp_path, [_annotation(1, 0, [10, 10, 20, 20]), _annotation(1, 0, [50, 10, 20, 20])])
    (tmp_path / "images" / "a.png").unlink()
    messages = " | ".join(f.message for f in audit_dataset(tmp_path).errors())
    assert "duplicate annotation id" in messages
    assert "missing file" in messages


def test_a_polygon_outside_the_image_is_an_error(tmp_path: Path) -> None:
    """Segmentation points must lie inside the image."""
    annotation = _annotation(1, 0, [10, 10, 40, 20])
    annotation["segmentation"] = [[10, 10, 250, 10, 250, 30]]
    _write(tmp_path, [annotation])
    assert any("polygon" in f.message for f in audit_dataset(tmp_path).errors())


def test_dark_images_and_empty_images_are_warnings(tmp_path: Path) -> None:
    """An almost black frame with no labels is flagged twice, but is not an error."""
    _write(tmp_path, [], brightness=5)
    report = audit_dataset(tmp_path)
    assert report.errors() == []
    assert {f.message.split()[0] for f in report.warnings()} >= {"mean", "no"}


def test_an_oddly_shaped_box_is_flagged_within_its_class(tmp_path: Path) -> None:
    """Among many similar car boxes, one extremely thin box is flagged."""
    boxes = [_annotation(i, 0, [5 + 3 * i, 10, 30, 15]) for i in range(1, 11)]
    boxes.append(_annotation(11, 0, [150, 10, 2, 80]))
    _write(tmp_path, boxes)
    flagged = [f.annotation_id for f in audit_dataset(tmp_path).warnings() if f.annotation_id > 0]
    assert flagged == [11]
