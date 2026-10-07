"""Closed-loop comparison: the same routes driven with ground truth and with each detector as the agent's eyes.

    .venv-train\Scripts\python.exe -m carla_loop.run_driving --seeds 0-19 \
        --arm real25r_s0=runs/carla_weights/real25r_s0.pt --arm v7p25_s0=runs/carla_weights/v7p25_s0.pt \
        --out results/carla/driving.json

Every seed is driven by all arms before the next seed starts, so a stopped run still holds paired
results. Finished (arm, seed) pairs in ``--out`` are skipped, so the command can be repeated to resume.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from carla_loop.harness import Episode, connect, restart_server, run_episode, summarise
from carla_loop.perception import CameraRig


def parse_seeds(text: str) -> List[int]:
    """'0-19' or '3' or '0,2,5' as a list of seeds."""
    seeds: List[int] = []
    for part in text.split(","):
        low, _, high = part.partition("-")
        seeds += list(range(int(low), int(high) + 1)) if high else [int(low)]
    return seeds


def main() -> None:
    """Drive every (seed, arm), saving after each episode."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--seeds", default="0-19")
    parser.add_argument("--arm", action="append", default=[], help="NAME=weights.pt (ground truth is always run)")
    parser.add_argument("--max-seconds", type=float, default=150.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    arms: Dict[str, Any] = {"gt": None}
    for item in args.arm:
        name, _, path = item.partition("=")
        arms[name] = CameraRig(Path(path))
    rows: List[Dict[str, Any]] = []
    if args.out.exists():
        rows = json.loads(args.out.read_text(encoding="utf-8"))["episodes"]
    done: set[Tuple[str, int]] = {(r["arm"], r["seed"]) for r in rows}

    client = connect()
    for seed in parse_seeds(args.seeds):
        for name, rig in arms.items():
            if (name, seed) in done:
                continue
            episode = Episode(seed=seed, max_seconds=args.max_seconds)
            row = None
            for attempt in range(3):  # a hung server is restarted and the episode repeated
                try:
                    row = run_episode(client, episode, rig.vision, rig) if rig else run_episode(client, episode)
                    break
                except RuntimeError as error:
                    print(f"seed {seed} {name}: {str(error)[:80]} (attempt {attempt + 1}); restarting CARLA", flush=True)
                    restart_server()
                    client = connect()
            if row is None:
                raise SystemExit(f"seed {seed} {name} failed three times")
            rows.append({"arm": name, **row})
            print(
                f"seed {seed:2d} {name:12s} {row['outcome']:8s} completion {row['route_completion']:.2f} "
                f"{row['distance_m']:6.0f} m  collisions {len(row['collisions'])}  lane {row['lane_invasions']}",
                flush=True,
            )
            by_arm = {a: [r for r in rows if r["arm"] == a] for a in arms}
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(
                json.dumps(
                    {"summary": {a: summarise(v) for a, v in by_arm.items() if v}, "episodes": rows}, indent=1
                ),
                encoding="utf-8",
            )
    for name in arms:
        mine = [r for r in rows if r["arm"] == name]
        if mine:
            print(name, summarise(mine))


if __name__ == "__main__":
    main()
