"""Compare simple image statistics of rendered frames with BDD100K val frames.

Used to calibrate the lighting and camera of the v7 profile: night sky brightness and colour,
saturation, sharpness, clipping and JPEG blockiness, per time of day. The BDD100K side is a
fixed random sample (seeded) of val images picked by their ``timeofday``/``weather`` labels.

    PYTHONPATH=. python bin/compare_image_stats.py --dataset live_dataset/v7_probe
"""

import argparse
import json
import random
from pathlib import Path

from PIL import Image

from src.evaluation.image_stats import BDD_ROOT, SAMPLE, bdd_names, image_stats, mean_stats


def main() -> None:
    """Print the statistics of the rendered frames and of matching BDD100K images."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--view", default="ego")
    args = parser.parse_args()
    random.seed(0)
    images = json.loads((args.dataset / "annotations.json").read_text(encoding="utf-8"))["images"]
    groups = {
        "night": ("night", ""),
        "day": ("daytime", ""),
        "day fog": ("daytime", "foggy"),
        "day clear": ("daytime", "clear"),
    }
    for name, (timeofday, weather) in groups.items():
        want_tod = "night" if timeofday == "night" else "day"
        synthetic = [
            image
            for image in images
            if image["time_of_day"] == want_tod
            and image["view"] == args.view
            and (not weather or image["weather"] == {"foggy": "fog", "clear": "clear"}[weather])
        ]
        if not synthetic:
            continue
        rows = [image_stats(Image.open(args.dataset / image["file_name"])) for image in synthetic]
        print(f"\n== {name}: rendered n={len(rows)}")
        print(json.dumps({k: round(v, 3) for k, v in mean_stats(rows).items()}))
        names = bdd_names(timeofday, weather)
        sample = random.sample(names, min(SAMPLE, len(names)))
        reference = [
            image_stats(Image.open(BDD_ROOT / f"images/100k/val/{item}.jpg")) for item in sample
        ]
        print(f"   BDD100K n={len(reference)}")
        print(json.dumps({k: round(v, 3) for k, v in mean_stats(reference).items()}))


if __name__ == "__main__":
    main()
