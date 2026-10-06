"""Summarise per-box outcomes of trained arms over seeds (reading rule: hpc/README.md section 16).

    python bin/summarise_box_outcomes.py --results results
        --arms hpc_real25r hpc_rand25 hpc_v7p25 hpc_v8a25

For each class (default truck, bus) and arm, prints the share of real val boxes that were found,
mislabelled, found only at low confidence, or missed, overall and by size, averaged over the seeds
that exist, plus what the mislabelled boxes were called.
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

OUTCOMES = ("correct", "wrong_class", "low_confidence", "missed")
SLICES = ("all", "small", "medium", "large")


def load(results: Path, arm: str, confidence: str) -> List[Dict[str, Any]]:
    """The by_confidence entry of every seed's file for ``arm``."""
    runs = []
    for path in sorted(results.glob(f"{arm}_s*_box_outcomes.json")):
        runs.append(json.loads(path.read_text(encoding="utf-8"))["by_confidence"][confidence])
    return runs


def shares(runs: List[Dict[str, Any]], cls: str, part: str) -> Dict[str, float]:
    """Mean percent of boxes per outcome over seeds, plus the mean box count."""
    cells = [run[cls][part] for run in runs if cls in run and part in run[cls]]
    boxes = [c["boxes"] for c in cells if c["boxes"]]
    if not boxes:
        return {}
    out = {
        o: sum(100.0 * c[o] / c["boxes"] for c in cells if c["boxes"]) / len(boxes)
        for o in OUTCOMES
    }
    out["boxes"] = sum(boxes) / len(boxes)
    return out


def confused(runs: List[Dict[str, Any]], cls: str) -> str:
    """What the mislabelled boxes were called, as percent of mislabelled."""
    total: Counter[str] = Counter()
    for run in runs:
        total.update(run.get(cls, {}).get("all", {}).get("confused_as", {}))
    count = sum(total.values())
    return (
        ", ".join(f"{k} {100 * v / count:.0f}%" for k, v in total.most_common()) if count else "-"
    )


def main() -> None:
    """Print the outcome table of each requested class."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=Path("results"))
    parser.add_argument("--arms", nargs="+", required=True)
    parser.add_argument("--classes", nargs="+", default=["truck", "bus"])
    parser.add_argument("--confidence", default="0.25")
    args = parser.parse_args()

    for cls in args.classes:
        print(f"\n== {cls} (confidence {args.confidence}; % of real val boxes, mean over seeds) ==")
        print(
            f"{'arm':14s}{'seeds':>6s} {'slice':7s}{'boxes':>7s}"
            + "".join(f"{o:>16s}" for o in OUTCOMES)
        )
        for arm in args.arms:
            runs = load(args.results, arm, args.confidence)
            for part in SLICES:
                row = shares(runs, cls, part)
                if row:
                    label = arm if part == "all" else ""
                    seeds = str(len(runs)) if part == "all" else ""
                    print(
                        f"{label:14s}{seeds:>6s} {part:7s}{row['boxes']:7.0f}"
                        + "".join(f"{row[o]:15.1f}%" for o in OUTCOMES)
                    )
            if runs:
                print(f"{'':14s}  mislabelled as: {confused(runs, cls)}")


if __name__ == "__main__":
    main()
