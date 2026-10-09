"""Bake Microsoft Rocketbox avatars into static posed meshes and import them into the Unreal
project.

    python bin/bake_rocketbox.py bake      # Blender: every adult avatar, several poses each
    python bin/bake_rocketbox.py import    # Unreal: into /Game/VantageCV/Pedestrians/Rocketbox

``bake`` runs Blender (``scripts/rocketbox_bake_poses.py``) for every adult avatar and writes the
measured extents of every mesh to ``configs/rocketbox_catalog.json``. ``import`` runs Unreal's
ImportAssets commandlet so each mesh, with its material and textures, lands in
``/Game/VantageCV/Pedestrians/Rocketbox/<avatar>/`` of this project (never in an Epic-owned
folder). Rocketbox is MIT-licensed (Microsoft, 2020).
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from src.ue5.import_assets import import_group, report_import, run_import

CATALOG = Path("configs/rocketbox_catalog.json")
UE_DESTINATION = "/Game/VantageCV/Pedestrians/Rocketbox"
EXCLUDED_PREFIXES = ("Female_Party", "Male_Party")


def avatar_names(root: Path) -> List[str]:
    """The adult avatars, everyday clothing only (the party avatars are left out)."""
    adults = root / "Assets" / "Avatars" / "Adults"
    return sorted(
        path.name
        for path in adults.iterdir()
        if path.is_dir() and not path.name.startswith(EXCLUDED_PREFIXES)
    )


def bake(root: Path, out: Path) -> None:
    """Run Blender once per avatar, then merge the per-avatar pose files into the catalog."""
    blender = shutil.which("blender")
    if blender is None:
        sys.exit("blender is not on PATH (scoop install blender)")
    names = avatar_names(root)
    for name in names:
        result = subprocess.run(
            [
                blender,
                "-b",
                "-P",
                "scripts/rocketbox_bake_poses.py",
                "--",
                str(root),
                name,
                str(out),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if f"baked {name}" not in result.stdout:
            sys.exit(f"baking {name} failed:\n{result.stdout[-1500:]}\n{result.stderr[-500:]}")
        print(f"baked {name}")
    avatars: List[Dict[str, Any]] = []
    for name in names:
        avatars.append(json.loads((out / name / "poses.json").read_text(encoding="utf-8")))
    CATALOG.write_text(
        json.dumps({"source": "Microsoft Rocketbox (MIT)", "avatars": avatars}, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"{len(avatars)} avatars, {sum(len(a['poses']) for a in avatars)} meshes -> {CATALOG}")


def import_to_unreal(out: Path) -> None:
    """Import every baked mesh into the project with the ImportAssets commandlet."""
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    groups = []
    for avatar in catalog["avatars"]:
        name = avatar["avatar"]
        files = [
            (out / name / f"{name}_{pose['pose']}.fbx").resolve().as_posix()
            for pose in avatar["poses"]
        ]
        groups.append(import_group(name, files, f"{UE_DESTINATION}/{name}"))
    code, errors = run_import(groups, out / "import_settings.json")
    report_import(code, errors, sum(len(g["Filenames"]) for g in groups))


def main() -> None:
    """Parse arguments and run the chosen step."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("step", choices=["bake", "import"])
    parser.add_argument("--root", type=Path, default=Path("external_data/rocketbox"))
    parser.add_argument("--out", type=Path, default=Path("external_data/rocketbox_baked"))
    args = parser.parse_args()
    if args.step == "bake":
        bake(args.root, args.out)
    else:
        import_to_unreal(args.out)


if __name__ == "__main__":
    main()
