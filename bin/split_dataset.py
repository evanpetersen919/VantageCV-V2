"""Split a live dataset into train and validation sets by scenario.

    PYTHONPATH=. python bin/split_dataset.py live_dataset/train2000 --val-fraction 0.1

Writes ``train.json``, ``val.json`` and ``split.json`` next to ``annotations.json``. Whole
scenarios go to one side, so near-duplicate frames of one scene never straddle the split.
"""

import argparse
import json
from pathlib import Path

from src.evaluation.split import write_split


def main() -> None:
    """Parse arguments, split, print the summary."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--val-fraction", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    summary = write_split(args.dataset, args.val_fraction, args.seed)
    for side in ("train", "val"):
        print(side, json.dumps(summary[side]))


if __name__ == "__main__":
    main()
