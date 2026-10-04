"""Measure a generator profile's scene-layout statistics without the game.

Scenarios, camera poses and 2D labels are all computed in Python, so class shares, pedestrian
presence, box overlap and the horizon spread can be measured over hundreds of scenarios in
minutes and compared with BDD100K before any frame is rendered.

    PYTHONPATH=. python bin/measure_layout.py --profile v7 --scenarios 300
    PYTHONPATH=. python bin/measure_layout.py --profile v6 --views ego ego lot

Reference values (BDD100K, 12,037 images; city-street frames in brackets): boxes per image
12.1; a person in 32% (44%) of frames and 3 or more in 15% (23%); truck 3.5% of boxes; boxes
overlapping another at IoU > 0.3: 6.8%; per-image horizon-row spread 0.105.
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from src.export.annotation_policy import AnnotationPolicy, apply_policy
from src.ground_truth.categories import PROFILES
from src.orchestration.dataset_generator import generate_scenario, render_frame
from src.orchestration.live_dataset import (  # pylint: disable=protected-access
    DEFAULT_VIEWS,
    _views_for,
    draw_conditions,
)
from src.orchestration.live_render import ue_camera
from src.orchestration.profiles import (
    V6_CONFIG,
    V6_PARKING_LOT_FRACTION,
    V7_CONFIG,
    V7_PARKING_LOT_FRACTION,
    V7_VIEWS,
)
from src.utils.config_loader import load_scenario_config

BOUNDS = (-150.0, -150.0, 150.0, 150.0)
WIDTH, HEIGHT = 1920, 1080
PERSON, CAR, BUS, TRUCK = 1, 3, 6, 8


def _iou_pairs_over(boxes: np.ndarray, threshold: float) -> int:  # type: ignore[type-arg]
    """How many boxes overlap some other box at IoU above ``threshold``."""
    count = 0
    for i, first in enumerate(boxes):
        for j, second in enumerate(boxes):
            if i == j:
                continue
            width = min(first[2], second[2]) - max(first[0], second[0])
            height = min(first[3], second[3]) - max(first[1], second[1])
            if width <= 0 or height <= 0:
                continue
            inter = width * height
            union = (
                (first[2] - first[0]) * (first[3] - first[1])
                + (second[2] - second[0]) * (second[3] - second[1])
                - inter
            )
            if inter / union > threshold:
                count += 1
                break
    return count


def measure(args: argparse.Namespace) -> Dict[str, Any]:  # pylint: disable=too-many-locals
    """Statistics over ``args.scenarios`` scenarios of the chosen profile."""
    v7 = args.profile == "v7"
    config = load_scenario_config(args.config or (V7_CONFIG if v7 else V6_CONFIG))
    config = config.model_copy(
        update={
            "parking_lot_fraction": args.parking_lot_fraction
            if args.parking_lot_fraction is not None
            else (V7_PARKING_LOT_FRACTION if v7 else V6_PARKING_LOT_FRACTION)
        }
    )
    views = tuple(args.views or (V7_VIEWS if v7 else DEFAULT_VIEWS))
    policy = AnnotationPolicy(PROFILES["coco"])
    classes: Counter = Counter()  # type: ignore[type-arg]
    per_image: List[Dict[str, int]] = []
    overlapped = boxes_total = 0
    horizons: List[float] = []
    for index in range(args.scenarios):
        seed = args.seed + index
        conditions = draw_conditions(seed, args.profile)
        try:
            scenario = generate_scenario(
                seed, config, BOUNDS, f"m_{index}", time_of_day=conditions[0]
            )
        except ValueError:
            continue
        for view_index, pose in enumerate(_views_for(scenario, views, BOUNDS, seed, args.profile)):
            camera = ue_camera(pose.position, pose.look_at, WIDTH, HEIGHT)
            frame, _ = apply_policy(render_frame(scenario, camera, view_index, "x.png"), policy)
            ids = {
                box.object_id: frame.bboxes_3d_by_id[box.object_id].category_id
                for box in frame.bboxes_2d
            }
            counts = Counter(policy.profile.mapping.get(cat) for cat in ids.values())
            classes.update(counts)
            per_image.append({str(k): v for k, v in counts.items()})
            rows = np.array([[b.x_min, b.y_min, b.x_max, b.y_max] for b in frame.bboxes_2d])
            if len(rows):
                overlapped += _iou_pairs_over(rows, 0.3)
                boxes_total += len(rows)
            direction = pose.look_at - pose.position
            horizons.append(
                float(np.degrees(np.arctan2(direction[2], np.linalg.norm(direction[:2]))))
            )
    images = len(per_image)
    people = [row.get(str(PERSON), 0) for row in per_image]
    total = sum(classes.values())
    return {
        "profile": args.profile,
        "views": list(views),
        "images": images,
        "boxes_per_image": round(total / images, 2),
        "frames_with_person": round(float(np.mean([p >= 1 for p in people])), 3),
        "frames_with_3_persons": round(float(np.mean([p >= 3 for p in people])), 3),
        "persons_per_image": round(float(np.mean(people)), 2),
        "class_share_of_boxes": {
            name: round(classes[code] / total, 3)
            for name, code in (("person", PERSON), ("car", CAR), ("bus", BUS), ("truck", TRUCK))
        },
        "trucks_per_image": round(classes[TRUCK] / images, 2),
        "cars_per_image": round(classes[CAR] / images, 2),
        "share_boxes_iou_gt_0.3": round(overlapped / max(boxes_total, 1), 3),
        "pitch_deg_std": round(float(np.std(horizons)), 2),
    }


def main() -> None:
    """Parse arguments, measure, print."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--profile", choices=["v6", "v7"], default="v7")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--views", nargs="+", choices=["ego", "lot", "overview"], default=None)
    parser.add_argument("--parking-lot-fraction", type=float, default=None)
    parser.add_argument("--scenarios", type=int, default=100)
    parser.add_argument("--seed", type=int, default=50000)
    print(json.dumps(measure(parser.parse_args()), indent=1))


if __name__ == "__main__":
    main()
