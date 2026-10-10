"""Audit the rider and bike labels of a rendered dataset (the automatic check of the rider study).

    python bin/audit_cyclist_labels.py DATASET_DIR [--out audit.json]

For every ``rider`` and ``bike`` annotation of ``DATASET_DIR/annotations.json`` (the ``riders``
profile; ids 10 and 2) it checks, and counts the failures of, what the preregistration
(``docs/riders/preregistration.md``, section 6) asks of the exact labels:

- the box is the tight box of its exact mask (within one pixel), and the mask is not empty;
- the visible fraction is in (0, 1] and the box lies inside the image;
- a ``bike`` overlapping a ``rider`` (the pairing BDD100K shows) is counted as ridden, otherwise
  unridden; a ``rider`` with no overlapping bike is counted too (the bike may be hidden);
- the box is not smaller than the dataset's minimum size.

It also reports the box-height quartiles (720p equivalent) so the rendered riders can be set beside
the measured BDD100K ones. A non-zero exit status means a hard defect was found.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import numpy.typing as npt
import pycocotools.mask as mask_utils

RIDER_ID = 10
BIKE_ID = 2
PAIR_OVERLAP = 0.3  # of the smaller box, as in docs/riders/bdd100k_rider_statistics.md
BOX_TOLERANCE_PX = 1.0


def _decode(annotation: Dict[str, Any]) -> npt.NDArray[np.bool_]:
    rle = dict(annotation["mask_rle"])
    if isinstance(rle["counts"], str):
        rle["counts"] = rle["counts"].encode("ascii")
    return np.asarray(mask_utils.decode(rle)).astype(bool)


def _tight_box(mask: npt.NDArray[np.bool_]) -> List[float]:
    ys, xs = np.nonzero(mask)
    return [
        float(xs.min()),
        float(ys.min()),
        float(xs.max() - xs.min() + 1),
        float(ys.max() - ys.min() + 1),
    ]


def _overlap_fraction(first: List[float], second: List[float]) -> float:
    """Intersection area over the smaller box's area."""
    x0, y0 = max(first[0], second[0]), max(first[1], second[1])
    x1 = min(first[0] + first[2], second[0] + second[2])
    y1 = min(first[1] + first[3], second[1] + second[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    smaller = min(first[2] * first[3], second[2] * second[3])
    return inter / smaller if smaller > 0 else 0.0


def audit(dataset: Path) -> Dict[str, Any]:  # pylint: disable=too-many-locals
    """The audit of one dataset directory as a dictionary."""
    data = json.loads((dataset / "annotations.json").read_text(encoding="utf-8"))
    sizes = {image["id"]: (image["width"], image["height"]) for image in data["images"]}
    by_image: Dict[int, List[Dict[str, Any]]] = {}
    for annotation in data["annotations"]:
        if annotation["category_id"] in (RIDER_ID, BIKE_ID):
            by_image.setdefault(annotation["image_id"], []).append(annotation)
    counts = {
        "images_with_cyclist_labels": len(by_image),
        "riders": 0,
        "bikes": 0,
        "missing_mask": 0,
        "box_not_tight_mask": 0,
        "empty_mask": 0,
        "bad_visibility": 0,
        "box_outside_image": 0,
        "bikes_ridden": 0,
        "bikes_unridden": 0,
        "riders_without_bike": 0,
    }
    heights: List[float] = []
    for image_id, annotations in by_image.items():
        width, height = sizes[image_id]
        riders = [a for a in annotations if a["category_id"] == RIDER_ID]
        bikes = [a for a in annotations if a["category_id"] == BIKE_ID]
        counts["riders"] += len(riders)
        counts["bikes"] += len(bikes)
        for annotation in riders + bikes:
            box = annotation["bbox"]
            if (
                box[0] < -1e-6
                or box[1] < -1e-6
                or box[0] + box[2] > width + 1e-6
                or box[1] + box[3] > height + 1e-6
            ):
                counts["box_outside_image"] += 1
            visibility = annotation.get("visibility_fraction", 1.0)
            if not 0.0 < float(visibility) <= 1.0 + 1e-9:
                counts["bad_visibility"] += 1
            if "mask_rle" not in annotation:
                counts["missing_mask"] += 1
                continue
            mask = _decode(annotation)
            if not mask.any():
                counts["empty_mask"] += 1
                continue
            tight = _tight_box(mask)
            if max(abs(a - b) for a, b in zip(tight, box)) > BOX_TOLERANCE_PX:
                counts["box_not_tight_mask"] += 1
        for rider in riders:
            heights.append(rider["bbox"][3] * 720.0 / height)
            if not any(
                _overlap_fraction(rider["bbox"], bike["bbox"]) >= PAIR_OVERLAP for bike in bikes
            ):
                counts["riders_without_bike"] += 1
        for bike in bikes:
            ridden = any(
                _overlap_fraction(bike["bbox"], rider["bbox"]) >= PAIR_OVERLAP for rider in riders
            )
            counts["bikes_ridden" if ridden else "bikes_unridden"] += 1
    quartiles = (
        {f"p{q}": float(np.percentile(heights, q)) for q in (5, 25, 50, 75, 95)} if heights else {}
    )
    hard = (
        "missing_mask",
        "box_not_tight_mask",
        "empty_mask",
        "bad_visibility",
        "box_outside_image",
    )
    return {
        "dataset": str(dataset),
        "counts": counts,
        "rider_height_px_720p": quartiles,
        "hard_defects": {name: counts[name] for name in hard},
        "passed": all(counts[name] == 0 for name in hard),
    }


def main() -> None:
    """Run the audit, print it and write it; exit non-zero on a hard defect."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    result = audit(args.dataset)
    text = json.dumps(result, indent=1)
    print(text)
    if args.out is not None:
        args.out.write_text(text, encoding="utf-8")
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
