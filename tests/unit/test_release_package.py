"""The release folder: layout, relative lists, YOLO segmentation lines, validation of damage."""

# pylint: disable=missing-function-docstring

import json
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pytest
from PIL import Image

from src.export.release_package import build_package, validate_package, yolo_segment_lines

WIDTH, HEIGHT = 64, 48


def _annotation(annotation_id: int, image_id: int) -> Dict[str, Any]:
    square = [10.0, 10.0, 30.0, 10.0, 30.0, 30.0, 10.0, 30.0]
    second = [40.0, 5.0, 50.0, 5.0, 50.0, 15.0]
    return {
        "id": annotation_id,
        "image_id": image_id,
        "category_id": 3,
        "bbox": [10.0, 10.0, 20.0, 20.0],
        "segmentation": [square, second],
    }


def _make_source(root: Path) -> Path:
    for folder in ("images", "semantic", "depth"):
        (root / folder).mkdir(parents=True)
    for name, image_id in (("a", 1), ("b", 2)):
        Image.fromarray(np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)).save(
            root / "images" / f"{name}.png"
        )
        Image.fromarray(np.full((HEIGHT, WIDTH), 7, dtype=np.uint8), mode="L").save(
            root / "semantic" / f"{name}.png"
        )
        Image.fromarray(np.full((HEIGHT, WIDTH), 256, dtype=np.uint16)).save(
            root / "depth" / f"{name}.png"
        )
    for split, name, image_id in (("train", "a", 1), ("val", "b", 2)):
        coco = {
            "images": [
                {
                    "id": image_id,
                    "file_name": f"images/{name}.png",
                    "semantic_file": f"semantic/{name}.png",
                    "depth_file": f"depth/{name}.png",
                    "width": WIDTH,
                    "height": HEIGHT,
                }
            ],
            "annotations": [_annotation(image_id * 10, image_id)],
            "categories": [{"id": 3, "name": "car"}],
        }
        (root / f"{split}.json").write_text(json.dumps(coco), encoding="utf-8")
    return root


def test_segment_lines_are_normalised_one_per_part() -> None:
    image = {"width": WIDTH, "height": HEIGHT}
    lines = yolo_segment_lines(image, [_annotation(1, 1)], (1, 3, 6, 8))
    assert len(lines) == 2 and lines[0].startswith("1 ")
    values = [float(v) for v in lines[0].split()[1:]]
    assert len(values) == 8 and all(0.0 <= v <= 1.0 for v in values)
    assert values[0] == pytest.approx(10.0 / WIDTH, abs=1e-6)
    assert values[1] == pytest.approx(10.0 / HEIGHT, abs=1e-6)


def test_package_layout_relative_lists_and_clean_validation(tmp_path: Path) -> None:
    source = _make_source(tmp_path / "source")
    out = tmp_path / "release"
    manifest = build_package(source, out, link=False)
    assert manifest["counts"] == {
        "train": {"images": 1, "annotations": 1},
        "val": {"images": 1, "annotations": 1},
    }
    for path in (
        "images/a.png",
        "semantic/a.png",
        "depth/b.png",
        "annotations/instances_train.json",
        "labels/a.txt",
        "labels_seg/a.txt",
        "classes.json",
    ):
        assert (out / path).exists(), path
    assert (out / "train.txt").read_text(encoding="utf-8").split() == ["./images/a.png"]
    assert "path:" not in (out / "data.yaml").read_text(encoding="utf-8")
    assert len((out / "labels_seg" / "a.txt").read_text(encoding="utf-8").splitlines()) == 2
    classes = json.loads((out / "classes.json").read_text(encoding="utf-8"))
    assert classes["depth"]["scale"] == 256 and {c["id"] for c in classes["semantic_classes"]} >= {
        7,
        23,
        24,
    }
    assert not validate_package(out)


def test_validation_reports_missing_files_unknown_ids_and_unlabeled_pixels(tmp_path: Path) -> None:
    source = _make_source(tmp_path / "source")
    out = tmp_path / "release"
    build_package(source, out, link=False)
    (out / "depth" / "a.png").unlink()
    Image.fromarray(np.full((HEIGHT, WIDTH), 99, dtype=np.uint8), mode="L").save(
        out / "semantic" / "b.png"
    )
    Image.fromarray(np.zeros((HEIGHT, WIDTH), dtype=np.uint8), mode="L").save(
        out / "semantic" / "a.png"
    )
    problems = "\n".join(validate_package(out))
    assert "missing depth_file" in problems
    assert "unknown class ids [99]" in problems
    assert "unlabeled pixels" in problems
