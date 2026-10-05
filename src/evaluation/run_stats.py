"""Summaries and significance tests over repeated runs (same recipe, different seeds).

Result files are named ``<arm>_s<seed>_<benchmark>.json`` (for example
``hpc_real_only_s0_bdd100k.json``; ``..._bdd100k_scene.json`` is the same benchmark scored with the
scene attribute added). Runs of one arm differ only by seed, so their mean and spread show what a
single run can and cannot tell; two arms are compared with Welch's t-test, which does not assume
equal spread.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import stats

_NAME = re.compile(
    r"^(?P<arm>.+)_s(?P<seed>\d+)_(?P<benchmark>bdd100k_scene|bdd100k|cityscapes)\.json$"
)


def arm_runs(
    results_dir: Path, arm: str, benchmark: str, exclude: Sequence[str] = ()
) -> List[Dict[str, Any]]:
    """Every seed's result for ``arm`` on ``benchmark``, ordered by seed.

    ``exclude`` lists run names (for example ``hpc_adamw_mixed_s1``) to leave out, for a run known
    to be invalid; the caller should say so wherever the numbers are reported.
    """
    found: List[Tuple[int, Dict[str, Any]]] = []
    for path in results_dir.glob(f"{arm}_s*_{benchmark}.json"):
        match = _NAME.match(path.name)
        if match and match["arm"] == arm and f"{arm}_s{match['seed']}" not in exclude:
            found.append((int(match["seed"]), json.loads(path.read_text(encoding="utf-8"))))
    return [data for _, data in sorted(found, key=lambda item: item[0])]


def metric(run: Dict[str, Any], key: str = "ap", condition: Optional[str] = None) -> float:
    """Overall ``key`` (``ap``, ``ap50``...) of a run, or of one of its conditions, in AP points
    (0-100). ``key`` may also be ``class:<name>`` for a class's AP."""
    block = run["overall"] if condition is None else run["by_condition"][condition]
    if key.startswith("class:"):
        return 100.0 * float(block["per_class_ap"][key[6:]])
    source = block["overall"] if "overall" in block else block
    return 100.0 * float(source[key])


def mean_sd(values: Sequence[float]) -> Tuple[float, float]:
    """Mean and sample standard deviation (0 for a single value)."""
    array = np.asarray(values, dtype=float)
    return float(array.mean()), float(array.std(ddof=1)) if len(array) > 1 else 0.0


def welch(first: Sequence[float], second: Sequence[float]) -> Tuple[float, float]:
    """Difference of means (second minus first) and Welch's two-sided p-value.

    The p-value is NaN when either group has fewer than two runs.
    """
    difference = float(np.mean(second) - np.mean(first))
    if len(first) < 2 or len(second) < 2:
        return difference, float("nan")
    return difference, float(stats.ttest_ind(second, first, equal_var=False).pvalue)
