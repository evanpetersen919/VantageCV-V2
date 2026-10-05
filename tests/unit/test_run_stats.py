"""Unit tests for the repeated-run summaries."""

import json
import math
from pathlib import Path

from src.evaluation.run_stats import arm_runs, mean_sd, metric, welch


def _result(ap: float, car: float, night: float) -> dict:  # type: ignore[type-arg]
    block = {"overall": {"ap": ap, "ap50": ap * 2}, "per_class_ap": {"car": car}}
    return {
        "overall": block,
        "by_condition": {"timeofday=night": {**block, "overall": {"ap": night}}},
    }


def test_arm_runs_orders_by_seed_and_ignores_similarly_named_arms(tmp_path: Path) -> None:
    """``real`` must not pick up ``real_3676`` results; seeds come back in numeric order."""
    for name, ap in (("real_s10", 0.3), ("real_s2", 0.2), ("real_3676_s0", 0.9)):
        (tmp_path / f"{name}_bdd100k.json").write_text(json.dumps(_result(ap, 0.5, 0.1)))
    runs = arm_runs(tmp_path, "real", "bdd100k")
    assert [round(metric(run), 1) for run in runs] == [20.0, 30.0]


def test_metric_reads_overall_class_and_condition_in_ap_points() -> None:
    """Values are scaled to 0-100; a class and a condition are addressable."""
    run = _result(0.28, 0.43, 0.25)
    assert math.isclose(metric(run), 28.0) and math.isclose(metric(run, "class:car"), 43.0)
    assert math.isclose(metric(run, "ap", "timeofday=night"), 25.0)


def test_welch_reports_difference_and_needs_two_runs_for_a_p_value() -> None:
    """Clear separation gives a small p; a single run gives NaN rather than a made-up value."""
    diff, p_value = welch([1.0, 1.1, 0.9], [2.0, 2.1, 1.9])
    assert math.isclose(diff, 1.0) and p_value < 0.01
    assert math.isnan(welch([1.0], [2.0, 2.1])[1])
    assert mean_sd([2.0]) == (2.0, 0.0)


def test_arm_runs_can_exclude_a_named_run(tmp_path: Path) -> None:
    """An invalid run is left out when named, and only that one."""
    for seed, ap in ((0, 0.3), (1, 0.1), (2, 0.31)):
        (tmp_path / f"arm_s{seed}_bdd100k.json").write_text(json.dumps(_result(ap, 0.5, 0.1)))
    runs = arm_runs(tmp_path, "arm", "bdd100k", exclude=["arm_s1"])
    assert [round(metric(run)) for run in runs] == [30, 31]


def test_scene_results_are_a_separate_benchmark(tmp_path: Path) -> None:
    """``..._bdd100k_scene.json`` files are found as the ``bdd100k_scene`` benchmark only."""
    for name in ("arm_s0_bdd100k.json", "arm_s0_bdd100k_scene.json", "arm_s1_bdd100k_scene.json"):
        (tmp_path / name).write_text(json.dumps({"overall": {"ap": 0.5}}), encoding="utf-8")
    assert len(arm_runs(tmp_path, "arm", "bdd100k")) == 1
    assert len(arm_runs(tmp_path, "arm", "bdd100k_scene")) == 2
