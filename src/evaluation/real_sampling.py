"""Draw real BDD100K training images for a dataset and write them out (shared by the builders).

``bin/prepare_real_control.py`` (the real-only control) and ``bin/prepare_rider_headroom.py``
(the rider headroom check) use the same seeded shuffle of the training images, so the headroom
study's base set is exactly the control. Everything here reads the downloaded BDD100K zips.
"""

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Sequence

import numpy as np

from src.evaluation.loaders import EvalSet

SPLIT_PREFIX = "100k/train/"
RARE_CATEGORIES = ("rider", "bike", "motor")


def training_names(labels_zip: zipfile.ZipFile) -> List[str]:
    """The names of every BDD100K training image, sorted, from the label zip."""
    return sorted(
        Path(info.filename).stem
        for info in labels_zip.infolist()
        if info.filename.startswith(SPLIT_PREFIX) and info.filename.endswith(".json")
    )


def read_rare_flags(labels_zip: Path) -> Dict[str, bool]:
    """For every training image, whether its labels hold a rider, bike or motor box."""
    flags: Dict[str, bool] = {}
    with zipfile.ZipFile(labels_zip) as archive:
        for info in archive.infolist():
            if info.filename.startswith(SPLIT_PREFIX) and info.filename.endswith(".json"):
                data = json.loads(archive.read(info))
                objects = [o for frame in data["frames"] for o in frame["objects"]]
                flags[Path(info.filename).stem] = any(
                    o["category"] in RARE_CATEGORIES and "box2d" in o for o in objects
                )
    return flags


def shuffled_names(names: Sequence[str], seed: int) -> List[str]:
    """The names sorted, then permuted with the seeded generator the control datasets use."""
    ordered = sorted(names)
    order = np.random.Generator(np.random.PCG64(seed)).permutation(len(ordered))
    return [ordered[index] for index in order]


def extract_images(names: Sequence[str], images_zip: Path, labels_zip: Path, out: Path) -> None:
    """The chosen images and label files, under ``out/images/100k/train`` and ``out/labels``."""
    with zipfile.ZipFile(images_zip) as images, zipfile.ZipFile(labels_zip) as labels:
        for name in names:
            images.extract(f"{SPLIT_PREFIX}{name}.jpg", out / "images")
            labels.extract(f"{SPLIT_PREFIX}{name}.json", out / "labels")


def subset_coco(eval_set: EvalSet, names: Sequence[str]) -> Dict[str, Any]:
    """The COCO dict of ``eval_set`` for ``names``; file paths relative to the output folder."""
    wanted = {f"{name}.jpg" for name in names}
    images = [
        {**image, "file_name": f"images/{SPLIT_PREFIX}{image['file_name']}"}
        for image in eval_set.coco["images"]
        if image["file_name"] in wanted
    ]
    ids = {image["id"] for image in images}
    annotations = [a for a in eval_set.coco["annotations"] if a["image_id"] in ids]
    return {"images": images, "annotations": annotations, "categories": eval_set.coco["categories"]}


def add_sampling_arguments(parser: argparse.ArgumentParser) -> None:
    """The arguments both dataset builders share: the zips, the output folder, sizes and seed."""
    parser.add_argument("--images-zip", type=Path, required=True)
    parser.add_argument("--labels-zip", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--n-train", type=int, default=1838)
    parser.add_argument("--n-val", type=int, default=199)
    parser.add_argument("--seed", type=int, default=0)
