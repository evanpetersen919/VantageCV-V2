"""Integration tests for Ray-based parallel dataset generation.

Covers MASTER_PROMPT Section 3.8's own "Ray task completion" and "Output
consistency (single vs distributed)" test bullets. "Scaling efficiency"
and GPU-count scaling tests are not applicable/testable here -- see
distributed_runner.py's module docstring.
"""

import json

import ray

from src.orchestration.dataset_generator import generate_dataset
from src.orchestration.distributed_runner import generate_dataset_distributed

# urban_config, bounds fixtures: see tests/conftest.py


def test_ray_task_completion(urban_config, bounds, tmp_path) -> None:
    """Ray tasks actually run and complete: a distributed generation run
    produces the expected number of frames and a valid COCO export."""
    result = generate_dataset_distributed(
        num_scenarios=3,
        base_seed=200,
        config=urban_config,
        bounds=bounds,
        output_dir=tmp_path,
        num_workers=2,
    )

    assert result.num_scenarios == 3
    assert result.num_frames == 3
    assert result.coco_path.exists()
    assert len(result.metadata_paths) == 3


def test_output_consistency_single_vs_distributed(urban_config, bounds, tmp_path) -> None:
    """The same (seed, config, bounds) inputs produce identical COCO
    output whether generated sequentially or via Ray -- generation is
    fully deterministic per seed and each scenario is independent, so
    parallelizing must not change the result."""
    sequential_dir = tmp_path / "sequential"
    distributed_dir = tmp_path / "distributed"

    sequential_result = generate_dataset(
        num_scenarios=3,
        base_seed=300,
        config=urban_config,
        bounds=bounds,
        output_dir=sequential_dir,
    )
    distributed_result = generate_dataset_distributed(
        num_scenarios=3,
        base_seed=300,
        config=urban_config,
        bounds=bounds,
        output_dir=distributed_dir,
        num_workers=2,
    )

    sequential_coco = json.loads(sequential_result.coco_path.read_text(encoding="utf-8"))
    distributed_coco = json.loads(distributed_result.coco_path.read_text(encoding="utf-8"))

    assert sequential_coco["images"] == distributed_coco["images"]
    assert sequential_coco["annotations"] == distributed_coco["annotations"]
    assert sequential_coco["categories"] == distributed_coco["categories"]


def test_generate_dataset_distributed_reuses_existing_ray_instance(
    urban_config, bounds, tmp_path
) -> None:
    """If Ray is already initialized (e.g. by an earlier test in the same
    process), generate_dataset_distributed reuses it rather than erroring
    on a duplicate ray.init() call."""
    if not ray.is_initialized():
        ray.init(
            num_cpus=2,
            include_dashboard=False,
            logging_level="ERROR",
            object_store_memory=200 * 1024 * 1024,
        )

    assert ray.is_initialized()

    result = generate_dataset_distributed(
        num_scenarios=2,
        base_seed=400,
        config=urban_config,
        bounds=bounds,
        output_dir=tmp_path,
        num_workers=2,
    )

    assert result.num_frames == 2
