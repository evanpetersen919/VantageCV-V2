"""Write a KITTI-style 3D detection folder from a rendered dataset's ``annotations.json``.

    PYTHONPATH=. python bin/export_kitti.py --dataset live_dataset/train_v8a --out kitti_out

For every image that has a KITTI projection matrix (forward-looking cameras; overview cameras have
none) it writes ``label_2/<id>.txt``, ``calib/<id>.txt`` and, with ``--images copy``,
``image_2/<id>.png``; boxes are in the level camera frame described in
``src/export/box3d_formats.py``. ``ImageSets/all.txt`` lists the ids.
"""

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from src.export.box3d_formats import KITTI_TYPES, CameraBox3D, calibration_text, kitti_label_line


def export_kitti(  # pylint: disable=too-many-locals
    dataset: Path, out: Path, images: str = "none"
) -> Dict[str, int]:
    """Write the KITTI folder; returns counts of images and boxes written and skipped."""
    data = json.loads((dataset / "annotations.json").read_text(encoding="utf-8"))
    names = {c["id"]: c["name"] for c in data["categories"]}
    by_image: Dict[int, List[Dict[str, Any]]] = {}
    for annotation in data["annotations"]:
        by_image.setdefault(annotation["image_id"], []).append(annotation)
    for folder in ("label_2", "calib", "ImageSets") + (("image_2",) if images == "copy" else ()):
        (out / folder).mkdir(parents=True, exist_ok=True)
    counts = {"images": 0, "boxes": 0, "skipped_images": 0, "skipped_boxes": 0}
    listed: List[str] = []
    for image in data["images"]:
        if "kitti_P2" not in image:
            counts["skipped_images"] += 1
            continue
        stem = f"{image['id']:06d}"
        lines = []
        for annotation in by_image.get(image["id"], []):
            kitti_type = KITTI_TYPES.get(names.get(annotation["category_id"], ""))
            if kitti_type is None or "box3d" not in annotation:
                counts["skipped_boxes"] += 1
                continue
            b = annotation["box3d"]
            box = CameraBox3D(
                tuple(b["location"]), tuple(b["dimensions_hwl"]), b["rotation_y"], b["alpha"]
            )
            lines.append(
                kitti_label_line(
                    kitti_type,
                    annotation["truncation"],
                    annotation["visibility_fraction"],
                    tuple(annotation["bbox"]),
                    box,
                )
            )
            counts["boxes"] += 1
        text = "\n".join(lines) + ("\n" if lines else "")
        (out / "label_2" / f"{stem}.txt").write_text(text, encoding="utf-8")
        (out / "calib" / f"{stem}.txt").write_text(
            calibration_text(np.array(image["kitti_P2"]).reshape(3, 4)), encoding="utf-8"
        )
        if images == "copy":
            source = dataset / "images" / Path(image["file_name"]).name
            shutil.copyfile(source, out / "image_2" / f"{stem}.png")
        listed.append(stem)
        counts["images"] += 1
    (out / "ImageSets" / "all.txt").write_text("\n".join(listed) + "\n", encoding="utf-8")
    return counts


def main() -> None:
    """Parse arguments and export."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--images", choices=["none", "copy"], default="none")
    args = parser.parse_args()
    print(export_kitti(args.dataset, args.out, args.images))


if __name__ == "__main__":
    main()
