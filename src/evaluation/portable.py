"""Move a YOLO dataset between machines: re-root its image lists and write its ``data.yaml``.

``bin/export_yolo.py`` writes ``train.txt``/``val.txt`` with absolute paths from the machine that
made them (for example ``F:\\datasets\\ds\\images\\100k\\train\\a.jpg``). Copied to a cluster those
paths point nowhere. Ultralytics finds each label by swapping ``images`` for ``labels`` in the image
path, so only the part of each path from its ``images`` folder onward matters; everything before
it is replaced with the dataset's new location.
"""

import random
from pathlib import Path, PureWindowsPath
from typing import Dict, Iterable, List, Optional, Sequence, Set

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


def data_yaml(
    train_lists: Sequence[Path], val_list: Path, names: Optional[Dict[int, str]] = None
) -> str:
    """A ``data.yaml`` for ultralytics: one or more train lists (a mixed dataset has several),
    one validation list, and this project's four classes."""
    names = CLASS_NAMES if names is None else names
    train_block = "\n".join(f"  - {path.as_posix()}" for path in train_lists)
    names_block = "\n".join(f"  {index}: {name}" for index, name in names.items())
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


def _image_lines(source_lists: Sequence[Path]) -> List[str]:
    """Every non-empty line of every list, in order."""
    lines: List[str] = []
    for source in source_lists:
        lines += [x for x in source.read_text(encoding="utf-8").splitlines() if x.strip()]
    return lines


def image_classes(image_line: str) -> Set[int]:
    """Class ids that appear in an image's label file (empty if it has none)."""
    label = label_path_for(Path(image_line.strip()))
    if not label.exists():
        return set()
    return {
        int(row.split()[0]) for row in label.read_text(encoding="utf-8").splitlines() if row.strip()
    }


def write_class_free_list(source_lists: Sequence[Path], classes: Set[int], out_path: Path) -> Path:
    """Write the images from ``source_lists`` whose labels contain none of ``classes``."""
    kept = [line for line in _image_lines(source_lists) if not image_classes(line) & classes]
    out_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return out_path


def class_counts(image_line: str) -> Dict[int, int]:
    """How many boxes of each class an image's label file holds (empty if it has none)."""
    label = label_path_for(Path(image_line.strip()))
    counts: Dict[int, int] = {}
    if label.exists():
        for row in label.read_text(encoding="utf-8").splitlines():
            if row.strip():
                counts[int(row.split()[0])] = counts.get(int(row.split()[0]), 0) + 1
    return counts


def write_ranked_list(  # pylint: disable=too-many-arguments
    source_lists: Sequence[Path],
    weights: Dict[int, float],
    count: int,
    out_path: Path,
    highest: bool = True,
) -> Path:
    """Write the ``count`` images with the highest (or, with ``highest=False``, the lowest)
    weighted box count (``weights`` per class); ties keep the source order. Used to give a
    supplement more or fewer instances of chosen classes without rendering anything."""
    lines = _image_lines(source_lists)
    score = {
        line: sum(weights.get(cls, 0.0) * n for cls, n in class_counts(line).items())
        for line in lines
    }
    chosen = sorted(lines, key=lambda line: -score[line] if highest else score[line])[:count]
    out_path.write_text("\n".join(chosen) + "\n", encoding="utf-8")
    return out_path


def write_random_list(source_lists: Sequence[Path], count: int, seed: int, out_path: Path) -> Path:
    """Write ``count`` images drawn at random (reproducibly) from ``source_lists``."""
    lines = _image_lines(source_lists)
    chosen = random.Random(seed).sample(lines, count)
    out_path.write_text("\n".join(chosen) + "\n", encoding="utf-8")
    return out_path
