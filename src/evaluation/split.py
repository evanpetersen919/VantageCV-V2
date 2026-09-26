"""Train / validation split of a live dataset, by scenario.

Several frames come from each generated scenario and share its buildings, vehicles,
season and weather. Splitting by image would put near-duplicates on both sides and inflate
the validation score, so whole scenarios go to one side. The split is deterministic for a
seed, and the split file records exactly which scenarios went where.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple

import numpy as np

ANNOTATIONS_FILE = "annotations.json"
CONDITION_KEYS = ("time_of_day", "weather", "view")


def split_scenarios(
    scenario_ids: Sequence[str], val_fraction: float, seed: int
) -> Tuple[List[str], List[str]]:
    """(train ids, validation ids), sorted; at least one scenario on each side if there are two."""
    if not 0.0 < val_fraction < 1.0:
        raise ValueError(f"val_fraction must be in (0, 1), got {val_fraction}")
    unique = sorted(set(scenario_ids))
    order = np.random.Generator(np.random.PCG64(seed)).permutation(len(unique))
    count = (
        min(max(1, round(len(unique) * val_fraction)), len(unique) - 1) if len(unique) > 1 else 0
    )
    validation = {unique[index] for index in order[:count]}
    return [s for s in unique if s not in validation], sorted(validation)


def _subset(coco: Dict[str, Any], image_ids: Set[int]) -> Dict[str, Any]:
    """The images with ``image_ids`` and their annotations (ids preserved)."""
    return {
        "images": [image for image in coco["images"] if image["id"] in image_ids],
        "annotations": [a for a in coco["annotations"] if a["image_id"] in image_ids],
        "categories": coco["categories"],
    }


def _summary(part: Dict[str, Any]) -> Dict[str, Any]:
    """Image, annotation and condition counts of one side of the split."""
    return {
        "images": len(part["images"]),
        "annotations": len(part["annotations"]),
        "scenarios": len({image["scenario_id"] for image in part["images"]}),
        **{
            key: dict(Counter(str(image.get(key, "?")) for image in part["images"]))
            for key in CONDITION_KEYS
        },
    }


def write_split(dataset_dir: Path, val_fraction: float = 0.1, seed: int = 0) -> Dict[str, Any]:
    """Write ``train.json``, ``val.json`` and ``split.json`` next to ``annotations.json``.

    Returns the summary that is also stored in ``split.json``.
    """
    coco = json.loads((dataset_dir / ANNOTATIONS_FILE).read_text(encoding="utf-8"))
    missing = [image["id"] for image in coco["images"] if "scenario_id" not in image]
    if missing:
        raise ValueError(f"{len(missing)} images have no scenario_id, cannot split by scenario")
    train_ids, val_ids = split_scenarios(
        [image["scenario_id"] for image in coco["images"]], val_fraction, seed
    )
    validation = set(val_ids)
    parts = {
        "train": _subset(
            coco, {i["id"] for i in coco["images"] if i["scenario_id"] not in validation}
        ),
        "val": _subset(coco, {i["id"] for i in coco["images"] if i["scenario_id"] in validation}),
    }
    if {i["scenario_id"] for i in parts["train"]["images"]} & validation:
        raise AssertionError("a scenario ended up on both sides of the split")
    for name, part in parts.items():
        (dataset_dir / f"{name}.json").write_text(json.dumps(part), encoding="utf-8")
    summary = {
        "seed": seed,
        "val_fraction": val_fraction,
        "train": _summary(parts["train"]),
        "val": _summary(parts["val"]),
        "train_scenarios": train_ids,
        "val_scenarios": val_ids,
    }
    (dataset_dir / "split.json").write_text(json.dumps(summary), encoding="utf-8")
    return summary
