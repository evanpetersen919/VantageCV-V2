"""Randomize every image's background (buildings, road, sidewalk, foliage, sky) while leaving
every labeled object's own pixels completely untouched.

Directly implements Tobin et al. 2017's domain-randomization technique (the foundational
sim-to-real paper): non-realistic background randomization -- a random solid color, a gradient
between two random colors, or a checker pattern of two random colors -- forces a detector to
key on object shape rather than background appearance, since the background carries no
consistent identity from image to image. Applied here with an advantage Tobin et al. didn't
have available (their backgrounds were random image crops, not segmented): every rendered
frame already carries exact per-instance polygon segmentation
(``src/export/coco_exporter.py``), so *only* background pixels are touched and object shape
is preserved exactly, with zero risk of corrupting the label-relevant signal.

Deterministic per image (seeded from the image's own id), same contract as
``bin/apply_image_realism.py``: only pixels change, every box/segmentation/split/manifest file
is carried over unchanged (no re-render, no relabeling needed).

    PYTHONPATH=. python bin/stylize_backgrounds.py --dataset live_dataset/train2000_v5 \\
        --out live_dataset/train2000_v5_stylized
"""

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageDraw

from src.evaluation.split import copy_dataset_side_files

_STYLES = ("solid", "gradient", "checker")
_CHECKER_CELL_RANGE_PX = (30, 90)


def _object_mask(
    width: int, height: int, annotations: List[Dict[str, Any]]
) -> npt.NDArray[np.bool_]:
    """The union of every instance's segmentation polygon, rasterized -- True where any
    labeled object is, False everywhere else (the region this script is allowed to touch)."""
    mask_image = Image.new("1", (width, height), 0)
    draw = ImageDraw.Draw(mask_image)
    for annotation in annotations:
        for polygon in annotation.get("segmentation", []):
            if len(polygon) >= 6:  # at least 3 points
                draw.polygon(polygon, fill=1)
    return np.array(mask_image, dtype=np.bool_)


def _random_background(width: int, height: int, rng: np.random.Generator) -> npt.NDArray[np.uint8]:
    """One full-frame background fill: a random solid color, a gradient between two random
    colors (random axis), or a checker pattern of two random colors (random cell size) --
    exactly Tobin et al. 2017's own three background styles."""
    style = _STYLES[int(rng.integers(len(_STYLES)))]
    color_a = rng.integers(0, 256, size=3, dtype=np.uint8)
    color_b = rng.integers(0, 256, size=3, dtype=np.uint8)

    if style == "solid":
        return np.tile(color_a, (height, width, 1))

    if style == "gradient":
        axis_length = width if rng.integers(2) == 0 else height
        ramp = np.linspace(0.0, 1.0, axis_length)[:, None]
        blended = color_a[None, :] * (1.0 - ramp) + color_b[None, :] * ramp
        blended = blended.astype(np.uint8)
        return (
            np.broadcast_to(blended[None, :, :], (height, width, 3))
            if axis_length == width
            else np.broadcast_to(blended[:, None, :], (height, width, 3))
        )

    cell = int(rng.integers(*_CHECKER_CELL_RANGE_PX))
    ys, xs = np.meshgrid(np.arange(height) // cell, np.arange(width) // cell, indexing="ij")
    use_a = (xs + ys) % 2 == 0
    background = np.where(use_a[..., None], color_a, color_b)
    return background.astype(np.uint8)


def _stylize(image: Image.Image, annotations: List[Dict[str, Any]], seed: int) -> Image.Image:
    """``image`` with its background replaced by one random Tobin-style fill; every pixel
    inside a labeled object's segmentation polygon is left exactly as rendered."""
    width, height = image.size
    mask = _object_mask(width, height, annotations)
    rng = np.random.Generator(np.random.PCG64([seed, 0xB6C6]))
    background = _random_background(width, height, rng)

    original = np.array(image.convert("RGB"))
    composited = np.where(mask[..., None], original, background)
    return Image.fromarray(composited.astype(np.uint8), "RGB")


def main() -> None:
    """Parse arguments, copy label files unchanged, stylize every image's background."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    annotations_data = json.loads((args.dataset / "annotations.json").read_text(encoding="utf-8"))
    annotations_by_image: Dict[int, List[Dict[str, Any]]] = {}
    for annotation in annotations_data["annotations"]:
        annotations_by_image.setdefault(annotation["image_id"], []).append(annotation)

    args.out.mkdir(parents=True, exist_ok=True)
    for name in ("annotations.json", "train.json", "val.json"):
        source = args.dataset / name
        if source.exists():
            shutil.copy2(source, args.out / name)
    copy_dataset_side_files(args.dataset, args.out)

    (args.out / "images").mkdir(parents=True, exist_ok=True)
    images = annotations_data["images"]
    for index, image_entry in enumerate(images):
        source_path = args.dataset / image_entry["file_name"]
        destination_path = args.out / image_entry["file_name"]
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source_path) as image:
            stylized = _stylize(
                image, annotations_by_image.get(image_entry["id"], []), image_entry["id"]
            )
        stylized.save(destination_path)
        if (index + 1) % 200 == 0:
            print(f"{index + 1}/{len(images)}")
    print(f"done: {len(images)} images -> {args.out / 'images'}")


if __name__ == "__main__":
    main()
