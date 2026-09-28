"""Fit each class's ``AnnotationPolicy.max_distance_m`` against real benchmark box sizes.

Our streets are long and mostly unobstructed, so one rendered frame's annotations include
not just the nearby traffic a detector needs but everything visible far down the road --
measured directly, this pushed the median synthetic box height (as a fraction of image
height) to 1.4-2.7x smaller than the same class's median in BDD100K and Cityscapes alike
(two independently-collected real datasets agreeing with each other rules out one of them
having an unusual camera setup as the explanation). This script finds, per class, the
maximum camera distance that makes the *kept* synthetic annotations' median height
fraction match the real benchmarks' own measured median as closely as possible (in log
space, so a 2x-too-small and a 2x-too-large candidate count equally).

It regenerates real training scenarios (deterministic from seed, no running game needed)
and re-projects every annotation through the exact production camera/render pipeline
(``render_frame``) to get an exact 3D distance for every box -- not an assumed real-world
object height, which is what the initial (superseded) distance estimate relied on.

    PYTHONPATH=. python bin/fit_max_annotation_distance.py --dataset live_dataset/train2000 \\
        --num-scenarios 150
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from src.ground_truth.categories import COCO_PROFILE
from src.orchestration.dataset_generator import ScenarioResult, generate_scenario, render_frame
from src.orchestration.live_render import camera_from_image_entry
from src.utils.config_loader import load_scenario_config

# Median box height as a fraction of image height, averaged across BDD100K val (10,000
# images) and Cityscapes val (500 images) -- see the analysis this script's docstring
# summarises. Both were measured directly from each benchmark's own ground-truth boxes.
REAL_TARGET_HEIGHT_FRACTION = {"person": 7.48, "car": 5.33, "bus": 10.73, "truck": 9.68}
COCO_NAMES = {1: "person", 3: "car", 6: "bus", 8: "truck"}


def _image_records(
    scenario: ScenarioResult, image: Dict[str, Any], records: Dict[str, List[Tuple[float, float]]]
) -> None:
    """Append this ego image's (distance_m, box_height_px) pairs into ``records``, in place."""
    camera = camera_from_image_entry(image)
    frame = render_frame(scenario, camera, image["id"], image["file_name"])
    origin = camera.extrinsics.get_translation_vector()
    for box in frame.bboxes_2d:
        bbox_3d = frame.bboxes_3d_by_id.get(box.object_id)
        coco_id = COCO_PROFILE.mapping.get(bbox_3d.category_id) if bbox_3d else None
        if bbox_3d is None or coco_id is None:
            continue
        distance = float(np.linalg.norm(bbox_3d.center - origin))
        records[COCO_NAMES[coco_id]].append((distance, box.y_max - box.y_min))


def _collect(
    dataset_dir: Path, config_path: Path, num_scenarios: int
) -> Dict[str, List[Tuple[float, float]]]:
    """(distance_m, box_height_px) per class, from ``num_scenarios`` regenerated scenarios."""
    manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    bounds = tuple(manifest["bounds"])
    config = load_scenario_config(config_path).model_copy(update={"parking_lot_fraction": 0.3})
    records: Dict[str, List[Tuple[float, float]]] = {name: [] for name in COCO_NAMES.values()}
    for index in range(num_scenarios):
        part_path = dataset_dir / "parts" / f"scenario_{index:04d}.json"
        if not part_path.exists():
            continue
        seed = manifest["base_seed"] + index
        scenario = generate_scenario(seed, config, bounds, f"live_{index:04d}")
        part = json.loads(part_path.read_text(encoding="utf-8"))
        for image in part["images"]:
            if image["view"] == "ego":
                _image_records(scenario, image, records)
    return records


def _best_cutoff(records: List[Tuple[float, float]], target_pct: float, image_height: int) -> float:
    """The 3D distance cutoff (metres) whose kept-median height fraction is closest to
    ``target_pct``, scanned at 1 m resolution from 15 to 70 m."""
    distances = np.array([r[0] for r in records])
    heights = np.array([r[1] for r in records])
    best_cutoff, best_error = 15.0, float("inf")
    for cutoff in np.arange(15.0, 70.0, 1.0):
        kept = distances <= cutoff
        if kept.sum() < 10:
            continue
        median_pct = 100 * float(np.median(heights[kept])) / image_height
        error = abs(np.log(median_pct) - np.log(target_pct))
        if error < best_error:
            best_cutoff, best_error = float(cutoff), error
    return best_cutoff


def main() -> None:
    """Parse arguments, fit each class's cutoff, print the result."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument(
        "--config", type=Path, default=Path("configs/scenario_templates/urban_dense.yaml")
    )
    parser.add_argument("--num-scenarios", type=int, default=150)
    parser.add_argument("--image-height", type=int, default=1080)
    args = parser.parse_args()

    records = _collect(args.dataset, args.config, args.num_scenarios)
    for name, recs in records.items():
        cutoff = _best_cutoff(recs, REAL_TARGET_HEIGHT_FRACTION[name], args.image_height)
        print(f"{name:8s} n={len(recs):6d}  fitted_max_distance_m={cutoff:5.1f}")


if __name__ == "__main__":
    main()
