"""Tests for the rider and bike label audit (``bin/audit_cyclist_labels.py``)."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pycocotools.mask as mask_utils

SPEC = importlib.util.spec_from_file_location(
    "audit_cyclist_labels", Path(__file__).resolve().parents[2] / "bin" / "audit_cyclist_labels.py"
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)  # type: ignore[union-attr]

WIDTH, HEIGHT = 200, 120


def _annotation(ann_id: int, category: int, box, tight: bool = True, visibility: float = 0.9):
    """An annotation whose mask fills ``box`` (x, y, w, h), the box optionally enlarged."""
    mask = np.zeros((HEIGHT, WIDTH), dtype=np.uint8, order="F")
    x, y, w, h = box
    mask[y : y + h, x : x + w] = 1
    rle = mask_utils.encode(mask)
    rle["counts"] = rle["counts"].decode("ascii")
    listed = [float(v) for v in box] if tight else [float(x), float(y), float(w + 6), float(h)]
    return {
        "id": ann_id,
        "image_id": 0,
        "category_id": category,
        "bbox": listed,
        "visibility_fraction": visibility,
        "mask_rle": rle,
    }


def _dataset(tmp_path: Path, annotations) -> Path:
    data = {"images": [{"id": 0, "width": WIDTH, "height": HEIGHT}], "annotations": annotations}
    (tmp_path / "annotations.json").write_text(json.dumps(data), encoding="utf-8")
    return tmp_path


def test_a_clean_rider_with_a_bike_passes(tmp_path: Path) -> None:
    """A rider and an overlapping bike with tight masks are two clean, paired labels."""
    path = _dataset(
        tmp_path,
        [_annotation(1, 10, (50, 20, 20, 50)), _annotation(2, 2, (48, 55, 24, 30))],
    )
    result = audit.audit(path)
    assert result["passed"] is True
    counts = result["counts"]
    assert counts["riders"] == 1 and counts["bikes"] == 1 and counts["bikes_ridden"] == 1
    assert counts["riders_without_bike"] == 0 and counts["bikes_unridden"] == 0


def test_a_box_that_is_not_the_masks_tight_box_is_a_hard_defect(tmp_path: Path) -> None:
    """A box 6 px wider than its mask fails the audit."""
    result = audit.audit(_dataset(tmp_path, [_annotation(1, 10, (50, 20, 20, 50), tight=False)]))
    assert result["counts"]["box_not_tight_mask"] == 1 and result["passed"] is False


def test_unridden_bikes_and_hidden_bikes_are_counted_not_failed(tmp_path: Path) -> None:
    """A far bike is unridden and a rider with no bike is counted; neither is a defect."""
    path = _dataset(
        tmp_path,
        [
            _annotation(1, 10, (10, 10, 20, 50)),
            _annotation(2, 2, (150, 60, 30, 30)),
        ],
    )
    result = audit.audit(path)
    assert result["counts"]["bikes_unridden"] == 1 and result["counts"]["riders_without_bike"] == 1
    assert result["passed"] is True


def test_bad_visibility_is_a_hard_defect(tmp_path: Path) -> None:
    """A visible fraction of zero (or above one) fails."""
    result = audit.audit(_dataset(tmp_path, [_annotation(1, 10, (50, 20, 20, 50), visibility=0.0)]))
    assert result["counts"]["bad_visibility"] == 1 and result["passed"] is False
