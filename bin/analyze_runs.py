"""Summarize repeated runs and compare arms (mean, spread, Welch t-test).

    PYTHONPATH=. python bin/analyze_runs.py --arms hpc_real_only hpc_mixed
    PYTHONPATH=. python bin/analyze_runs.py --baseline hpc_real3676 --arms hpc_mixed

Each arm is the result-file prefix before ``_s<seed>_<benchmark>.json``. With ``--baseline`` every
other arm is also compared with it. Values are AP points (0-100).
"""

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.evaluation.portable import CLASS_NAMES
from src.evaluation.run_stats import arm_runs, mean_sd, metric, welch

BENCHMARKS = ("bdd100k", "cityscapes", "bdd100k_scene")
NIGHT = "timeofday=night"


def _rows(runs: List[Dict[str, Any]], benchmark: str) -> Dict[str, List[float]]:
    """The tracked numbers of every run: overall AP, each class, BDD100K night, and (for the scene
    benchmark) AP, truck and bus AP in each scene."""
    rows: Dict[str, List[float]] = {
        "AP": [metric(r) for r in runs],
        "AP50": [metric(r, "ap50") for r in runs],
    }
    for name in CLASS_NAMES.values():
        rows[name] = [metric(r, f"class:{name}") for r in runs]
    if benchmark == "bdd100k":
        rows["night AP"] = [metric(r, "ap", NIGHT) for r in runs]
    if benchmark == "bdd100k_scene":
        for scene in sorted(c for c in runs[0]["by_condition"] if c.startswith("scene=")):
            label = scene.split("=", 1)[1]
            rows[f"AP {label}"] = [metric(r, "ap", scene) for r in runs]
            for name in ("truck", "bus"):
                rows[f"{name} {label}"] = [metric(r, f"class:{name}", scene) for r in runs]
    return rows


def main() -> None:
    """Print one table per benchmark; exit quietly if an arm has no runs yet."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--results", type=Path, default=Path("results"))
    parser.add_argument("--arms", nargs="+", required=True)
    parser.add_argument("--baseline", default=None, help="arm every other arm is compared with")
    parser.add_argument(
        "--exclude", nargs="*", default=[], help="run names to leave out, e.g. hpc_adamw_mixed_s1"
    )
    args = parser.parse_args()

    arms = ([args.baseline] if args.baseline else []) + [a for a in args.arms if a != args.baseline]
    for benchmark in BENCHMARKS:
        runs = {arm: arm_runs(args.results, arm, benchmark, args.exclude) for arm in arms}
        print(f"\n=== {benchmark} ===")
        tables: Dict[str, Dict[str, List[float]]] = {}
        for arm, arm_results in runs.items():
            if not arm_results:
                print(f"{arm}: no runs yet")
                continue
            tables[arm] = _rows(arm_results, benchmark)
            summary = "  ".join(
                f"{key} {mean_sd(vals)[0]:.2f}+-{mean_sd(vals)[1]:.2f}"
                for key, vals in tables[arm].items()
            )
            print(f"{arm} (n={len(arm_results)}): {summary}")
        base: Optional[str] = args.baseline if args.baseline in tables else None
        for arm, table in tables.items():
            if base is None or arm == base:
                continue
            print(f"\n{arm} minus {base}:")
            for key, vals in table.items():
                diff, p_value = welch(tables[base][key], vals)
                print(f"  {key:22s} {diff:+.2f}  (p = {p_value:.3f})")


if __name__ == "__main__":
    main()
