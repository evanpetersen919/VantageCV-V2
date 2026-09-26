"""Turn a detector's raw output into COCO result dicts in this project's class ids.

Kept free of any deep-learning import so it can be tested without PyTorch: the evaluation
script passes in plain lists of boxes, confidences and class indices taken from whichever
detector produced them.

Two class spaces occur: a model trained on this project's export predicts indices 0..3 in
``yolo_export.CLASS_ORDER``; a COCO-pretrained model predicts COCO-80 indices, of which only
person, car, bus and truck are kept (``class_maps.COCO80_INDEX_TO_OURS``).
"""

from typing import Any, Dict, List, Sequence

from src.evaluation.class_maps import COCO80_INDEX_TO_OURS
from src.evaluation.yolo_export import CLASS_ORDER

CLASS_SPACES = ("ours", "coco80")


def boxes_to_detections(
    image_id: int,
    boxes_xyxy: Sequence[Sequence[float]],
    confidences: Sequence[float],
    class_indices: Sequence[int],
    class_space: str,
) -> List[Dict[str, Any]]:
    """COCO result dicts (``bbox`` as x, y, width, height) for one image.

    Predictions whose class has no counterpart in our four are dropped.
    """
    if class_space not in CLASS_SPACES:
        raise ValueError(f"class_space must be one of {CLASS_SPACES}, got {class_space!r}")
    detections = []
    for (x1, y1, x2, y2), confidence, index in zip(boxes_xyxy, confidences, class_indices):
        if class_space == "ours":
            category = CLASS_ORDER[int(index)] if 0 <= int(index) < len(CLASS_ORDER) else None
        else:
            category = COCO80_INDEX_TO_OURS.get(int(index))
        if category is None:
            continue
        detections.append(
            {
                "image_id": image_id,
                "category_id": category,
                "bbox": [float(x1), float(y1), float(x2 - x1), float(y2 - y1)],
                "score": float(confidence),
            }
        )
    return detections
