"""Load real-image benchmarks as COCO-style ground truth over this project's four classes.

``load_bdd100k`` reads BDD100K's detection label JSON (one entry per image, with its
weather / scene / time-of-day attributes and ``box2d`` boxes); ``load_cityscapes`` reads the
``gtFine`` polygon files and takes each instance's polygon extent as its box. Both apply the
label mapping in ``class_maps`` and return an ``EvalSet``: a COCO dict whose images carry
their attributes, whose annotations are positives (``iscrowd`` 0) or ignore regions
(``iscrowd`` 1), plus the image root so the images can be found.

The formats are read as published (BDD100K's ``det_20`` labels and Cityscapes ``gtFine``); a
file that does not match raises rather than being silently skipped.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.evaluation import class_maps

BDD100K_IMAGE_SIZE = (1280, 720)
CITYSCAPES_IMAGE_SIZE = (2048, 1024)


@dataclass
class EvalSet:
    """A benchmark's ground truth in COCO form, plus where its images live."""

    name: str
    coco: Dict[str, Any]
    image_root: Path
    notes: Dict[str, Any] = field(default_factory=dict)

    def image_path(self, image: Dict[str, Any]) -> Path:
        """The file of one ``coco["images"]`` entry."""
        return Path(self.image_root / image["file_name"])

    def counts(self) -> Dict[str, int]:
        """Scored (non-ignore) ground-truth boxes per class name, and the ignore-region count."""
        totals = {name: 0 for name in class_maps.OUR_CLASSES.values()}
        totals["ignore_regions"] = 0
        for annotation in self.coco["annotations"]:
            if annotation["iscrowd"]:
                totals["ignore_regions"] += 1
            else:
                totals[class_maps.OUR_CLASSES[annotation["category_id"]]] += 1
        return totals


def _categories() -> List[Dict[str, Any]]:
    """The COCO ``categories`` list for our four classes."""
    return [{"id": cid, "name": name} for cid, name in class_maps.OUR_CLASSES.items()]


def _add_object(  # pylint: disable=too-many-arguments,too-many-locals
    annotations: List[Dict[str, Any]],
    image: Dict[str, Any],
    box: Tuple[float, float, float, float],
    positive: Optional[int],
    ignore: Tuple[int, ...],
    minimum: Tuple[float, float],
) -> None:
    """Add one real object as a scored box and/or ignore regions.

    ``positive`` is the class it counts as (or ``None``); ``ignore`` the classes whose
    detections over it are not penalised. A positive smaller than ``minimum`` (height, width)
    becomes an ignore region for its own class instead of being scored.
    """
    x_min, y_min = max(box[0], 0.0), max(box[1], 0.0)
    x_max, y_max = min(box[2], float(image["width"])), min(box[3], float(image["height"]))
    if x_max <= x_min or y_max <= y_min:
        return
    width, height = x_max - x_min, y_max - y_min
    targets: List[Tuple[int, int]] = []
    if positive is not None:
        too_small = height < minimum[0] or width < minimum[1]
        targets.append((positive, 1 if too_small else 0))
    targets += [(category, 1) for category in ignore]
    for category, crowd in targets:
        annotations.append(
            {
                "id": len(annotations) + 1,
                "image_id": image["id"],
                "category_id": category,
                "bbox": [x_min, y_min, width, height],
                "area": width * height,
                "iscrowd": crowd,
            }
        )


def load_bdd100k(
    labels_path: Path,
    image_dir: Path,
    image_size: Tuple[int, int] = BDD100K_IMAGE_SIZE,
    minimum: Tuple[float, float] = (class_maps.MIN_BOX_HEIGHT_PX, class_maps.MIN_BOX_WIDTH_PX),
) -> EvalSet:
    """BDD100K detection labels (a JSON list of frames) as an ``EvalSet``.

    Each frame's ``attributes`` (weather, scene, timeofday) are kept on its image so results
    can be broken down by condition.
    """
    frames = json.loads(labels_path.read_text(encoding="utf-8"))
    if not isinstance(frames, list):
        raise ValueError(f"{labels_path} is not a BDD100K label list")
    images: List[Dict[str, Any]] = []
    annotations: List[Dict[str, Any]] = []
    for frame in frames:
        image = {
            "id": len(images) + 1,
            "file_name": frame["name"],
            "width": image_size[0],
            "height": image_size[1],
            "attributes": dict(frame.get("attributes", {})),
        }
        images.append(image)
        for label in frame.get("labels", []):
            box = label.get("box2d")
            if box is None:
                continue
            category = label["category"]
            _add_object(
                annotations,
                image,
                (box["x1"], box["y1"], box["x2"], box["y2"]),
                class_maps.BDD100K_POSITIVE.get(category),
                class_maps.BDD100K_IGNORE.get(category, ()),
                minimum,
            )
    coco = {"images": images, "annotations": annotations, "categories": _categories()}
    return EvalSet("bdd100k", coco, image_dir, {"minimum_height_width_px": list(minimum)})


def _cityscapes_mapping(label: str) -> Tuple[Optional[int], Tuple[int, ...]]:
    """(positive class, ignore classes) for a Cityscapes label; ``(None, ())`` drops it."""
    if label in class_maps.CITYSCAPES_POSITIVE:
        return class_maps.CITYSCAPES_POSITIVE[label], ()
    if label in class_maps.CITYSCAPES_IGNORE:
        return None, class_maps.CITYSCAPES_IGNORE[label]
    suffix = class_maps.CITYSCAPES_GROUP_SUFFIX
    if label.endswith(suffix) and label[: -len(suffix)] in class_maps.CITYSCAPES_POSITIVE:
        return None, (class_maps.CITYSCAPES_POSITIVE[label[: -len(suffix)]],)
    return None, ()


def _cityscapes_image(
    path: Path,
    split: str,
    image_id: int,
    annotations: List[Dict[str, Any]],
    minimum: Tuple[float, float],
) -> Dict[str, Any]:
    """One Cityscapes polygon file as an image; its objects are appended to ``annotations``."""
    data = json.loads(path.read_text(encoding="utf-8"))
    city = path.parent.name
    stem = path.name[: -len("_gtFine_polygons.json")]
    image = {
        "id": image_id,
        "file_name": f"leftImg8bit/{split}/{city}/{stem}_leftImg8bit.png",
        "width": int(data.get("imgWidth", CITYSCAPES_IMAGE_SIZE[0])),
        "height": int(data.get("imgHeight", CITYSCAPES_IMAGE_SIZE[1])),
        "attributes": {"city": city},
    }
    for instance in data.get("objects", []):
        positive, ignore = _cityscapes_mapping(instance["label"])
        if positive is None and not ignore:
            continue
        xs = [point[0] for point in instance["polygon"]]
        ys = [point[1] for point in instance["polygon"]]
        _add_object(
            annotations, image, (min(xs), min(ys), max(xs), max(ys)), positive, ignore, minimum
        )
    return image


def load_cityscapes(
    root: Path,
    split: str = "val",
    minimum: Tuple[float, float] = (class_maps.MIN_BOX_HEIGHT_PX, class_maps.MIN_BOX_WIDTH_PX),
) -> EvalSet:
    """Cityscapes ``gtFine`` polygons of one split as an ``EvalSet``.

    Boxes are the extents of each instance's polygon. Images are the matching
    ``leftImg8bit`` files; the city is kept as the image attribute.
    """
    polygon_files = sorted((root / "gtFine" / split).glob("*/*_gtFine_polygons.json"))
    if not polygon_files:
        raise FileNotFoundError(f"no gtFine polygon files under {root / 'gtFine' / split}")
    images: List[Dict[str, Any]] = []
    annotations: List[Dict[str, Any]] = []
    for path in polygon_files:
        images.append(_cityscapes_image(path, split, len(images) + 1, annotations, minimum))
    coco = {"images": images, "annotations": annotations, "categories": _categories()}
    return EvalSet(f"cityscapes_{split}", coco, root, {"minimum_height_width_px": list(minimum)})
