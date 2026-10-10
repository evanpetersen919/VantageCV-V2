"""Tests for the rider headroom decision rule (``bin/analyze_rider_headroom.py``)."""

import importlib.util
import json
from pathlib import Path
from typing import Dict

import pytest

SPEC = importlib.util.spec_from_file_location(
    "analyze_rider_headroom",
    Path(__file__).resolve().parents[2] / "bin" / "analyze_rider_headroom.py",
)
analyze = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analyze)  # type: ignore[union-attr]


def _write(  # pylint: disable=too-many-arguments
    root: Path, arm: str, seed: int, ap: float, car: float = 0.4, person: float = 0.3
) -> None:
    """One result file whose rider, bike and motor AP are all ``ap`` (a fraction)."""
    per_class = {
        "rider": ap,
        "bike": ap,
        "motor": ap,
        "car": car,
        "person": person,
        "bus": 0.3,
        "truck": 0.3,
    }
    path = root / f"hpc_rider_{arm}_s{seed}_bdd100k_riders.json"
    path.write_text(json.dumps({"overall": {"per_class_ap": per_class}}), encoding="utf-8")


def _arms(root: Path, values: Dict[str, float], seeds: Dict[str, Dict[int, float]] = None) -> None:
    for arm in analyze.ARMS:
        for seed in analyze.SEEDS:
            ap = (seeds or {}).get(arm, {}).get(seed, values[arm])
            _write(root, arm, seed, ap)


BASE = {"A": 0.07, "rare2": 0.10, "rare4": 0.14, "rand2": 0.08, "rand4": 0.08}


def test_headroom_when_the_gap_is_large_and_positive_in_every_seed(tmp_path: Path) -> None:
    """rare4 beats rand4 by 6 AP in every seed: the registered rule says headroom exists."""
    _arms(tmp_path, BASE)
    result = analyze.analyse(tmp_path)
    assert result["headroom_exists"] is True
    assert result["d_rare_mean"] == pytest.approx(6.0)
    assert all(value == pytest.approx(6.0) for value in result["d_rare_by_seed"])


def test_no_headroom_when_the_mean_gap_is_below_the_bar(tmp_path: Path) -> None:
    """A 0.5 AP gap is positive everywhere but under the 1.0 AP bar."""
    values = dict(BASE, rare4=0.085)
    _arms(tmp_path, values)
    result = analyze.analyse(tmp_path)
    assert result["headroom_exists"] is False
    assert result["d_rare_mean"] == pytest.approx(0.5)


def test_no_headroom_when_one_seed_is_not_positive(tmp_path: Path) -> None:
    """A large mean gap carried by two seeds is not enough: the sign rule needs all three."""
    _arms(tmp_path, BASE, seeds={"rare4": {0: 0.20, 1: 0.20, 2: 0.07}})
    result = analyze.analyse(tmp_path)
    assert result["d_rare_mean"] >= analyze.MIN_MEAN_AP
    assert result["rule"]["all_seeds_positive"] is False
    assert result["headroom_exists"] is False


def test_guards_and_reported_items(tmp_path: Path) -> None:
    """Guard classes are compared with arm A; the reported differences are per seed."""
    _arms(tmp_path, BASE)
    _write(tmp_path, "rare4", 0, 0.14, car=0.30)
    result = analyze.analyse(tmp_path)
    assert result["guard_difference_vs_A"]["rare4"]["car"] < 0.0
    assert result["guard_difference_vs_A"]["A"] == {"car": 0.0, "person": 0.0}
    assert len(result["reported"]["rand4_minus_A_by_seed"]) == 3
    assert "HEADROOM EXISTS" in analyze.render(result)[-1]
