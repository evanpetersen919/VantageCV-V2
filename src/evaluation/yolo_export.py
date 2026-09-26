"""Write a split live dataset in the layout ultralytics (YOLO) trains from.

Given ``train.json`` and ``val.json`` (from ``split.write_split``), this writes one
``<image>.txt`` label file per image in a ``labels/`` folder beside the dataset's ``images/``
folder (ultralytics finds a label by replacing ``/images/`` with ``/labels/`` in the image
path, so the images are used where they are, not copied), list files ``train.txt`` and
``val.txt`` of absolute image paths, and a ``data.yaml``.

Class indices follow ``CLASS_ORDER`` (COCO ids person 1, car 3, bus 6, truck 8, as exported by
the COCO profile), which is also the order ``detections.py`` maps back from.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from src.evaluation.class_maps import OUR_CLASSES

CLASS_ORDER: Tuple[int, ...] = tuple(sorted(OUR_CLASSES))
IMAGES_DIR, LABELS_DIR = "images", "labels"


def label_path_for(image_path: Path) -> Path:
    """The label file ultralytics looks for: last ``images`` folder -> ``labels``, ``.txt``."""
    parts = list(image_path.parts)
    for index in range(len(parts) - 2, -1, -1):
        if parts[index] == IMAGES_DIR:
            parts[index] = LABELS_DIR
            return Path(*parts).with_suffix(".txt")
    raise ValueError(f"{image_path} has no '{IMAGES_DIR}' folder in its path")


def _label_lines(  # pylint: disable=too-many-locals
    image: Dict[str, Any], annotations: Sequence[Dict[str, Any]], class_order: Sequence[int]
) -> List[str]:
    """YOLO lines (``class cx cy w h``, normalised and clipped to the image) for one image."""
    width, height = float(image["width"]), float(image["height"])
    lines = []
    for annotation in annotations:
        if annotation["category_id"] not in class_order:
            raise ValueError(f"category {annotation['category_id']} is not in {list(class_order)}")
        x, y, w, h = annotation["bbox"]
        x_min, y_min = max(x, 0.0), max(y, 0.0)
        x_max, y_max = min(x + w, width), min(y + h, height)
        if x_max <= x_min or y_max <= y_min:
            continue
        centre_x, centre_y = (x_min + x_max) / 2.0 / width, (y_min + y_max) / 2.0 / height
        lines.append(
            f"{class_order.index(annotation['category_id'])} {centre_x:.6f} {centre_y:.6f} "
            f"{(x_max - x_min) / width:.6f} {(y_max - y_min) / height:.6f}"
        )
    return lines


def _write_side(dataset_dir: Path, name: str, class_order: Sequence[int]) -> Tuple[int, int]:
    """Labels and the list file for ``<name>.json``; returns (images, boxes)."""
    coco = json.loads((dataset_dir / f"{name}.json").read_text(encoding="utf-8"))
    by_image: Dict[int, List[Dict[str, Any]]] = {}
    for annotation in coco["annotations"]:
        by_image.setdefault(annotation["image_id"], []).append(annotation)
    paths, boxes = [], 0
    for image in coco["images"]:
        image_path = (dataset_dir / image["file_name"]).resolve()
        lines = _label_lines(image, by_image.get(image["id"], []), class_order)
        label_path = label_path_for(image_path)
        label_path.parent.mkdir(parents=True, exist_ok=True)
        label_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        paths.append(str(image_path))
        boxes += len(lines)
    (dataset_dir / f"{name}.txt").write_text("\n".join(paths) + "\n", encoding="utf-8")
    return len(paths), boxes


def write_yolo_dataset(
    dataset_dir: Path, class_order: Sequence[int] = CLASS_ORDER
) -> Dict[str, Any]:
    """Write labels, list files and ``data.yaml`` for a dataset that has been split.

    Returns image and box counts per side.
    """
    counts = {}
    for name in ("train", "val"):
        images, boxes = _write_side(dataset_dir, name, class_order)
        counts[name] = {"images": images, "boxes": boxes}
    names = "\n".join(f"  {index}: {OUR_CLASSES[cid]}" for index, cid in enumerate(class_order))
    root = dataset_dir.resolve().as_posix()
    yaml = f"path: {root}\ntrain: train.txt\nval: val.txt\nnames:\n{names}\n"
    (dataset_dir / "data.yaml").write_text(yaml, encoding="utf-8")
    return counts
