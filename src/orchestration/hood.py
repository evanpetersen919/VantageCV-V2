"""A dark vehicle hood across the bottom of some frames, with the labels kept exact.

BDD100K and Cityscapes are dash-cam data: the car's own hood fills the bottom of many frames
(about a tenth of the height in the BDD100K night frames looked at), and a detector's
attention on real images peaks there (see ``EXPERIMENT_LOG.md``'s Grad-CAM entries). The
renders have no hood. This paints one over the finished PNG for the v7 profile and trims the
labels to match: a box that lies entirely under the hood is dropped and one that reaches into
it is cut at the hood's highest row, so the labels still describe what is visible.

How often a hood appears and how tall it is are disclosed starting values (half of the frames,
5-12% of the height), not measured shares.
"""

import dataclasses
from typing import Any, Dict, List, Optional

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from pycocotools import mask as mask_utils

from src.export.coco_exporter import CocoFrame
from src.ground_truth.bbox_2d import BoundingBox2D

HOOD_PROBABILITY = 0.5
HOOD_HEIGHT_FRACTION_RANGE = (0.05, 0.12)
# The hood's centre rises this fraction of the image height above its sides (a crowned edge).
HOOD_CROWN_FRACTION = 0.015


def hood_top_row(rng: np.random.Generator, image_height: int) -> Optional[int]:
    """The highest row of this frame's hood, or ``None`` when the frame has none."""
    if rng.random() >= HOOD_PROBABILITY:
        return None
    fraction = float(rng.uniform(*HOOD_HEIGHT_FRACTION_RANGE))
    return int(round(image_height * (1.0 - fraction)))


def _hood_luma(pixels: NDArray[np.float64], top_row: int, rng: np.random.Generator) -> float:
    """The hood's base brightness: 0.4 of the road region's mean (darker at night), jittered."""
    start = int(pixels.shape[0] * 0.6)
    scene_luma = float(pixels[start:top_row].mean()) if top_row > start else 60.0
    return float(np.clip(0.4 * scene_luma, 6.0, 70.0)) * float(rng.uniform(0.7, 1.3))


def hood_mask(top_row: int, size: tuple[int, int]) -> NDArray[np.bool_]:
    """The pixels ``paint_hood`` covers in a ``size`` = (width, height) frame."""
    width, height = size
    rows = np.arange(height, dtype=np.float64)[:, None]
    columns = np.linspace(-1.0, 1.0, width)[None, :]
    covered: NDArray[np.bool_] = rows >= top_row + HOOD_CROWN_FRACTION * height * columns**2
    return covered


def clip_exact_to_hood(frame: CocoFrame, top_row: int) -> CocoFrame:
    """``frame`` with every exact object mask trimmed to the pixels the hood leaves visible.

    The box becomes the tight extent of what remains, the visible fraction shrinks with the
    pixels lost, and an object with nothing left is dropped. Objects without an exact mask keep
    the crown-row cut of ``clip_to_hood``.
    """
    masks = dict(frame.masks_by_id)
    if not masks:
        return frame
    width = frame.camera.intrinsics.width
    height = frame.camera.intrinsics.height
    hood = hood_mask(top_row, (width, height))
    boxes: List[BoundingBox2D] = []
    for box in frame.bboxes_2d:
        rle = masks.get(box.object_id)
        if rle is None:
            boxes.append(box)
            continue
        visible = (
            mask_utils.decode({"size": rle["size"], "counts": rle["counts"].encode("ascii")}) > 0
        )
        before = int(visible.sum())
        visible &= ~hood
        after = int(visible.sum())
        if after == 0:
            masks.pop(box.object_id)
            continue
        rows, columns = np.nonzero(visible)
        encoded = mask_utils.encode(np.asfortranarray(visible.astype(np.uint8)))
        masks[box.object_id] = {
            "size": [int(v) for v in encoded["size"]],
            "counts": encoded["counts"].decode("ascii"),
        }
        boxes.append(
            dataclasses.replace(
                box,
                x_min=float(columns.min()),
                y_min=float(rows.min()),
                x_max=float(columns.max() + 1),
                y_max=float(rows.max() + 1),
                visible_fraction=box.visible_fraction * after / max(before, 1),
            )
        )
    return dataclasses.replace(frame, bboxes_2d=boxes, masks_by_id=masks)


def paint_hood(  # pylint: disable=too-many-locals
    image: Image.Image, top_row: int, rng: np.random.Generator
) -> Image.Image:
    """``image`` with a dark, slightly glossy hood below ``top_row`` (its crown) at the centre."""
    pixels = np.array(image.convert("RGB"), dtype=np.float64)
    height, width = pixels.shape[:2]
    scene_luma = (
        float(pixels[int(height * 0.6) : top_row].mean()) if top_row > height * 0.6 else 60.0
    )
    base = float(np.clip(0.4 * scene_luma, 6.0, 70.0)) * float(rng.uniform(0.7, 1.3))
    rows = np.arange(height, dtype=np.float64)[:, None]
    columns = np.linspace(-1.0, 1.0, width)[None, :]
    edge = top_row + HOOD_CROWN_FRACTION * height * columns**2
    depth = np.clip((rows - edge) / max(height - top_row, 1), 0.0, 1.0)
    # Brighter along the top edge (it reflects the sky), fading to dark at the frame's bottom.
    luma = base * (1.0 + 0.8 * (1.0 - depth) ** 3)
    hood = np.clip(luma + rng.normal(0.0, 1.5, size=(height, width)), 0.0, 255.0)
    covered = (rows >= edge)[..., None]
    tint = np.array([0.97, 1.0, 1.04])[None, None, :]
    pixels = np.where(covered, hood[..., None] * tint, pixels)
    return Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8), "RGB")


def clip_to_hood(frame: CocoFrame, top_row: int, min_height_px: float) -> CocoFrame:
    """``frame`` with every box cut at ``top_row``; boxes left shorter than ``min_height_px``
    (including those wholly under the hood) are dropped, and silhouettes are cut the same way."""
    kept = []
    for box in frame.bboxes_2d:
        if box.object_id in frame.masks_by_id:  # exact mask: trimmed by clip_exact_to_hood
            if box.y_max - box.y_min >= min_height_px:
                kept.append(box)
            continue
        if box.y_min >= top_row:
            continue
        clipped = dataclasses.replace(box, y_max=min(box.y_max, float(top_row)))
        if clipped.y_max - clipped.y_min >= min_height_px:
            kept.append(clipped)
    silhouettes: Dict[int, Any] = {
        object_id: np.column_stack(
            [np.asarray(polygon)[:, 0], np.minimum(np.asarray(polygon)[:, 1], top_row)]
        )
        for object_id, polygon in frame.silhouettes_by_id.items()
    }
    return dataclasses.replace(frame, bboxes_2d=kept, silhouettes_by_id=silhouettes)
