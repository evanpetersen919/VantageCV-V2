"""How red are the vehicle lights, and how warm is the scene, in real night frames and in ours?

    .venv-train/Scripts/python.exe scripts/taillight_colour.py live_dataset/train_v13r --n 300

The same measurement on both sides, at the size a detector sees (1280 x 720): inside the lower 70% of
every car box (so road, sky and signals are left out), the bright (V >= 0.7) pixels whose hue is in the
red band (within 25 degrees of red) and that are not white (S >= 0.15) are the lights' colour. Reported:
their share of the box area, and the median and spread of their saturation and hue. Also the mean
chromaticity of the dark-to-mid surface pixels (0.10 <= V <= 0.50) of the whole frame, which is the
scene's colour cast.
"""

import argparse
import glob
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image

BDD = Path("F:/datasets/bdd100k")
SIZE = (1280, 720)


def hsv(rgb: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Hue (degrees), saturation and value of an RGB uint8 array."""
    x = rgb.astype(np.float64) / 255.0
    maximum, minimum = x.max(-1), x.min(-1)
    delta = maximum - minimum
    value, saturation = maximum, np.where(maximum > 0, delta / np.maximum(maximum, 1e-9), 0.0)
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    hue = np.zeros_like(maximum)
    safe = np.maximum(delta, 1e-9)
    hue = np.where(maximum == r, ((g - b) / safe) % 6, hue)
    hue = np.where(maximum == g, (b - r) / safe + 2, hue)
    hue = np.where(maximum == b, (r - g) / safe + 4, hue)
    return np.where(delta > 0, hue * 60.0, 0.0), saturation, value


def measure(image: Image.Image, boxes: List[Tuple[float, float, float, float]]) -> Dict[str, Any]:
    """Light-pixel statistics inside ``boxes`` and the scene's mid-tone chromaticity."""
    rgb = np.array(image.convert("RGB").resize(SIZE, Image.BICUBIC))
    hue, sat, val = hsv(rgb)
    red = ((hue <= 25) | (hue >= 335)) & (val >= 0.7) & (sat >= 0.15)
    area, lit, saturations, hues = 0, 0, [], []
    for x0, y0, x1, y1 in boxes:
        top = int(y0 + 0.3 * (y1 - y0))
        sub = red[top : int(y1), int(x0) : int(x1)]
        area += sub.size
        lit += int(sub.sum())
        saturations.append(sat[top : int(y1), int(x0) : int(x1)][sub])
        hues.append(np.where(hue[top : int(y1), int(x0) : int(x1)][sub] > 180, hue[top : int(y1), int(x0) : int(x1)][sub] - 360, hue[top : int(y1), int(x0) : int(x1)][sub]))
    mid = (val >= 0.10) & (val <= 0.50)
    total = rgb[mid].astype(np.float64).sum(-1, keepdims=True)
    chroma = (rgb[mid] / np.maximum(total, 1.0)).mean(0) if mid.any() else np.zeros(3)
    return {
        "area": area,
        "lit": lit,
        "sat": np.concatenate(saturations) if saturations else np.zeros(0),
        "hue": np.concatenate(hues) if hues else np.zeros(0),
        "chroma": chroma,
    }


def summarise(name: str, rows: List[Dict[str, Any]]) -> None:
    sat = np.concatenate([r["sat"] for r in rows])
    hue = np.concatenate([r["hue"] for r in rows])
    area, lit = sum(r["area"] for r in rows), sum(r["lit"] for r in rows)
    chroma = np.mean([r["chroma"] for r in rows], axis=0)
    print(
        f"{name:10s} frames {len(rows):4d} | red-light px {1e4 * lit / max(area, 1):6.1f} per 10k box px | "
        f"saturation median {np.median(sat):.2f} (10-90%: {np.percentile(sat, 10):.2f}-{np.percentile(sat, 90):.2f}), "
        f"share below 0.5: {100 * (sat < 0.5).mean():4.1f}% | hue median {np.median(hue):5.1f} deg | "
        f"scene chromaticity r,g,b = {chroma[0]:.3f}, {chroma[1]:.3f}, {chroma[2]:.3f}"
    )


def real_rows(count: int) -> List[Dict[str, Any]]:
    paths = sorted(glob.glob(str(BDD / "labels/100k/val/*.json")))
    random.Random(0).shuffle(paths)
    rows: List[Dict[str, Any]] = []
    for path in paths:
        label = json.loads(Path(path).read_text(encoding="utf-8"))
        if label["attributes"].get("timeofday") != "night":
            continue
        boxes = [
            (o["box2d"]["x1"], o["box2d"]["y1"], o["box2d"]["x2"], o["box2d"]["y2"])
            for o in label["frames"][0]["objects"]
            if o["category"] == "car" and 20 <= o["box2d"]["y2"] - o["box2d"]["y1"] <= 220
        ]
        if not boxes:
            continue
        image = Image.open(BDD / "images/100k/val" / (Path(path).stem + ".jpg"))
        rows.append(measure(image, boxes))
        if len(rows) >= count:
            break
    return rows


def synthetic_rows(root: Path, count: int) -> List[Dict[str, Any]]:
    coco: Dict[str, Any] = {"images": [], "annotations": []}
    parts = sorted(glob.glob(str(root / "parts" / "scenario_*.json")))
    sources = parts if parts else [str(root / "annotations.json")]
    for source in sources:
        data = json.loads(Path(source).read_text(encoding="utf-8"))
        coco["images"] += data["images"]
        coco["annotations"] += data["annotations"]
    by_image: Dict[int, List[Any]] = {}
    for a in coco["annotations"]:
        if a["category_id"] == 3:
            x, y, w, h = a["bbox"]
            scale = SIZE[0] / 1920.0
            if 20 <= h * scale <= 220:
                by_image.setdefault(a["image_id"], []).append((x * scale, y * scale, (x + w) * scale, (y + h) * scale))
    rows = []
    for image in coco["images"]:
        if image["time_of_day"] != "night" or image["id"] not in by_image:
            continue
        rows.append(measure(Image.open(root / image["file_name"]), by_image[image["id"]]))
        if len(rows) >= count:
            break
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("synthetic", type=Path, nargs="*")
    parser.add_argument("--n", type=int, default=300)
    parser.add_argument(
        "--group", action="store_true", help="treat all given folders as one set of frames"
    )
    parser.add_argument("--no-real", action="store_true", help="skip the BDD100K measurement")
    args = parser.parse_args()
    if not args.no_real:
        summarise("BDD100K", real_rows(args.n))
    if args.group:
        rows = [row for root in args.synthetic for row in synthetic_rows(root, args.n)]
        summarise(args.synthetic[0].parent.name, rows)
        return
    for root in args.synthetic:
        summarise(root.name, synthetic_rows(root, args.n))


if __name__ == "__main__":
    main()
