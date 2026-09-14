"""Ray-based parallel scenario generation.

Implements MASTER_PROMPT Section 3.8's "Ray integration for parallel
processing" bullet and its own "Output consistency (single vs
distributed)" test bullet.

Scope note: Section 3.8 also lists "Scaling tests (2GPU, 4GPU, 8GPU)".
This codebase's actual workload (procedural geometry generation, camera
projection, JSON export) is pure CPU/NumPy -- nothing in Phases 1-6 uses
a GPU at all, so GPU-count scaling tests don't meaningfully apply to what
this pipeline does. What *is* genuinely testable and implemented here is
CPU-core parallelism via Ray's local-mode scheduler, which needs no
cluster or GPU. See KNOWN_GAPS_AND_ISSUES.md.
"""

# pylint: disable=duplicate-code
# generate_dataset_distributed's result-construction tail intentionally
# mirrors generate_dataset's own (dataset_generator.py) -- same shape of
# DatasetGenerationResult built the same way; extracting an even smaller
# shared helper for those ~8 lines would be over-engineering for the
# marginal duplication involved.

import time
from pathlib import Path
from typing import List, Tuple

import ray

from src.export.coco_exporter import CocoFrame, export_coco
from src.orchestration.dataset_generator import (
    Bounds,
    DatasetGenerationResult,
    generate_and_render_one_scenario,
    write_json,
)
from src.procedural.scenario import ScenarioTypeConfig
from src.validation.sanity_checker import check_annotation_count_consistency

generate_and_render_one_scenario_remote = ray.remote(generate_and_render_one_scenario)


def generate_dataset_distributed(  # pylint: disable=too-many-arguments
    num_scenarios: int,
    base_seed: int,
    config: ScenarioTypeConfig,
    bounds: Bounds,
    output_dir: Path,
    num_workers: int = 4,
) -> DatasetGenerationResult:
    """Parallel counterpart to ``dataset_generator.generate_dataset``.

    Each scenario is generated and rendered independently (no shared
    mutable state between scenarios -- every generator in this codebase
    is seeded and self-contained), so scenarios can run as concurrent Ray
    tasks with no coordination needed beyond collecting results. Produces
    byte-for-byte identical output to the sequential version for the same
    arguments (verified directly in
    ``tests/integration/test_distributed_runner.py``), since generation
    is fully deterministic per seed and independent per scenario.

    Parameters
    ----------
    num_scenarios, base_seed, config, bounds, output_dir
        Same as ``generate_dataset``.
    num_workers : int
        Ray CPU count to request if Ray isn't already initialized. If Ray
        is already running (e.g. a test suite initialized it once for
        several tests), this is ignored -- ``ray.init`` is a no-op after
        the first successful call within a process.

    Returns
    -------
    DatasetGenerationResult
    """
    start_time = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not ray.is_initialized():
        ray.init(num_cpus=num_workers, include_dashboard=False, logging_level="ERROR")

    futures = [
        generate_and_render_one_scenario_remote.remote(i, base_seed, config, bounds, output_dir)
        for i in range(num_scenarios)
    ]
    results: List[Tuple[CocoFrame, Path]] = ray.get(futures)

    frames = [frame for frame, _ in results]
    metadata_paths = [path for _, path in results]

    coco_data = export_coco(frames)
    coco_path = output_dir / "annotations.json"
    write_json(coco_path, coco_data)

    sanity_report = check_annotation_count_consistency(frames)
    elapsed_seconds = time.perf_counter() - start_time

    return DatasetGenerationResult(
        num_scenarios=num_scenarios,
        num_frames=len(frames),
        coco_path=coco_path,
        metadata_paths=metadata_paths,
        sanity_report=sanity_report,
        elapsed_seconds=elapsed_seconds,
    )
