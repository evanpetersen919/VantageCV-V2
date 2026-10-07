"""Read ``results/carla/driving.json`` and print what the logged reading rule needs.

    .venv-train\Scripts\python.exe -m carla_loop.compare --results results/carla/driving.json
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


def routes_with_collision(rows: List[Dict[str, Any]], arm: str) -> int:
    """Number of routes on which ``arm`` had at least one collision."""
    return sum(1 for r in rows if r["arm"] == arm and r["collisions"])


def main() -> None:
    """Per-arm summary, collisions by what they hit, and the paired per-route table."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--results", type=Path, default=Path("results/carla/driving.json"))
    args = parser.parse_args()
    data = json.loads(args.results.read_text(encoding="utf-8"))
    rows: List[Dict[str, Any]] = data["episodes"]
    arms = list(data["summary"])
    for arm, summary in data["summary"].items():
        hits = Counter(
            "vehicle" if c["with"].startswith("vehicle.") else c["with"]
            for r in rows
            if r["arm"] == arm
            for c in r["collisions"]
        )
        print(arm, summary)
        print(f"   collisions by what they hit: {dict(hits)}; routes with a collision: {routes_with_collision(rows, arm)}")
    by_seed: Dict[int, Dict[str, Dict[str, Any]]] = {}
    for row in rows:
        by_seed.setdefault(row["seed"], {})[row["arm"]] = row
    print("\nseed | collisions " + " / ".join(arms) + " | outcome | hard brakes")
    for seed in sorted(by_seed):
        row = by_seed[seed]
        print(
            f"{seed:3d} | {'/'.join(str(len(row[a]['collisions'])) for a in arms)} | "
            f"{'/'.join(row[a]['outcome'][:4] for a in arms)} | "
            f"{'/'.join(str(row[a]['hard_brake_events']) for a in arms)}"
        )


if __name__ == "__main__":
    main()
