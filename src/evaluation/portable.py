"""Move a YOLO dataset between machines: re-root its image lists and write its ``data.yaml``.

``bin/export_yolo.py`` writes ``train.txt``/``val.txt`` with absolute paths from the machine that
made them (for example ``F:\\datasets\\ds\\images\\100k\\train\\a.jpg``). Copied to a cluster those
paths point nowhere. Ultralytics finds each label by swapping ``images`` for ``labels`` in the image
path, so only the part of each path from its ``images`` folder onward matters; everything before
it is replaced with the dataset's new location.
"""

from pathlib import Path, PureWindowsPath
from typing import Dict, Iterable, List, Sequence

from src.evaluation.yolo_export import label_path_for

CLASS_NAMES: Dict[int, str] = {0: "person", 1: "car", 2: "bus", 3: "truck"}


def reroot_image_path(line: str, dataset_root: Path) -> str:
    """``line`` (an absolute image path from any OS) placed under ``dataset_root``.

    Everything from the path's last ``images`` folder onward is kept, so
    ``F:\\data\\ds\\images\\100k\\train\\a.jpg`` becomes ``<dataset_root>/images/100k/train/a.jpg``.
    """
    parts = PureWindowsPath(line.strip()).parts
    if "images" not in parts:
        raise ValueError(f"no 'images' folder in image path: {line!r}")
    index = len(parts) - 1 - parts[::-1].index("images")
    return (dataset_root / Path(*parts[index:])).as_posix()


def reroot_image_list(lines: Iterable[str], dataset_root: Path) -> List[str]:
    """``reroot_image_path`` for every non-empty line."""
    return [reroot_image_path(line, dataset_root) for line in lines if line.strip()]


def write_rerooted_lists(source_dir: Path, dataset_root: Path, out_dir: Path) -> Dict[str, Path]:
    """Write ``<dataset>_train.txt`` / ``<dataset>_val.txt`` into ``out_dir``.

    Reads ``train.txt``/``val.txt`` from ``source_dir`` and re-roots every path under
    ``dataset_root`` (where the dataset's ``images/`` and ``labels/`` now live). Returns the two
    new file paths keyed ``"train"`` and ``"val"``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written: Dict[str, Path] = {}
    for split in ("train", "val"):
        source = source_dir / f"{split}.txt"
        lines = reroot_image_list(source.read_text(encoding="utf-8").splitlines(), dataset_root)
        target = out_dir / f"{dataset_root.name}_{split}.txt"
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written[split] = target
    return written


def data_yaml(train_lists: Sequence[Path], val_list: Path) -> str:
    """A ``data.yaml`` for ultralytics: one or more train lists (a mixed dataset has several),
    one validation list, and this project's four classes."""
    train_block = "\n".join(f"  - {path.as_posix()}" for path in train_lists)
    names_block = "\n".join(f"  {index}: {name}" for index, name in CLASS_NAMES.items())
    return (
        f"path: {val_list.parent.as_posix()}\n"
        f"train:\n{train_block}\n"
        f"val: {val_list.as_posix()}\n"
        f"names:\n{names_block}\n"
    )


def write_fraction_list(source_list: Path, fraction: float, out_path: Path) -> Path:
    """Write the first ``round(fraction * n)`` lines of ``source_list`` to ``out_path``.

    The control's list is a seeded random order, so the first lines are a random sample, and a
    smaller fraction is always contained in a larger one (25% inside 50% inside 100%).
    """
    lines = [line for line in source_list.read_text(encoding="utf-8").splitlines() if line.strip()]
    count = round(len(lines) * fraction)
    out_path.write_text("\n".join(lines[:count]) + "\n", encoding="utf-8")
    return out_path


def missing_files(list_path: Path) -> List[str]:
    """Image files listed in ``list_path`` that do not exist, plus any whose label file is
    missing (a label file may be empty, but it must exist for ultralytics to count the image)."""
    problems: List[str] = []
    for line in list_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        image = Path(line.strip())
        if not image.exists():
            problems.append(f"image missing: {image}")
        elif not label_path_for(image).exists():
            problems.append(f"label missing: {label_path_for(image)}")
    return problems
