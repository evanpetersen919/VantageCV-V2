"""How far are synthetic person crops from real ones? A Frechet distance on ResNet-50 features.

    .venv-train/Scripts/python.exe scripts/person_crop_realism.py live_dataset/train_v12e live_dataset/train_v13r

For each dataset the person annotations that are clearly visible (visibility fraction >= 0.7, not truncated)
and 40 to 140 px tall at 1280 x 720 (the synthetic frames are first scaled to that size, as the detector sees
both at one training size) are cropped with context (a square 1.3 x the longer box side) and embedded with an
ImageNet ResNet-50 (2048-d pooled features). The Frechet distance (as in FID, with this network instead of
Inception) is computed between each dataset's crops and real BDD100K val person crops (not occluded, not
truncated, same size range, same day/night mix as the dataset), over several real resamples. A
real-against-real distance gives the noise floor. Lower is closer to real. This is a relative measure for
comparing two synthetic sources, not an absolute realism score.
"""

import argparse
import glob
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import torch
import torchvision
from PIL import Image
from scipy import linalg

BDD = Path("F:/datasets/bdd100k")
SIZE = (1280, 720)
MIN_H, MAX_H = 40, 140
CROP = 224


def crop_square(image: Image.Image, box: Tuple[float, float, float, float]) -> Image.Image:
    """A square crop around ``box`` (x0, y0, x1, y1) with context, resized to CROP x CROP."""
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    side = 1.3 * max(box[2] - box[0], box[3] - box[1])
    region = (cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2)
    return image.crop(tuple(int(round(v)) for v in region)).resize((CROP, CROP), Image.BICUBIC)  # type: ignore[arg-type]


def synthetic_crops(dataset: Path) -> List[Tuple[Image.Image, str]]:
    """(crop, time of day) of the clearly visible, mid-sized persons of a rendered dataset."""
    data = json.loads((dataset / "annotations.json").read_text(encoding="utf-8"))
    images = {i["id"]: i for i in data["images"]}
    by_image: Dict[int, List[Dict[str, Any]]] = {}
    for annotation in data["annotations"]:
        if annotation["category_id"] == 1:
            by_image.setdefault(annotation["image_id"], []).append(annotation)
    out: List[Tuple[Image.Image, str]] = []
    for image_id, annotations in by_image.items():
        entry = images[image_id]
        scale = SIZE[0] / entry["width"]
        image = None
        for a in annotations:
            x, y, w, h = (v * scale for v in a["bbox"])
            if a["visibility_fraction"] < 0.7 or a["truncation"] > 0 or not MIN_H <= h <= MAX_H:
                continue
            if image is None:
                image = Image.open(dataset / entry["file_name"]).convert("RGB").resize(SIZE, Image.BICUBIC)
            out.append((crop_square(image, (x, y, x + w, y + h)), entry["time_of_day"]))
    return out


def real_boxes() -> List[Tuple[str, Tuple[float, float, float, float], str]]:
    """(image path, box, time of day) of every clean mid-sized person in BDD100K val."""
    rows = []
    for path in sorted(glob.glob(str(BDD / "labels/100k/val/*.json"))):
        label = json.loads(Path(path).read_text(encoding="utf-8"))
        tod = {"daytime": "day", "night": "night"}.get(label["attributes"].get("timeofday"))
        if tod is None:
            continue
        for obj in label["frames"][0]["objects"]:
            attrs = obj.get("attributes", {})
            if obj["category"] != "person" or attrs.get("occluded") or attrs.get("truncated"):
                continue
            b = obj["box2d"]
            if MIN_H <= b["y2"] - b["y1"] <= MAX_H:
                image = BDD / "images/100k/val" / (Path(path).stem + ".jpg")
                rows.append((str(image), (b["x1"], b["y1"], b["x2"], b["y2"]), tod))
    return rows


def real_crops(rows: List[Tuple[str, Tuple[float, float, float, float], str]]) -> List[Image.Image]:
    """The crops of the chosen real boxes."""
    cache: Dict[str, Image.Image] = {}
    out = []
    for path, box, _ in rows:
        if path not in cache:
            cache.clear()
            cache[path] = Image.open(path).convert("RGB")
        out.append(crop_square(cache[path], box))
    return out


def embed(crops: List[Image.Image], model: torch.nn.Module, device: str) -> np.ndarray:
    """2048-d ResNet-50 features of ``crops``."""
    mean = torch.tensor([0.485, 0.456, 0.406], device=device).view(1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225], device=device).view(1, 3, 1, 1)
    features = []
    with torch.no_grad():
        for start in range(0, len(crops), 128):
            batch = np.stack([np.asarray(c, dtype=np.float32) / 255.0 for c in crops[start : start + 128]])
            tensor = torch.from_numpy(batch).permute(0, 3, 1, 2).to(device)
            features.append(model((tensor - mean) / std).cpu().numpy())
    return np.concatenate(features)


def frechet(a: np.ndarray, b: np.ndarray) -> float:
    """Frechet distance between Gaussians fitted to two feature sets."""
    mu_a, mu_b = a.mean(0), b.mean(0)
    cov_a, cov_b = np.cov(a, rowvar=False), np.cov(b, rowvar=False)
    root, _ = linalg.sqrtm(cov_a @ cov_b, disp=False)
    root = root.real
    return float(((mu_a - mu_b) ** 2).sum() + np.trace(cov_a + cov_b - 2 * root))


def main() -> None:
    """Embed every dataset's person crops and the real ones, print the distances."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("datasets", type=Path, nargs="+")
    parser.add_argument("--resamples", type=int, default=5)
    args = parser.parse_args()
    random.seed(0)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = torchvision.models.resnet50(weights=torchvision.models.ResNet50_Weights.IMAGENET1K_V2)
    model.fc = torch.nn.Identity()  # type: ignore[assignment]
    model = model.eval().to(device)
    pool = real_boxes()
    print(f"real pool: {len(pool)} clean mid-sized persons in BDD100K val")
    synthetic = {d.name: synthetic_crops(d) for d in args.datasets}
    for name, crops in synthetic.items():
        print(f"{name}: {len(crops)} crops ({sum(t == 'night' for _, t in crops)} night)")
    features = {name: embed([c for c, _ in crops], model, device) for name, crops in synthetic.items()}
    count = min(len(c) for c in synthetic.values())
    results: Dict[str, List[float]] = {name: [] for name in synthetic}
    floor: List[float] = []
    for k in range(args.resamples):
        random.seed(k)
        # real crops with each dataset's own day/night mix
        drawn = {}
        chosen_first: List[Any] = []
        for name, crops in synthetic.items():
            share = sum(t == "night" for _, t in crops) / len(crops)
            night = [r for r in pool if r[2] == "night"]
            day = [r for r in pool if r[2] == "day"]
            chosen = random.sample(night, int(round(count * share))) + random.sample(day, count - int(round(count * share)))
            drawn[name] = embed(real_crops(chosen), model, device)
            if not chosen_first:
                chosen_first = chosen
        for name in synthetic:
            idx = np.random.default_rng(k).choice(len(features[name]), count, replace=False)
            results[name].append(frechet(features[name][idx], drawn[name]))
        first = list(synthetic)[0]
        share = sum(t == "night" for _, t in synthetic[first]) / len(synthetic[first])
        taken = {id(r) for r in chosen_first}
        night = [r for r in pool if r[2] == "night" and id(r) not in taken]
        day = [r for r in pool if r[2] == "day" and id(r) not in taken]
        other = random.sample(night, int(round(count * share))) + random.sample(day, count - int(round(count * share)))
        floor.append(frechet(drawn[first], embed(real_crops(other), model, device)))
        print(f"resample {k}: " + ", ".join(f"{n} {results[n][-1]:.1f}" for n in synthetic) + f"; real-vs-real {floor[-1]:.1f}")
    print("\nFrechet distance to real person crops (lower = closer), mean +- sd over resamples:")
    for name, values in results.items():
        print(f"  {name}: {np.mean(values):.1f} +- {np.std(values, ddof=1):.1f}   ({len(synthetic[name])} crops, {count} used)")
    print(f"  real vs real (two disjoint samples of {count}): {np.mean(floor):.1f} +- {np.std(floor, ddof=1):.1f}  (noise floor)")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
