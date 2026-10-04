"""Render the same scenes under several environment settings and score each against BDD100K.

Needs the running UE5 game (``bin/launch_ue5.ps1``). For each candidate (a set of
``EnvironmentConfig`` overrides on the v7 night preset, or with ``--base day`` on the clear
summer day) it renders the same ego views of the same scenarios, then prints the image
statistics of ``src/evaluation/image_stats.py`` next to the BDD100K reference, so the settings are
chosen by measurement, not by eye.

    PYTHONPATH=. python bin/calibrate_night.py --candidates candidates.json --out cal_out
    PYTHONPATH=. python bin/calibrate_night.py --base day --candidates roads.json --out cal_out

``candidates.json`` maps a name to the overrides, for example
``{"sun0.05": {"sun_intensity_lux": 0.05}, "warm": {"color_gain": [1.0, 0.98, 0.95]}}``.
"""

import argparse
import asyncio
import dataclasses
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from PIL import Image

from src.evaluation.image_stats import BDD_ROOT, bdd_names, image_stats
from src.orchestration.camera_sampling import sample_ego_pose
from src.orchestration.dataset_generator import generate_scenario
from src.orchestration.live_render import LiveRenderer
from src.orchestration.scenario_serializer import serialize_scenario
from src.procedural.environment import (
    NIGHT_ENVIRONMENT_V7,
    Season,
    TimeOfDay,
    Weather,
    scenario_environment,
)
from src.ue5.backend import UE5Backend
from src.utils.config_loader import load_scenario_config

BOUNDS = (-150.0, -150.0, 150.0, 150.0)
CONFIG = Path("configs/scenario_templates/urban_dense_v7.yaml")
REFERENCE_SAMPLE = 120


def _tuples(overrides: Dict[str, Any]) -> Dict[str, Any]:
    """JSON lists back to the tuples ``EnvironmentConfig`` expects."""
    return {k: tuple(v) if isinstance(v, list) else v for k, v in overrides.items()}


async def _run(args: argparse.Namespace) -> None:  # pylint: disable=too-many-locals
    candidates: Dict[str, Dict[str, Any]] = json.loads(args.candidates.read_text(encoding="utf-8"))
    config = load_scenario_config(CONFIG)
    day = args.base == "day"
    base_environment = (
        scenario_environment(Season.SUMMER, TimeOfDay.DAY, Weather.CLEAR, None, "v7")
        if day
        else NIGHT_ENVIRONMENT_V7
    )
    scenarios = []
    for seed in range(args.seed, args.seed + args.scenarios):
        scenario = generate_scenario(
            seed,
            config,
            BOUNDS,
            f"cal_{seed}",
            time_of_day=TimeOfDay.DAY if day else TimeOfDay.NIGHT,
        )
        pose = sample_ego_pose(
            scenario, np.random.Generator(np.random.PCG64([seed, 0x51C3])), BOUNDS, "v7"
        )
        if pose is not None:
            scenarios.append((scenario, pose))
    reference = [
        image_stats(Image.open(BDD_ROOT / f"images/100k/val/{name}.jpg"))
        for name in bdd_names("daytime" if day else "night", "clear")[:REFERENCE_SAMPLE]
    ]
    print(f"BDD100K {'day' if day else 'night'} (clear):", _summary(reference))
    async with UE5Backend(args.ue5_uri, timeout_seconds=300.0) as backend:
        renderer = LiveRenderer(backend)
        for name, overrides in candidates.items():
            environment = dataclasses.replace(base_environment, **_tuples(overrides))
            rows: List[Dict[str, float]] = []
            for scenario, pose in scenarios:
                await renderer.load(serialize_scenario(scenario, environment))
                path = args.out / name / f"{scenario.scenario_id}.png"
                await renderer.capture(pose.position, pose.look_at, path)
                rows.append(image_stats(Image.open(path)))
            print(f"{name}:", _summary(rows), flush=True)


def _summary(rows: List[Dict[str, float]]) -> str:
    keys = (
        "luma_top",
        "luma_mid",
        "luma_bot",
        "top_blue_over_red",
        "saturation_lit",
        "laplacian_var",
        "mirror_corr",
    )
    return "  ".join(f"{k}={np.mean([row[k] for row in rows]):.2f}" for k in keys)


def main() -> None:
    """Parse arguments and run."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base", choices=["night", "day"], default="night")
    parser.add_argument("--seed", type=int, default=40000)
    parser.add_argument("--scenarios", type=int, default=5)
    parser.add_argument("--ue5-uri", default="ws://localhost:8765")
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
