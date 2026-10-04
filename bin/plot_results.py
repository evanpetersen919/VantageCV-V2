"""Draw the results figures used in ``EXPERIMENT_LOG.md`` from the result files.

    PYTHONPATH=. python bin/plot_results.py --out docs/images

Points are the mean over seeds with the sample standard deviation as the error bar; an arm with
two usable seeds (the AdamW 1,838 real + 1,838 synthetic arm, one seed was invalid) is marked.
"""

import argparse
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from matplotlib.axes import Axes
from matplotlib.figure import Figure

from src.evaluation.run_stats import arm_runs, mean_sd, metric

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
EXCLUDE = ("hpc_adamw_mixed_s1",)
RESULTS = Path("results")


def _ap(arm: str, key: str = "ap") -> Tuple[float, float, int]:
    runs = arm_runs(RESULTS, arm, "bdd100k", EXCLUDE)
    mean, spread = mean_sd([metric(run, key) for run in runs])
    return mean, spread, len(runs)


def _style(axis: Axes) -> None:
    axis.set_facecolor(SURFACE)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axis.spines[side].set_color(INK_2)
    axis.tick_params(colors=INK_2, labelsize=10)
    axis.grid(axis="y", color=GRID, linewidth=0.8)
    axis.set_axisbelow(True)


def figure_benefit(out: Path) -> None:
    """BDD100K AP against the number of real images, with and without synthetic images."""
    real = [
        ("hpc_real25", 460),
        ("hpc_real50", 919),
        ("hpc_real_only", 1838),
        ("hpc_adamw_real3676", 3676),
    ]
    first = [("hpc_mixed25", 460), ("hpc_mixed50", 919), ("hpc_adamw_mixed", 1838)]
    second = [("hpc_adamw_mixed25big", 460), ("hpc_adamw_mixedbig", 1838)]
    fig = Figure(figsize=(8.2, 4.8), dpi=170, facecolor=SURFACE)
    axis = fig.add_subplot()
    _style(axis)
    for arms, color, marker, label in (
        (real, BLUE, "o", "real images only"),
        (first, ORANGE, "s", "real + 1,838 synthetic"),
        (second, AQUA, "^", "real + 3,691 synthetic"),
    ):
        xs = [n for _, n in arms]
        stats = [_ap(arm) for arm, _ in arms]
        axis.errorbar(
            xs,
            [s[0] for s in stats],
            yerr=[s[1] for s in stats],
            color=color,
            linewidth=2,
            marker=marker,
            markersize=8,
            markeredgecolor=SURFACE,
            markeredgewidth=2,
            capsize=3,
            label=label,
        )
    axis.legend(loc="upper left", frameon=False, fontsize=10.5, labelcolor=INK)
    axis.set_xscale("log")
    axis.set_xticks([460, 919, 1838, 3676])
    axis.set_xticklabels(["460", "919", "1,838", "3,676"])
    axis.minorticks_off()
    axis.set_xlim(380, 6200)
    axis.set_xlabel("real BDD100K training images", color=INK_2)
    axis.set_ylabel("BDD100K val AP (mean of 3 seeds, bar = sd)", color=INK_2)
    axis.set_title(
        "Synthetic images help most when real data is scarce", color=INK, loc="left", fontsize=13
    )
    fig.text(
        0.01,
        0.01,
        "All points use AdamW (chosen automatically for small runs, fixed for larger ones).\n"
        "The 1,838 real + 1,838 synthetic point has 2 seeds; the others have 3.",
        color=INK_2,
        fontsize=8.5,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(out / "results_benefit_vs_real_data.png", facecolor=SURFACE)


def figure_control(out: Path) -> None:
    """At 1,838 real images: what synthetic images add, and what real images add."""
    arms: List[Tuple[str, str]] = [
        ("hpc_adamw_real400", "1,838 real\n(step-matched)"),
        ("hpc_adamw_mixed", "+ 1,838 synthetic\n(2 seeds)"),
        ("hpc_adamw_mixedbig", "+ 3,691 synthetic"),
        ("hpc_adamw_real3676", "3,676 real"),
    ]
    stats = [_ap(arm) for arm, _ in arms]
    fig = Figure(figsize=(8.2, 4.6), dpi=170, facecolor=SURFACE)
    axis = fig.add_subplot()
    _style(axis)
    colors = [BLUE, ORANGE, ORANGE, BLUE]
    bars = axis.bar(
        range(4),
        [s[0] for s in stats],
        yerr=[s[1] for s in stats],
        color=colors,
        width=0.55,
        capsize=3,
        error_kw={"ecolor": INK_2, "linewidth": 1.2},
        edgecolor=SURFACE,
        linewidth=2,
    )
    for rect, (mean, _, _) in zip(bars, stats):
        axis.text(
            rect.get_x() + rect.get_width() / 2,
            20.4,
            f"{mean:.1f}",
            ha="center",
            color="white",
            fontsize=11,
            fontweight="bold",
        )
    axis.set_xticks(range(4))
    axis.set_xticklabels([label for _, label in arms], color=INK_2)
    axis.set_ylim(20, 34)
    axis.set_ylabel("BDD100K val AP (mean, bar = sd)", color=INK_2)
    axis.set_title(
        "Adding 1,838 images to 1,838 real: synthetic adds about 2 AP, real adds about 5",
        color=INK,
        loc="left",
        fontsize=13,
    )
    fig.text(
        0.01,
        0.01,
        "Blue: real images only. Orange: real + synthetic. Same optimizer (AdamW), "
        "same recipe, 3 seeds unless marked.",
        color=INK_2,
        fontsize=8.5,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(out / "results_control_at_1838_real.png", facecolor=SURFACE)


def figure_gap(out: Path) -> None:
    """Where the remaining gap to equal-count real data is, per class."""
    classes: Sequence[str] = ("truck", "bus", "car", "person")
    gaps: Dict[str, Tuple[float, float]] = {}
    for name in classes:
        mixed = [
            metric(r, f"class:{name}") for r in arm_runs(RESULTS, "hpc_adamw_mixedbig", "bdd100k")
        ]
        real = [
            metric(r, f"class:{name}") for r in arm_runs(RESULTS, "hpc_adamw_real3676", "bdd100k")
        ]
        gaps[name] = (mean_sd(mixed)[0] - mean_sd(real)[0], 0.0)
    fig = Figure(figsize=(8.2, 3.6), dpi=170, facecolor=SURFACE)
    axis = fig.add_subplot()
    _style(axis)
    axis.grid(axis="x", color=GRID, linewidth=0.8)
    axis.grid(axis="y", visible=False)
    values = [gaps[name][0] for name in classes]
    axis.barh(range(len(classes)), values, color=ORANGE, height=0.5, edgecolor=SURFACE, linewidth=2)
    for index, value in enumerate(values):
        axis.text(
            value - 0.1, index, f"{value:.1f}", ha="right", va="center", color=INK, fontsize=11
        )
    axis.set_yticks(range(len(classes)))
    axis.set_yticklabels(classes, color=INK_2, fontsize=11)
    axis.invert_yaxis()
    axis.set_xlim(min(values) - 0.8, 0)
    axis.set_xlabel(
        "AP difference: (1,838 real + 3,691 synthetic) minus 3,676 real, BDD100K", color=INK_2
    )
    axis.set_title(
        "The gap to real data is largest for trucks and buses", color=INK, loc="left", fontsize=13
    )
    fig.text(
        0.01,
        0.01,
        "Difference of 3-seed means; seed sd is 0.1 to 0.5 AP overall, larger for bus and truck.",
        color=INK_2,
        fontsize=8.5,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(out / "results_gap_by_class.png", facecolor=SURFACE)


def main() -> None:
    """Draw all three figures into ``--out``."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--out", type=Path, default=Path("docs/images"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    figure_benefit(args.out)
    figure_control(args.out)
    figure_gap(args.out)
    print("wrote", sorted(p.name for p in args.out.glob("results_*.png")))


if __name__ == "__main__":
    main()
