"""Tests for the real-data control dataset builder, with tiny fake BDD100K zips."""

import importlib.util
import io
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest
from PIL import Image

from src.evaluation import class_maps
from src.evaluation.yolo_export import CLASS_ORDER, write_yolo_split

_SPEC = importlib.util.spec_from_file_location(
    "prepare_real_control", Path(__file__).resolve().parents[2] / "bin" / "prepare_real_control.py"
)
assert _SPEC is not None and _SPEC.loader is not None
control = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(control)


def _label(category: str, x1: float, y1: float, x2: float, y2: float) -> Dict[str, Any]:
    """One BDD100K object."""
    return {"category": category, "id": 0, "box2d": {"x1": x1, "y1": y1, "x2": x2, "y2": y2}}


def _zips(tmp_path: Path, count: int) -> Tuple[Path, Path, List[str]]:
    """Fake image and label zips holding ``count`` training and 3 validation entries."""
    names = [f"img{index:03d}" for index in range(count)]
    images_zip, labels_zip = tmp_path / "images.zip", tmp_path / "labels.zip"
    jpeg = io.BytesIO()
    Image.new("RGB", (1280, 720)).save(jpeg, "JPEG")
    with zipfile.ZipFile(images_zip, "w") as images, zipfile.ZipFile(labels_zip, "w") as labels:
        for split, split_names in (("train", names), ("val", ["v0", "v1", "v2"])):
            for name in split_names:
                images.writestr(f"100k/{split}/{name}.jpg", jpeg.getvalue())
                objects = [
                    _label("car", 100, 100, 220, 180),
                    _label("rider", 400, 100, 440, 200),
                    _label("traffic sign", 10, 10, 30, 30),
                ]
                entry = {
                    "name": name,
                    "attributes": {"weather": "clear"},
                    "frames": [{"objects": objects}],
                }
                labels.writestr(f"100k/{split}/{name}.json", json.dumps(entry))
    return images_zip, labels_zip, names


def test_control_samples_only_training_images_and_is_deterministic(tmp_path: Path) -> None:
    """Train and validation both come from BDD's training split; the seed fixes the draw."""
    images_zip, labels_zip, names = _zips(tmp_path, 12)
    first = control.build_control(images_zip, labels_zip, tmp_path / "a", 6, 2, 0)
    again = control.build_control(images_zip, labels_zip, tmp_path / "b", 6, 2, 0)
    other = control.build_control(images_zip, labels_zip, tmp_path / "c", 6, 2, 1)
    assert first == again == {"train": {"images": 6, "boxes": 6}, "val": {"images": 2, "boxes": 2}}
    chosen = json.loads((tmp_path / "a" / "split.json").read_text(encoding="utf-8"))
    assert set(chosen["train"]) | set(chosen["val"]) <= set(names)  # never a val-split name
    assert not set(chosen["train"]) & set(chosen["val"])
    other_split = json.loads((tmp_path / "c" / "split.json").read_text(encoding="utf-8"))
    assert other_split["train"] != chosen["train"] and other == first


def test_control_labels_use_our_classes_and_leave_riders_and_signs_out(tmp_path: Path) -> None:
    """Each image has exactly one label line, the car, as class index 1; a rider is not a label."""
    images_zip, labels_zip, _ = _zips(tmp_path, 4)
    control.build_control(images_zip, labels_zip, tmp_path / "out", 3, 1, 0)
    label_files = sorted((tmp_path / "out" / "labels").rglob("*.txt"))
    assert len(label_files) == 4
    for path in label_files:
        (line,) = path.read_text(encoding="utf-8").splitlines()
        assert line.split()[0] == str(CLASS_ORDER.index(class_maps.CAR))
    listed = (tmp_path / "out" / "train.txt").read_text(encoding="utf-8").splitlines()
    assert len(listed) == 3 and all(Path(p).exists() for p in listed)
    assert "  1: car" in (tmp_path / "out" / "data.yaml").read_text(encoding="utf-8")


def test_write_yolo_split_skips_ignore_regions(tmp_path: Path) -> None:
    """Ignore regions (iscrowd 1) are not labels."""
    (tmp_path / "images").mkdir()
    coco = {
        "images": [{"id": 1, "file_name": "images/a.jpg", "width": 100, "height": 100}],
        "annotations": [
            {"id": 1, "image_id": 1, "category_id": 3, "bbox": [10, 10, 20, 20], "iscrowd": 0},
            {"id": 2, "image_id": 1, "category_id": 1, "bbox": [50, 10, 20, 20], "iscrowd": 1},
        ],
    }
    assert write_yolo_split(tmp_path, "train", coco) == (1, 1)


def test_missing_zip_member_is_an_error(tmp_path: Path) -> None:
    """Asking for more images than the zip holds fails loudly instead of returning fewer."""
    images_zip, labels_zip, _ = _zips(tmp_path, 3)
    with pytest.raises((KeyError, ValueError, IndexError)):
        control.build_control(images_zip, labels_zip, tmp_path / "out", 5, 1, 0)
