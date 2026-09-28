"""Re-export YOLO labels from the existing live_dataset split at a stricter visibility floor.

The original export kept any annotation with ``visibility_fraction >= 0.1`` (see
``src.ground_truth.occlusion.MIN_VISIBLE_FRACTION``), but the box itself is always the
object's full, un-occluded projected extent (see ``bbox_2d.py``) -- it is never shrunk to
the visible portion. That means an object 90% hidden behind another vehicle still gets a
box drawn as if fully visible. This re-exports ``train.json``/``val.json`` with a stricter
``--min-visible`` floor, overwriting the ``labels/`` folder and list files in place (the
source COCO JSON and images are untouched, so this is fully reversible by re-running with
``--min-visible 0.1``).

    PYTHONPATH=. python bin/refilter_labels.py --dataset live_dataset/train2000 --min-visible 0.5
"""

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Dict

from src.evaluation.yolo_export import write_data_yaml, write_yolo_split


def _filtered(coco: Dict[str, Any], min_visible: float) -> Dict[str, Any]:
    """``coco`` with annotations below ``min_visible`` removed."""
    kept = [a for a in coco["annotations"] if a.get("visibility_fraction", 1.0) >= min_visible]
    out = copy.copy(coco)
    out["annotations"] = kept
    return out


def main() -> None:
    """Parse arguments, re-filter both splits, print the before/after box counts."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--min-visible", type=float, required=True)
    args = parser.parse_args()

    counts = {}
    for side in ("train", "val"):
        coco = json.loads((args.dataset / f"{side}.json").read_text(encoding="utf-8"))
        before = len(coco["annotations"])
        filtered = _filtered(coco, args.min_visible)
        images, boxes = write_yolo_split(args.dataset, side, filtered)
        counts[side] = {"images": images, "boxes_before": before, "boxes_after": boxes}
    write_data_yaml(args.dataset)
    print(json.dumps(counts, indent=1))


if __name__ == "__main__":
    main()
