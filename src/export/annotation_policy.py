"""Which projected objects become annotations, and under which class names.

Every visible object is projected, but a detection dataset should not contain labels no
detector could be expected to find: an object a few pixels tall is noise, and a class
absent from the real datasets the model will be tested on (buildings, for COCO-style
street data) only adds unverified labels. The policy drops those and counts what it
dropped; truncation and visible fraction stay on each annotation so a consumer can filter
further.

The size limits are design choices (no measured ground truth exists for "too small to
label"); they are recorded in the run manifest and can be changed per run.
"""

import dataclasses
from dataclasses import dataclass, field
from typing import Dict, Tuple

from src.export.coco_exporter import CocoFrame
from src.ground_truth.categories import COCO_PROFILE, CategoryProfile

MIN_BOX_HEIGHT_PX = 8.0
MIN_BOX_WIDTH_PX = 4.0
EXCLUDED_CLASS = "excluded_class"
TOO_SMALL = "too_small"


@dataclass(frozen=True)
class AnnotationPolicy:
    """The classes to export and the smallest box worth labelling."""

    profile: CategoryProfile = field(default=COCO_PROFILE)
    min_box_height_px: float = MIN_BOX_HEIGHT_PX
    min_box_width_px: float = MIN_BOX_WIDTH_PX

    def settings(self) -> Dict[str, object]:
        """The policy as plain values, for the run manifest."""
        return {
            "profile": self.profile.name,
            "min_box_height_px": self.min_box_height_px,
            "min_box_width_px": self.min_box_width_px,
        }


def apply_policy(frame: CocoFrame, policy: AnnotationPolicy) -> Tuple[CocoFrame, Dict[str, int]]:
    """``frame`` without the annotations the policy drops, and the count dropped per reason."""
    dropped = {EXCLUDED_CLASS: 0, TOO_SMALL: 0}
    kept = []
    for box in frame.bboxes_2d:
        bbox_3d = frame.bboxes_3d_by_id.get(box.object_id)
        if bbox_3d is not None and bbox_3d.category_id not in policy.profile.mapping:
            dropped[EXCLUDED_CLASS] += 1
        elif (
            box.y_max - box.y_min < policy.min_box_height_px
            or box.x_max - box.x_min < policy.min_box_width_px
        ):
            dropped[TOO_SMALL] += 1
        else:
            kept.append(box)
    return dataclasses.replace(frame, bboxes_2d=kept), dropped
