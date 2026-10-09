"""Measure rider, bike and motor statistics in BDD100K's detection labels.

    PYTHONPATH=. python bin/measure_rider_stats.py \
        --labels-zip C:/Users/evanp/Downloads/bdd100k_labels.zip --split train \
        --out results/rider_stats_bdd100k_train.json

Per class (rider, bike, motor, and person and car for scale): instances, images that
contain one, instances per image, box size and position (percentiles), occluded and
truncated rates, all split by time of day. Then how a ``rider`` box pairs with a ``bike``
or ``motor`` box (rider-vehicle pairing, unridden vehicles, vehicles with two riders), at
three overlap thresholds so the dependence on that choice is visible. Nothing is
estimated: every value is counted from the labels. The numbers are the targets the
generator is matched to (docs/riders/).
"""

import argparse
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple

import numpy as np

CLASSES = ("rider", "bike", "motor", "person", "car")
VEHICLES = ("bike", "motor")
PERCENTILES = (5, 25, 50, 75, 95)
OVERLAP_THRESHOLDS = (0.1, 0.3, 0.5)
Box = Tuple[float, float, float, float]
IMAGE_HEIGHT_PX = 720.0
IMAGE_WIDTH_PX = 1280.0


def overlap_over_min(a: Box, b: Box) -> float:
    """Intersection area over the smaller box's area (1 when one box lies inside the other)."""
    width = min(a[2], b[2]) - max(a[0], b[0])
    height = min(a[3], b[3]) - max(a[1], b[1])
    if width <= 0.0 or height <= 0.0:
        return 0.0
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return float(width * height / smaller) if smaller > 0.0 else 0.0


def match_riders(
    riders: Sequence[Box], vehicles: Sequence[Box], threshold: float
) -> List[Tuple[int, int]]:
    """Greedy one-to-one (rider, vehicle) index pairs by largest overlap, at least ``threshold``."""
    scored = sorted(
        (
            (overlap_over_min(rider, vehicle), i, j)
            for i, rider in enumerate(riders)
            for j, vehicle in enumerate(vehicles)
        ),
        reverse=True,
    )
    used_riders: Set[int] = set()
    used_vehicles: Set[int] = set()
    pairs: List[Tuple[int, int]] = []
    for score, i, j in scored:
        if score < threshold:
            break
        if i not in used_riders and j not in used_vehicles:
            used_riders.add(i)
            used_vehicles.add(j)
            pairs.append((i, j))
    return pairs


def vehicle_rider_counts(
    riders: Sequence[Box], vehicles: Sequence[Box], threshold: float
) -> List[int]:
    """Per vehicle, how many riders overlap it by at least ``threshold`` (a pillion is 2)."""
    return [
        sum(1 for rider in riders if overlap_over_min(rider, vehicle) >= threshold)
        for vehicle in vehicles
    ]


def _percentiles(values: Sequence[float]) -> Dict[str, float]:
    """The standard percentiles of ``values`` (empty gives an empty dict)."""
    if len(values) == 0:
        return {}
    return {f"p{p}": float(np.percentile(values, p)) for p in PERCENTILES}


def _rate(flags: Sequence[bool]) -> float:
    """Fraction of True in ``flags`` (nan-free: 0.0 when empty)."""
    return float(np.mean(flags)) if len(flags) else 0.0


def read_images(labels_zip: Path, split: str) -> List[Dict[str, Any]]:
    """Every image of ``split``: time, weather and objects (category, box, occluded, truncated)."""
    images: List[Dict[str, Any]] = []
    with zipfile.ZipFile(labels_zip) as archive:
        for info in archive.infolist():
            if not info.filename.startswith(f"100k/{split}/") or not info.filename.endswith(
                ".json"
            ):
                continue
            data = json.loads(archive.read(info))
            frame = data["frames"][0]
            objects = []
            for label in frame["objects"]:
                box = label.get("box2d")
                if box is None:
                    continue
                attributes = label.get("attributes", {})
                objects.append(
                    (
                        label["category"],
                        (box["x1"], box["y1"], box["x2"], box["y2"]),
                        bool(attributes.get("occluded", False)),
                        bool(attributes.get("truncated", False)),
                    )
                )
            images.append(
                {
                    "time": data.get("attributes", {}).get("timeofday", "undefined"),
                    "weather": data.get("attributes", {}).get("weather", "undefined"),
                    "objects": objects,
                }
            )
    return images


def class_statistics(images: Sequence[Dict[str, Any]], category: str) -> Dict[str, Any]:
    """Counts, geometry and occlusion of one class, overall and by time of day."""
    result: Dict[str, Any] = {}
    for scope in ("all", "daytime", "night", "dawn/dusk"):
        selected = [i for i in images if scope in ("all", i["time"])]
        counts = [sum(1 for o in i["objects"] if o[0] == category) for i in selected]
        rows = [o for i in selected for o in i["objects"] if o[0] == category]
        heights = [o[1][3] - o[1][1] for o in rows]
        widths = [o[1][2] - o[1][0] for o in rows]
        entry: Dict[str, Any] = {
            "images": len(selected),
            "instances": len(rows),
            "images_with": int(sum(1 for c in counts if c > 0)),
            "per_image_mean": float(np.mean(counts)) if counts else 0.0,
            "p_at_least_1": _rate([c >= 1 for c in counts]),
            "p_at_least_2": _rate([c >= 2 for c in counts]),
            "occluded_rate": _rate([o[2] for o in rows]),
            "truncated_rate": _rate([o[3] for o in rows]),
            "height_px": _percentiles(heights),
            "width_px": _percentiles(widths),
            "aspect_h_over_w": _percentiles([h / w for h, w in zip(heights, widths) if w > 0]),
            "area_px": _percentiles([h * w for h, w in zip(heights, widths)]),
            "bottom_y_px": _percentiles([o[1][3] for o in rows]),
            "center_x_px": _percentiles([(o[1][0] + o[1][2]) / 2 for o in rows]),
        }
        result[scope] = entry
    return result


def pairing_statistics(images: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """How riders pair with bikes and motors, at each overlap threshold."""
    result: Dict[str, Any] = {}
    for threshold in OVERLAP_THRESHOLDS:
        tally: Dict[str, Any] = defaultdict(int)
        pillion: Dict[str, int] = defaultdict(int)
        by_time: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for image in images:
            riders = [o[1] for o in image["objects"] if o[0] == "rider"]
            tally["riders"] += len(riders)
            by_time[image["time"]]["riders"] += len(riders)
            matched_riders: Set[int] = set()
            for kind in VEHICLES:
                vehicles = [o[1] for o in image["objects"] if o[0] == kind]
                tally[f"{kind}_boxes"] += len(vehicles)
                by_time[image["time"]][f"{kind}_boxes"] += len(vehicles)
                pairs = match_riders(riders, vehicles, threshold)
                matched_riders.update(i for i, _ in pairs)
                tally[f"{kind}_with_rider"] += len(pairs)
                by_time[image["time"]][f"{kind}_with_rider"] += len(pairs)
                for count in vehicle_rider_counts(riders, vehicles, threshold):
                    if count >= 2:
                        pillion[kind] += 1
            tally["riders_matched_to_vehicle"] += len(matched_riders)
        entry: Dict[str, Any] = dict(tally)
        entry["riders_without_vehicle"] = entry.get("riders", 0) - entry.get(
            "riders_matched_to_vehicle", 0
        )
        entry["vehicles_with_two_or_more_riders_overlapping"] = dict(pillion)
        entry["by_time_of_day"] = {k: dict(v) for k, v in by_time.items()}
        for kind in VEHICLES:
            boxes = entry.get(f"{kind}_boxes", 0)
            entry[f"{kind}_unridden_fraction"] = (
                1.0 - entry.get(f"{kind}_with_rider", 0) / boxes if boxes else 0.0
            )
        riders = entry.get("riders", 0)
        entry["rider_matched_fraction"] = (
            entry.get("riders_matched_to_vehicle", 0) / riders if riders else 0.0
        )
        result[f"overlap_over_min>={threshold}"] = entry
    return result


def measure(images: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """All statistics of one split."""
    times: Dict[str, int] = defaultdict(int)
    for image in images:
        times[image["time"]] += 1
    return {
        "images": len(images),
        "images_by_time_of_day": dict(times),
        "image_size_px": [IMAGE_WIDTH_PX, IMAGE_HEIGHT_PX],
        "classes": {name: class_statistics(images, name) for name in CLASSES},
        "pairing": pairing_statistics(images),
    }


def _fmt(value: float, digits: int = 0) -> str:
    """A number with ``digits`` decimals (``-`` for a missing value)."""
    return f"{value:.{digits}f}"


def render_markdown(train: Dict[str, Any], val: Dict[str, Any]) -> str:
    """The statistics of the train and validation splits as markdown tables."""
    lines = [
        "| Class | Split | Instances | Images with one (share) | Per image |"
        " Per image containing one |"
        " Occluded | Truncated | Height px p5/p50/p95 | Aspect h/w p50 | Bottom y px p50 |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name in ("rider", "bike", "motor", "person", "car"):
        for label, data in (("train", train), ("val", val)):
            stat = data["classes"][name]["all"]
            heights = {k: stat["height_px"].get(k, 0.0) for k in ("p5", "p50", "p95")}
            containing = stat["instances"] / stat["images_with"] if stat["images_with"] else 0.0
            lines.append(
                f"| {name} | {label} | {stat['instances']:,} | {stat['images_with']:,}"
                f" ({_fmt(100 * stat['p_at_least_1'], 1)}%) | {_fmt(stat['per_image_mean'], 3)}"
                f" | {_fmt(containing, 2)} | {_fmt(100 * stat['occluded_rate'], 1)}%"
                f" | {_fmt(100 * stat['truncated_rate'], 1)}%"
                f" | {_fmt(heights['p5'])}/{_fmt(heights['p50'])}/{_fmt(heights['p95'])}"
                f" | {_fmt(stat['aspect_h_over_w'].get('p50', 0.0), 2)}"
                f" | {_fmt(stat['bottom_y_px'].get('p50', 0.0))} |"
            )
    lines += ["", "By time of day (train), share of images that contain the class:", ""]
    lines += ["| Class | daytime | night | dawn/dusk |", "|---|---|---|---|"]
    for name in ("rider", "bike", "motor"):
        cells = [
            f"{_fmt(100 * train['classes'][name][scope]['p_at_least_1'], 2)}%"
            f" ({train['classes'][name][scope]['instances']:,} instances)"
            for scope in ("daytime", "night", "dawn/dusk")
        ]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "Rider-vehicle pairing in train (overlap = intersection over the smaller box):",
        "",
    ]
    lines += [
        "| Overlap threshold | Riders matched to a bike or motor | Bike boxes with no rider |"
        " Motor boxes with no rider | Bikes with 2+ overlapping riders | Motors with 2+ |",
        "|---|---|---|---|---|---|",
    ]
    for key, entry in train["pairing"].items():
        pillion = entry["vehicles_with_two_or_more_riders_overlapping"]
        lines.append(
            f"| {key.split('>=')[1]} | {_fmt(100 * entry['rider_matched_fraction'], 1)}%"
            f" | {_fmt(100 * entry['bike_unridden_fraction'], 1)}%"
            f" | {_fmt(100 * entry['motor_unridden_fraction'], 1)}%"
            f" | {pillion.get('bike', 0)} | {pillion.get('motor', 0)} |"
        )
    return chr(10).join(lines) + chr(10)


def main() -> None:
    """Read a split's labels and write the statistics."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--labels-zip", type=Path)
    parser.add_argument("--split", default="train", choices=["train", "val"])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--markdown",
        type=Path,
        help="instead of reading labels: render --out (train) and --val-json as markdown here",
    )
    parser.add_argument("--val-json", type=Path)
    args = parser.parse_args()
    if args.markdown:
        train = json.loads(args.out.read_text(encoding="utf-8"))
        val = json.loads(args.val_json.read_text(encoding="utf-8"))
        args.markdown.write_text(render_markdown(train, val), encoding="utf-8")
        print(f"tables -> {args.markdown}")
        return
    if args.labels_zip is None:
        parser.error("--labels-zip is required unless --markdown is given")
    images = read_images(args.labels_zip, args.split)
    result = measure(images)
    result["source"] = {"labels_zip": args.labels_zip.name, "split": args.split}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"{len(images)} images -> {args.out}")


if __name__ == "__main__":
    main()
