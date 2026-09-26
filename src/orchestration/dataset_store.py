"""On-disk state of a live dataset run: manifest, per-scenario parts, merged COCO.

Every finished scenario is written as its own small file (``parts/scenario_0007.json``,
atomically) as soon as it completes, so a crash or an interrupt loses at most the
scenario in progress. ``merge`` rebuilds ``annotations.json`` from the parts (with
annotation ids renumbered globally), so an interrupted-then-resumed run produces the same
file as an uninterrupted one. The manifest records the settings the run started with, and
a resume with different settings is refused instead of silently mixing two datasets.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from src.export.coco_exporter import export_coco

PARTS_DIR = "parts"
MANIFEST_FILE = "manifest.json"
ANNOTATIONS_FILE = "annotations.json"


class ManifestMismatchError(ValueError):
    """The output directory belongs to a run with different settings."""


def write_json_atomic(path: Path, data: Any) -> None:
    """Write ``data`` as JSON so a reader (or a crash) never sees half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data), encoding="utf-8")
    os.replace(temporary, path)


class DatasetStore:
    """Reads and writes one run's files under ``output_dir``."""

    def __init__(self, output_dir: Path, categories: Optional[List[Dict[str, Any]]] = None) -> None:
        self.output_dir = output_dir
        self._categories = categories

    def check_manifest(self, settings: Dict[str, Any]) -> None:
        """Record ``settings`` on a fresh directory; on an existing one they must match."""
        path = self.output_dir / MANIFEST_FILE
        if not path.exists():
            write_json_atomic(path, settings)
            return
        existing = json.loads(path.read_text(encoding="utf-8"))
        differing = sorted(key for key in settings if existing.get(key) != settings[key])
        if differing:
            raise ManifestMismatchError(
                f"{self.output_dir} was started with different settings ({', '.join(differing)}); "
                "use a new output directory to change them"
            )

    def part_path(self, index: int) -> Path:
        """Where scenario ``index``'s part lives."""
        return self.output_dir / PARTS_DIR / f"scenario_{index:04d}.json"

    def load_part(self, index: int) -> Optional[Dict[str, Any]]:
        """Scenario ``index``'s finished part, or ``None`` if absent or unreadable."""
        path = self.part_path(index)
        if not path.exists():
            return None
        try:
            part: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return part if {"images", "annotations"} <= part.keys() else None

    def save_part(
        self, index: int, images: List[Dict[str, Any]], annotations: List[Dict[str, Any]]
    ) -> None:
        """Record scenario ``index`` as finished (an empty part means it was skipped)."""
        write_json_atomic(
            self.part_path(index),
            {"scenario_index": index, "images": images, "annotations": annotations},
        )

    def completed(self) -> Set[int]:
        """Indices of every finished scenario."""
        directory = self.output_dir / PARTS_DIR
        if not directory.exists():
            return set()
        indices = (int(path.stem.split("_")[1]) for path in directory.glob("scenario_*.json"))
        return {index for index in indices if self.load_part(index) is not None}

    def merge(self) -> Dict[str, Any]:
        """Combine every finished part into ``annotations.json`` and return it."""
        images: List[Dict[str, Any]] = []
        annotations: List[Dict[str, Any]] = []
        for index in sorted(self.completed()):
            part = self.load_part(index)
            assert part is not None
            images += part["images"]
            annotations += part["annotations"]
        for new_id, annotation in enumerate(annotations, start=1):
            annotation["id"] = new_id
        coco = export_coco([])
        coco["images"], coco["annotations"] = images, annotations
        if self._categories is not None:
            coco["categories"] = self._categories
        write_json_atomic(self.output_dir / ANNOTATIONS_FILE, coco)
        return coco
