"""Resumable, checkpointed dataset generation.

Implements MASTER_PROMPT Section 3.8's "Fault tolerance and resumable
checkpoints" bullet and its own "Checkpoints restore correctly" /
"Output consistency (single vs distributed)" test bullets (the latter
applies equally to "interrupted-then-resumed vs never-interrupted").

Design: each scenario's COCO contribution (its own images/annotations
entries) is written to its own small JSON file
(``<scenario_id>_coco_part.json``) immediately after that scenario
completes, alongside a checkpoint file listing which scenario indices are
done. On resume, a completed scenario's contribution is *loaded* from its
part file rather than regenerated -- this is what makes resuming actually
skip the (otherwise fully re-run) compute for already-finished scenarios,
not just re-derive the same result a second time. Every generator in this
codebase is deterministic and scenarios are independent, so this is safe:
a resumed run produces byte-identical final output to an uninterrupted
one (verified directly in
``tests/integration/test_resume_handler.py``).
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from src.export.coco_exporter import export_coco
from src.orchestration.dataset_generator import (
    Bounds,
    DatasetGenerationResult,
    generate_and_render_one_scenario,
    write_json,
)
from src.procedural.scenario import ScenarioTypeConfig
from src.validation.sanity_checker import check_annotation_count_consistency_from_counts

_CHECKPOINT_FILENAME = "checkpoint.json"


@dataclass
class Checkpoint:
    """Tracks which scenario indices have already completed."""

    completed_indices: Set[int] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation."""
        return {"completed_indices": sorted(self.completed_indices)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        """Reconstruct a Checkpoint from its to_dict() representation."""
        return cls(completed_indices=set(data.get("completed_indices", [])))


def load_checkpoint(checkpoint_path: Path) -> Checkpoint:
    """Load a checkpoint from disk, or return an empty one if the file
    doesn't exist yet (first run, nothing completed)."""
    if not checkpoint_path.exists():
        return Checkpoint()
    return Checkpoint.from_dict(json.loads(checkpoint_path.read_text(encoding="utf-8")))


def save_checkpoint(checkpoint_path: Path, checkpoint: Checkpoint) -> None:
    """Persist a checkpoint to disk."""
    write_json(checkpoint_path, checkpoint.to_dict())


def _part_path(output_dir: Path, scenario_id: str) -> Path:
    return output_dir / f"{scenario_id}_coco_part.json"


def _resolve_one_scenario(  # pylint: disable=too-many-arguments
    index: int,
    base_seed: int,
    config: ScenarioTypeConfig,
    bounds: Bounds,
    output_dir: Path,
    checkpoint: Checkpoint,
    checkpoint_path: Path,
) -> Tuple[Dict[str, Any], Path]:
    """Resolve one scenario's COCO part and metadata path: load it from
    disk if the checkpoint already marks it complete, otherwise generate
    it fresh and record completion. Extracted from
    ``generate_dataset_resumable``'s own loop to keep that function's
    local-variable count manageable."""
    scenario_id = f"proc_scenario_{index:04d}"
    part_path = _part_path(output_dir, scenario_id)
    metadata_path = output_dir / f"{scenario_id}_metadata.json"

    if index in checkpoint.completed_indices and part_path.exists():
        part: Dict[str, Any] = json.loads(part_path.read_text(encoding="utf-8"))
        return part, metadata_path

    frame, metadata_path = generate_and_render_one_scenario(
        index=index, base_seed=base_seed, config=config, bounds=bounds, output_dir=output_dir
    )
    part_coco = export_coco([frame])
    part = {"images": part_coco["images"], "annotations": part_coco["annotations"]}
    write_json(part_path, part)

    checkpoint.completed_indices.add(index)
    save_checkpoint(checkpoint_path, checkpoint)

    return part, metadata_path


def generate_dataset_resumable(  # pylint: disable=too-many-arguments,too-many-locals
    num_scenarios: int,
    base_seed: int,
    config: ScenarioTypeConfig,
    bounds: Bounds,
    output_dir: Path,
    checkpoint_path: Optional[Path] = None,
) -> DatasetGenerationResult:
    """Generate a dataset, skipping any scenario already recorded as
    complete in the checkpoint file (from a prior, interrupted run).

    Parameters
    ----------
    num_scenarios, base_seed, config, bounds, output_dir
        Same as ``dataset_generator.generate_dataset``.
    checkpoint_path : Path, optional
        Defaults to ``output_dir / "checkpoint.json"``.

    Returns
    -------
    DatasetGenerationResult
    """
    start_time = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    if checkpoint_path is None:
        checkpoint_path = output_dir / _CHECKPOINT_FILENAME

    checkpoint = load_checkpoint(checkpoint_path)

    images: List[Dict[str, Any]] = []
    annotations: List[Dict[str, Any]] = []
    metadata_paths: List[Path] = []

    for i in range(num_scenarios):
        part, metadata_path = _resolve_one_scenario(
            index=i,
            base_seed=base_seed,
            config=config,
            bounds=bounds,
            output_dir=output_dir,
            checkpoint=checkpoint,
            checkpoint_path=checkpoint_path,
        )
        images.extend(part["images"])
        annotations.extend(part["annotations"])
        metadata_paths.append(metadata_path)

    # Each scenario's part file was built via export_coco([frame]) in
    # isolation, so every part's own annotation "id" numbering restarts
    # at 1 -- merging parts naively would produce colliding IDs across
    # scenarios (the exact defect QOL_RESEARCH_CHECKLIST.md Section
    # H.1's "no ID collisions" check exists to catch, and which
    # coco_exporter.export_coco's own single-pass counter prevents for
    # the non-resumable path). Renumber post-merge to restore global
    # uniqueness; bbox/segmentation/category content is untouched.
    for new_id, annotation in enumerate(annotations, start=1):
        annotation["id"] = new_id

    coco_data = export_coco([])
    coco_data["images"] = images
    coco_data["annotations"] = annotations
    coco_path = output_dir / "annotations.json"
    write_json(coco_path, coco_data)

    frame_count_by_image: Dict[int, int] = {}
    for ann in annotations:
        frame_count_by_image[ann["image_id"]] = frame_count_by_image.get(ann["image_id"], 0) + 1

    sanity_report = check_annotation_count_consistency_from_counts(
        [(img["id"], frame_count_by_image.get(img["id"], 0)) for img in images]
    )

    elapsed_seconds = time.perf_counter() - start_time

    return DatasetGenerationResult(
        num_scenarios=num_scenarios,
        num_frames=len(images),
        coco_path=coco_path,
        metadata_paths=metadata_paths,
        sanity_report=sanity_report,
        elapsed_seconds=elapsed_seconds,
    )
