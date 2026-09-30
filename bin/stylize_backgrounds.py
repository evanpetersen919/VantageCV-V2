"""Randomize every image's background (buildings, road, sidewalk, foliage, sky) while leaving
every labeled object's own pixels completely untouched.

Directly implements Tobin et al. 2017's domain-randomization technique (the foundational
sim-to-real paper): non-realistic background randomization forces a detector to key on object
shape rather than background appearance, since the background carries no consistent identity
from image to image. Applied here with an advantage Tobin et al. didn't have available (their
backgrounds were random image crops, not segmented): every rendered frame already carries exact
per-instance polygon segmentation (``src/export/coco_exporter.py``), so *only* background
pixels are touched and object shape is preserved exactly, with zero risk of corrupting the
label-relevant signal.

A first version of this (solid/gradient/checker fills, on every image) collapsed AP to near
zero and made Grad-CAM's spurious-texture attention *worse* (``EXPERIMENT_LOG.md``'s
"Segmentation-guided background stylization -- negative result" entry). Root cause, measured
directly: labeled objects cover only ~6% of the average frame in this project's wide street
scenes, so replacing the rest with flat, textureless color wiped out nearly every pixel of
low-level statistics a from-scratch CNN needs to bootstrap general features, in an already
small (1,838-image) training set. This version fixes both contributing factors at once (see
``EXPERIMENT_LOG.md`` for why bundling them here, rather than isolating each separately, is an
acceptable, disclosed tradeoff given the render/train cost per test):

1. ``--noise-fraction`` of stylized images get a multi-octave value-noise fill (colorized
   between two random colors) instead of a flat solid/gradient/checker -- still a
   non-realistic, randomized background with no consistent identity, but one that keeps real
   low-level pixel statistics (edges, gradients, local contrast) everywhere in the frame.
2. ``--apply-fraction`` of images get any background swap at all; the rest keep their real,
   unmodified background -- Tremblay et al. 2018 themselves recommend mixing
   domain-randomized data with realistic renders rather than training on pure DR alone, for
   exactly the stability reason this project's own first attempt ran into.

Deterministic per image (seeded from the image's own id), same contract as
``bin/apply_image_realism.py``: only pixels change, every box/segmentation/split/manifest file
is carried over unchanged (no re-render, no relabeling needed).

    PYTHONPATH=. python bin/stylize_backgrounds.py --dataset live_dataset/train2000_v5 \\
        --out live_dataset/train2000_v5_stylized2
"""

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageDraw
from scipy.ndimage import zoom

from src.evaluation.split import copy_dataset_side_files

_FLAT_STYLES = ("solid", "gradient", "checker")
_CHECKER_CELL_RANGE_PX = (30, 90)
_NOISE_OCTAVES = 3
_NOISE_BASE_CELL_PX = 24


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


def _value_noise(height: int, width: int, rng: np.random.Generator) -> npt.NDArray[np.float64]:
    """Multi-octave value noise in [0, 1]: a low-resolution random grid per octave, upsampled
    (bilinear) to full size and summed at halving amplitude -- a cheap, dependency-free
    approximation of Perlin noise, giving real local texture/gradient statistics rather than a
    flat fill."""
    noise = np.zeros((height, width))
    amplitude, total_amplitude, scale = 1.0, 0.0, _NOISE_BASE_CELL_PX
    for _ in range(_NOISE_OCTAVES):
        low_h, low_w = max(2, height // scale), max(2, width // scale)
        low_res = rng.random((low_h, low_w))
        upsampled = zoom(low_res, (height / low_h, width / low_w), order=1)[:height, :width]
        noise += amplitude * upsampled
        total_amplitude += amplitude
        amplitude *= 0.5
        scale = max(1, scale // 2)
    return noise / total_amplitude


def _random_background(
    width: int, height: int, rng: np.random.Generator, noise_fraction: float
) -> npt.NDArray[np.uint8]:
    """One full-frame background fill: with probability ``noise_fraction`` a colorized
    multi-octave value-noise field (real per-pixel texture, still no consistent identity
    across images); otherwise one of Tobin et al. 2017's own three flat styles (solid color,
    gradient between two colors, or a checker pattern)."""
    color_a = rng.integers(0, 256, size=3, dtype=np.uint8)
    color_b = rng.integers(0, 256, size=3, dtype=np.uint8)

    if rng.random() < noise_fraction:
        blend = _value_noise(height, width, rng)[..., None]
        return (color_a[None, None, :] * (1.0 - blend) + color_b[None, None, :] * blend).astype(
            np.uint8
        )

    style = _FLAT_STYLES[int(rng.integers(len(_FLAT_STYLES)))]
    if style == "solid":
        return np.tile(color_a, (height, width, 1))

    if style == "gradient":
        axis_length = width if rng.integers(2) == 0 else height
        ramp = np.linspace(0.0, 1.0, axis_length)[:, None]
        blended = (color_a[None, :] * (1.0 - ramp) + color_b[None, :] * ramp).astype(np.uint8)
        return (
            np.broadcast_to(blended[None, :, :], (height, width, 3))
            if axis_length == width
            else np.broadcast_to(blended[:, None, :], (height, width, 3))
        )

    cell = int(rng.integers(*_CHECKER_CELL_RANGE_PX))
    ys, xs = np.meshgrid(np.arange(height) // cell, np.arange(width) // cell, indexing="ij")
    use_a = (xs + ys) % 2 == 0
    return np.where(use_a[..., None], color_a, color_b).astype(np.uint8)


def _stylize(
    image: Image.Image,
    annotations: List[Dict[str, Any]],
    seed: int,
    apply_fraction: float,
    noise_fraction: float,
) -> Image.Image:
    """``image``, unchanged with probability ``1 - apply_fraction``; otherwise with its
    background replaced by one random fill (see ``_random_background``). Every pixel inside a
    labeled object's segmentation polygon is always left exactly as rendered."""
    rng = np.random.Generator(np.random.PCG64([seed, 0xB6C6]))
    if rng.random() >= apply_fraction:
        return image.convert("RGB")

    width, height = image.size
    mask = _object_mask(width, height, annotations)
    background = _random_background(width, height, rng, noise_fraction)

    original = np.array(image.convert("RGB"))
    composited = np.where(mask[..., None], original, background)
    return Image.fromarray(composited.astype(np.uint8), "RGB")


def main() -> None:
    """Parse arguments, copy label files unchanged, stylize a fraction of images' backgrounds."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--apply-fraction", type=float, default=0.5)
    parser.add_argument("--noise-fraction", type=float, default=0.7)
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
                image,
                annotations_by_image.get(image_entry["id"], []),
                image_entry["id"],
                args.apply_fraction,
                args.noise_fraction,
            )
        stylized.save(destination_path)
        if (index + 1) % 200 == 0:
            print(f"{index + 1}/{len(images)}")
    print(f"done: {len(images)} images -> {args.out / 'images'}")


if __name__ == "__main__":
    main()
