"""Build the arms of the rider study (docs/riders/preregistration.md, section 3) from the real
headroom bundle plus a rendered synthetic dataset in the ``riders`` profile.

    PYTHONPATH=. python bin/prepare_rider_synthetic_arms.py \\
        --bundle F:/datasets/rider_headroom --synthetic live_dataset/rider_v18 \\
        --images-zip C:/Users/evanp/Downloads/bdd100k_images_100k.zip \\
        --labels-zip C:/Users/evanp/Downloads/bdd100k_labels.zip --extra 1000 --sweep 250 500

``--bundle`` is the output of ``bin/prepare_rider_headroom.py`` (its base set, validation list and
the seeded shuffle are reused, so arm ``A`` is the same set). Added to ``bundle/arms/``:

* ``B``      A + S real rare images (the first S rare images of the pool, as ``rare2``/``rare4``);
* ``C``      A with repeat-factor sampling: r_c = max(1, sqrt(t / f_c)) over rider, bike and motor,
  f_c the share of base images containing the class, t = 9 x the smallest f_c, an image taking
  the largest r_c of its classes; r is rounded stochastically (seeded by the image name) and the
  image is listed that many times;
* ``E``      A + S synthetic rare images (images with a rider or bike label, first S of a seeded
  shuffle); ``E<n>`` and ``B<n>`` for the exploratory sweep sizes ``n``.

Every arm shares ``val.txt``. Epochs, not steps, are fixed (the recipe), so arms with more
images take more steps; that is the same for B, C and E and is reported with the results.
"""

import argparse
import json
import math
import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

import numpy as np

from src.evaluation.class_maps import RIDER_PROFILE
from src.evaluation.loaders import load_bdd100k
from src.evaluation.portable import data_yaml
from src.evaluation.real_sampling import (
    RARE_CATEGORIES,
    SPLIT_PREFIX,
    extract_images,
    read_rare_flags,
    shuffled_names,
    subset_coco,
    training_names,
)
from src.evaluation.yolo_export import write_yolo_split

SYNTHETIC_RARE_IDS = (10, 2)  # rider, bike in the riders profile
REPEAT_T_FACTOR = 9.0
SYNTHETIC_SUBDIR = "synthetic"


def repeat_counts(
    base_classes: Dict[str, Set[str]], classes: Sequence[str], factor: float, seed: int
) -> Dict[str, int]:
    """How many times each base image is listed under repeat-factor sampling.

    ``base_classes`` maps image name to the set of class names it contains.
    """
    n_images = len(base_classes)
    shares = {c: sum(1 for have in base_classes.values() if c in have) / n_images for c in classes}
    present = [share for share in shares.values() if share > 0]
    if not present:
        return {name: 1 for name in base_classes}
    threshold = factor * min(present)
    class_factor = {c: max(1.0, math.sqrt(threshold / s)) for c, s in shares.items() if s > 0}
    counts: Dict[str, int] = {}
    for name, have in base_classes.items():
        r = max((class_factor[c] for c in have if c in class_factor), default=1.0)
        rng = np.random.Generator(np.random.PCG64([seed, abs(hash_name(name))]))
        counts[name] = int(math.floor(r) + (1 if rng.random() < r - math.floor(r) else 0))
    return counts


def hash_name(name: str) -> int:
    """A stable integer for an image name (Python's ``hash`` is salted per process)."""
    return int.from_bytes(name.encode("utf-8")[-8:].rjust(8, b"\0"), "big") % (2**31)


def pick_synthetic(coco: Dict[str, Any], count: int, seed: int) -> List[Dict[str, Any]]:
    """The first ``count`` images with a rider or bike label from a seeded shuffle."""
    with_rare = {
        a["image_id"] for a in coco["annotations"] if a["category_id"] in SYNTHETIC_RARE_IDS
    }
    images = sorted((i for i in coco["images"] if i["id"] in with_rare), key=lambda i: i["id"])
    order = np.random.Generator(np.random.PCG64(seed)).permutation(len(images))
    if count > len(images):
        raise ValueError(f"only {len(images)} synthetic images have a rider or bike, need {count}")
    return [images[k] for k in order[:count]]


def import_synthetic(synthetic: Path, bundle: Path, seed: int, count: int) -> List[str]:
    """Copy ``count`` chosen synthetic images into the bundle and label them; absolute paths."""
    coco = json.loads((synthetic / "annotations.json").read_text(encoding="utf-8"))
    chosen = pick_synthetic(coco, count, seed)
    target = bundle / "images" / SYNTHETIC_SUBDIR
    target.mkdir(parents=True, exist_ok=True)
    renamed: Dict[int, str] = {}
    for image in chosen:
        name = Path(image["file_name"]).as_posix().replace("/", "_")
        shutil.copyfile(synthetic / image["file_name"], target / name)
        renamed[image["id"]] = f"images/{SYNTHETIC_SUBDIR}/{name}"
    subset = {
        "images": [{**i, "file_name": renamed[i["id"]]} for i in chosen],
        "annotations": [a for a in coco["annotations"] if a["image_id"] in renamed],
        "categories": coco.get("categories", []),
    }
    write_yolo_split(bundle, "synthetic_chosen", subset, RIDER_PROFILE.class_order)
    return [str((bundle / renamed[i["id"]]).resolve()) for i in chosen]


def _write_arm(bundle: Path, arm: str, lines: Sequence[str]) -> None:
    arms = bundle / "arms"
    arms.mkdir(exist_ok=True)
    train_list = arms / f"{arm}.txt"
    train_list.write_text("\n".join(lines) + "\n", encoding="utf-8")
    names = {i: RIDER_PROFILE.classes[c] for i, c in enumerate(RIDER_PROFILE.class_order)}
    (arms / f"{arm}.yaml").write_text(
        data_yaml([train_list], bundle / "val.txt", names), encoding="utf-8"
    )


def build(  # pylint: disable=too-many-arguments,too-many-locals
    bundle: Path,
    synthetic: Path,
    images_zip: Path,
    labels_zip: Path,
    extra: int,
    sweep: Sequence[int],
    seed: int,
) -> Dict[str, Any]:
    """Write arms B, C, E (and the sweep) next to the headroom arms; returns image counts."""
    split = json.loads((bundle / "split.json").read_text(encoding="utf-8"))
    base = list(split["names"]["A"])
    seen = set(base) | set(split["validation"])
    with zipfile.ZipFile(labels_zip) as archive:
        order = shuffled_names(training_names(archive), seed)
    flags = read_rare_flags(labels_zip)
    pool = [n for n in order if n not in seen and flags[n]]
    sizes = sorted({extra, *sweep})
    if len(pool) < max(sizes):
        raise ValueError(f"only {len(pool)} real rare images in the pool, need {max(sizes)}")
    images_dir = bundle / "images" / SPLIT_PREFIX
    needed = [n for n in pool[: max(sizes)] if not (images_dir / f"{n}.jpg").exists()]
    extract_images(needed, images_zip, labels_zip, bundle)
    eval_set = load_bdd100k(
        bundle / "labels" / "100k" / "train",
        bundle / "images" / SPLIT_PREFIX,
        profile=RIDER_PROFILE,
    )
    write_yolo_split(
        bundle,
        "real_extra",
        subset_coco(eval_set, pool[: max(sizes)] + base),
        RIDER_PROFILE.class_order,
    )

    def real(names: Sequence[str]) -> List[str]:
        return [str((bundle / "images" / SPLIT_PREFIX / f"{n}.jpg").resolve()) for n in names]

    base_lines = real(base)
    by_id = {c["id"]: c["name"] for c in eval_set.coco["categories"]}
    stem = {i["id"]: Path(i["file_name"]).stem for i in eval_set.coco["images"]}
    have: Dict[str, Set[str]] = {n: set() for n in base}
    for annotation in eval_set.coco["annotations"]:
        name = stem[annotation["image_id"]]
        if name in have and not annotation["iscrowd"]:
            have[name].add(by_id[annotation["category_id"]])
    counts = repeat_counts(have, RARE_CATEGORIES, REPEAT_T_FACTOR, seed)
    synthetic_lines = import_synthetic(synthetic, bundle, seed, max(sizes))
    summary: Dict[str, Any] = {"seed": seed, "arms": {}}
    arms: Dict[str, List[str]] = {
        "C": [line for n, line in zip(base, base_lines) for _ in range(counts[n])]
    }
    for size in sizes:
        suffix = "" if size == extra else str(size)
        arms[f"B{suffix}"] = base_lines + real(pool[:size])
        arms[f"E{suffix}"] = base_lines + synthetic_lines[:size]
    for arm, lines in arms.items():
        _write_arm(bundle, arm, lines)
        summary["arms"][arm] = {"images": len(lines)}
    summary["repeat_t_factor"] = REPEAT_T_FACTOR
    summary["repeat_histogram"] = {
        str(k): sum(1 for v in counts.values() if v == k) for k in sorted(set(counts.values()))
    }
    (bundle / "synthetic_arms.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Parse arguments, build the arms, print the counts."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--synthetic", type=Path, required=True)
    parser.add_argument("--images-zip", type=Path, required=True)
    parser.add_argument("--labels-zip", type=Path, required=True)
    parser.add_argument("--extra", type=int, default=1000)
    parser.add_argument("--sweep", type=int, nargs="*", default=[250, 500])
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            build(
                args.bundle,
                args.synthetic,
                args.images_zip,
                args.labels_zip,
                args.extra,
                args.sweep,
                args.seed,
            ),
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
