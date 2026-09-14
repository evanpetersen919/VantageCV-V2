"""Dataset-wide sanity checks and statistics.

Implements MASTER_PROMPT Section 3.7's "Dataset statistics reporting"
bullet and Section 1.1's "Sanity Checker (basic invariants)" architecture
entry, informed by QOL_RESEARCH_CHECKLIST.md Section H.2's dataset-
consistency checks.

Section H.2's own example test compares annotation *class* distribution
against ``config.vehicle_mix`` -- this codebase generates no vehicles
(see KNOWN_GAPS_AND_ISSUES.md), so the closest genuinely-applicable
analogue here is comparing generated *building height* distribution
against ``config.building_heights``, which this module does instead.
"""

from dataclasses import dataclass
from typing import List, Sequence, Tuple

import numpy as np
import pandas as pd

from src.export.coco_exporter import CocoFrame
from src.procedural.scenario import ScenarioTypeConfig


@dataclass
class SanityReport:
    """Result of running sanity checks against one dataset (a list of
    exported COCO frames)."""

    num_frames: int
    num_annotations: int
    annotation_counts_per_frame: List[int]
    mean_annotations_per_frame: float
    std_annotations_per_frame: float
    outlier_frame_ids: List[int]

    @property
    def is_healthy(self) -> bool:
        """True iff no frame's annotation count is a statistical outlier."""
        return not self.outlier_frame_ids


def check_annotation_count_consistency(frames: List[CocoFrame]) -> SanityReport:
    """Check that annotation counts don't vary wildly frame-to-frame.

    Parameters
    ----------
    frames : List[CocoFrame]

    Returns
    -------
    SanityReport
    """
    return check_annotation_count_consistency_from_counts(
        [(frame.image_id, len(frame.bboxes_2d)) for frame in frames]
    )


def check_annotation_count_consistency_from_counts(
    image_id_and_count: Sequence[Tuple[int, int]],
) -> SanityReport:
    """Lower-level counterpart to ``check_annotation_count_consistency``
    that works from plain ``(image_id, annotation_count)`` pairs instead
    of full ``CocoFrame`` objects.

    Exists so callers that only have already-exported COCO data on hand
    (e.g. ``resume_handler.py``, which reconstructs a dataset from
    per-scenario JSON parts rather than holding live ``CocoFrame``
    objects) can run this check without fabricating fake frame objects
    just to satisfy the frame-based signature.

    A frame is flagged as an outlier if its annotation count deviates
    from the dataset mean by more than 3 standard deviations --
    QOL_RESEARCH_CHECKLIST.md Section H.2's own threshold.
    """
    if not image_id_and_count:
        return SanityReport(
            num_frames=0,
            num_annotations=0,
            annotation_counts_per_frame=[],
            mean_annotations_per_frame=0.0,
            std_annotations_per_frame=0.0,
            outlier_frame_ids=[],
        )

    image_ids = [image_id for image_id, _ in image_id_and_count]
    counts = [count for _, count in image_id_and_count]

    series = pd.Series(counts)
    mean = float(series.mean())
    std = float(series.std(ddof=0))

    outlier_frame_ids = [
        image_id
        for image_id, count in zip(image_ids, counts)
        if std > 0 and abs(count - mean) > 3 * std
    ]

    return SanityReport(
        num_frames=len(image_id_and_count),
        num_annotations=int(series.sum()),
        annotation_counts_per_frame=counts,
        mean_annotations_per_frame=mean,
        std_annotations_per_frame=std,
        outlier_frame_ids=outlier_frame_ids,
    )


def check_building_height_distribution(
    building_heights: List[float], config: ScenarioTypeConfig, tolerance: float = 0.15
) -> bool:
    """Check that generated building heights are plausible relative to
    ``config.building_heights``.

    Every height must fall within the configured [min, max] range
    (buildings are sampled from `self.rng.uniform(*self.config
    .building_heights)` in ``building_placement.py``, so this should
    always hold by construction -- this check exists to catch a future
    regression, not because it's expected to ever fail today), and the
    empirical mean must be within ``tolerance`` (relative) of the
    theoretical mean of a uniform distribution over that range.

    Parameters
    ----------
    building_heights : List[float]
        Heights of every building in the dataset (across all scenarios).
    config : ScenarioTypeConfig
    tolerance : float
        Allowed relative deviation of the empirical mean from the
        theoretical uniform-distribution mean.

    Returns
    -------
    bool
        True iff every height is in range and the mean is within
        tolerance.
    """
    if not building_heights:
        return True

    min_height, max_height = config.building_heights
    heights = np.array(building_heights)

    if not ((heights >= min_height) & (heights <= max_height)).all():
        return False

    expected_mean = (min_height + max_height) / 2.0
    actual_mean = float(heights.mean())
    relative_error = abs(actual_mean - expected_mean) / expected_mean

    return relative_error <= tolerance
