"""Tests for the annotation policy, class profiles and truncation."""

from pathlib import Path
from typing import List

import numpy as np
import pytest

from src.export.annotation_policy import EXCLUDED_CLASS, TOO_SMALL, AnnotationPolicy, apply_policy
from src.export.coco_exporter import CocoFrame, export_coco
from src.ground_truth.bbox_2d import BoundingBox2D, project_bbox_3d_to_2d
from src.ground_truth.bbox_3d import BoundingBox3D
from src.ground_truth.categories import (
    BUILDING,
    BUS,
    COCO_PROFILE,
    FINE_PROFILE,
    PEDESTRIAN,
    SEDAN,
    SUV,
    TRUCK,
)
from src.orchestration.dataset_store import DatasetStore
from src.orchestration.live_render import ue_camera


def _frame(categories: List[int], heights_px: List[float]) -> CocoFrame:
    """A frame with one box per (category, height): 3D boxes are placeholders."""
    camera = ue_camera(np.zeros(3), np.array([10.0, 0.0, 0.0]), 1920, 1080)
    boxes_2d = []
    boxes_3d = {}
    for index, (category, height) in enumerate(zip(categories, heights_px)):
        boxes_2d.append(BoundingBox2D(index, 100.0, 100.0, 100.0 + height, 100.0 + height, 1.0))
        boxes_3d[index] = BoundingBox3D(
            index, np.array([5.0, 0.0, 1.0]), np.array([2.0, 2.0, 2.0]), category_id=category
        )
    return CocoFrame(0, "x.png", camera, boxes_2d, boxes_3d)


def test_coco_profile_drops_buildings_and_keeps_street_classes() -> None:
    """Buildings are not a COCO street class; everything else is kept."""
    frame = _frame([BUILDING, SEDAN, PEDESTRIAN], [50.0, 50.0, 50.0])
    kept, dropped = apply_policy(frame, AnnotationPolicy(COCO_PROFILE))
    assert [box.object_id for box in kept.bboxes_2d] == [1, 2]
    assert dropped == {EXCLUDED_CLASS: 1, TOO_SMALL: 0}


def test_fine_profile_keeps_buildings() -> None:
    """The fine profile exports every class."""
    frame = _frame([BUILDING, SEDAN], [50.0, 50.0])
    kept, dropped = apply_policy(frame, AnnotationPolicy(FINE_PROFILE))
    assert len(kept.bboxes_2d) == 2 and dropped[EXCLUDED_CLASS] == 0


def test_objects_below_the_size_floor_are_dropped_and_counted() -> None:
    """A box under the minimum height or width is dropped; one at the limit is kept."""
    policy = AnnotationPolicy(COCO_PROFILE, min_box_height_px=8.0, min_box_width_px=4.0)
    frame = _frame([SEDAN, SEDAN, SEDAN], [7.9, 8.0, 40.0])
    kept, dropped = apply_policy(frame, policy)
    assert [box.object_id for box in kept.bboxes_2d] == [1, 2]
    assert dropped[TOO_SMALL] == 1
    narrow = _frame([SEDAN], [40.0])
    narrow.bboxes_2d[0] = BoundingBox2D(0, 100.0, 100.0, 103.0, 140.0, 1.0)
    assert apply_policy(narrow, policy)[1][TOO_SMALL] == 1


def test_export_maps_classes_to_coco_ids_and_keeps_the_fine_id() -> None:
    """Sedan and SUV both become COCO 'car' (3); the fine id stays on the annotation."""
    frame = _frame([SEDAN, SUV, TRUCK, BUS, PEDESTRIAN, BUILDING], [50.0] * 6)
    coco = export_coco([frame], COCO_PROFILE)
    assert [a["category_id"] for a in coco["annotations"]] == [3, 3, 8, 6, 1]
    assert [a["fine_category_id"] for a in coco["annotations"]] == [
        SEDAN,
        SUV,
        TRUCK,
        BUS,
        PEDESTRIAN,
    ]
    assert {c["id"]: c["name"] for c in coco["categories"]} == {
        1: "person",
        3: "car",
        6: "bus",
        8: "truck",
    }
    assert {c["supercategory"] for c in coco["categories"] if c["name"] == "person"} == {"person"}


def test_default_export_is_unchanged_fine_categories() -> None:
    """Without a profile the export keeps this project's own six classes."""
    coco = export_coco([_frame([SEDAN, BUILDING], [50.0, 50.0])])
    assert [a["category_id"] for a in coco["annotations"]] == [SEDAN, BUILDING]
    assert len(coco["categories"]) == 6


def test_truncation_is_zero_in_frame_and_grows_at_the_edge() -> None:
    """A box wholly in the image has no truncation; half cut off by the edge reads about 0.5."""
    camera = ue_camera(np.zeros(3), np.array([10.0, 0.0, 0.0]), 1920, 1080)
    inside = project_bbox_3d_to_2d(
        camera, BoundingBox3D(1, np.array([10.0, 0.0, 1.0]), np.array([1.0, 1.0, 1.0]))
    )
    assert inside is not None and inside.truncation == pytest.approx(0.0, abs=1e-9)
    half_x = 10.0 * np.tan(np.radians(53.0))  # about the right image edge at 10 m
    edge = project_bbox_3d_to_2d(
        camera, BoundingBox3D(2, np.array([10.0, -half_x, 1.0]), np.array([0.2, 2.0, 0.2]))
    )
    assert edge is not None and 0.2 < edge.truncation < 0.8


def test_truncation_must_be_a_fraction() -> None:
    """Values outside [0, 1] are rejected."""
    with pytest.raises(ValueError):
        BoundingBox2D(1, 0.0, 0.0, 10.0, 10.0, 1.0, truncation=1.5)


def test_store_writes_the_profile_categories_into_the_merged_file(tmp_path: Path) -> None:
    """The merged annotations file lists the run's own classes, not the fine ones."""
    categories = export_coco([], COCO_PROFILE)["categories"]
    store = DatasetStore(tmp_path, categories)
    store.save_part(0, [], [])
    assert [c["name"] for c in store.merge()["categories"]] == ["person", "car", "bus", "truck"]
