"""Apply the pre-registered decision rule of the rider headroom check.

The rule is in ``docs/riders/headroom_check.md``. This reads
``results/hpc_rider_<arm>_s<seed>_bdd100k_riders.json`` for the five arms and three seeds and
reports:

- the primary outcome M: the mean AP@[.5:.95] of rider, bike and motor, per arm and seed;
- the decision quantity d_rare(s) = M(rare4, s) - M(rand4, s), and the rule: headroom exists only if
  the mean of d_rare is at least ``MIN_MEAN_AP`` AP and d_rare is positive for every seed;
- the reported-but-not-decisive items: M(rand4) - M(A), the doubled arms, per-class AP, and the
  guards (car and person AP of every arm against A).

Nothing here is tuned after seeing results: the threshold and the sign condition are the registered
ones.

    python bin/analyze_rider_headroom.py [--results DIR] [--out FILE]
"""

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List

ARMS = ("A", "rare2", "rare4", "rand2", "rand4")
SEEDS = (0, 1, 2)
PRIMARY_CLASSES = ("rider", "bike", "motor")
GUARD_CLASSES = ("car", "person")
MIN_MEAN_AP = (
    1.0  # registered: the mean of d_rare must be at least this many AP points (x100 scale)
)


def load_arm(results: Path, arm: str, seed: int) -> Dict[str, float]:
    """Per-class AP@[.5:.95] of one run, in AP points (0 to 100)."""
    path = results / f"hpc_rider_{arm}_s{seed}_bdd100k_riders.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {name: 100.0 * value for name, value in data["overall"]["per_class_ap"].items()}


def primary(per_class: Dict[str, float]) -> float:
    """M: the mean AP of rider, bike and motor."""
    return mean(per_class[name] for name in PRIMARY_CLASSES)


def analyse(results: Path) -> Dict[str, Any]:
    """The full analysis as a JSON-serialisable dictionary."""
    runs = {arm: {seed: load_arm(results, arm, seed) for seed in SEEDS} for arm in ARMS}
    m = {arm: [primary(runs[arm][seed]) for seed in SEEDS] for arm in ARMS}
    d_rare = [m["rare4"][i] - m["rand4"][i] for i in range(len(SEEDS))]
    headroom = mean(d_rare) >= MIN_MEAN_AP and all(value > 0 for value in d_rare)
    per_class = {
        arm: {name: mean(runs[arm][seed][name] for seed in SEEDS) for name in runs[arm][0]}
        for arm in ARMS
    }
    guards = {
        arm: {name: per_class[arm][name] - per_class["A"][name] for name in GUARD_CLASSES}
        for arm in ARMS
    }
    return {
        "seeds": list(SEEDS),
        "m_by_arm_and_seed": m,
        "m_mean_by_arm": {arm: mean(values) for arm, values in m.items()},
        "d_rare_by_seed": d_rare,
        "d_rare_mean": mean(d_rare),
        "rule": {"min_mean_ap": MIN_MEAN_AP, "all_seeds_positive": all(v > 0 for v in d_rare)},
        "headroom_exists": headroom,
        "reported": {
            "rand4_minus_A_by_seed": [m["rand4"][i] - m["A"][i] for i in range(len(SEEDS))],
            "rare2_minus_rand2_by_seed": [m["rare2"][i] - m["rand2"][i] for i in range(len(SEEDS))],
            "rand2_minus_A_by_seed": [m["rand2"][i] - m["A"][i] for i in range(len(SEEDS))],
        },
        "per_class_ap_mean": per_class,
        "guard_difference_vs_A": guards,
    }


def render(analysis: Dict[str, Any]) -> List[str]:
    """A short plain-text report."""
    lines = ["M = mean AP of rider, bike and motor (AP points), BDD100K val", ""]
    lines.append(f"{'arm':7s} " + " ".join(f"s{seed:<6d}" for seed in analysis["seeds"]) + "  mean")
    for arm, values in analysis["m_by_arm_and_seed"].items():
        cells = " ".join(f"{value:7.2f}" for value in values)
        lines.append(f"{arm:7s} {cells}  {mean(values):5.2f}")
    d = analysis["d_rare_by_seed"]
    lines += ["", "d_rare = M(rare4) - M(rand4): " + ", ".join(f"{v:+.2f}" for v in d)]
    lines.append(
        f"mean d_rare = {analysis['d_rare_mean']:+.2f} "
        f"(rule: >= {MIN_MEAN_AP} and positive in every seed)"
    )
    lines.append("HEADROOM EXISTS" if analysis["headroom_exists"] else "NO HEADROOM SHOWN")
    return lines


def main() -> None:
    """Run the analysis and write its JSON."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", type=Path, default=Path("results"))
    parser.add_argument("--out", type=Path, default=Path("results/rider_headroom_analysis.json"))
    args = parser.parse_args()
    analysis = analyse(args.results)
    args.out.write_text(json.dumps(analysis, indent=1), encoding="utf-8")
    print("\n".join(render(analysis)))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
