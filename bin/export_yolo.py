"""Write a split live dataset in the layout ultralytics trains from.

    PYTHONPATH=. python bin/split_dataset.py live_dataset/train2000
    PYTHONPATH=. python bin/export_yolo.py live_dataset/train2000

Creates ``labels/``, ``train.txt``, ``val.txt`` and ``data.yaml`` inside the dataset folder.
The images stay where they are.
"""

import argparse
import json
from pathlib import Path

from src.evaluation.yolo_export import write_yolo_dataset


def main() -> None:
    """Parse arguments, export, print the counts."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("dataset", type=Path)
    args = parser.parse_args()
    print(json.dumps(write_yolo_dataset(args.dataset)))
    print(f"data file: {(args.dataset / 'data.yaml').resolve()}")


if __name__ == "__main__":
    main()
