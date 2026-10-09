"""Build the real-data control dataset: real BDD100K *training* images in YOLO format.

The synthetic-only result means little without knowing what the same number of REAL images
achieves. This samples ``--n-train`` + ``--n-val`` images at random (fixed seed) from BDD100K's
training split, extracts them from the downloaded zips, and writes them in the same YOLO
layout and class mapping as the synthetic dataset (person, car, bus, truck; riders, trains and
objects under the size floor are simply unlabelled). The validation slice, used only to pick
the best checkpoint, also comes from the training split, so BDD100K's own validation set stays
untouched for the final scoring.

    PYTHONPATH=. python bin/prepare_real_control.py \\
        --images-zip C:/Users/evanp/Downloads/bdd100k_images_100k.zip \\
        --labels-zip C:/Users/evanp/Downloads/bdd100k_labels.zip \\
        --out F:/datasets/bdd100k_control --n-train 1838 --n-val 199
"""

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from src.evaluation.loaders import load_bdd100k
from src.evaluation.real_sampling import (
    SPLIT_PREFIX,
    add_sampling_arguments,
    extract_images,
    shuffled_names,
    subset_coco,
    training_names,
)
from src.evaluation.yolo_export import write_data_yaml, write_yolo_split


def _sample_names(labels_zip: zipfile.ZipFile, count: int, seed: int, skip: int = 0) -> List[str]:
    """``count`` image names drawn at random (fixed seed) from the training label files.

    The draw is one seeded shuffle of every training image; ``skip`` starts ``skip`` places into
    it, so a second call with ``skip`` equal to the first call's total returns a disjoint slice
    (more real images that cannot overlap the first set's train or validation images).
    """
    names = training_names(labels_zip)
    if skip + count > len(names):
        raise ValueError(
            f"asked for {count} images after skipping {skip} but the zip has only "
            f"{len(names)} training labels"
        )
    return shuffled_names(names, seed)[skip : skip + count]


def build_control(  # pylint: disable=too-many-arguments,too-many-locals
    images_zip: Path,
    labels_zip: Path,
    out: Path,
    n_train: int,
    n_val: int,
    seed: int,
    skip: int = 0,
) -> Dict[str, Any]:
    """Sample, extract and convert; returns the image and box counts per side.

    ``skip`` starts the draw that many places into the seeded shuffle (see ``_sample_names``);
    the original control uses 0, an extra disjoint set uses the original's n_train + n_val.
    """
    with zipfile.ZipFile(labels_zip) as labels:
        names = _sample_names(labels, n_train + n_val, seed, skip)
    train_names, val_names = names[:n_train], names[n_train:]
    extract_images(names, images_zip, labels_zip, out)
    eval_set = load_bdd100k(out / "labels" / "100k" / "train", out / "images" / SPLIT_PREFIX)
    counts: Dict[str, Any] = {}
    for side, side_names in (("train", train_names), ("val", val_names)):
        images, boxes = write_yolo_split(out, side, subset_coco(eval_set, side_names))
        counts[side] = {"images": images, "boxes": boxes}
    write_data_yaml(out)
    (out / "split.json").write_text(
        json.dumps(
            {"seed": seed, "skip": skip, "train": train_names, "val": val_names, "counts": counts}
        ),
        encoding="utf-8",
    )
    return counts


def main() -> None:
    """Parse arguments, build the control dataset, print the counts."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    add_sampling_arguments(parser)
    parser.add_argument(
        "--skip",
        type=int,
        default=0,
        help="start this far into the seeded shuffle (2037 = a set disjoint from the default one)",
    )
    args = parser.parse_args()
    counts = build_control(
        args.images_zip, args.labels_zip, args.out, args.n_train, args.n_val, args.seed, args.skip
    )
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
