"""Render a dataset of real UE5 frames with labels from the same camera.

Needs a running UE5 game with the plugin. Draws time of day and weather per
scenario from its seed, renders ego and overview views, and writes
``images/``, ``qa/`` (labels drawn on every image), ``annotations.json`` (COCO)
under ``--out``. A camera self-check (four known squares) runs first and aborts
the run if the render and the camera model disagree.

    PYTHONPATH=. python bin/generate_live_dataset.py --num-scenarios 3 --seed 100
"""

import argparse
import asyncio
from pathlib import Path
from typing import List, Optional

from src.export.annotation_policy import MIN_BOX_HEIGHT_PX, MIN_BOX_WIDTH_PX, AnnotationPolicy
from src.ground_truth.categories import BUS, PEDESTRIAN, PROFILES, SEDAN, SUV, TRUCK
from src.orchestration.dataset_store import ManifestMismatchError
from src.orchestration.live_dataset import DEFAULT_VIEWS, default_output_dir, generate_live_dataset
from src.orchestration.live_render import GameUnavailableError, LiveRenderer
from src.orchestration.profiles import (
    V6_CONFIG,
    V6_PARKING_LOT_FRACTION,
    V7_CONFIG,
    V7_PARKING_LOT_FRACTION,
    V7_VIEWS,
)
from src.ue5.backend import UE5Backend
from src.utils.config_loader import load_scenario_config

# --max-distance names -> the policy's category ids ("car" covers both sedan and SUV)
DISTANCE_CLASSES = {
    "person": (PEDESTRIAN,),
    "car": (SEDAN, SUV),
    "bus": (BUS,),
    "truck": (TRUCK,),
}


def _policy(args: argparse.Namespace) -> AnnotationPolicy:
    """The annotation policy, with any ``--max-distance CLASS=METRES`` overrides applied."""
    policy = AnnotationPolicy(PROFILES[args.classes], args.min_box_height, args.min_box_width)
    for item in args.max_distance:
        name, _, metres = item.partition("=")
        if name not in DISTANCE_CLASSES or not metres:
            raise SystemExit(
                f"error: --max-distance wants CLASS=METRES, CLASS in {sorted(DISTANCE_CLASSES)}"
            )
        for category in DISTANCE_CLASSES[name]:
            policy.max_distance_m[category] = float(metres)
    return policy


def _resolve_profile(args: argparse.Namespace) -> None:
    """Fill the flags left unset from the chosen ``--profile`` (v6 keeps the old defaults)."""
    v7 = args.profile == "v7"
    if args.config is None:
        args.config = V7_CONFIG if v7 else V6_CONFIG
    if args.views is None:
        args.views = list(V7_VIEWS if v7 else DEFAULT_VIEWS)
    if args.parking_lot_fraction is None:
        args.parking_lot_fraction = V7_PARKING_LOT_FRACTION if v7 else V6_PARKING_LOT_FRACTION


def _relaunch_command(args: argparse.Namespace) -> Optional[List[str]]:
    """The command that restarts the game after a crash, or None without ``--relaunch-game``."""
    if not args.relaunch_game:
        return None
    script = Path(__file__).resolve().parent / "launch_ue5.ps1"
    return ["powershell", "-NoProfile", "-File", str(script)]


async def _run(args: argparse.Namespace) -> None:
    """Build the renderer, run the dataset generation, print a summary."""
    output_dir = args.out or default_output_dir()
    async with UE5Backend(args.ue5_uri, timeout_seconds=300.0) as backend:
        result = await generate_live_dataset(
            LiveRenderer(backend, relaunch_command=_relaunch_command(args)),
            load_scenario_config(args.config).model_copy(
                update={"parking_lot_fraction": args.parking_lot_fraction}
            ),
            tuple(args.bounds),
            output_dir,
            args.num_scenarios,
            args.seed,
            tuple(args.views),
            _policy(args),
            args.profile,
            args.exact_labels,
            args.semantic_maps,
            args.lamp_bloom,
        )
    print(
        f"{result.frames} frames in {result.elapsed_seconds:.0f} s -> {output_dir} "
        f"(rendered {result.rendered_scenarios} scenarios, resumed {result.resumed_scenarios}, "
        f"rejected {result.skipped_scenarios}; calibration {result.calibration_error_px:.2f} px)"
    )


def main() -> None:
    """Parse arguments and run."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument(
        "--profile",
        choices=["v6", "v7"],
        default="v6",
        help="v6 is the generator as it was (jitter on, original fleet and views); v7 selects "
        "the realism fixes (fleet, views, lots, night, weather) unless the matching flag is given",
    )
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--bounds", type=float, nargs=4, default=[-150.0, -150.0, 150.0, 150.0])
    parser.add_argument("--num-scenarios", type=int, default=3)
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument(
        "--views", nargs="+", choices=["ego", "lot", "overview", "rider"], default=None
    )
    parser.add_argument(
        "--classes",
        choices=sorted(PROFILES),
        default="coco",
        help="output classes: coco (person/car/bus/truck, COCO ids, no buildings) or fine",
    )
    parser.add_argument(
        "--parking-lot-fraction",
        type=float,
        default=None,
        help="share of city blocks holding a surface lot (v6: 0.3, since the template default of "
        "0.1 left over half the scenarios without one; v7: 0.1)",
    )
    parser.add_argument(
        "--max-distance",
        nargs="+",
        default=[],
        metavar="CLASS=METRES",
        help="label objects of CLASS (person, car, bus, truck) out to this camera distance "
        "instead of the policy default; the manifest records the result",
    )
    parser.add_argument("--min-box-height", type=float, default=MIN_BOX_HEIGHT_PX)
    parser.add_argument("--min-box-width", type=float, default=MIN_BOX_WIDTH_PX)
    parser.add_argument(
        "--semantic-maps",
        action="store_true",
        help="also write a full-scene class map (Cityscapes label ids: road, sidewalk, building, "
        "pole, vegetation, sky, ...) and a depth map per frame, from what the game renders",
    )
    parser.add_argument(
        "--lamp-bloom",
        action="store_true",
        help="add the camera glare of visible vehicle lamps at night (needs --semantic-maps for "
        "depth); fitted to real night frames",
    )
    parser.add_argument(
        "--relaunch-game",
        action="store_true",
        help="if the game stops answering, start it again with bin/launch_ue5.ps1 and carry on",
    )
    parser.add_argument(
        "--exact-labels",
        action="store_true",
        help="take every vehicle and pedestrian box, visible fraction and mask from what the game "
        "renders (CaptureObjectMasks) instead of from proxy shapes; costs about 1.5 s a frame",
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--ue5-uri", default="ws://localhost:8765")
    try:
        args = parser.parse_args()
        _resolve_profile(args)
        if args.lamp_bloom and not args.semantic_maps:
            parser.error(
                "--lamp-bloom needs --semantic-maps (the depth map decides which lamps are visible)"
            )
        asyncio.run(_run(args))
    except (GameUnavailableError, ManifestMismatchError) as error:
        raise SystemExit(f"error: {error}") from error
    except OSError as error:
        raise SystemExit(
            f"error: cannot reach the game ({error}); start it and rerun the same command"
        ) from error


if __name__ == "__main__":
    main()
