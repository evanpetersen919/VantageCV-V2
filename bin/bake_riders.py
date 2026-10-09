"""Bake Rocketbox riders and the bicycle into static meshes and import them into the Unreal project.

    python bin/bake_riders.py bake   --avatars Male_Adult_01 Female_Adult_01 --saddle 0.5757
    python bin/bake_riders.py import                     # Unreal (the game must be closed)

``bake`` runs ``scripts/rider_bake.py`` in Blender once per avatar: four right-crank angles
(0, 90, 180, 270 degrees) of the rider on the bicycle, plus the bicycle itself in two spoke
variants (a real 2 mm spoke and a 6 mm one). All meshes share one frame, so placing a rider
mesh and a bike mesh at the same transform puts the rider on the bike. The contact errors of
every pose are written beside the meshes (``rider_<avatar>.json``). ``import`` brings the
meshes into ``/Game/VantageCV/Riders/Spike`` of this project (never an Epic-owned folder).
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

from src.ue5.import_assets import import_group, report_import, run_import

UE_DESTINATION = "/Game/VantageCV/Riders/Spike"


def bake(root: Path, out: Path, avatars: List[str], saddle: float) -> None:
    """Run Blender once per avatar."""
    blender = shutil.which("blender")
    if blender is None:
        sys.exit("blender is not on PATH (scoop install blender)")
    for name in avatars:
        result = subprocess.run(
            [
                blender,
                "-b",
                "-P",
                "scripts/rider_bake.py",
                "--",
                str(root),
                name,
                str(out),
                "--saddle",
                str(saddle),
                "--bikes",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if f"RIDER_DONE {name}" not in result.stdout:
            sys.exit(f"baking {name} failed:\n{result.stdout[-1500:]}\n{result.stderr[-500:]}")
        report = json.loads((out / f"rider_{name}.json").read_text(encoding="utf-8"))
        worst = max(
            max(
                pose[k]
                for k in ("R_wrist_error", "L_wrist_error", "R_ankle_error", "L_ankle_error")
            )
            for pose in report["poses"].values()
        )
        print(
            f"baked {name}: {len(report['poses'])} poses, worst contact error {worst * 1000:.1f} mm"
        )


def import_to_unreal(out: Path) -> None:
    """Import every baked mesh with the ImportAssets commandlet."""
    files = sorted(path.resolve().as_posix() for path in out.glob("*.fbx"))
    code, errors = run_import(
        [import_group("spike", files, UE_DESTINATION)], out / "import_settings.json"
    )
    report_import(code, errors, len(files))


def main() -> None:
    """Parse arguments and run the chosen step."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("step", choices=["bake", "import"])
    parser.add_argument("--root", type=Path, default=Path("external_data/rocketbox"))
    parser.add_argument("--out", type=Path, default=Path("external_data/riders_baked"))
    parser.add_argument("--avatars", nargs="+", default=["Male_Adult_01"])
    parser.add_argument("--saddle", type=float, default=0.5757)
    args = parser.parse_args()
    if args.step == "bake":
        args.out.mkdir(parents=True, exist_ok=True)
        bake(args.root, args.out, args.avatars, args.saddle)
    else:
        import_to_unreal(args.out)


if __name__ == "__main__":
    main()
