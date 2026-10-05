"""Draw the results figures used in ``README.md`` and ``EXPERIMENT_LOG.md`` from the result files.

    PYTHONPATH=. python bin/plot_results.py --out docs/images

Each figure is a dark rounded card (transparent outside the card, so it sits cleanly on a light
or a dark page) with a title, a one-line takeaway, a hero number and thin marks on a recessive
grid. Series colours are the dark categorical slots 1 to 3 (blue, orange, aqua), validated
against the card surface. Points are the mean over three seeds, with the sample standard
deviation as the error bar.
"""

# pylint: disable=too-many-locals,too-many-statements,too-many-arguments,line-too-long

import argparse
import math
import textwrap
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import matplotlib
from matplotlib import font_manager
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Rectangle

from src.evaluation.run_stats import arm_runs, mean_sd, metric

SURFACE = "#1a1a19"
INK = "#ffffff"
INK_2 = "#c3c2b7"
MUTED = "#898781"
GRID = "#2c2c2a"
BASELINE = "#383835"
PILL = "#262625"
BLUE, ORANGE, AQUA = "#3987e5", "#d95926", "#199e70"
EXCLUDE: Tuple[str, ...] = ()
RESULTS = Path("results")
DPI = 200
FONTS = Path("C:/Windows/Fonts")


def _use_fonts() -> None:
    """Segoe UI (the demo video's face) when it is installed, the matplotlib default otherwise."""
    found = False
    for name in ("segoeui.ttf", "segoeuib.ttf"):
        if (FONTS / name).exists():
            font_manager.fontManager.addfont(str(FONTS / name))
            found = True
    if found:
        matplotlib.rcParams["font.family"] = "Segoe UI"


def _ap(arm: str, key: str = "ap") -> Tuple[float, float, int]:
    runs = arm_runs(RESULTS, arm, "bdd100k", EXCLUDE)
    mean, spread = mean_sd([metric(run, key) for run in runs])
    return mean, spread, len(runs)


def _card(
    title: str,
    takeaway: str,
    hero: str,
    hero_caption: str,
    note: str,
    size: Tuple[float, float] = (8.2, 4.9),
    box: Tuple[float, float, float, float] = (0.105, 0.235, 0.845, 0.415),
) -> Tuple[Figure, Axes]:
    """A dark rounded card with a title, takeaway, hero number, footnote and one set of axes."""
    _use_fonts()
    fig = Figure(figsize=size, dpi=DPI)
    FigureCanvasAgg(fig)
    fig.patch.set_alpha(0.0)
    fig.add_artist(
        FancyBboxPatch(
            (0.004, 0.006),
            0.992,
            0.988,
            boxstyle="round,pad=0,rounding_size=0.028",
            mutation_aspect=size[0] / size[1],
            transform=fig.transFigure,
            facecolor=SURFACE,
            edgecolor=(1, 1, 1, 0.10),
            linewidth=1.2,
            zorder=-10,
        )
    )
    fig.text(0.05, 0.925, title, color=INK, fontsize=17, fontweight="bold", va="top")
    fig.text(0.05, 0.855, takeaway, color=INK_2, fontsize=10.5, va="top")
    if hero:
        fig.text(0.95, 0.925, hero, color=INK, fontsize=30, fontweight="bold", va="top", ha="right")
        fig.text(0.95, 0.835, hero_caption, color=MUTED, fontsize=9.5, va="top", ha="right")
    fig.text(
        0.05,
        0.04,
        textwrap.fill(note, width=130),
        color=MUTED,
        fontsize=8.2,
        va="bottom",
        linespacing=1.4,
    )
    axis = fig.add_axes(box)
    _style(axis)
    return fig, axis


def _style(axis: Axes) -> None:
    """Transparent axes with a baseline, a recessive horizontal grid and muted tick labels."""
    axis.set_facecolor("none")
    for side in ("top", "right", "left"):
        axis.spines[side].set_visible(False)
    axis.spines["bottom"].set_color(BASELINE)
    axis.tick_params(colors=MUTED, labelsize=9.5, length=0, pad=8)
    axis.grid(axis="y", color=GRID, linewidth=0.9)
    axis.set_axisbelow(True)


def _legend(
    fig: Figure, entries: Sequence[Tuple[str, str]], x: float = 0.05, y: float = 0.775
) -> None:
    """A swatch-and-label row under the takeaway (label text stays in ink, not the series colour)."""
    renderer = fig.canvas.get_renderer()  # type: ignore[attr-defined]
    for label, colour in entries:
        fig.add_artist(
            Line2D(
                [x + 0.006],
                [y],
                marker="o",
                markersize=7,
                color=colour,
                linestyle="none",
                transform=fig.transFigure,
            )
        )
        text = fig.text(x + 0.018, y, label, color=INK_2, fontsize=9.8, va="center")
        width = text.get_window_extent(renderer).width / (fig.get_figwidth() * fig.dpi)
        x += 0.018 + width + 0.035


def _rounded_bar(
    axis: Axes,
    left: float,
    bottom: float,
    width: float,
    height: float,
    colour: str,
    end: str,
    radius_px: float = 8.0,
) -> None:
    """A bar with a rounded data-end and a square baseline end (``end`` is "top" or "left")."""
    to_px = axis.transData.transform
    px_per_x = abs(to_px((1.0, 0.0))[0] - to_px((0.0, 0.0))[0])
    px_per_y = abs(to_px((0.0, 1.0))[1] - to_px((0.0, 0.0))[1])
    radius_x, radius_y = radius_px / px_per_x, radius_px / px_per_y
    if end == "top":
        patch = FancyBboxPatch(
            (left, bottom - 2 * radius_y),
            width,
            height + 2 * radius_y,
            boxstyle=f"round,pad=0,rounding_size={radius_x}",
            mutation_aspect=radius_y / radius_x,
            facecolor=colour,
            edgecolor="none",
        )
        clip = Rectangle((left, bottom), width, height + 1.0, transform=axis.transData)
    else:
        patch = FancyBboxPatch(
            (left, bottom),
            width + 2 * radius_x,
            height,
            boxstyle=f"round,pad=0,rounding_size={radius_x}",
            mutation_aspect=radius_y / radius_x,
            facecolor=colour,
            edgecolor="none",
        )
        clip = Rectangle((left - 1.0, bottom), width + 1.0, height, transform=axis.transData)
    axis.add_patch(patch)
    patch.set_clip_path(clip)


def _pill(axis: Axes, text: str, xy: Tuple[float, float], ha: str = "left") -> None:
    """A small dark label with a hairline border, for a value called out on the chart."""
    axis.annotate(
        text,
        xy,
        color=INK,
        fontsize=10.5,
        fontweight="bold",
        va="center",
        ha=ha,
        bbox={"boxstyle": "round,pad=0.38", "fc": PILL, "ec": BASELINE, "lw": 1.0},
    )


def _save(fig: Figure, out: Path, name: str) -> None:
    fig.savefig(out / name, transparent=True)


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
    gain_at_460 = _ap(first[0][0])[0] - _ap(real[0][0])[0]
    fig, axis = _card(
        "Synthetic data helps most when real data is scarce",
        "BDD100K validation AP, mean of 3 seeds, with synthetic images added to real ones",
        f"+{gain_at_460:.1f} AP",
        "with 460 real images",
        "All points use AdamW (chosen automatically for small runs, fixed for larger ones). 3 seeds each; bars are the standard deviation.",
    )
    _legend(
        fig,
        [("real images only", BLUE), ("+ 1,838 synthetic", ORANGE), ("+ 3,691 synthetic", AQUA)],
    )
    axis.set_ylim(15.0, 34.5)
    real_by_size = {size: _ap(arm)[0] for arm, size in real}
    gain_xs = [n for _, n in first]
    axis.fill_between(  # the gain: what the synthetic images add at each real-data size
        gain_xs,
        [real_by_size[x] for x in gain_xs],
        [_ap(arm)[0] for arm, _ in first],
        color=ORANGE,
        alpha=0.13,
        linewidth=0,
    )
    for arms, colour in ((real, BLUE), (first, ORANGE), (second, AQUA)):
        xs = [n for _, n in arms]
        stats = [_ap(arm) for arm, _ in arms]
        ys = [s[0] for s in stats]
        axis.vlines(
            xs,
            [y - s[1] for y, s in zip(ys, stats)],
            [y + s[1] for y, s in zip(ys, stats)],
            color=colour,
            linewidth=1.4,
            alpha=0.8,
        )
        axis.plot(
            xs, ys, color=colour, linewidth=1.8, solid_capstyle="round", solid_joinstyle="round"
        )
        axis.plot(
            xs,
            ys,
            "o",
            markersize=8,
            markerfacecolor=colour,
            markeredgecolor=SURFACE,
            markeredgewidth=2,
        )
    for (real_arm, size), (mixed_arm, _) in zip(real, first):
        low_ap, high_ap = _ap(real_arm)[0], _ap(mixed_arm)[0]
        axis.vlines(size * 1.045, low_ap, high_ap, color=MUTED, linewidth=1.1)
        _pill(axis, f"+{high_ap - low_ap:.1f}", (size * 1.075, low_ap - 1.35))
    axis.set_xscale("log")
    axis.set_xticks([460, 919, 1838, 3676])
    axis.set_xticklabels(["460", "919", "1,838", "3,676"])
    axis.minorticks_off()
    axis.set_xlim(390, 5200)
    axis.set_yticks([18, 22, 26, 30, 34])
    axis.spines["bottom"].set_position(("data", 15.0))
    axis.set_xlabel("real BDD100K training images", color=MUTED, fontsize=9.8, labelpad=8)
    _save(fig, out, "results_benefit_vs_real_data.png")


def figure_control(out: Path) -> None:
    """At 1,838 real images: what synthetic images add, and what real images add."""
    arms: List[Tuple[str, str]] = [
        ("hpc_adamw_real400", "1,838 real\n(step-matched)"),
        ("hpc_adamw_mixed", "+ 1,838\nsynthetic"),
        ("hpc_adamw_mixedbig", "+ 3,691\nsynthetic"),
        ("hpc_adamw_real3676", "3,676 real"),
    ]
    stats = [_ap(arm) for arm, _ in arms]
    synthetic_gain = stats[1][0] - stats[0][0]
    real_gain = stats[3][0] - stats[0][0]
    fig, axis = _card(
        "Real images add more than synthetic ones",
        f"1,838 synthetic images add about {synthetic_gain:.0f} AP; 1,838 more real images add about {real_gain:.0f}",
        f"+{synthetic_gain:.1f} AP",
        "from 1,838 synthetic images",
        "Blue: real images only. Orange: real + synthetic. Same optimizer (AdamW) and recipe, 3 seeds, BDD100K validation AP.",
    )
    _legend(fig, [("real images only", BLUE), ("real + synthetic", ORANGE)])
    axis.set_ylim(20, 35)
    axis.set_xlim(-0.6, 3.6)
    width = 0.2
    for index, ((_, label), (mean, spread, _)) in enumerate(zip(arms, stats)):
        colour = ORANGE if index in (1, 2) else BLUE
        _rounded_bar(axis, index - width / 2, 20.0, width, mean - 20.0, colour, "top")
        axis.vlines(index, mean - spread, mean + spread, color=INK_2, linewidth=1.2)
        axis.text(
            index, mean + 0.9, f"{mean:.1f}", color=INK, fontsize=12, fontweight="bold", ha="center"
        )
    axis.set_xticks(range(4))
    axis.set_xticklabels([label for _, label in arms], color=INK_2)
    axis.set_yticks([20, 25, 30, 35])
    _save(fig, out, "results_control_at_1838_real.png")


def figure_gap(out: Path) -> None:
    """Where the remaining gap to equal-count real data is, per class."""
    classes: Sequence[str] = ("truck", "bus", "car", "person")
    gaps: Dict[str, float] = {}
    for name in classes:
        mixed = [
            metric(r, f"class:{name}") for r in arm_runs(RESULTS, "hpc_adamw_mixedbig", "bdd100k")
        ]
        real = [
            metric(r, f"class:{name}") for r in arm_runs(RESULTS, "hpc_adamw_real3676", "bdd100k")
        ]
        gaps[name] = mean_sd(mixed)[0] - mean_sd(real)[0]
    worst = min(gaps.values())
    fig, axis = _card(
        "The gap to real data is largest for trucks and buses",
        "AP difference per class: 1,838 real + 3,691 synthetic images, minus 3,676 real images",
        f"{worst:.1f} AP",
        "truck, the widest gap",
        "Difference of 3-seed means on BDD100K validation; seed sd is 0.1 to 0.5 AP overall, larger for bus and truck.",
        size=(8.2, 4.5),
        box=(0.05, 0.24, 0.78, 0.50),
    )
    axis.grid(axis="y", visible=False)
    axis.grid(axis="x", color=GRID, linewidth=0.9)
    axis.set_ylim(len(classes) - 0.4, -0.6)
    axis.set_xlim(worst - 1.0, 0)
    for index, name in enumerate(classes):
        value = gaps[name]
        _rounded_bar(axis, value, index - 0.14, -value, 0.28, BLUE, "left")
        axis.text(
            value - 0.12,
            index,
            f"{value:.1f}",
            color=INK,
            fontsize=11.5,
            fontweight="bold",
            va="center",
            ha="right",
        )
    axis.spines["bottom"].set_visible(False)
    axis.axvline(0, color=BASELINE, linewidth=1.2)
    axis.set_yticks([])
    axis.set_xticks([-3, -2, -1, 0])
    for index, name in enumerate(classes):
        axis.text(0.12, index, name, color=INK_2, fontsize=11.5, va="center", ha="left")
    axis.set_xlabel("AP difference", color=MUTED, fontsize=9.8, labelpad=8)
    _save(fig, out, "results_gap_by_class.png")


# instances of each class in the 510-image supplements (counted from their label files), by arm
SUPPLY_COUNTS = {
    "hpc_poor25": {"person": 547, "truck": 226, "bus": 89},
    "hpc_rand25": {"person": 1256, "truck": 1120, "bus": 69},
    "hpc_rich25": {"person": 2052, "truck": 1800, "bus": 245},
}


def figure_supply(out: Path) -> None:
    """Class AP against the instances of that class in a 510-image supplement (25% real).

    Person AP follows the number of persons; truck and bus AP do not follow their counts. The three
    panels share one vertical span so the slopes can be compared."""
    classes = [("person", "persons", BLUE), ("truck", "trucks", ORANGE), ("bus", "buses", AQUA)]
    span = 4.0
    fig, first = _card(
        "Persons in the data move person AP; trucks and buses don't",
        "BDD100K AP per class, mean of 3 seeds, for three 510-image synthetic supplements",
        "",
        "",
        "25% real BDD100K + 510 synthetic images chosen for few, random or many persons, trucks and buses. "
        "AdamW, 3 seeds; bars are the standard deviation. Every panel spans the same 4 AP.",
        box=(0.075, 0.29, 0.235, 0.39),
    )
    for index, (name, plural, colour) in enumerate(classes):
        axis = first if index == 0 else fig.add_axes((0.075 + index * 0.305, 0.29, 0.235, 0.39))
        if index:
            _style(axis)
        points = sorted(
            (
                counts[name],
                *mean_sd(
                    [metric(r, f"class:{name}") for r in arm_runs(RESULTS, arm, "bdd100k", EXCLUDE)]
                ),
            )
            for arm, counts in SUPPLY_COUNTS.items()
        )
        xs = [count for count, _, _ in points]
        ys = [mean for _, mean, _ in points]
        centre = (min(ys) + max(ys)) / 2.0
        axis.set_ylim(centre - span / 2.0, centre + span / 2.0)
        axis.vlines(
            xs,
            [m - sd for _, m, sd in points],
            [m + sd for _, m, sd in points],
            color=colour,
            linewidth=1.4,
            alpha=0.85,
        )
        axis.plot(
            xs, ys, color=colour, linewidth=1.8, solid_capstyle="round", solid_joinstyle="round"
        )
        axis.plot(
            xs,
            ys,
            "o",
            markersize=9,
            markerfacecolor=colour,
            markeredgecolor=SURFACE,
            markeredgewidth=2,
        )
        for x, (_, mean, _) in zip(xs, points):
            axis.text(
                x,
                mean + 0.34,
                f"{mean:.1f}",
                color=INK,
                fontsize=11.5,
                fontweight="bold",
                ha="center",
                va="bottom",
                bbox={"boxstyle": "round,pad=0.12", "fc": SURFACE, "ec": "none"},
                zorder=5,
            )
        axis.set_xscale("log")
        axis.set_xticks([])
        axis.minorticks_off()
        low_x, high_x = min(xs) / 1.6, max(xs) * 1.6
        axis.set_xlim(low_x, high_x)
        axis.set_yticks([])
        row, previous = 0, None
        for x in xs:
            fraction = math.log(x / low_x) / math.log(high_x / low_x)
            row = 1 - row if previous is not None and fraction - previous < 0.2 else 0
            axis.text(
                x,
                -0.07 - 0.09 * row,
                f"{x:,}",
                color=INK_2,
                fontsize=9.5,
                ha="center",
                va="top",
                transform=axis.get_xaxis_transform(),
            )
            previous = fraction
        axis.set_xlabel(f"{plural} in the supplement", color=MUTED, fontsize=9.3, labelpad=40)
        fig.add_artist(
            Line2D(
                [0.075 + index * 0.305 + 0.006],
                [0.745],
                marker="o",
                markersize=7,
                color=colour,
                linestyle="none",
                transform=fig.transFigure,
            )
        )
        verdict = "rises with the count" if name == "person" else "no clear trend"
        fig.text(
            0.075 + index * 0.305 + 0.02,
            0.745,
            f"{name}: {verdict}",
            color=INK,
            fontsize=11,
            fontweight="bold",
            va="center",
        )
        axis.grid(axis="y", visible=False)
    _save(fig, out, "results_class_supply.png")


def main() -> None:
    """Draw all four figures into ``--out``."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--out", type=Path, default=Path("docs/images"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    figure_benefit(args.out)
    figure_control(args.out)
    figure_gap(args.out)
    figure_supply(args.out)
    print("wrote", sorted(p.name for p in args.out.glob("results_*.png")))


if __name__ == "__main__":
    main()
