"""Build the YOLO ``data.yaml`` files for the cluster, from the uploaded dataset folders.

After untarring the data bundle on the cluster (see ``hpc/README.md``), the data root holds the
dataset folders with their original ``train.txt``/``val.txt`` (absolute paths from the machine
that made them). This re-roots those lists to the cluster's paths and writes three data files:

* ``synth_v5.yaml``   -- synthetic v5 only (train and validation both synthetic)
* ``real_control.yaml`` -- the real-only control (1,838 real BDD100K training images)
* ``mixed_real_v5.yaml`` -- real + synthetic training, validated on the real validation slice

    python bin/hpc_make_data.py --root /scratch/me/vantagecv_data --out /scratch/me/vantagecv_yaml
"""

import argparse
from pathlib import Path

from src.evaluation.portable import data_yaml, write_rerooted_lists

SYNTH_DIR = "train2000_v5"
REAL_DIR = "bdd100k_control"


def main() -> None:
    """Parse arguments, re-root both datasets' lists, write the three data files."""
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
    for name, content in files.items():
        (args.out / name).write_text(content, encoding="utf-8")
        print(f"wrote {args.out / name}")


if __name__ == "__main__":
    main()
