"""Per real ground-truth box of each class: did a trained detector find it, mislabel it, find it
only at low confidence, or miss it? (needs PyTorch + ultralytics)

    PYTHONPATH=. python bin/box_outcomes.py --weights runs/hpc_v7p25_s0/weights/best.pt \
        --labels data/bdd100k/labels/100k/val --images data/bdd100k/images/100k/val \
        --out results/hpc_v7p25_s0_box_outcomes.json

The detector is run once at a very low confidence; the outcomes are then counted at each of
``--confidences`` (0.25 and 0.10 by default). Results are broken down by box size and by BDD100K
time of day. The rules are in ``src/evaluation/box_outcomes.py``.
"""

import argparse
import json
from pathlib import Path

from src.evaluation.box_outcomes import box_outcomes, summarise
from src.evaluation.class_maps import BUS, CAR, PERSON, TRUCK
from src.evaluation.inference import run_detector
from src.evaluation.loaders import load_bdd100k


def main() -> None:
    """Parse arguments, detect, count outcomes and save."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True, help="BDD100K val labels")
    parser.add_argument("--images", type=Path, required=True, help="BDD100K val image folder")
    parser.add_argument("--confidences", type=float, nargs="+", default=[0.25, 0.10])
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--iou", type=float, default=0.6)
    parser.add_argument("--max-det", type=int, default=100)
    parser.add_argument("--max-images", type=int, default=None)
    parser.add_argument("--device", default="0")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    eval_set = load_bdd100k(args.labels, args.images)
    detections = run_detector(
        eval_set,
        args.weights,
        "ours",
        args.imgsz,
        0.001,
        args.iou,
        args.max_det,
        args.device,
        args.max_images,
    )
    if args.max_images is not None:
        kept = {image["id"] for image in eval_set.coco["images"][: args.max_images]}
        eval_set.coco["annotations"] = [
            a for a in eval_set.coco["annotations"] if a["image_id"] in kept
        ]
    conditions = {
        image["id"]: image["attributes"].get("timeofday", "undefined")
        for image in eval_set.coco["images"]
    }
    by_confidence = {
        str(confidence): summarise(
            box_outcomes(
                eval_set.coco["annotations"], detections, [PERSON, CAR, BUS, TRUCK], confidence
            ),
            conditions,
        )
        for confidence in args.confidences
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {"settings": {k: str(v) for k, v in vars(args).items()}, "by_confidence": by_confidence}
        ),
        encoding="utf-8",
    )
    for name, entry in by_confidence[str(args.confidences[0])].items():
        everything = entry["all"]
        print(
            f"{name}: {everything['boxes']} boxes, "
            + ", ".join(
                f"{o} {everything[o]}"
                for o in ("correct", "wrong_class", "low_confidence", "missed")
            )
        )


if __name__ == "__main__":
    main()
