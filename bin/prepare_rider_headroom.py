"""Build the datasets of the rider headroom check: how much does more real rare-class data help?

    PYTHONPATH=. python bin/prepare_rider_headroom.py \\
        --images-zip C:/Users/evanp/Downloads/bdd100k_images_100k.zip \\
        --labels-zip C:/Users/evanp/Downloads/bdd100k_labels.zip --out F:/datasets/rider_headroom

The base set is the project's real control: the first 1,838 images of the seeded shuffle of
BDD100K's training images (seed 0, the same draw as ``bin/prepare_real_control.py``), with the
next 199 as the validation list used to pick the best checkpoint. A rare image contains a rider,
bike or motor box. Let r0 be the number of rare images in the base set. Five arms share that
validation list:

* ``A``      the base set;
* ``rare2``  A + r0 rare images from the rest of the shuffle (twice the rare images);
* ``rare4``  A + 3 r0 rare images (four times; contains ``rare2``'s extras);
* ``rand2``  A + r0 images drawn at random from the rest of the shuffle (the same number of
  extra images, at the natural rare rate);
* ``rand4``  A + 3 r0 random images (contains ``rand2``'s extras).

``rare`` against ``rand`` separates "more rare images" from "more images". Labels are written
in the rider class profile (person, bike, car, motor, bus, truck, rider). Rules for reading the
result: ``docs/riders/headroom_check.md``.
"""

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Sequence

from src.evaluation.class_maps import RIDER_PROFILE
from src.evaluation.loaders import EvalSet, load_bdd100k
from src.evaluation.portable import data_yaml
from src.evaluation.real_sampling import (
    SPLIT_PREFIX,
    add_sampling_arguments,
    extract_images,
    shuffled_names,
    subset_coco,
    training_names,
)
from src.evaluation.yolo_export import write_yolo_split

RARE_CATEGORIES = ("rider", "bike", "motor")
ARMS = ("A", "rare2", "rare4", "rand2", "rand4")


def select_arms(
    order: Sequence[str], is_rare: Dict[str, bool], n_train: int, n_val: int
) -> Dict[str, Any]:
    """The image names of every arm and of the validation list, from one shuffled order.

    The base set is ``order[:n_train]`` and the validation list the next ``n_val``; extras come
    only from the rest.
    """
    base = list(order[:n_train])
    validation = list(order[n_train : n_train + n_val])
    pool = list(order[n_train + n_val :])
    r0 = sum(1 for name in base if is_rare[name])
    rare_extra = [name for name in pool if is_rare[name]][: 3 * r0]
    random_extra = pool[: 3 * r0]
    if len(rare_extra) < 3 * r0:
        raise ValueError(f"only {len(rare_extra)} rare images in the pool, need {3 * r0}")
    arms = {
        "A": base,
        "rare2": base + rare_extra[:r0],
        "rare4": base + rare_extra,
        "rand2": base + random_extra[:r0],
        "rand4": base + random_extra,
    }
    return {"arms": arms, "validation": validation, "r0": r0}


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


def instance_counts(eval_set: EvalSet, names: Sequence[str]) -> Dict[str, int]:
    """Scored boxes per class over ``names`` (ignore regions excluded)."""
    wanted = {f"{name}.jpg" for name in names}
    ids = {i["id"] for i in eval_set.coco["images"] if i["file_name"] in wanted}
    classes = {c["id"]: c["name"] for c in eval_set.coco["categories"]}
    counts = {name: 0 for name in classes.values()}
    for annotation in eval_set.coco["annotations"]:
        if annotation["image_id"] in ids and not annotation["iscrowd"]:
            counts[classes[annotation["category_id"]]] += 1
    return counts


def build(  # pylint: disable=too-many-arguments,too-many-locals
    images_zip: Path, labels_zip: Path, out: Path, n_train: int, n_val: int, seed: int
) -> Dict[str, Any]:
    """Select, extract, label and list every arm; returns the counts that go in ``split.json``."""
    with zipfile.ZipFile(labels_zip) as archive:
        names = training_names(archive)
    chosen = select_arms(shuffled_names(names, seed), read_rare_flags(labels_zip), n_train, n_val)
    needed = sorted({n for arm in chosen["arms"].values() for n in arm} | set(chosen["validation"]))
    extract_images(needed, images_zip, labels_zip, out)
    eval_set = load_bdd100k(
        out / "labels" / "100k" / "train",
        out / "images" / SPLIT_PREFIX,
        profile=RIDER_PROFILE,
    )
    write_yolo_split(out, "all", subset_coco(eval_set, needed), RIDER_PROFILE.class_order)
    (out / "arms").mkdir(exist_ok=True)

    def listing(items: Sequence[str]) -> List[str]:
        return [str((out / "images" / SPLIT_PREFIX / f"{n}.jpg").resolve()) for n in items]

    val_list = out / "val.txt"
    val_list.write_text("\n".join(listing(chosen["validation"])) + "\n", encoding="utf-8")
    names_by_index = {i: RIDER_PROFILE.classes[c] for i, c in enumerate(RIDER_PROFILE.class_order)}
    summary: Dict[str, Any] = {"seed": seed, "r0": chosen["r0"], "arms": {}}
    for arm, items in chosen["arms"].items():
        train_list = out / "arms" / f"{arm}.txt"
        train_list.write_text("\n".join(listing(items)) + "\n", encoding="utf-8")
        (out / "arms" / f"{arm}.yaml").write_text(
            data_yaml([train_list], val_list, names_by_index), encoding="utf-8"
        )
        summary["arms"][arm] = {
            "images": len(items),
            "boxes": instance_counts(eval_set, items),
        }
    summary["names"] = dict(chosen["arms"])
    summary["validation"] = chosen["validation"]
    (out / "split.json").write_text(json.dumps(summary), encoding="utf-8")
    return {k: v for k, v in summary.items() if k not in ("names", "validation")}


def main() -> None:
    """Parse arguments, build the datasets, print the counts."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    add_sampling_arguments(parser)
    args = parser.parse_args()
    print(
        json.dumps(
            build(args.images_zip, args.labels_zip, args.out, args.n_train, args.n_val, args.seed),
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
