"""Score lamp-bloom parameters against real night frames, offline, on a rendered night set.

    PYTHONPATH=. .venv-train/Scripts/python.exe scripts/calibrate_bloom.py live_dataset/_calib_night/seed_*

Needs frames rendered with ``--semantic-maps`` (the depth maps) and without bloom. For each ego night
frame the lamps are rebuilt from the scenario (seed and conditions are in the frame's metadata), the
bloom is applied with each parameter set, and ``lamp_profile`` statistics of the car boxes are printed
next to BDD100K's.
"""

import argparse
import glob
import itertools
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lamp_profile import MIN_PX, SIZE, car_stats, summarise  # noqa: E402

from src.orchestration.dataset_generator import generate_scenario
from src.orchestration.hood import hood_mask
from src.orchestration.lamp_bloom import BloomParams, add_glare, visible_lamps
from src.orchestration.live_render import camera_from_image_entry
from src.orchestration.scenario_serializer import serialize_scenario
from src.procedural.environment import Season, TimeOfDay, Weather, scenario_environment
from src.utils.config_loader import load_scenario_config

BOUNDS = (-150.0, -150.0, 150.0, 150.0)


def load_frames(roots: List[Path]) -> List[Dict[str, Any]]:
    """Ego night frames with their cars' boxes, lamps and depth, rebuilt from the stored metadata."""
    config = load_scenario_config("configs/scenario_templates/urban_dense_v13r.yaml")
    frames = []
    for root in roots:
        part = sorted(glob.glob(str(root / "parts" / "*.json")))[0]
        data = json.loads(Path(part).read_text(encoding="utf-8"))
        for image in data["images"]:
            if image["time_of_day"] != "night" or image.get("view") != "ego":
                continue
            scenario = generate_scenario(
                image["seed"], config, BOUNDS, "c", time_of_day=TimeOfDay.NIGHT
            )
            environment = scenario_environment(
                Season(image["season"]),
                TimeOfDay.NIGHT,
                Weather(image["weather"]),
                image["seed"],
                "v7",
            )
            payload = serialize_scenario(scenario, environment)
            depth = (
                np.array(Image.open(root / image["depth_file"])).astype(np.float32)
                / image["depth_scale"]
            )
            scale = SIZE[0] / 1920.0
            boxes = [
                (
                    a["bbox"][0] * scale,
                    a["bbox"][1] * scale,
                    (a["bbox"][0] + a["bbox"][2]) * scale,
                    (a["bbox"][1] + a["bbox"][3]) * scale,
                )
                for a in data["annotations"]
                if a["image_id"] == image["id"]
                and a["category_id"] == 3
                and MIN_PX <= a["bbox"][3] * scale <= 220
            ]
            frames.append(
                {
                    "image": np.array(Image.open(root / image["file_name"]).convert("RGB")),
                    "camera": camera_from_image_entry(image),
                    "glows": payload.get("glows", []),
                    "depth": depth,
                    "boxes": boxes,
                    "hood": image.get("hood_top_px"),
                }
            )
    return frames


def score(frames: List[Dict[str, Any]], params: BloomParams) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    for frame in frames:
        picture = frame["image"]
        if params is not None:
            lamps = visible_lamps(frame["glows"], frame["camera"], frame["depth"], params)
            keep = (
                hood_mask(frame["hood"], (picture.shape[1], picture.shape[0]))
                if frame["hood"]
                else None
            )
            picture = add_glare(picture, lamps, params, keep)
        if frame["boxes"]:
            rows += car_stats(Image.fromarray(picture), frame["boxes"])
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", type=Path, nargs="+")
    args = parser.parse_args()
    frames = load_frames(args.roots)
    print(len(frames), "night ego frames;", sum(len(f["boxes"]) for f in frames), "car boxes")
    print(
        "target (BDD100K night): with lamps 44.5% | area median 10.7 (2.7-35.1) | V 0.59 | S 0.65 | radius 0.042"
    )
    summarise("no bloom", score(frames, None))
    results = []
    for core, brake, running in itertools.product((0.4, 0.45, 0.5), (1.5, 2.0, 2.5), (0.5, 0.7)):
        params = BloomParams(
            brake_peak=brake, running_peak=running, sigma_radii=(core, 2.5 * core, 7.0 * core)
        )
        rows = score(frames, params)
        lit = [r for r in rows if r["has"]]
        if not lit:
            continue
        area = float(np.median([r["area"] for r in lit]))
        radius = float(np.median([r["radius"] for r in lit]))
        sat, val = float(np.median([r["s"] for r in lit])), float(np.median([r["v"] for r in lit]))
        distance = (
            abs(np.log(area / 10.7))
            + abs(np.log(radius / 0.042))
            + 5 * abs(sat - 0.65)
            + 5 * abs(val - 0.59)
        )
        results.append((distance, f"c{core:g} b{brake:g} r{running:g}", rows))
    for distance, name, rows in sorted(results, key=lambda x: x[0])[:6]:
        print(f"distance {distance:.3f}")
        summarise(name, rows)


if __name__ == "__main__":
    main()
