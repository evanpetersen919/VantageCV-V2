"""Score a detector on a real benchmark (needs PyTorch + ultralytics).

Runs the model over the benchmark's images, converts its output to COCO detections in our
four classes, and scores them with COCO's evaluation, overall and per class and condition.

    PYTHONPATH=. python bin/evaluate_detector.py --weights runs/synthetic_scratch/weights/best.pt \\
        --class-space ours --benchmark bdd100k --labels F:/datasets/bdd100k/labels/det_val.json \\
        --images F:/datasets/bdd100k/images/100k/val --out results/synthetic_scratch_bdd.json

``--class-space ours`` is for a model trained on this project's export; ``coco80`` is for a
COCO-pretrained model (person, car, bus, truck are kept, everything else discarded).
Use ``--max-images`` for a quick smoke test; the number of images is stored in the results.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from src.evaluation.detections import CLASS_SPACES, boxes_to_detections
from src.evaluation.loaders import EvalSet, load_bdd100k, load_cityscapes
from src.evaluation.scoring import ScoreReport, format_report, score

BATCH_SIZE = 16


def _load(args: argparse.Namespace) -> EvalSet:
    """The benchmark's ground truth."""
    if args.benchmark == "bdd100k":
        return load_bdd100k(args.labels, args.images)
    return load_cityscapes(args.cityscapes_root, args.split)


def _detect(eval_set: EvalSet, args: argparse.Namespace) -> List[Dict[str, Any]]:
    """Run the model over the benchmark images."""
    from ultralytics import YOLO  # pylint: disable=import-outside-toplevel,import-error

    model = YOLO(str(args.weights))
    images = eval_set.coco["images"][: args.max_images]
    detections: List[Dict[str, Any]] = []
    for start in range(0, len(images), BATCH_SIZE):
        batch = images[start : start + BATCH_SIZE]
        results = model.predict(
            [str(eval_set.image_path(image)) for image in batch],
            imgsz=args.imgsz,
            conf=args.conf,
            iou=args.iou,
            max_det=args.max_det,
            device=args.device,
            verbose=False,
        )
        for image, result in zip(batch, results):
            boxes = result.boxes
            detections += boxes_to_detections(
                image["id"],
                boxes.xyxy.cpu().tolist(),
                boxes.conf.cpu().tolist(),
                boxes.cls.cpu().tolist(),
                args.class_space,
            )
    return detections


def _summary(report: ScoreReport) -> Dict[str, Any]:
    """The report as plain values for the results file."""

    def scores(one: Any) -> Dict[str, Any]:
        return {
            "images": one.images,
            "overall": one.overall,
            "per_class_ap": one.per_class_ap,
            "per_class_ap50": one.per_class_ap50,
            "ground_truth_boxes": one.ground_truth_boxes,
        }

    return {
        "overall": scores(report.overall),
        "by_condition": {name: scores(one) for name, one in report.by_condition.items()},
    }


def main() -> None:
    """Parse arguments, detect, score, print and save."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--class-space", choices=CLASS_SPACES, required=True)
    parser.add_argument("--benchmark", choices=["bdd100k", "cityscapes"], required=True)
    parser.add_argument("--labels", type=Path, help="BDD100K label JSON")
    parser.add_argument("--images", type=Path, help="BDD100K image folder")
    parser.add_argument("--cityscapes-root", type=Path)
    parser.add_argument("--split", default="val")
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--conf", type=float, default=0.001)
    parser.add_argument("--iou", type=float, default=0.6)
    parser.add_argument("--max-det", type=int, default=300)
    parser.add_argument("--max-images", type=int, default=None)
    parser.add_argument("--device", default="0")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    eval_set = _load(args)
    detections = _detect(eval_set, args)
    evaluated = {d["image_id"] for d in detections}
    if args.max_images is not None:
        eval_set.coco["images"] = eval_set.coco["images"][: args.max_images]
        kept = {image["id"] for image in eval_set.coco["images"]}
        eval_set.coco["annotations"] = [
            a for a in eval_set.coco["annotations"] if a["image_id"] in kept
        ]
    report = score(eval_set, detections)
    print(format_report(report))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "settings": {k: str(v) for k, v in vars(args).items()},
                "benchmark_counts": eval_set.counts(),
                "images_with_detections": len(evaluated),
                **_summary(report),
            }
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
