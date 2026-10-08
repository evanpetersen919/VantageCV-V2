"""Write instance and semantic mask PNGs from a rendered dataset's ``annotations.json``.

    PYTHONPATH=. python bin/export_masks.py --dataset live_dataset/train_v8a --out masks_out

``instance/<id>.png`` is 16-bit (0 background, 1.. per annotation in file order),
``semantic/<id>.png`` is 8-bit (COCO category ids of the labelled objects only; 0 is everything
else, including road, buildings and sky) and
``instance_table/<id>.json`` maps instance values to annotation and category ids. Objects are
painted far to near; see ``src/export/masks.py`` for what the polygons are.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image

from src.export.masks import rasterise


def export_masks(dataset: Path, out: Path) -> int:
    """Write the masks of every image; returns how many images were written."""
    data = json.loads((dataset / "annotations.json").read_text(encoding="utf-8"))
    by_image: Dict[int, List[Dict[str, Any]]] = {}
    for annotation in data["annotations"]:
        by_image.setdefault(annotation["image_id"], []).append(annotation)
    for folder in ("instance", "semantic", "instance_table"):
        (out / folder).mkdir(parents=True, exist_ok=True)
    for image in data["images"]:
        size = (image["width"], image["height"])
        instance, semantic, table = rasterise(by_image.get(image["id"], []), size)
        stem = f"{image['id']:06d}"
        Image.fromarray(instance).save(out / "instance" / f"{stem}.png")
        Image.fromarray(semantic).save(out / "semantic" / f"{stem}.png")
        (out / "instance_table" / f"{stem}.json").write_text(json.dumps(table), encoding="utf-8")
    return len(data["images"])


def main() -> None:
    """Parse arguments and export."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(f"{export_masks(args.dataset, args.out)} images")


if __name__ == "__main__":
    main()
