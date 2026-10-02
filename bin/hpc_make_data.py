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

    python bin/hpc_make_data.py --root /scratch/me/vantagecv_data --out /scratch/me/vantagecv_yaml
"""

import argparse
from pathlib import Path

from src.evaluation.portable import data_yaml, write_fraction_list, write_rerooted_lists

SYNTH_DIR = "train2000_v5"
REAL_DIR = "bdd100k_control"
EXTRA_DIR = "bdd100k_control_extra"
FRACTIONS = (25, 50)


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
    for percent in FRACTIONS:
        subset = write_fraction_list(
            real["train"], percent / 100.0, args.out / f"{REAL_DIR}_{percent}pct_train.txt"
        )
        files[f"real_{percent}pct.yaml"] = data_yaml([subset], real["val"])
        files[f"mixed_{percent}pct.yaml"] = data_yaml([subset, synth["train"]], real["val"])

    for name, content in files.items():
        (args.out / name).write_text(content, encoding="utf-8")
        print(f"wrote {args.out / name}")


if __name__ == "__main__":
    main()
