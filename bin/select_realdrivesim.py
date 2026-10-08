"""Choose 512 RealDriveSim frames and write them as a VantageCV-style batch folder.

    PYTHONPATH=. python bin/select_realdrivesim.py --mode matched --out live_dataset/train_rdsm
    PYTHONPATH=. python bin/select_realdrivesim.py --mode random  --out live_dataset/train_rdsr

Labels come only from the dataset's official 2D annotations
(``external_data/realdrivesim/annotations_2d``) and its official class table. The rules are the ones
fixed in EXPERIMENT_LOG.md before any frame was chosen:

* class mapping: person 22; car 5 and 103 (van); truck 36 and 104; bus 4 and 47; everything else is
  dropped;
* an object counts only if its box is at least 8 px high and 4 px wide, its visibility is at least
  0.1, and it is not ``iscrowd``;
* the pool is one frame per scene (a seeded draw), from the normal and both adverse sets;
* ``matched``: 512 frames whose person, car, truck and bus counts are each within 10% of the targets
  (those of ``train_v7p``) and whose night share is within 5 points of ``train_v7p``'s; night is
  measured from the mean luminance of the top of the frame, with the threshold fitted to
  ``train_v7p``'s own day and night frames;
* ``random``: 512 frames at random from the same pool (reported only).
"""

import argparse
import json
import random
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import numpy.typing as npt
from PIL import Image

CLASS_MAP = {
    22: 0,
    5: 1,
    103: 1,
    4: 2,
    47: 2,
    36: 3,
    104: 3,
}  # official class id -> person, car, bus, truck
CLASS_NAMES = ("person", "car", "bus", "truck")
MIN_HEIGHT_PX, MIN_WIDTH_PX, MIN_VISIBILITY = 8.0, 4.0, 0.1
WIDTH, HEIGHT = 2048, 1024
BRIGHTNESS_ROWS = 0.7  # the top 70% of the frame (the bottom of an ego view can hold the hood)
CONDITIONS = ("normal", "adverse_1", "adverse_2")
DEFAULT_TARGET = (1690.0, 4076.0, 55.0, 214.0)  # person, car, bus, truck in train_v7p
DEFAULT_NIGHT = 0.39


def object_class(annotation: Dict[str, Any]) -> Optional[int]:
    """This project's class id (0 person, 1 car, 2 bus, 3 truck) of one official annotation.

    None if it is dropped by the class mapping, the size rule, the visibility rule or ``iscrowd``.
    """
    cls = CLASS_MAP.get(annotation["class_id"])
    box = annotation["box"]
    if (
        cls is None
        or annotation.get("iscrowd")
        or box["h"] < MIN_HEIGHT_PX
        or box["w"] < MIN_WIDTH_PX
    ):
        return None
    try:
        visibility = float(json.loads(annotation["attributes"]["user_data"])["visibility"])
    except (KeyError, ValueError, TypeError):
        return None
    return cls if visibility >= MIN_VISIBILITY else None


def yolo_line(cls: int, box: Dict[str, float]) -> Optional[str]:
    """One YOLO label line for a pixel box, clipped to the image, or None if nothing is left."""
    x0, y0 = max(float(box["x"]), 0.0), max(float(box["y"]), 0.0)
    x1, y1 = min(float(box["x"] + box["w"]), WIDTH), min(float(box["y"] + box["h"]), HEIGHT)
    if x1 - x0 < 1 or y1 - y0 < 1:
        return None
    return (
        f"{cls} {(x0 + x1) / 2 / WIDTH:.6f} {(y0 + y1) / 2 / HEIGHT:.6f} "
        f"{(x1 - x0) / WIDTH:.6f} {(y1 - y0) / HEIGHT:.6f}"
    )


def frame_labels(annotations: Sequence[Dict[str, Any]]) -> List[Tuple[int, Dict[str, float]]]:
    """(class id, box) of every annotation that passes the rules."""
    kept = []
    for annotation in annotations:
        cls = object_class(annotation)
        if cls is not None:
            kept.append((cls, annotation["box"]))
    return kept


def brightness(image: Image.Image) -> float:
    """Mean luma (0-255) of the top ``BRIGHTNESS_ROWS`` of the frame, on a 1/8 scale copy."""
    rgb = image.convert("RGB")
    rgb = rgb.crop((0, 0, rgb.width, int(rgb.height * BRIGHTNESS_ROWS)))
    small = np.asarray(rgb.reduce(8), dtype=np.float64)
    return float((0.299 * small[..., 0] + 0.587 * small[..., 1] + 0.114 * small[..., 2]).mean())


def fit_night_threshold(values: Sequence[float], is_night: Sequence[bool]) -> Tuple[float, float]:
    """(threshold, accuracy): the brightness below which a frame is night, fitted to labels."""
    order = np.argsort(values)
    sorted_values = np.asarray(values)[order]
    night = np.asarray(is_night)[order]
    best_threshold, best_accuracy = float(sorted_values[0]), 0.0
    for i in range(1, len(sorted_values)):
        threshold = float((sorted_values[i - 1] + sorted_values[i]) / 2.0)
        accuracy = float(((sorted_values < threshold) == night).mean())
        if accuracy > best_accuracy:
            best_threshold, best_accuracy = threshold, accuracy
    return best_threshold, best_accuracy


def choose_matched(  # pylint: disable=too-many-locals,too-many-arguments
    counts: npt.NDArray[np.int_],
    night: npt.NDArray[np.bool_],
    targets: Sequence[float],
    night_share: float,
    n: int,
    seed: int,
    iterations: int = 800_000,
    tolerance: float = 0.1,
    night_tolerance: float = 0.05,
) -> Tuple[List[int], bool]:
    """Indices of ``n`` rows whose class counts and night share are closest to the targets.

    Also whether all are within tolerance. A seeded swap search over a score in which 1.0 means
    exactly at the tolerance.
    """
    rng = random.Random(seed)
    target = np.asarray(targets, dtype=float)
    chosen = rng.sample(range(len(counts)), n)
    inside = set(chosen)
    outside = [i for i in range(len(counts)) if i not in inside]
    totals = counts[chosen].sum(axis=0).astype(float)
    nights = float(night[chosen].sum())

    def score(sums: npt.NDArray[np.float64], night_count: float) -> float:
        count_term = (((sums - target) / (tolerance * target)) ** 2).sum()
        return float(count_term + ((night_count / n - night_share) / night_tolerance) ** 2)

    best = score(totals, nights)
    for _ in range(iterations):
        a, b = rng.randrange(n), rng.randrange(len(outside))
        trial = totals - counts[chosen[a]] + counts[outside[b]]
        trial_nights = nights - float(night[chosen[a]]) + float(night[outside[b]])
        trial_score = score(trial, trial_nights)
        if trial_score < best:
            chosen[a], outside[b] = outside[b], chosen[a]
            totals, nights, best = trial, trial_nights, trial_score
    within = bool(
        (np.abs(totals / target - 1.0) <= tolerance).all()
        and abs(nights / n - night_share) <= night_tolerance
    )
    return sorted(chosen), within


def pick_frames(annotations_root: Path, seed: int) -> List[Dict[str, Any]]:
    """One seeded frame per scene of every condition (condition, scene, stamp, annotation)."""
    frames = []
    for condition in CONDITIONS:
        for scene in sorted(p.name for p in (annotations_root / condition).iterdir() if p.is_dir()):
            files = sorted((annotations_root / condition / scene / "CS_FRONT").glob("*.json"))
            if not files:
                continue
            choice = random.Random(f"{seed}-{condition}-{scene}").choice(files)
            frames.append(
                {
                    "condition": condition,
                    "scene": scene,
                    "stamp": choice.name.split("_")[0],
                    "annotation": choice,
                }
            )
    return frames


def rgb_path(raw: Path, frame: Dict[str, Any]) -> Path:
    """The RGB frame of a picked frame in the dataset's own folder."""
    condition, scene, stamp = frame["condition"], frame["scene"], frame["stamp"]
    path: Path = raw / condition / "rgb" / "rgb" / scene / "CS_FRONT" / f"{stamp}.png"
    return path


def v7p_night_calibration(batch: Path) -> Tuple[float, float, int]:
    """(threshold, accuracy, frames) of the brightness rule fitted on a batch's ego frames."""
    data = json.loads((batch / "annotations.json").read_text(encoding="utf-8"))
    values, night = [], []
    for image in data["images"]:
        if image.get("view") != "ego":
            continue
        with Image.open(batch / "images" / Path(image["file_name"]).name) as im:
            values.append(brightness(im))
        night.append(image["time_of_day"] == "night")
    threshold, accuracy = fit_night_threshold(values, night)
    return threshold, accuracy, len(values)


def write_batch(out: Path, rows: List[Dict[str, Any]], seed: int) -> Dict[str, int]:
    """Write the chosen frames as images, YOLO labels, train/val lists, data.yaml and a manifest."""
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "labels").mkdir(parents=True, exist_ok=True)
    for row in rows:
        stem = row["name"]
        with Image.open(row["rgb"]) as im:
            im.convert("RGB").save(out / "images" / f"{stem}.png")
        lines = [line for cls, box in row["labels"] if (line := yolo_line(cls, box))]
        (out / "labels" / f"{stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    stems = [row["name"] for row in rows]
    order = random.Random(seed).sample(stems, len(stems))
    val, train = sorted(order[: len(order) // 10]), sorted(order[len(order) // 10 :])
    for name, group in (("train", train), ("val", val)):
        text = "\n".join(str((out / "images" / f"{s}.png").resolve()) for s in group) + "\n"
        (out / f"{name}.txt").write_text(text, encoding="utf-8")
    (out / "data.yaml").write_text(
        f"path: {out.resolve().as_posix()}\ntrain: train.txt\nval: val.txt\n"
        "names:\n  0: person\n  1: car\n  2: bus\n  3: truck\n",
        encoding="utf-8",
    )
    return {"train": len(train), "val": len(val)}


def main() -> None:  # pylint: disable=too-many-locals
    """Pick the pool, measure it, choose the frames, write the batch, and print what was chosen."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument(
        "--annotations", type=Path, default=Path("external_data/realdrivesim/annotations_2d")
    )
    parser.add_argument(
        "--raw", type=Path, default=Path(r"F:\vscode\Sensor_Fusion_Study\data\realDriveSim\raw")
    )
    parser.add_argument("--calibration-batch", type=Path, default=Path("live_dataset/train_v7p"))
    parser.add_argument("--mode", choices=["matched", "random"], required=True)
    parser.add_argument("--n", type=int, default=512)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--target", type=float, nargs=4, default=list(DEFAULT_TARGET))
    parser.add_argument("--night-share", type=float, default=DEFAULT_NIGHT)
    parser.add_argument(
        "--cache", type=Path, default=Path("external_data/realdrivesim/pool_cache.json")
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    frames = pick_frames(args.annotations, args.seed)
    cache: Dict[str, Any] = {}
    if args.cache.exists():
        cache = json.loads(args.cache.read_text(encoding="utf-8"))

    def measure(frame: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        key = f"{frame['condition']}/{frame['scene']}/{frame['stamp']}"
        if key in cache:
            return key, cache[key]
        data = json.loads(frame["annotation"].read_text(encoding="utf-8"))
        labels = frame_labels(data["annotations"])
        with Image.open(rgb_path(args.raw, frame)) as im:
            return key, {"labels": labels, "brightness": brightness(im)}

    with ThreadPoolExecutor(max_workers=8) as pool:
        for key, value in pool.map(measure, frames):
            cache[key] = value
    args.cache.parent.mkdir(parents=True, exist_ok=True)
    args.cache.write_text(json.dumps(cache), encoding="utf-8")

    threshold, accuracy, calibration_frames = v7p_night_calibration(args.calibration_batch)
    print(
        f"night rule: mean luma of the top {int(BRIGHTNESS_ROWS * 100)}% below {threshold:.1f}; "
        f"accuracy {accuracy:.3f} on {calibration_frames} {args.calibration_batch.name} ego frames"
    )
    rows = []
    for frame in frames:
        entry = cache[f"{frame['condition']}/{frame['scene']}/{frame['stamp']}"]
        rows.append(
            {
                "rgb": rgb_path(args.raw, frame),
                "labels": list(entry["labels"]),
                "night": entry["brightness"] < threshold,
                "condition": frame["condition"],
                "name": f"rds_{frame['condition']}_{frame['scene']}_{frame['stamp']}",
            }
        )
    counts = np.array([[sum(1 for c, _ in r["labels"] if c == k) for k in range(4)] for r in rows])
    night = np.array([r["night"] for r in rows])
    print(
        f"pool: {len(rows)} frames; night share {night.mean():.2f}; "
        f"counts per frame {counts.mean(axis=0).round(2)}"
    )

    if args.mode == "matched":
        picked, within = choose_matched(
            counts, night, args.target, args.night_share, args.n, args.seed
        )
        if not within:
            print("WARNING: the search did not reach every tolerance")
    else:
        picked, within = sorted(random.Random(args.seed).sample(range(len(rows)), args.n)), None
    chosen = [rows[i] for i in picked]
    sums = counts[picked].sum(axis=0)
    print(
        "chosen counts",
        dict(zip(CLASS_NAMES, (int(v) for v in sums))),
        "targets",
        dict(zip(CLASS_NAMES, (int(v) for v in args.target))),
        "relative error",
        tuple(round(float(s / t - 1.0), 3) for s, t in zip(sums, args.target)),
    )
    print(
        f"night share {night[picked].mean():.3f} (target {args.night_share});",
        "conditions",
        dict(Counter(r["condition"] for r in chosen)),
        "; within tolerance:",
        within,
    )
    print(write_batch(args.out, chosen, args.seed))
    manifest = {
        "mode": args.mode,
        "seed": args.seed,
        "night_threshold": threshold,
        "night_accuracy_on_calibration_batch": accuracy,
        "targets": dict(zip(CLASS_NAMES, args.target)),
        "chosen_counts": dict(zip(CLASS_NAMES, (int(v) for v in sums))),
        "frames": [r["name"] for r in chosen],
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
