"""How well does a detector see CARLA's vehicles? The agent drives on ground truth; the detector only watches.

    .venv-train\Scripts\python.exe -m carla_loop.run_detection_check --weights runs/carla_weights/v7p25_s0.pt \
        --seeds 0 1 2 --out results/carla/detection_v7p25_s0.json

For every true vehicle within 50 m that is visible to the front camera (depth-checked), reports whether
a detected vehicle box overlaps it at IoU 0.5 and whether its class is right, by kind and distance.
"""

import argparse
import json
from pathlib import Path

from carla_loop.harness import Episode, connect, run_episode
from carla_loop.perception import CameraRig


def main() -> None:
    """Run the episodes with the detector watching, print the recall table, save the counts."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--max-seconds", type=float, default=60.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    client = connect()
    rig = CameraRig(args.weights, record_gt=True)
    for seed in args.seeds:
        run_episode(client, Episode(seed=seed, max_seconds=args.max_seconds), rig=rig)
        print(f"seed {seed}: {rig.score.frames} frames scored so far", flush=True)
    report = rig.report()
    print(f"{'kind|distance':22s}{'true':>7s}{'found':>8s}{'recall':>8s}   called as (of the found)")
    for key in sorted(report["gt"]):
        total, found = report["gt"][key], report["found"].get(key, 0)
        called = report["called"].get(key, {})
        shown = ", ".join(f"{n} {100 * c / max(found, 1):.0f}%" for n, c in sorted(called.items(), key=lambda i: -i[1]))
        print(f"{key:22s}{total:7d}{found:8d}{100 * found / total:7.0f}%   {shown}")
    print("(unmatched boxes are mostly static parked cars, which are map props with no ground truth)")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"weights": str(args.weights), **report}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
