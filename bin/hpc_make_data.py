"""Build the YOLO ``data.yaml`` files for the cluster, from the uploaded dataset folders.

After untarring the data bundle on the cluster (see ``hpc/README.md``), the data root holds the
dataset folders with their original ``train.txt``/``val.txt`` (absolute paths from the machine
that made them). This re-roots those lists to the cluster's paths and writes the data files
below. Every file validates on the same 199 real images, so scores are comparable across them.

* ``synth_v5.yaml``      -- synthetic v5 only (validated on synthetic validation images)
* ``real_control.yaml``  -- the real-only control (1,838 real BDD100K training images)
* ``mixed_real_v5.yaml`` -- those real images + the 1,838 synthetic v5 images
* ``real_3676.yaml``     -- real only, 3,676 images (the control + an extra disjoint 1,838), the
  data-volume match for the mixed set (written only if ``bdd100k_control_extra`` is present)
* ``real_25pct.yaml`` / ``real_50pct.yaml`` -- 25% / 50% of the control's training images
* ``mixed_25pct.yaml`` / ``mixed_50pct.yaml`` -- those fractions + all 1,838 synthetic images
* ``mixed_big.yaml`` / ``mixed_25pct_big.yaml`` / ``mixed_50pct_big.yaml`` -- the same real data +
  both synthetic batches (v5 and v5b, 3,691 images; written only if ``train2000_v5b`` is present)
* ``mixed_25pct_notb.yaml`` / ``mixed_25pct_rand.yaml`` -- 25% real + the synthetic images with
  no truck or bus (both batches), vs 25% real + the same number of randomly chosen synthetic
  images (written only if ``train2000_v5b`` is present): do synthetic trucks/buses carry the gain?
* ``mixed_25pct_poor.yaml`` / ``mixed_25pct_rich.yaml`` -- 25% real + 510 of the v5/v5b images
  chosen for few persons and trucks (about the supply of the v7 batch) or for many persons, trucks
  and buses; written only if ``train2000_v5b`` is present
* ``mixed_modal.yaml`` / ``mixed_25pct_modal.yaml`` -- the same v5 images with visible-part labels
  (``train2000_v5_modal``: boxes cover only what can be seen of a partly hidden object), at 100%
  and 25% real; written only if that folder is present
* ``mixed_25pct_v7a.yaml`` (and ``_v7c``, ``_v7p``, ``_v8a``, ``_v8b``, ``_v9a``, ``_v10n``) --
  25% real + a 512-image v7 to v10 batch
  (``train_v7a``: train and val frames together, 972 images in all, the size of
  ``mixed_25pct_rand``); each is written only if its folder is present
* ``mixed_25pct_realism.yaml`` -- 25% real + the v5 synthetic images after the calibrated realism
  post-process (``train2000_v5_realism``; written only if that folder is present)

    python bin/hpc_make_data.py --root /scratch/me/vantagecv_data --out /scratch/me/vantagecv_yaml
"""

import argparse
from pathlib import Path
from typing import Dict, List

from src.evaluation.portable import (
    data_yaml,
    write_class_free_list,
    write_fraction_list,
    write_random_list,
    write_ranked_list,
    write_rerooted_lists,
)

SYNTH_DIR = "train2000_v5"
REAL_DIR = "bdd100k_control"
EXTRA_DIR = "bdd100k_control_extra"
SYNTH_B_DIR = "train2000_v5b"
REALISM_DIR = "train2000_v5_realism"
MODAL_DIR = "train2000_v5_modal"
BATCHES = (
    "v7a",
    "v7c",
    "v7p",
    "v8a",
    "v8b",
    "v9a",
    "v10n",
)  # train_<name> folders (v7 and v8 log entries)
FRACTIONS = (25, 50)
TRUCK_BUS = {2, 3}  # class ids of bus and truck in this project's four classes
PERSON, BUS, TRUCK = 0, 2, 3
SUPPLY_COUNT = 510
# Fewest persons and trucks first (a truck counts 1.6: the weight at which the choice reproduces
# the v7 batch's 508 persons and 209 trucks to within 8%), and the most persons, trucks and buses.
POOR_WEIGHTS = {PERSON: 1.0, TRUCK: 1.6}
RICH_WEIGHTS = {PERSON: 1.0, TRUCK: 1.0, BUS: 3.0}
POOL_SEED = 0


def _truck_bus_files(
    out: Path, real: Dict[str, Path], batches: List[Dict[str, Path]]
) -> Dict[str, str]:
    """25% real + the synthetic images without a truck or bus, and + as many random ones."""
    pool = [batch["train"] for batch in batches]
    no_tb = write_class_free_list(pool, TRUCK_BUS, out / "synth_no_truck_bus_train.txt")
    count = len(no_tb.read_text(encoding="utf-8").split())
    rand = write_random_list(pool, count, POOL_SEED, out / "synth_random_train.txt")
    quarter = out / f"{REAL_DIR}_25pct_train.txt"
    return {
        "mixed_25pct_notb.yaml": data_yaml([quarter, no_tb], real["val"]),
        "mixed_25pct_rand.yaml": data_yaml([quarter, rand], real["val"]),
    }


def _supply_files(
    out: Path, real: Dict[str, Path], batches: List[Dict[str, Path]]
) -> Dict[str, str]:
    """25% real + 510 images chosen for a poor or a rich supply of persons, trucks and buses."""
    pool = [batch["train"] for batch in batches]
    poor = write_ranked_list(pool, POOR_WEIGHTS, SUPPLY_COUNT, out / "synth_poor_train.txt", False)
    rich = write_ranked_list(pool, RICH_WEIGHTS, SUPPLY_COUNT, out / "synth_rich_train.txt")
    quarter = out / f"{REAL_DIR}_25pct_train.txt"
    return {
        "mixed_25pct_poor.yaml": data_yaml([quarter, poor], real["val"]),
        "mixed_25pct_rich.yaml": data_yaml([quarter, rich], real["val"]),
    }


def _v7_batch_files(root: Path, out: Path, real: Dict[str, Path]) -> Dict[str, str]:
    """25% real + each batch folder that is present (``train_v7a``, ``train_v8a``, ...)."""
    files: Dict[str, str] = {}
    quarter = out / f"{REAL_DIR}_25pct_train.txt"
    for name in BATCHES:
        folder = f"train_{name}"
        if (root / folder).is_dir():
            batch = write_rerooted_lists(root / folder, root / folder, out)
            files[f"mixed_25pct_{name}.yaml"] = data_yaml(
                [quarter, batch["train"], batch["val"]], real["val"]
            )
    return files


def main() -> None:
    """Parse arguments, re-root the datasets' lists, write the data files."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--root", type=Path, required=True, help="folder holding the datasets")
    parser.add_argument("--out", type=Path, required=True, help="where to write the data files")
    args = parser.parse_args()

    synth = write_rerooted_lists(args.root / SYNTH_DIR, args.root / SYNTH_DIR, args.out)
    real = write_rerooted_lists(args.root / REAL_DIR, args.root / REAL_DIR, args.out)

    files = {
        "synth_v5.yaml": data_yaml([synth["train"]], synth["val"]),
        "real_control.yaml": data_yaml([real["train"]], real["val"]),
        "mixed_real_v5.yaml": data_yaml([real["train"], synth["train"]], real["val"]),
    }
    if (args.root / EXTRA_DIR).is_dir():
        extra = write_rerooted_lists(args.root / EXTRA_DIR, args.root / EXTRA_DIR, args.out)
        files["real_3676.yaml"] = data_yaml([real["train"], extra["train"]], real["val"])
    synth_b = None
    if (args.root / SYNTH_B_DIR).is_dir():
        synth_b = write_rerooted_lists(args.root / SYNTH_B_DIR, args.root / SYNTH_B_DIR, args.out)
        files["mixed_big.yaml"] = data_yaml(
            [real["train"], synth["train"], synth_b["train"]], real["val"]
        )
    for percent in FRACTIONS:
        subset = write_fraction_list(
            real["train"], percent / 100.0, args.out / f"{REAL_DIR}_{percent}pct_train.txt"
        )
        files[f"real_{percent}pct.yaml"] = data_yaml([subset], real["val"])
        files[f"mixed_{percent}pct.yaml"] = data_yaml([subset, synth["train"]], real["val"])
        if synth_b is not None:
            files[f"mixed_{percent}pct_big.yaml"] = data_yaml(
                [subset, synth["train"], synth_b["train"]], real["val"]
            )

    if synth_b is not None:
        files.update(_truck_bus_files(args.out, real, [synth, synth_b]))
        files.update(_supply_files(args.out, real, [synth, synth_b]))
    if (args.root / REALISM_DIR).is_dir():
        processed = write_rerooted_lists(args.root / REALISM_DIR, args.root / REALISM_DIR, args.out)
        quarter = args.out / f"{REAL_DIR}_25pct_train.txt"
        files["mixed_25pct_realism.yaml"] = data_yaml([quarter, processed["train"]], real["val"])

    if (args.root / MODAL_DIR).is_dir():
        modal = write_rerooted_lists(args.root / MODAL_DIR, args.root / MODAL_DIR, args.out)
        quarter = args.out / f"{REAL_DIR}_25pct_train.txt"
        files["mixed_modal.yaml"] = data_yaml([real["train"], modal["train"]], real["val"])
        files["mixed_25pct_modal.yaml"] = data_yaml([quarter, modal["train"]], real["val"])

    files.update(_v7_batch_files(args.root, args.out, real))

    for name, content in files.items():
        (args.out / name).write_text(content, encoding="utf-8")
        print(f"wrote {args.out / name}")


if __name__ == "__main__":
    main()
