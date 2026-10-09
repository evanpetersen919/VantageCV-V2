"""Per-car taillight statistics in real night frames and in ours, for calibrating lamp bloom.

    .venv-train/Scripts/python.exe scripts/lamp_profile.py live_dataset/kaggle_v1 --n 400

For every car box 30-220 px tall (at 1280 x 720) in a night frame: the deep-red pixels (red hue within
25 degrees, S >= 0.55, V >= 0.45) in the lower 70% of the box. Reported over all such boxes: the share
of boxes with visible deep-red lamps, and for those boxes the deep-red area as parts per thousand of
the box width squared (lamp size relative to the car), the median brightness (V) and saturation (S) of
the deep-red pixels, and the largest single deep-red blob's equivalent radius in box widths.
"""

import argparse
import glob
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image
from scipy import ndimage

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from taillight_colour import BDD, SIZE, hsv  # noqa: E402

MIN_PX, MAX_PX = 30, 220


def car_stats(
    image: Image.Image, boxes: List[Tuple[float, float, float, float]]
) -> List[Dict[str, float]]:
    rgb = np.array(image.convert("RGB").resize(SIZE, Image.BICUBIC))
    hue, sat, val = hsv(rgb)
    deep = ((hue <= 25) | (hue >= 335)) & (sat >= 0.55) & (val >= 0.45)
    rows = []
    for x0, y0, x1, y1 in boxes:
        width = x1 - x0
        top = int(y0 + 0.3 * (y1 - y0))
        sub = deep[top : int(y1), int(x0) : int(x1)]
        count = int(sub.sum())
        record: Dict[str, float] = {"area": 1000.0 * count / width**2, "has": float(count >= 4)}
        if count >= 4:
            record["v"] = float(np.median(val[top : int(y1), int(x0) : int(x1)][sub]))
            record["s"] = float(np.median(sat[top : int(y1), int(x0) : int(x1)][sub]))
            labels, n = ndimage.label(sub)
            largest = int(np.bincount(labels.ravel())[1:].max()) if n else 0
            record["radius"] = float(np.sqrt(largest / np.pi) / width)
        rows.append(record)
    return rows


def real_rows(count: int) -> List[Dict[str, float]]:
    paths = sorted(glob.glob(str(BDD / "labels/100k/val/*.json")))
    random.Random(1).shuffle(paths)
    out: List[Dict[str, float]] = []
    frames = 0
    for path in paths:
        label = json.loads(Path(path).read_text(encoding="utf-8"))
        if label["attributes"].get("timeofday") != "night":
            continue
        boxes = [
            (o["box2d"]["x1"], o["box2d"]["y1"], o["box2d"]["x2"], o["box2d"]["y2"])
            for o in label["frames"][0]["objects"]
            if o["category"] == "car" and MIN_PX <= o["box2d"]["y2"] - o["box2d"]["y1"] <= MAX_PX
        ]
        if boxes:
            out += car_stats(
                Image.open(BDD / "images/100k/val" / (Path(path).stem + ".jpg")), boxes
            )
            frames += 1
        if frames >= count:
            break
    return out


def synthetic_rows(root: Path, count: int) -> List[Dict[str, float]]:
    images: List[Dict[str, Any]] = []
    annotations: List[Dict[str, Any]] = []
    for part in sorted(glob.glob(str(root / "parts" / "scenario_*.json"))) or [
        str(root / "annotations.json")
    ]:
        data = json.loads(Path(part).read_text(encoding="utf-8"))
        images += data["images"]
        annotations += data["annotations"]
    scale = SIZE[0] / 1920.0
    by_image: Dict[int, List[Tuple[float, float, float, float]]] = {}
    for a in annotations:
        x, y, w, h = a["bbox"]
        if a["category_id"] == 3 and MIN_PX <= h * scale <= MAX_PX:
            by_image.setdefault(a["image_id"], []).append(
                (x * scale, y * scale, (x + w) * scale, (y + h) * scale)
            )
    out: List[Dict[str, float]] = []
    frames = 0
    for image in images:
        if (
            image["time_of_day"] == "night"
            and image.get("view") == "ego"
            and image["id"] in by_image
        ):
            out += car_stats(Image.open(root / image["file_name"]), by_image[image["id"]])
            frames += 1
        if frames >= count:
            break
    return out


def summarise(name: str, rows: List[Dict[str, float]]) -> None:
    lit = [r for r in rows if r["has"]]
    if not lit:
        print(f"{name:14s} cars {len(rows):4d} | with deep-red lamps 0.0% (none)")
        return
    print(
        f"{name:14s} cars {len(rows):4d} | with deep-red lamps {100 * len(lit) / max(len(rows), 1):4.1f}% | "
        f"lamp area (per mille of width^2) median {np.median([r['area'] for r in lit]):5.1f} "
        f"(25-75%: {np.percentile([r['area'] for r in lit], 25):.1f}-{np.percentile([r['area'] for r in lit], 75):.1f}) | "
        f"V median {np.median([r['v'] for r in lit]):.2f} | S median {np.median([r['s'] for r in lit]):.2f} | "
        f"largest blob radius {np.median([r['radius'] for r in lit]):.3f} widths"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("synthetic", type=Path, nargs="*")
    parser.add_argument("--n", type=int, default=400)
    parser.add_argument("--group", action="store_true")
    parser.add_argument("--no-real", action="store_true")
    args = parser.parse_args()
    if not args.no_real:
        summarise("BDD100K", real_rows(args.n))
    if args.group:
        summarise(
            args.synthetic[0].parent.name,
            [r for root in args.synthetic for r in synthetic_rows(root, args.n)],
        )
        return
    for root in args.synthetic:
        summarise(root.name, synthetic_rows(root, args.n))


if __name__ == "__main__":
    main()
