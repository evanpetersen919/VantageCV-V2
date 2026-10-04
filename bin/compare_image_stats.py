"""Compare simple image statistics of rendered frames with BDD100K val frames.

Used to calibrate the lighting and camera of the v7 profile: night sky brightness and colour,
saturation, sharpness, clipping and JPEG blockiness, per time of day. The BDD100K side is a
fixed random sample (seeded) of val images picked by their ``timeofday``/``weather`` labels.

    PYTHONPATH=. python bin/compare_image_stats.py --dataset live_dataset/v7_probe
"""

import argparse
import glob
import json
import random
from pathlib import Path
from typing import Dict, List

import numpy as np
from PIL import Image
from scipy import ndimage

BDD_ROOT = Path("F:/datasets/bdd100k")
SIZE = (1280, 720)
BANDS = {"top": (0, 240), "mid": (240, 480), "bot": (480, 720)}
SAMPLE = 120


def image_stats(image: Image.Image) -> Dict[str, float]:
    """Brightness by band, colour, saturation, sharpness, clipping and JPEG blockiness."""
    pixels = np.asarray(
        image.convert("RGB").resize(SIZE, Image.Resampling.LANCZOS), dtype=np.float32
    )
    luma = 0.299 * pixels[..., 0] + 0.587 * pixels[..., 1] + 0.114 * pixels[..., 2]
    top, bottom = pixels.max(2), pixels.min(2)
    saturation = np.where(top > 8, (top - bottom) / np.maximum(top, 1), 0)
    lit = top > 40
    result = {f"luma_{name}": float(luma[a:b].mean()) for name, (a, b) in BANDS.items()}
    result["top_blue_over_red"] = float(
        pixels[:240, :, 2].mean() / max(float(pixels[:240, :, 0].mean()), 1.0)
    )
    result["saturation_lit"] = float(saturation[lit].mean()) if lit.any() else 0.0
    result["laplacian_var"] = float(ndimage.laplace(luma).var())
    result["share_ge_250"] = float((luma >= 250).mean())
    result["share_lt_10"] = float((luma < 10).mean())
    step = np.abs(np.diff(luma, axis=1))
    result["jpeg_blockiness"] = float(step[:, 7::8].mean() / max(float(step.mean()), 1e-6))
    return result


def _mean(rows: List[Dict[str, float]]) -> Dict[str, float]:
    return {key: float(np.mean([row[key] for row in rows])) for key in rows[0]}


def bdd_names(timeofday: str, weather: str = "") -> List[str]:
    """Names of BDD100K val images with the attributes (weather optional)."""
    names = []
    for path in sorted(glob.glob(str(BDD_ROOT / "labels/100k/val/*.json"))):
        label = json.loads(Path(path).read_text(encoding="utf-8"))
        attributes = label["attributes"]
        if attributes.get("timeofday") == timeofday and weather in ("", attributes.get("weather")):
            names.append(label["name"])
    return names


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
        print(json.dumps({k: round(v, 3) for k, v in _mean(rows).items()}))
        names = bdd_names(timeofday, weather)
        sample = random.sample(names, min(SAMPLE, len(names)))
        reference = [
            image_stats(Image.open(BDD_ROOT / f"images/100k/val/{item}.jpg")) for item in sample
        ]
        print(f"   BDD100K n={len(reference)}")
        print(json.dumps({k: round(v, 3) for k, v in _mean(reference).items()}))


if __name__ == "__main__":
    main()
