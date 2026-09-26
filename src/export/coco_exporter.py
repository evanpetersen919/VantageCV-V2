"""COCO JSON export for a generated dataset's camera frames and annotations.

Implements MASTER_PROMPT Section 3.7's "COCO JSON export" bullet,
informed directly by QOL_RESEARCH_CHECKLIST.md Section H.1's own test
signatures (required fields, no ID collisions, valid cross-references,
JSON-serializability).

Every category in ``src.ground_truth.categories`` is exported (building,
sedan, suv, truck, bus, pedestrian) -- one annotation's ``category_id``
comes directly from its source ``BoundingBox3D.category_id``, so
buildings/vehicles/pedestrians all export correctly as long as
``CocoFrame.bboxes_3d_by_id`` covers every annotated object (see
``dataset_generator.render_frame``, the only real caller).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.ground_truth.bbox_2d import BoundingBox2D
from src.ground_truth.bbox_3d import BoundingBox3D
from src.ground_truth.categories import BUILDING, CATEGORY_NAMES
from src.ground_truth.segmentation import compute_silhouette
from src.sensors.camera_model import Camera

# Fallback only: a bbox_2d with no matching bboxes_3d_by_id entry (should
# not happen for any real caller, since every BoundingBox2D is derived
# from a BoundingBox3D -- see project_bboxes_3d_to_2d).
BUILDING_CATEGORY_ID = BUILDING


@dataclass
class CocoFrame:
    """One camera frame's worth of data to export."""

    image_id: int
    file_name: str
    camera: Camera
    bboxes_2d: List[BoundingBox2D]
    bboxes_3d_by_id: Dict[int, BoundingBox3D] = field(default_factory=dict)
    # Extra per-image fields written next to id/file_name/width/height (scenario
    # conditions, camera pose, ...).
    metadata: Dict[str, Any] = field(default_factory=dict)


def _bbox_2d_to_coco_annotation(
    annotation_id: int,
    image_id: int,
    bbox_2d: BoundingBox2D,
    category_id: int,
    silhouette: Any,
) -> Dict[str, Any]:
    """Build one COCO annotation dict from a projected 2D box and
    (optionally) its polygon silhouette."""
    width = bbox_2d.x_max - bbox_2d.x_min
    height = bbox_2d.y_max - bbox_2d.y_min

    segmentation: List[List[float]] = []
    if silhouette is not None and len(silhouette) >= 3:
        segmentation = [silhouette.flatten().tolist()]

    return {
        "id": annotation_id,
        "image_id": image_id,
        "category_id": category_id,
        "bbox": [bbox_2d.x_min, bbox_2d.y_min, width, height],
        "area": bbox_2d.area,
        "iscrowd": 0,
        "segmentation": segmentation,
        "visibility_fraction": round(bbox_2d.visible_fraction, 3),
    }


def export_coco(frames: List[CocoFrame]) -> Dict[str, Any]:
    """Build a complete COCO-format dict from a list of frames.

    Parameters
    ----------
    frames : List[CocoFrame]
        One entry per rendered camera view. Each frame's own
        ``bboxes_2d`` (already visibility-filtered by
        ``project_bboxes_3d_to_2d``) becomes that image's annotations.

    Returns
    -------
    Dict[str, Any]
        A dict with ``images``, ``annotations``, and ``categories`` keys,
        JSON-serializable as-is (``json.dumps`` needs no special
        encoder -- every value is a plain int/float/str/list/dict).
    """
    images: List[Dict[str, Any]] = []
    annotations: List[Dict[str, Any]] = []
    annotation_id_counter = 1

    for frame in frames:
        images.append(
            {
                **frame.metadata,
                "id": frame.image_id,
                "file_name": frame.file_name,
                "width": frame.camera.intrinsics.width,
                "height": frame.camera.intrinsics.height,
            }
        )

        for bbox_2d in frame.bboxes_2d:
            silhouette = None
            category_id = BUILDING_CATEGORY_ID
            bbox_3d = frame.bboxes_3d_by_id.get(bbox_2d.object_id)
            if bbox_3d is not None:
                silhouette = compute_silhouette(frame.camera, bbox_3d)
                category_id = bbox_3d.category_id

            annotations.append(
                _bbox_2d_to_coco_annotation(
                    annotation_id_counter, frame.image_id, bbox_2d, category_id, silhouette
                )
            )
            annotation_id_counter += 1

    categories = [
        {"id": category_id, "name": name, "supercategory": _supercategory(name)}
        for category_id, name in sorted(CATEGORY_NAMES.items())
    ]

    return {"images": images, "annotations": annotations, "categories": categories}


def _supercategory(category_name: str) -> str:
    """COCO's conventional broad grouping for one of this dataset's own
    category names."""
    if category_name == "building":
        return "structure"
    if category_name == "pedestrian":
        return "person"
    return "vehicle"
