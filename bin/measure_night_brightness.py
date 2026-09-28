"""Measure mean-pixel-brightness statistics for night images, synthetic and real.

Used to derive ``environment.NIGHT_EXPOSURE_BIAS_RANGE_EV``: our night renders used one
fixed preset, so every night image had nearly identical brightness regardless of scene
content, unlike real night photos, which vary hugely by street lighting. This script
prints mean/std/min/max brightness for both, so a fresh dataset (after any generator
change) can be re-measured and compared against the same real target.

    PYTHONPATH=. python bin/measure_night_brightness.py --dataset live_dataset/train2000 \\
        --bdd-labels F:/datasets/bdd100k/labels/100k/val \\
        --bdd-images F:/datasets/bdd100k/images/100k/val
"""

import argparse
import glob
import json
import random
from pathlib import Path
from typing import List

import numpy as np
from PIL import Image


def _mean_brightness(path: Path) -> float:
    """A grayscale image's mean pixel value (0-255)."""
    return float(np.asarray(Image.open(path).convert("L"), dtype=np.float32).mean())


def _synthetic_night_means(dataset_dir: Path) -> List[float]:
    """Mean brightness of every ego-view night image already rendered into ``dataset_dir``."""
    means = []
    for part_path in sorted(glob.glob(str(dataset_dir / "parts" / "scenario_*.json"))):
        part = json.loads(Path(part_path).read_text(encoding="utf-8"))
        for image in part["images"]:
            if image.get("time_of_day") == "night" and image.get("view") == "ego":
                means.append(_mean_brightness(dataset_dir / image["file_name"]))
    return means


def _bdd_night_means(
    labels_path: Path, image_dir: Path, sample_size: int, seed: int
) -> List[float]:
    """Mean brightness of ``sample_size`` random BDD100K night images."""
    from src.evaluation.loaders import load_bdd100k  # pylint: disable=import-outside-toplevel

    eval_set = load_bdd100k(labels_path, image_dir)
    night_images = [
        image
        for image in eval_set.coco["images"]
        if image["attributes"].get("timeofday") == "night"
    ]
    sample = random.Random(seed).sample(night_images, min(sample_size, len(night_images)))
    return [_mean_brightness(eval_set.image_path(image)) for image in sample]


def _report(name: str, means: List[float]) -> None:
    """Print mean/std/min/max for one collection of per-image brightness values."""
    values = np.array(means)
    print(
        f"{name:10s} n={len(values):5d}  mean={values.mean():6.2f}  std={values.std():6.2f}  "
        f"min={values.min():6.2f}  max={values.max():6.2f}"
    )


def main() -> None:
    """Parse arguments, measure both collections, print the comparison."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--bdd-labels", type=Path, required=True)
    parser.add_argument("--bdd-images", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=300)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    _report("synthetic", _synthetic_night_means(args.dataset))
    bdd_means = _bdd_night_means(args.bdd_labels, args.bdd_images, args.sample_size, args.seed)
    _report("bdd100k", bdd_means)


if __name__ == "__main__":
    main()
