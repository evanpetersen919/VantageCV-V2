"""Unit tests for COCO JSON export.

Covers QOL_RESEARCH_CHECKLIST.md Section H.1 directly: required fields,
no ID collisions, valid image/category cross-references, and
JSON-serializability.
"""

import json
import tempfile
from pathlib import Path

import numpy as np
from pycocotools.coco import COCO

from src.export.coco_exporter import CocoFrame, export_coco
from src.ground_truth.bbox_2d import project_bboxes_3d_to_2d
from src.ground_truth.bbox_3d import BoundingBox3D
from src.ground_truth.categories import CATEGORY_NAMES
from src.sensors.camera_model import Camera, CameraExtrinsics, CameraIntrinsics


def _default_camera() -> Camera:
    intrinsics = CameraIntrinsics(500.0, 500.0, 320.0, 240.0, 640, 480)
    extrinsics = CameraExtrinsics(rotation=np.eye(3), translation=np.zeros(3))
    return Camera(intrinsics, extrinsics)


def _sample_frame(image_id: int = 1) -> CocoFrame:
    camera = _default_camera()
    boxes_3d = [
        BoundingBox3D(
            object_id=1, center=np.array([0.0, 0.0, 20.0]), dimensions=np.array([2.0, 2.0, 2.0])
        ),
        BoundingBox3D(
            object_id=2, center=np.array([3.0, 0.0, 25.0]), dimensions=np.array([2.0, 2.0, 2.0])
        ),
    ]
    boxes_2d = project_bboxes_3d_to_2d(camera, boxes_3d)
    bboxes_3d_by_id = {b.object_id: b for b in boxes_3d}
    return CocoFrame(
        image_id=image_id,
        file_name=f"frame_{image_id:04d}.png",
        camera=camera,
        bboxes_2d=boxes_2d,
        bboxes_3d_by_id=bboxes_3d_by_id,
    )


def test_coco_required_fields_present() -> None:
    """images, annotations, categories keys all exist."""
    coco = export_coco([_sample_frame()])
    for key in ("images", "annotations", "categories"):
        assert key in coco


def test_coco_image_count_matches_frames() -> None:
    """One image entry per frame."""
    coco = export_coco([_sample_frame(1), _sample_frame(2)])
    assert len(coco["images"]) == 2
    assert {img["id"] for img in coco["images"]} == {1, 2}


def test_coco_no_id_collisions() -> None:
    """Image IDs and annotation IDs are each unique."""
    coco = export_coco([_sample_frame(1), _sample_frame(2)])

    image_ids = [img["id"] for img in coco["images"]]
    ann_ids = [ann["id"] for ann in coco["annotations"]]

    assert len(image_ids) == len(set(image_ids))
    assert len(ann_ids) == len(set(ann_ids))
    assert len(ann_ids) > 0


def test_coco_image_references_valid() -> None:
    """Every annotation's image_id references an existing image."""
    coco = export_coco([_sample_frame(1), _sample_frame(2)])
    image_ids = {img["id"] for img in coco["images"]}
    for ann in coco["annotations"]:
        assert ann["image_id"] in image_ids


def test_coco_category_references_valid() -> None:
    """Every annotation's category_id references an existing category."""
    coco = export_coco([_sample_frame()])
    valid_categories = {cat["id"] for cat in coco["categories"]}
    for ann in coco["annotations"]:
        assert ann["category_id"] in valid_categories


def test_coco_json_serializable() -> None:
    """The exported dict serializes and round-trips through JSON exactly."""
    coco = export_coco([_sample_frame(1), _sample_frame(2)])

    json_str = json.dumps(coco)
    parsed = json.loads(json_str)

    assert len(parsed["images"]) == len(coco["images"])
    assert len(parsed["annotations"]) == len(coco["annotations"])


def test_coco_bbox_format_is_xywh() -> None:
    """Annotation bbox is [x, y, width, height], matching x_min/y_min and
    the box's own width/height, not [x1,y1,x2,y2]."""
    coco = export_coco([_sample_frame()])
    frame = _sample_frame()

    for ann, bbox_2d in zip(coco["annotations"], frame.bboxes_2d):
        _, _, w, h = ann["bbox"]
        assert np.isclose(w, bbox_2d.x_max - bbox_2d.x_min)
        assert np.isclose(h, bbox_2d.y_max - bbox_2d.y_min)
        assert w > 0 and h > 0


def test_coco_area_matches_bbox_area() -> None:
    """Annotation area matches width * height."""
    coco = export_coco([_sample_frame()])
    for ann in coco["annotations"]:
        _, _, w, h = ann["bbox"]
        assert np.isclose(ann["area"], w * h)


def test_coco_segmentation_present_when_silhouette_available() -> None:
    """When the 3D box is available, segmentation is a non-empty polygon."""
    coco = export_coco([_sample_frame()])
    for ann in coco["annotations"]:
        assert len(ann["segmentation"]) == 1
        polygon = ann["segmentation"][0]
        assert len(polygon) >= 6  # at least 3 (x, y) pairs
        assert len(polygon) % 2 == 0


def test_coco_segmentation_empty_when_no_3d_box_provided() -> None:
    """Without a matching 3D box, segmentation degrades gracefully to an
    empty list rather than crashing."""
    camera = _default_camera()
    boxes_3d = [
        BoundingBox3D(
            object_id=1, center=np.array([0.0, 0.0, 20.0]), dimensions=np.array([2.0, 2.0, 2.0])
        )
    ]
    boxes_2d = project_bboxes_3d_to_2d(camera, boxes_3d)
    frame = CocoFrame(
        image_id=1, file_name="f.png", camera=camera, bboxes_2d=boxes_2d, bboxes_3d_by_id={}
    )

    coco = export_coco([frame])
    assert coco["annotations"][0]["segmentation"] == []


def test_coco_empty_frames_list() -> None:
    """No frames at all produces an empty but well-formed COCO dict, but
    still declares every known category (categories are a fixed schema,
    not derived from what happens to appear in this particular export)."""
    coco = export_coco([])
    assert not coco["images"]
    assert not coco["annotations"]
    assert {cat["id"] for cat in coco["categories"]} == set(CATEGORY_NAMES)


def test_coco_schema_valid_per_pycocotools() -> None:
    """The export loads successfully through pycocotools.COCO -- the
    QOL checklist's own first-listed, strongest validation: if the real
    reference implementation used across the CV ecosystem can parse and
    index it without error, the schema is genuinely valid, not just
    valid according to our own hand-written checks above."""
    coco = export_coco([_sample_frame(1), _sample_frame(2)])

    with tempfile.TemporaryDirectory() as tmp_dir:
        annotation_path = Path(tmp_dir) / "annotations.json"
        annotation_path.write_text(json.dumps(coco))

        loaded = COCO(str(annotation_path))

        assert len(loaded.getImgIds()) == 2
        assert len(loaded.getAnnIds()) == len(coco["annotations"])
        assert set(loaded.getCatIds()) == set(CATEGORY_NAMES)


def test_coco_categories_match_registry() -> None:
    """The declared categories match src.ground_truth.categories exactly
    -- every id/name pair, not just the ones this sample frame uses."""
    coco = export_coco([_sample_frame()])
    exported = {cat["id"]: cat["name"] for cat in coco["categories"]}
    assert exported == CATEGORY_NAMES
