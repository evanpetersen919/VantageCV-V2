"""Run the ground-truth baseline: the agent sees every vehicle exactly (the perception ceiling).

    .venv-train\Scripts\python.exe -m carla_loop.run_baseline --seeds 0 1 2 --out results/carla/baseline_gt.json

Needs the CARLA server running (``F:\\CARLA_0.9.16\\CarlaUE4.exe``).
"""

import argparse
import json
from pathlib import Path

from carla_loop.harness import Episode, connect, run_episode, summarise


def main() -> None:
    """Run one episode per seed, print each and the summary, and save them."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--town", default="Town10HD_Opt")
    parser.add_argument("--traffic", type=int, default=40)
    parser.add_argument("--max-seconds", type=float, default=180.0)
    parser.add_argument("--out", type=Path, default=Path("results/carla/baseline_gt.json"))
    args = parser.parse_args()

    client = connect()
    rows = []
    for seed in args.seeds:
        episode = Episode(
            seed=seed, town=args.town, traffic=args.traffic, max_seconds=args.max_seconds
        )
        row = run_episode(client, episode)
        rows.append(row)
        print(
            f"seed {seed}: {row['outcome']}, completion {row['route_completion']}, "
            f"{row['seconds']} s, {row['distance_m']} m, "
            f"{len(row['collisions'])} collision(s), {row['lane_invasions']} lane invasion(s)",
            flush=True,
        )
    summary = summarise(rows)
    print(summary)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"summary": summary, "episodes": rows}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
