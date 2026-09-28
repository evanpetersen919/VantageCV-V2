"""Regenerate a live dataset's annotations with modal (visible-region) occlusion boxes.

Reuses the exact production label pipeline (``generate_scenario`` -> ``render_frame`` ->
``apply_policy`` -> ``export_coco``) against the *existing* camera poses stored in each
scenario's part file, so this is a pure geometry recompute: no running game, no new images.
Only ``filter_occluded``'s box-shrinking behaviour differs from how the source dataset was
originally exported (see the occlusion.py commit that added ``visible_region_box``).

Images are hard-linked into the output directory (same file, no 6 GB copy) since only the
label geometry changes, not the pixels.

    PYTHONPATH=. python bin/regenerate_modal_boxes.py --dataset live_dataset/train2000_v3 \\
        --out live_dataset/train2000_v4b
"""

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from src.export.annotation_policy import AnnotationPolicy, apply_policy
from src.export.coco_exporter import CocoFrame, export_coco
from src.ground_truth.categories import COCO_PROFILE
from src.orchestration.dataset_generator import ScenarioResult, generate_scenario, render_frame
from src.orchestration.live_dataset import draw_conditions
from src.orchestration.live_render import camera_from_image_entry
from src.utils.config_loader import load_scenario_config


def _link_images(dataset_dir: Path, out_dir: Path) -> None:
    """Hard-link every image from ``dataset_dir`` into ``out_dir`` (same bytes, no copy)."""
    (out_dir / "images").mkdir(parents=True, exist_ok=True)
    for source in (dataset_dir / "images").iterdir():
        destination = out_dir / "images" / source.name
        if not destination.exists():
            os.link(source, destination)


def _frame_for(
    image: Dict[str, Any], scenario: ScenarioResult, policy: AnnotationPolicy
) -> CocoFrame:
    """One image's freshly computed (modal) ``CocoFrame``, from its stored camera pose."""
    camera = camera_from_image_entry(image)
    frame = render_frame(scenario, camera, image["id"], image["file_name"])
    frame, dropped = apply_policy(frame, policy)
    frame.metadata = {k: v for k, v in image.items() if k not in ("id", "file_name")}
    frame.metadata["dropped_annotations"] = dropped
    return frame


def _regenerate(dataset_dir: Path, config_path: Path, policy: AnnotationPolicy) -> List[CocoFrame]:
    """One ``CocoFrame`` per existing image, with freshly computed (modal) boxes."""
    manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    bounds = tuple(manifest["bounds"])
    config = load_scenario_config(config_path).model_copy(update={"parking_lot_fraction": 0.3})
    frames: List[CocoFrame] = []
    part_paths = sorted((dataset_dir / "parts").glob("scenario_*.json"))
    for scenario_index, part_path in enumerate(part_paths):
        seed = manifest["base_seed"] + scenario_index
        images = json.loads(part_path.read_text(encoding="utf-8"))["images"]
        if not images:
            continue
        time_of_day, _weather = draw_conditions(seed)
        scenario = generate_scenario(
            seed, config, bounds, images[0]["scenario_id"], time_of_day=time_of_day
        )
        frames.extend(_frame_for(image, scenario, policy) for image in images)
        if (scenario_index + 1) % 100 == 0:
            print(f"{scenario_index + 1}/{len(part_paths)} scenarios")
    return frames


def main() -> None:
    """Parse arguments, regenerate annotations, link images, write the new dataset."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--config", type=Path, default=Path("configs/scenario_templates/urban_dense.yaml")
    )
    args = parser.parse_args()

    policy = AnnotationPolicy(COCO_PROFILE)
    frames = _regenerate(args.dataset, args.config, policy)
    coco: Dict[str, Any] = export_coco(frames, policy.profile)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "annotations.json").write_text(json.dumps(coco), encoding="utf-8")
    _link_images(args.dataset, args.out)
    print(
        f"done: {len(coco['images'])} images, {len(coco['annotations'])} annotations -> {args.out}"
    )


if __name__ == "__main__":
    main()
