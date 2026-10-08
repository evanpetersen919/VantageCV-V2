"""Labels taken from what the engine actually draws, not from proxy shapes.

After a frame is photographed, the game is asked (``CaptureObjectMasks``) to render the scene's
depth once and
each labelled object alone. An object's visible pixels are those where its own depth equals the
full-scene
depth (nothing nearer hides it); its full extent is wherever it renders at all. From that:

* the 2D box is the exact extent of the visible pixels (this project's modal convention: only the
  part that can
  be seen, as in BDD100K and Cityscapes), with no proxy shape or measured pose extent involved;
* an object with no visible pixel is dropped (the engine says it is hidden or out of frame);
* ``visible_fraction`` is visible pixels over the object's full in-frame pixels, an exact
  occlusion measure;
* the visible mask is kept, run-length encoded, as the annotation's ``mask_rle``.

What it does not change: truncation (still from geometry), 3D boxes, and the hull polygon in
``segmentation``,
which stays as an approximation. The class and id of every object come from the scenario as before.
"""

import dataclasses
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import numpy.typing as npt
from pycocotools import mask as mask_utils

from src.export.coco_exporter import CocoFrame
from src.ground_truth.bbox_2d import BoundingBox2D
from src.orchestration.live_render import vertical_fov_deg


@dataclasses.dataclass
class ExactLabels:
    """The engine's answer for one frame."""

    visible_map: npt.NDArray[np.uint16]  # 0 = none, k + 1 = the k-th requested object
    order: List[int]  # label object id of each requested object, in request order
    reports: List[Dict[str, Any]]  # one per requested object


async def capture_exact(
    backend: Any,
    members: Dict[int, List[int]],
    frame: CocoFrame,
    size: Tuple[int, int],
    scratch: Path,
) -> Optional[ExactLabels]:
    """Ask the game for the exact masks of every labelled object of ``frame`` that it can find.

    ``members`` maps a label object id to the payload asset indices of its actors. The game
    must still
    be at the camera pose the frame was photographed from. Returns None if there is nothing to
    ask for.
    """
    order = [box.object_id for box in frame.bboxes_2d if box.object_id in members]
    if not order:
        return None
    scratch.parent.mkdir(parents=True, exist_ok=True)
    reply = await backend.call(
        "CaptureObjectMasks",
        {
            "out_path": str(scratch.resolve()),
            "objects": [members[object_id] for object_id in order],
            "width": size[0],
            "height": size[1],
            "vertical_fov_deg": vertical_fov_deg(),
        },
    )
    visible = np.fromfile(scratch, dtype="<u2").reshape(reply["height"], reply["width"])
    scratch.unlink(missing_ok=True)
    return ExactLabels(visible, order, reply["objects"])


def apply_exact(frame: CocoFrame, exact: ExactLabels) -> CocoFrame:
    """``frame`` with the exact boxes, visible fractions and masks in place of the geometric ones.

    Objects the game had no actor for keep their geometric label; objects with no visible
    pixel are dropped.
    """
    position = {object_id: k for k, object_id in enumerate(exact.order)}
    boxes: List[BoundingBox2D] = []
    masks: Dict[int, Dict[str, Any]] = dict(frame.masks_by_id)
    for box in frame.bboxes_2d:
        k = position.get(box.object_id)
        report = exact.reports[k] if k is not None and k < len(exact.reports) else None
        if k is None or report is None or report.get("actors_found", 0) == 0:
            boxes.append(box)
            continue
        visible_px = report.get("visible_px", 0)
        if visible_px == 0:
            continue
        x0, y0, x1, y1 = report["visible_bbox"]
        boxes.append(
            BoundingBox2D(
                object_id=box.object_id,
                x_min=float(x0),
                y_min=float(y0),
                x_max=float(x1 + 1),
                y_max=float(y1 + 1),
                visibility=box.visibility,
                visible_fraction=visible_px / max(report["amodal_px"], 1),
                truncation=box.truncation,
            )
        )
        encoded = mask_utils.encode(
            np.asfortranarray((exact.visible_map == k + 1).astype(np.uint8))
        )
        masks[box.object_id] = {
            "size": [int(v) for v in encoded["size"]],
            "counts": encoded["counts"].decode("ascii"),
        }
    return dataclasses.replace(frame, bboxes_2d=boxes, masks_by_id=masks)
