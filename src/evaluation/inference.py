"""Run a YOLO detector over a benchmark's images and return COCO detections (needs ultralytics).

Shared by the scoring script (``bin/evaluate_detector.py``) and the per-box outcome check
(``bin/box_outcomes.py``), so both see exactly the same predictions.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from src.evaluation.detections import boxes_to_detections
from src.evaluation.loaders import EvalSet

BATCH_SIZE = 16


def run_detector(  # pylint: disable=too-many-arguments,too-many-locals
    eval_set: EvalSet,
    weights: Path,
    class_space: str,
    imgsz: int,
    conf: float,
    iou: float,
    max_det: int,
    device: str,
    max_images: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """COCO detections of ``weights`` over the benchmark's images (the first ``max_images``)."""
    from ultralytics import YOLO  # pylint: disable=import-outside-toplevel,import-error

    model = YOLO(str(weights))
    images = eval_set.coco["images"][:max_images]
    detections: List[Dict[str, Any]] = []
    for start in range(0, len(images), BATCH_SIZE):
        batch = images[start : start + BATCH_SIZE]
        results = model.predict(
            [str(eval_set.image_path(image)) for image in batch],
            imgsz=imgsz,
            conf=conf,
            iou=iou,
            max_det=max_det,
            device=device,
            verbose=False,
        )
        for image, result in zip(batch, results):
            boxes = result.boxes
            detections += boxes_to_detections(
                image["id"],
                boxes.xyxy.cpu().tolist(),
                boxes.conf.cpu().tolist(),
                boxes.cls.cpu().tolist(),
                class_space,
            )
    return detections
