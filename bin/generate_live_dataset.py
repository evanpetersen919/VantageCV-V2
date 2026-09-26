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

from src.export.annotation_policy import MIN_BOX_HEIGHT_PX, MIN_BOX_WIDTH_PX, AnnotationPolicy
from src.ground_truth.categories import PROFILES
from src.orchestration.dataset_store import ManifestMismatchError
from src.orchestration.live_dataset import DEFAULT_VIEWS, default_output_dir, generate_live_dataset
from src.orchestration.live_render import GameUnavailableError, LiveRenderer
from src.ue5.backend import UE5Backend
from src.utils.config_loader import load_scenario_config


async def _run(args: argparse.Namespace) -> None:
    """Build the renderer, run the dataset generation, print a summary."""
    output_dir = args.out or default_output_dir()
    async with UE5Backend(args.ue5_uri, timeout_seconds=300.0) as backend:
        result = await generate_live_dataset(
            LiveRenderer(backend),
            load_scenario_config(args.config),
            tuple(args.bounds),
            output_dir,
            args.num_scenarios,
            args.seed,
            tuple(args.views),
            AnnotationPolicy(PROFILES[args.classes], args.min_box_height, args.min_box_width),
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
        "--config", type=Path, default=Path("configs/scenario_templates/urban_dense.yaml")
    )
    parser.add_argument("--bounds", type=float, nargs=4, default=[-150.0, -150.0, 150.0, 150.0])
    parser.add_argument("--num-scenarios", type=int, default=3)
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument("--views", nargs="+", choices=["ego", "overview"], default=DEFAULT_VIEWS)
    parser.add_argument(
        "--classes",
        choices=sorted(PROFILES),
        default="coco",
        help="output classes: coco (person/car/bus/truck, COCO ids, no buildings) or fine",
    )
    parser.add_argument("--min-box-height", type=float, default=MIN_BOX_HEIGHT_PX)
    parser.add_argument("--min-box-width", type=float, default=MIN_BOX_WIDTH_PX)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--ue5-uri", default="ws://localhost:8765")
    try:
        asyncio.run(_run(parser.parse_args()))
    except (GameUnavailableError, ManifestMismatchError) as error:
        raise SystemExit(f"error: {error}") from error
    except OSError as error:
        raise SystemExit(
            f"error: cannot reach the game ({error}); start it and rerun the same command"
        ) from error


if __name__ == "__main__":
    main()
