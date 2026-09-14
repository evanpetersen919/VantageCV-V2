"""Integration tests for checkpointed/resumable dataset generation.

Covers MASTER_PROMPT Section 3.8's own "Checkpoints restore correctly"
and "Output consistency" test bullets, applied to the
interrupted-then-resumed case.
"""

import json
from unittest.mock import patch

from src.orchestration.dataset_generator import generate_and_render_one_scenario, generate_dataset
from src.orchestration.resume_handler import (
    Checkpoint,
    generate_dataset_resumable,
    load_checkpoint,
    save_checkpoint,
)

# urban_config, bounds fixtures: see tests/conftest.py


def test_checkpoint_round_trips_through_disk(tmp_path) -> None:
    """A saved checkpoint loads back with the same completed indices."""
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint = Checkpoint(completed_indices={0, 1, 2})

    save_checkpoint(checkpoint_path, checkpoint)
    loaded = load_checkpoint(checkpoint_path)

    assert loaded.completed_indices == {0, 1, 2}


def test_load_checkpoint_missing_file_returns_empty(tmp_path) -> None:
    """No checkpoint file yet (first run) loads as empty, not an error."""
    checkpoint = load_checkpoint(tmp_path / "does_not_exist.json")
    assert checkpoint.completed_indices == set()


def test_resumable_generation_from_scratch_matches_sequential(
    urban_config, bounds, tmp_path
) -> None:
    """A completely fresh resumable run (no prior checkpoint) produces
    the same COCO output as the plain sequential generator."""
    sequential_dir = tmp_path / "sequential"
    resumable_dir = tmp_path / "resumable"

    sequential_result = generate_dataset(
        num_scenarios=3,
        base_seed=500,
        config=urban_config,
        bounds=bounds,
        output_dir=sequential_dir,
    )
    resumable_result = generate_dataset_resumable(
        num_scenarios=3, base_seed=500, config=urban_config, bounds=bounds, output_dir=resumable_dir
    )

    sequential_coco = json.loads(sequential_result.coco_path.read_text(encoding="utf-8"))
    resumable_coco = json.loads(resumable_result.coco_path.read_text(encoding="utf-8"))

    assert sequential_coco["images"] == resumable_coco["images"]
    assert sequential_coco["annotations"] == resumable_coco["annotations"]


def test_checkpoint_restores_correctly_after_simulated_crash(
    urban_config, bounds, tmp_path
) -> None:
    """Simulating a crash after 2 of 5 scenarios (by calling the
    resumable generator with num_scenarios=2, matching what a real crash
    would have left on disk), then resuming with the full num_scenarios=5,
    produces the same final output as an uninterrupted 5-scenario run --
    and does not regenerate the first 2 scenarios' geometry a second
    time."""
    base_seed = 600
    interrupted_dir = tmp_path / "interrupted"
    clean_dir = tmp_path / "clean"

    # "Crash" after scenario 0 and 1 complete.
    generate_dataset_resumable(
        num_scenarios=2,
        base_seed=base_seed,
        config=urban_config,
        bounds=bounds,
        output_dir=interrupted_dir,
    )
    checkpoint = load_checkpoint(interrupted_dir / "checkpoint.json")
    assert checkpoint.completed_indices == {0, 1}

    # Resume: request all 5 scenarios. Scenarios 0-1 must be loaded from
    # their part files, not regenerated -- verified by patching the
    # actual generation function and asserting it's only called for the
    # 3 new scenarios.
    with patch(
        "src.orchestration.resume_handler.generate_and_render_one_scenario",
        side_effect=generate_and_render_one_scenario,
    ) as mock_generate:
        resumed_result = generate_dataset_resumable(
            num_scenarios=5,
            base_seed=base_seed,
            config=urban_config,
            bounds=bounds,
            output_dir=interrupted_dir,
        )

    assert mock_generate.call_count == 3  # only scenarios 2, 3, 4
    assert resumed_result.num_frames == 5

    final_checkpoint = load_checkpoint(interrupted_dir / "checkpoint.json")
    assert final_checkpoint.completed_indices == {0, 1, 2, 3, 4}

    # Output consistency: matches an uninterrupted 5-scenario run exactly.
    clean_result = generate_dataset(
        num_scenarios=5,
        base_seed=base_seed,
        config=urban_config,
        bounds=bounds,
        output_dir=clean_dir,
    )
    resumed_coco = json.loads(resumed_result.coco_path.read_text(encoding="utf-8"))
    clean_coco = json.loads(clean_result.coco_path.read_text(encoding="utf-8"))

    assert resumed_coco["images"] == clean_coco["images"]
    assert resumed_coco["annotations"] == clean_coco["annotations"]


def test_resumable_generation_is_idempotent_when_already_complete(
    urban_config, bounds, tmp_path
) -> None:
    """Calling the resumable generator again after a fully-completed run
    does not regenerate anything."""
    generate_dataset_resumable(
        num_scenarios=2, base_seed=700, config=urban_config, bounds=bounds, output_dir=tmp_path
    )

    with patch(
        "src.orchestration.resume_handler.generate_and_render_one_scenario",
        side_effect=generate_and_render_one_scenario,
    ) as mock_generate:
        generate_dataset_resumable(
            num_scenarios=2, base_seed=700, config=urban_config, bounds=bounds, output_dir=tmp_path
        )

    assert mock_generate.call_count == 0
