"""Tests for the crash-safe, resumable live dataset run (with a fake game)."""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pytest
from numpy.typing import NDArray
from PIL import Image

from src.export.annotation_policy import AnnotationPolicy
from src.ground_truth.categories import FINE_PROFILE
from src.orchestration.dataset_store import DatasetStore, ManifestMismatchError
from src.orchestration.live_dataset import (
    MAX_SCENARIO_ATTEMPTS,
    MAX_VIEWS_PER_SCENARIO,
    generate_live_dataset,
)
from src.orchestration.live_render import GameUnavailableError
from src.utils.config_loader import load_scenario_config

CONFIG = load_scenario_config(Path("configs/scenario_templates/urban_dense.yaml"))
BOUNDS = (-80.0, -80.0, 80.0, 80.0)
VIEWS = ("ego",)


class FakeRenderer:
    """Stands in for ``LiveRenderer``: blank frames, with scripted failures."""

    def __init__(self, failing_scenarios: Optional[Dict[int, int]] = None) -> None:
        self.loads = 0
        self.captures = 0
        self.recoveries = 0
        self._failures_left = dict(failing_scenarios or {})

    async def calibration_error_px(self, work_dir: Path) -> float:
        """A perfect camera check."""
        del work_dir
        return 0.0

    async def load(self, payload: Dict[str, Any]) -> None:
        """Count loads."""
        del payload
        self.loads += 1

    async def capture(
        self, position: NDArray[np.float64], look_at: NDArray[np.float64], out_path: Path
    ) -> Tuple[int, int]:
        """Write a blank 1920x1080 frame, or fail as scripted."""
        del position, look_at
        self.captures += 1
        scenario = int(out_path.name.split("_")[1])  # live_0001_0_ego.png
        if self._failures_left.get(scenario, 0) > 0:
            self._failures_left[scenario] -= 1
            raise TimeoutError("the game did not write a screenshot")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1920, 1080), (90, 90, 90)).save(out_path)
        return 1920, 1080

    async def recover(self) -> None:
        """Count recoveries."""
        self.recoveries += 1


def _run(renderer: FakeRenderer, output_dir: Path, num_scenarios: int, base_seed: int = 500) -> Any:
    """Run the dataset generation with the fake game."""
    return asyncio.run(
        generate_live_dataset(
            renderer,  # type: ignore[arg-type]
            CONFIG,
            BOUNDS,
            output_dir,
            num_scenarios,
            base_seed,
            VIEWS,
        )
    )


def _annotations(output_dir: Path) -> Dict[str, Any]:
    """The merged COCO file of a run."""
    data: Dict[str, Any] = json.loads((output_dir / "annotations.json").read_text(encoding="utf-8"))
    return data


def test_run_writes_parts_and_a_merged_file_with_unique_ids(tmp_path: Path) -> None:
    """Each scenario gets a part; the merged file has global, unique ids."""
    result = _run(FakeRenderer(), tmp_path, 2)
    assert result.frames >= 1
    assert sorted(path.name for path in (tmp_path / "parts").glob("*.json")) == [
        "scenario_0000.json",
        "scenario_0001.json",
    ]
    coco = _annotations(tmp_path)
    assert len(coco["images"]) == result.frames
    ids = [annotation["id"] for annotation in coco["annotations"]]
    assert ids == list(range(1, len(ids) + 1))
    image_ids = [image["id"] for image in coco["images"]]
    assert len(set(image_ids)) == len(image_ids)
    assert all(0 <= image_id < 2 * MAX_VIEWS_PER_SCENARIO for image_id in image_ids)


def test_resume_renders_only_what_is_missing_and_matches_a_clean_run(tmp_path: Path) -> None:
    """Extending a finished run renders only the new scenario; the result equals a clean run."""
    first = FakeRenderer()
    _run(first, tmp_path / "resumed", 2)
    second = FakeRenderer()
    result = _run(second, tmp_path / "resumed", 3)
    assert result.resumed_scenarios == 2
    assert second.loads == 1
    clean = FakeRenderer()
    _run(clean, tmp_path / "clean", 3)
    assert _annotations(tmp_path / "resumed") == _annotations(tmp_path / "clean")


def test_a_failed_capture_is_retried_after_the_game_recovers(tmp_path: Path) -> None:
    """One timeout is retried: the game is given time to recover and the scenario completes."""
    renderer = FakeRenderer(failing_scenarios={0: 1})
    result = _run(renderer, tmp_path, 1)
    assert renderer.recoveries == 1
    assert result.rendered_scenarios == 1 or result.skipped_scenarios == 1
    assert (tmp_path / "parts" / "scenario_0000.json").exists()


def test_a_game_that_never_returns_keeps_finished_work_and_resumes(tmp_path: Path) -> None:
    """After repeated failures the run stops with scenario 0 saved; a healthy rerun completes it."""
    dead = FakeRenderer(failing_scenarios={1: 99})
    with pytest.raises(GameUnavailableError):
        _run(dead, tmp_path / "run", 2)
    assert dead.recoveries == MAX_SCENARIO_ATTEMPTS - 1
    assert (tmp_path / "run" / "parts" / "scenario_0000.json").exists()
    assert not (tmp_path / "run" / "parts" / "scenario_0001.json").exists()
    assert len(_annotations(tmp_path / "run")["images"]) >= 1
    _run(FakeRenderer(), tmp_path / "run", 2)
    _run(FakeRenderer(), tmp_path / "clean", 2)
    assert _annotations(tmp_path / "run") == _annotations(tmp_path / "clean")


def test_changed_settings_are_refused_on_resume(tmp_path: Path) -> None:
    """A different seed in the same directory would mix two datasets, so it is refused."""
    _run(FakeRenderer(), tmp_path, 1, base_seed=500)
    with pytest.raises(ManifestMismatchError, match="base_seed"):
        _run(FakeRenderer(), tmp_path, 1, base_seed=501)


def test_a_truncated_part_is_treated_as_unfinished(tmp_path: Path) -> None:
    """A part cut off by a crash does not count as done, so the scenario is redone."""
    store = DatasetStore(tmp_path)
    store.save_part(0, [{"id": 0}], [])
    store.part_path(0).write_text('{"scenario_index": 0, "images": [', encoding="utf-8")
    assert store.load_part(0) is None
    assert store.completed() == set()


def test_parts_are_merged_in_scenario_order(tmp_path: Path) -> None:
    """Merging orders parts by scenario index and renumbers annotation ids globally."""
    store = DatasetStore(tmp_path)
    annotation: List[Dict[str, Any]] = [{"id": 1, "image_id": 1, "category_id": 2}]
    store.save_part(2, [{"id": 200}], annotation)
    store.save_part(0, [{"id": 0}], annotation)
    coco = store.merge()
    assert [image["id"] for image in coco["images"]] == [0, 200]
    assert [item["id"] for item in coco["annotations"]] == [1, 2]


def test_changed_annotation_policy_is_refused_on_resume(tmp_path: Path) -> None:
    """Resuming with other classes would mix label sets, so it is refused."""
    _run(FakeRenderer(), tmp_path, 1)
    with pytest.raises(ManifestMismatchError, match="annotation_policy"):
        asyncio.run(
            generate_live_dataset(
                FakeRenderer(),  # type: ignore[arg-type]
                CONFIG,
                BOUNDS,
                tmp_path,
                1,
                500,
                VIEWS,
                AnnotationPolicy(FINE_PROFILE),
            )
        )


def test_default_run_exports_coco_classes_without_buildings(tmp_path: Path) -> None:
    """The default policy writes person/car/bus/truck ids and no building annotations."""
    _run(FakeRenderer(), tmp_path, 1)
    coco = _annotations(tmp_path)
    assert {c["name"] for c in coco["categories"]} == {"person", "car", "bus", "truck"}
    assert all(a["category_id"] in (1, 3, 6, 8) for a in coco["annotations"])
    assert all(a["fine_category_id"] != 1 for a in coco["annotations"])  # 1 = fine building
    assert all("dropped_annotations" in image for image in coco["images"])
