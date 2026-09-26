"""Tests for the YOLO dataset export and the detector-output conversion."""

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.evaluation import class_maps
from src.evaluation.detections import boxes_to_detections
from src.evaluation.yolo_export import CLASS_ORDER, label_path_for, write_yolo_dataset

PERSON, CAR, BUS, TRUCK = class_maps.PERSON, class_maps.CAR, class_maps.BUS, class_maps.TRUCK


def _image(image_id: int, name: str) -> Dict[str, Any]:
    """A 1920x1080 image entry."""
    return {"id": image_id, "file_name": f"images/{name}.png", "width": 1920, "height": 1080}


def _annotation(image_id: int, category: int, bbox: List[float]) -> Dict[str, Any]:
    """A minimal COCO annotation."""
    return {"id": 1, "image_id": image_id, "category_id": category, "bbox": bbox}


def _write(
    root: Path, side: str, images: List[Dict[str, Any]], annotations: List[Dict[str, Any]]
) -> None:
    """One split side as COCO JSON."""
    coco = {"images": images, "annotations": annotations, "categories": []}
    (root / f"{side}.json").write_text(json.dumps(coco), encoding="utf-8")


def test_class_order_is_the_exported_coco_ids() -> None:
    """YOLO indices 0..3 are person, car, bus, truck."""
    assert CLASS_ORDER == (PERSON, CAR, BUS, TRUCK)


def test_label_path_replaces_the_last_images_folder(tmp_path: Path) -> None:
    """Ultralytics' rule: the last ``images`` folder becomes ``labels`` and the suffix ``.txt``."""
    path = tmp_path / "images" / "run" / "images" / "a.png"
    assert label_path_for(path) == tmp_path / "images" / "run" / "labels" / "a.txt"
    with pytest.raises(ValueError):
        label_path_for(tmp_path / "pictures" / "a.png")


def test_export_writes_normalised_labels_lists_and_yaml(tmp_path: Path) -> None:
    """A car at known pixels becomes the expected normalised line; empty images get empty files."""
    (tmp_path / "images").mkdir()
    _write(
        tmp_path,
        "train",
        [_image(1, "a"), _image(2, "b")],
        [_annotation(1, CAR, [960, 540, 192, 108]), _annotation(1, TRUCK, [0, 0, 1920, 1080])],
    )
    _write(tmp_path, "val", [_image(3, "c")], [_annotation(3, PERSON, [100, 100, 20, 60])])
    counts = write_yolo_dataset(tmp_path)
    assert counts == {"train": {"images": 2, "boxes": 2}, "val": {"images": 1, "boxes": 1}}
    lines = (tmp_path / "labels" / "a.txt").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "1 0.550000 0.550000 0.100000 0.100000"  # car -> index 1
    assert lines[1] == "3 0.500000 0.500000 1.000000 1.000000"  # truck -> index 3
    assert (tmp_path / "labels" / "b.txt").read_text(encoding="utf-8") == ""
    train_list = (tmp_path / "train.txt").read_text(encoding="utf-8").splitlines()
    assert train_list == [str((tmp_path / "images" / n).resolve()) + ".png" for n in ("a", "b")]
    yaml = (tmp_path / "data.yaml").read_text(encoding="utf-8")
    assert "train: train.txt" in yaml and "  0: person" in yaml and "  3: truck" in yaml


def test_export_clips_boxes_and_rejects_unknown_classes(tmp_path: Path) -> None:
    """A box hanging off the frame is clipped; a class outside the four is an error."""
    (tmp_path / "images").mkdir()
    _write(tmp_path, "train", [_image(1, "a")], [_annotation(1, CAR, [1900, 1000, 100, 200])])
    _write(tmp_path, "val", [], [])
    write_yolo_dataset(tmp_path)
    line = (tmp_path / "labels" / "a.txt").read_text(encoding="utf-8").strip()
    assert line == "1 0.994792 0.962963 0.010417 0.074074"
    _write(tmp_path, "train", [_image(1, "a")], [_annotation(1, 99, [0, 0, 10, 10])])
    with pytest.raises(ValueError, match="99"):
        write_yolo_dataset(tmp_path)


def test_our_class_indices_map_back_to_coco_ids() -> None:
    """A model trained on our export predicts 0..3, which map back to person, car, bus, truck."""
    found = boxes_to_detections(7, [[10, 20, 50, 100]] * 4, [0.9] * 4, [0, 1, 2, 3], "ours")
    assert [d["category_id"] for d in found] == [PERSON, CAR, BUS, TRUCK]
    assert found[0]["bbox"] == [10.0, 20.0, 40.0, 80.0]
    assert found[0]["image_id"] == 7 and found[0]["score"] == pytest.approx(0.9)


def test_coco80_predictions_keep_only_our_four_classes() -> None:
    """COCO-pretrained output: person 0, car 2, bus 5, truck 7 kept; bicycle 1, chair 56 dropped."""
    found = boxes_to_detections(1, [[0, 0, 10, 10]] * 6, [0.5] * 6, [0, 1, 2, 5, 7, 56], "coco80")
    assert [d["category_id"] for d in found] == [PERSON, CAR, BUS, TRUCK]


def test_out_of_range_indices_and_unknown_spaces_are_handled() -> None:
    """An index outside our four is dropped; an unknown class space is an error."""
    assert not boxes_to_detections(1, [[0, 0, 5, 5]], [0.5], [9], "ours")
    with pytest.raises(ValueError):
        boxes_to_detections(1, [[0, 0, 5, 5]], [0.5], [0], "voc")
