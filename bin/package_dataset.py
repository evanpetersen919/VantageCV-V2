"""Build the self-contained release folder (Kaggle layout) from a rendered and split dataset.

    PYTHONPATH=. python bin/split_dataset.py live_dataset/kaggle_v1
    PYTHONPATH=. python bin/package_dataset.py \
        --source live_dataset/kaggle_v1 --out release/vantagecv_v1

Hard-links the images and maps where possible (use ``--copy`` to copy), writes COCO, YOLO
detection and segmentation labels, KITTI labels, instance masks and the class table, then
validates the folder and prints every problem found. See ``src/export/release_package.py``.
"""

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType

from src.export.dataset_card import write_card
from src.export.release_package import build_package, validate_package


def _load(name: str) -> ModuleType:
    """Import a sibling script of ``bin/`` by file name."""
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    """Package, add KITTI and instance masks, write the manifest, validate."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--name", default="v1", help="name used in the dataset card title")
    parser.add_argument("--copy", action="store_true", help="copy files instead of hard-linking")
    args = parser.parse_args()
    manifest = build_package(args.source, args.out, link=not args.copy)
    kitti = _load("export_kitti").export_kitti(args.source, args.out / "kitti")
    scratch = args.out / "_masks_tmp"
    count = _load("export_masks").export_masks(args.source, scratch)
    for folder in ("instance", "instance_table"):
        shutil.move(str(scratch / folder), str(args.out / folder))
    shutil.rmtree(scratch, ignore_errors=True)
    manifest["kitti"], manifest["instance_masks"] = kitti, count
    (args.out / "MANIFEST.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    write_card(args.out, args.source / "manifest.json", args.name)
    problems = validate_package(args.out)
    print(json.dumps(manifest["counts"]), f"| kitti {kitti} | instance masks {count}")
    print(f"{len(problems)} problems" + (":" if problems else " (clean)"))
    for line in problems[:40]:
        print(" ", line)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
