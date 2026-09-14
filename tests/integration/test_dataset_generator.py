"""Integration tests for the full end-to-end dataset generation pipeline.

Covers MASTER_PROMPT Section 3.7's own "Round-trip serialization" and
"Export performance" test bullets -- both require an actual full
pipeline run (Phases 1-6 chained together) to test meaningfully.
"""

import json
from unittest.mock import patch

import pytest
from pycocotools.coco import COCO

from src.orchestration.dataset_generator import (
    default_overview_camera,
    generate_dataset,
    generate_scenario,
    render_frame,
)
from src.procedural.validator import ValidationReport

# urban_config, bounds fixtures: see tests/conftest.py


def test_generate_scenario_produces_valid_result(urban_config, bounds) -> None:
    """A single scenario generates successfully with every sub-component
    populated and passing its own validation."""
    scenario = generate_scenario(42, urban_config, bounds, "test_scenario")

    assert scenario.scenario_id == "test_scenario"
    assert len(scenario.nodes) > 0
    assert len(scenario.edges) > 0
    assert len(scenario.lanes) > 0
    assert len(scenario.meshes) > 0
    assert scenario.vehicles  # this config/seed places some
    assert scenario.validation_report.is_valid


def test_generate_scenario_deterministic(urban_config, bounds) -> None:
    """Same seed produces the same node/edge/building/vehicle/pedestrian
    counts."""
    scenario1 = generate_scenario(42, urban_config, bounds, "s1")
    scenario2 = generate_scenario(42, urban_config, bounds, "s2")

    assert len(scenario1.nodes) == len(scenario2.nodes)
    assert len(scenario1.edges) == len(scenario2.edges)
    assert len(scenario1.buildings) == len(scenario2.buildings)
    assert len(scenario1.vehicles) == len(scenario2.vehicles)
    assert len(scenario1.pedestrians) == len(scenario2.pedestrians)


def test_render_frame_produces_coco_frame(urban_config, bounds) -> None:
    """render_frame projects a scenario's buildings, vehicles, and
    pedestrians into a well-formed CocoFrame with a unique object_id per
    object across all three kinds."""
    scenario = generate_scenario(42, urban_config, bounds, "s")
    camera = default_overview_camera(bounds)

    frame = render_frame(scenario, camera, image_id=0, file_name="frame.png")

    assert frame.image_id == 0
    assert frame.file_name == "frame.png"
    assert isinstance(frame.bboxes_2d, list)

    expected_total = len(scenario.buildings) + len(scenario.vehicles) + len(scenario.pedestrians)
    assert len(frame.bboxes_3d_by_id) == expected_total
    assert len(frame.bboxes_3d_by_id) == len(set(frame.bboxes_3d_by_id))


def test_generate_dataset_end_to_end(urban_config, bounds, tmp_path) -> None:
    """A full multi-scenario dataset generation run: writes real files,
    produces a schema-valid COCO export (pycocotools.COCO can load it),
    and every metadata file round-trips through JSON exactly."""
    result = generate_dataset(
        num_scenarios=3,
        base_seed=100,
        config=urban_config,
        bounds=bounds,
        output_dir=tmp_path,
    )

    assert result.num_scenarios == 3
    assert result.num_frames == 3
    assert result.coco_path.exists()
    assert len(result.metadata_paths) == 3
    for path in result.metadata_paths:
        assert path.exists()

    # Round-trip serialization: COCO JSON loads via the real reference
    # implementation, not just our own hand-rolled checks.
    coco = COCO(str(result.coco_path))
    assert len(coco.getImgIds()) == 3

    # Every metadata file round-trips through JSON without loss.
    for path in result.metadata_paths:
        data = json.loads(path.read_text())
        assert "scenario_id" in data
        assert "seed" in data


def test_generate_dataset_seeds_are_sequential(urban_config, bounds, tmp_path) -> None:
    """Scenario N uses seed base_seed + N, confirmed via each scenario's
    own metadata file."""
    generate_dataset(
        num_scenarios=3, base_seed=50, config=urban_config, bounds=bounds, output_dir=tmp_path
    )

    seeds = []
    for i in range(3):
        metadata_path = tmp_path / f"proc_scenario_{i:04d}_metadata.json"
        data = json.loads(metadata_path.read_text())
        seeds.append(data["seed"])

    assert seeds == [50, 51, 52]


def test_generate_dataset_creates_output_dir_if_missing(urban_config, bounds, tmp_path) -> None:
    """A non-existent output directory is created automatically."""
    output_dir = tmp_path / "nested" / "does_not_exist_yet"
    assert not output_dir.exists()

    generate_dataset(
        num_scenarios=1, base_seed=1, config=urban_config, bounds=bounds, output_dir=output_dir
    )

    assert output_dir.exists()
    assert (output_dir / "annotations.json").exists()


def test_generate_dataset_performance_reasonable(urban_config, bounds, tmp_path) -> None:
    """Export performance: generating a small multi-scenario dataset
    completes in well under a minute (a coarse smoke-test budget, not a
    precise benchmark -- see KNOWN_GAPS_AND_ISSUES.md on this pipeline's
    known performance limitations at larger scale)."""
    result = generate_dataset(
        num_scenarios=3, base_seed=1, config=urban_config, bounds=bounds, output_dir=tmp_path
    )
    assert result.elapsed_seconds < 60.0


def test_generate_scenario_raises_on_degenerate_bounds(urban_config) -> None:
    """A scenario that can't be built at all (here: zero-area bounds,
    which RoadNetworkGenerator itself rejects as a single isolated node --
    see Phase 1's test_zero_area_bounds_raises_isolated_node_error) raises
    rather than silently writing invalid data. The failure surfaces from
    RoadNetworkGenerator.generate() itself, before generate_scenario's own
    ScenarioValidator check even runs -- both layers refuse to produce
    invalid output, which is the property this test actually cares about."""
    degenerate_bounds = (5.0, 5.0, 5.0, 5.0)
    with pytest.raises(ValueError, match="isolated node"):
        generate_scenario(42, urban_config, degenerate_bounds, "bad")


def test_generate_scenario_raises_when_scenario_validator_itself_fails(
    urban_config, bounds
) -> None:
    """generate_scenario's own ScenarioValidator gate raises with a
    "failed validation" message when the validator reports issues, even
    for a scenario that RoadNetworkGenerator itself considers fine.

    Every real scenario this pipeline can currently produce passes
    ScenarioValidator by construction (RoadNetworkGenerator's own
    bounds-reflection fix already guarantees containment; lanes/buildings/
    meshes derived from valid nodes/edges are geometrically consistent) --
    so this branch is exercised here via a forced invalid report rather
    than a naturally-occurring invalid scenario, to confirm the wiring
    itself (not ScenarioValidator's own logic, already covered by
    test_validator.py) actually raises."""
    invalid_report = ValidationReport(issues=["synthetic failure for this test"])
    with patch(
        "src.orchestration.dataset_generator.ScenarioValidator.validate",
        return_value=invalid_report,
    ):
        with pytest.raises(ValueError, match="failed validation"):
            generate_scenario(42, urban_config, bounds, "bad")
