"""A self-contained release folder from a rendered, split dataset (for Kaggle and similar).

Layout written (all paths in files are relative to the folder, so it can be moved or downloaded):

    images/                      RGB frames (PNG)
    semantic/ , depth/           full-scene class maps (Cityscapes label ids) and 16-bit depth
    instance/ , instance_table/  per-image instance ids and their annotation / category ids
    annotations/instances_{train,val}.json   COCO: boxes, exact polygons, run-length masks, 3D boxes
    labels/ , labels_seg/        YOLO detection and YOLO segmentation lines (one per mask part)
    {train,val}.txt , data.yaml  list files and the ultralytics data file (detection)
    kitti/                       label_2, calib, ImageSets (images are the PNGs in images/)
    classes.json                 object categories, semantic classes with colours, depth encoding
    MANIFEST.json                counts and checksums of the annotation files (written by the CLI)

``validate_package`` re-reads a written folder and lists every inconsistency it finds.
"""

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Sequence

import numpy as np
from PIL import Image

from src.evaluation.class_maps import OUR_CLASSES
from src.evaluation.yolo_export import CLASS_ORDER, _label_lines
from src.ground_truth.semantic_classes import CLASS_NAMES, PALETTE
from src.orchestration.semantic_labels import DEPTH_SCALE

SPLITS = ("train", "val")
IMAGE_FOLDERS = ("images", "semantic", "depth")


def _place(source: Path, target: Path, link: bool) -> None:
    """Hard-link (same volume) or copy ``source`` to ``target``."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return
    if link:
        try:
            os.link(source, target)
            return
        except OSError:
            pass
    shutil.copy2(source, target)


def yolo_segment_lines(
    image: Dict[str, Any], annotations: Sequence[Dict[str, Any]], class_order: Sequence[int]
) -> List[str]:
    """YOLO segmentation lines (``class x1 y1 x2 y2 ...``, normalised), one per polygon part."""
    width, height = float(image["width"]), float(image["height"])
    lines = []
    for annotation in annotations:
        for polygon in annotation.get("segmentation", []):
            if len(polygon) < 6:
                continue
            points = " ".join(
                f"{min(max(polygon[i] / width, 0.0), 1.0):.6f} "
                f"{min(max(polygon[i + 1] / height, 0.0), 1.0):.6f}"
                for i in range(0, len(polygon) - 1, 2)
            )
            lines.append(f"{class_order.index(annotation['category_id'])} {points}")
    return lines


def _write_labels(out: Path, name: str, coco: Dict[str, Any]) -> None:
    """YOLO detection and segmentation labels plus the relative list file of one split."""
    by_image: Dict[int, List[Dict[str, Any]]] = {}
    for annotation in coco["annotations"]:
        by_image.setdefault(annotation["image_id"], []).append(annotation)
    listing = []
    for image in coco["images"]:
        stem = Path(image["file_name"]).stem
        annotations = by_image.get(image["id"], [])
        detect = _label_lines(image, annotations, CLASS_ORDER)
        segments = yolo_segment_lines(image, annotations, CLASS_ORDER)
        for folder, lines in (("labels", detect), ("labels_seg", segments)):
            (out / folder).mkdir(parents=True, exist_ok=True)
            (out / folder / f"{stem}.txt").write_text(
                "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
            )
        listing.append(f"./{image['file_name']}")
    (out / f"{name}.txt").write_text("\n".join(listing) + "\n", encoding="utf-8")


def class_table() -> Dict[str, Any]:
    """Object categories, semantic classes with colours, and how depth is stored."""
    return {
        "object_categories": [
            {"id": cid, "name": OUR_CLASSES[cid], "yolo_index": index}
            for index, cid in enumerate(CLASS_ORDER)
        ],
        "semantic_classes": [
            {"id": cid, "name": CLASS_NAMES[cid], "color_rgb": list(PALETTE[cid])}
            for cid in sorted(CLASS_NAMES)
        ],
        "semantic_note": "Cityscapes label ids; sky is where the engine reports no surface; "
        "ego vehicle is the painted hood; trailers are truck; curbs and tree-pit grates are "
        "sidewalk",
        "depth": {
            "encoding": f"16-bit PNG, metres * {DEPTH_SCALE:.0f}, along the camera's viewing axis",
            "scale": DEPTH_SCALE,
            "no_surface": 0,
        },
    }


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_package(source: Path, out: Path, link: bool = True) -> Dict[str, Any]:
    """Write images, maps, COCO, YOLO labels, classes and manifest of the release folder ``out``.

    KITTI and instance-mask folders come from the ``bin/export_kitti.py`` and
    ``bin/export_masks.py`` functions, which ``bin/package_dataset.py`` calls afterwards.
    """
    out.mkdir(parents=True, exist_ok=True)
    (out / "annotations").mkdir(exist_ok=True)
    counts: Dict[str, Any] = {}
    files: Dict[str, str] = {}
    for name in SPLITS:
        coco = json.loads((source / f"{name}.json").read_text(encoding="utf-8"))
        for image in coco["images"]:
            for key in ("file_name", "semantic_file", "depth_file"):
                if key in image:
                    _place(source / image[key], out / image[key], link)
        coco["semantic_classes"] = class_table()["semantic_classes"]
        coco["depth"] = class_table()["depth"]
        target = out / "annotations" / f"instances_{name}.json"
        target.write_text(json.dumps(coco), encoding="utf-8")
        files[f"annotations/instances_{name}.json"] = _checksum(target)
        _write_labels(out, name, coco)
        counts[name] = {"images": len(coco["images"]), "annotations": len(coco["annotations"])}
    (out / "data.yaml").write_text(
        "train: train.txt\nval: val.txt\nnames:\n"
        + "\n".join(f"  {i}: {OUR_CLASSES[cid]}" for i, cid in enumerate(CLASS_ORDER))
        + "\n",
        encoding="utf-8",
    )
    (out / "classes.json").write_text(json.dumps(class_table(), indent=1), encoding="utf-8")
    return {"counts": counts, "sha256": files}


def validate_package(out: Path) -> List[str]:  # pylint: disable=too-many-branches
    """Every inconsistency found in a written release folder (empty list = clean)."""
    problems: List[str] = []
    valid_classes = set(CLASS_NAMES)
    for name in SPLITS:
        coco = json.loads(
            (out / "annotations" / f"instances_{name}.json").read_text(encoding="utf-8")
        )
        ids = {image["id"] for image in coco["images"]}
        for annotation in coco["annotations"]:
            if annotation["image_id"] not in ids:
                problems.append(f"{name}: annotation {annotation['id']} has no image")
            if not annotation.get("segmentation"):
                problems.append(f"{name}: annotation {annotation['id']} has no polygon")
        for image in coco["images"]:
            stem = Path(image["file_name"]).stem
            for key in ("file_name", "semantic_file", "depth_file"):
                if key not in image or not (out / image[key]).exists():
                    problems.append(f"{name}: {image.get('file_name')} is missing {key}")
            for folder in ("labels", "labels_seg"):
                if not (out / folder / f"{stem}.txt").exists():
                    problems.append(f"{name}: {stem} has no {folder} file")
            if "semantic_file" in image and (out / image["semantic_file"]).exists():
                semantic = np.array(Image.open(out / image["semantic_file"]))
                if semantic.shape != (image["height"], image["width"]):
                    problems.append(f"{stem}: semantic map has shape {semantic.shape}")
                unknown = set(np.unique(semantic).tolist()) - valid_classes
                if unknown:
                    problems.append(f"{stem}: unknown class ids {sorted(unknown)}")
                if (semantic == 0).any():
                    problems.append(f"{stem}: {(semantic == 0).sum()} unlabeled pixels")
    return problems
