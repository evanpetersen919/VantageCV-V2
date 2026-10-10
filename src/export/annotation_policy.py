"""Which projected objects become annotations, and under which class names.

Every visible object is projected, but a detection dataset should not contain labels no
detector could be expected to find: an object a few pixels tall is noise, and a class
absent from the real datasets the model will be tested on (buildings, for COCO-style
street data) only adds unverified labels. The policy drops those and counts what it
dropped; truncation and visible fraction stay on each annotation so a consumer can filter
further.

The size limits are design choices (no measured ground truth exists for "too small to
label"); they are recorded in the run manifest and can be changed per run.

``max_distance_m`` exists for a different, measured reason: our streets are long and
mostly unobstructed, so one frame's annotations include not just the nearby traffic a
detector needs but also everything visible far down the road -- these numerically
dominate a class's training boxes and skew them toward "small and distant" relative to
BDD100K/Cityscapes, whose shorter real sightlines naturally cut off how many distant
instances appear per frame. The values below were fit, per class, against both real
benchmarks: for a candidate cutoff, keep only objects within that 3D distance of the
camera and take the median box height as a fraction of image height; the chosen cutoff is
the one whose predicted fraction is closest (in log space) to the two benchmarks' own
measured median (see ``bin/fit_max_annotation_distance.py``). Pedestrians need a much
tighter cutoff than vehicles because they sit laterally offset on the sidewalk, not along
the camera's forward axis, so straight-line distance grows faster for them per metre of
actual road progress.
"""

import dataclasses
from dataclasses import dataclass, field
from typing import Dict, Tuple

import numpy as np

from src.export.coco_exporter import CocoFrame
from src.ground_truth.categories import (
    BICYCLE,
    BUS,
    COCO_PROFILE,
    PEDESTRIAN,
    RIDER,
    SEDAN,
    SUV,
    TRUCK,
    CategoryProfile,
)

MIN_BOX_HEIGHT_PX = 8.0
MIN_BOX_WIDTH_PX = 4.0
EXCLUDED_CLASS = "excluded_class"
TOO_SMALL = "too_small"
TOO_FAR = "too_far"

# Fit against BDD100K + Cityscapes median box-height fractions; see the module docstring.
MAX_DISTANCE_M: Dict[int, float] = {
    PEDESTRIAN: 30.0,
    # Rider and bike: the distance at which a 1.64 m rider box is BDD100K's measured 5th-percentile
    # height (15.97 px at 720p, 73.74 degree vertical field): 480 px * 1.64 m / 15.97 px = 49.3 m,
    # rounded to 50 m (docs/riders/preregistration.md, amendment 3). Only the riders profile
    # exports these classes.
    RIDER: 50.0,
    BICYCLE: 50.0,
    SEDAN: 54.0,
    SUV: 54.0,
    BUS: 41.0,
    TRUCK: 53.0,
}


@dataclass(frozen=True)
class AnnotationPolicy:
    """The classes to export, the smallest box worth labelling, and the farthest."""

    profile: CategoryProfile = field(default=COCO_PROFILE)
    min_box_height_px: float = MIN_BOX_HEIGHT_PX
    min_box_width_px: float = MIN_BOX_WIDTH_PX
    max_distance_m: Dict[int, float] = field(default_factory=lambda: dict(MAX_DISTANCE_M))

    def settings(self) -> Dict[str, object]:
        """The policy as plain values, for the run manifest.

        ``max_distance_m``'s keys become strings: a JSON round-trip through the manifest
        file does that anyway (JSON object keys are always strings), so a freshly computed
        settings dict must match that shape too, or a resumed run would see its own,
        unchanged policy as "different settings" forever (``DatasetStore.check_manifest``
        compares the two directly).
        """
        return {
            "profile": self.profile.name,
            "min_box_height_px": self.min_box_height_px,
            "min_box_width_px": self.min_box_width_px,
            # only the classes the profile exports can matter (later-added classes, such as the
            # rider and bicycle cutoffs, must not change the identity of a coco or fine run)
            "max_distance_m": {
                str(k): v for k, v in self.max_distance_m.items() if k in self.profile.mapping
            },
        }


def apply_policy(frame: CocoFrame, policy: AnnotationPolicy) -> Tuple[CocoFrame, Dict[str, int]]:
    """``frame`` without the annotations the policy drops, and the count dropped per reason."""
    dropped = {EXCLUDED_CLASS: 0, TOO_SMALL: 0, TOO_FAR: 0}
    origin = frame.camera.extrinsics.get_translation_vector()
    kept = []
    for box in frame.bboxes_2d:
        bbox_3d = frame.bboxes_3d_by_id.get(box.object_id)
        max_distance = (
            policy.max_distance_m.get(bbox_3d.category_id) if bbox_3d is not None else None
        )
        distance = float(np.linalg.norm(bbox_3d.center - origin)) if bbox_3d is not None else 0.0
        if bbox_3d is not None and bbox_3d.category_id not in policy.profile.mapping:
            dropped[EXCLUDED_CLASS] += 1
        elif (
            box.y_max - box.y_min < policy.min_box_height_px
            or box.x_max - box.x_min < policy.min_box_width_px
        ):
            dropped[TOO_SMALL] += 1
        elif max_distance is not None and distance > max_distance:
            dropped[TOO_FAR] += 1
        else:
            kept.append(box)
    return dataclasses.replace(frame, bboxes_2d=kept), dropped
