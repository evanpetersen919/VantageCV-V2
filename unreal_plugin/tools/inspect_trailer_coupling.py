"""Read-only: how City Sample itself couples its trailer to the cab.

Lists every asset under the cab and trailer folders and any asset whose name mentions "Trailer"
elsewhere in the project, then prints, for each blueprint's default object and each data asset,
the properties whose names mention trailer, hitch, offset, socket, attach or constraint. Run in a
headless editor session (the game/editor must not be running):

    UnrealEditor.exe <project>.uproject -d3d11 -nosplash -unattended -nullrhi
        -ExecutePythonScript=<this file>

Writes the report to ``VANTAGECV_COUPLING_REPORT`` (default ``C:/Temp/trailer_coupling.txt``);
makes no change to any asset.
"""

import os

import unreal  # type: ignore[import-not-found]  # pylint: disable=import-error

REPORT = os.environ.get("VANTAGECV_COUPLING_REPORT", "C:/Temp/trailer_coupling.txt")
KEYS = ("trailer", "hitch", "offset", "socket", "attach", "constraint", "pivot", "kingpin")


def _props(obj: "unreal.Object") -> list:
    found = []
    for name in dir(obj):
        if name.startswith("_") or not any(k in name.lower() for k in KEYS):
            continue
        try:
            value = getattr(obj, name)
        except Exception:  # pylint: disable=broad-except
            continue
        if callable(value):
            continue
        found.append(f"      {name} = {str(value)[:200]}")
    return found


def main() -> None:
    """Write the report, then quit the editor."""
    out = []
    paths = []
    for folder in ("/Game/Vehicle/vehTruck_vehicle08", "/Game/Vehicle/vehTruck_trailer01"):
        paths += list(unreal.EditorAssetLibrary.list_assets(folder, recursive=True))
    for path in unreal.EditorAssetLibrary.list_assets("/Game", recursive=True):
        if "trailer" in path.lower() and path not in paths:
            paths.append(path)
    for path in sorted(set(paths)):
        asset = unreal.EditorAssetLibrary.load_asset(path)
        cls = asset.get_class().get_name() if asset else "?"
        if cls in ("StaticMesh", "SkeletalMesh", "Skeleton", "Texture2D", "MaterialInstanceConstant"):
            continue
        out.append(f"== {cls}: {path}")
        target = asset
        if cls == "Blueprint":
            try:
                target = unreal.get_default_object(asset.generated_class())
            except Exception as error:  # pylint: disable=broad-except
                out.append(f"      (no default object: {error})")
        out += _props(target)
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as handle:
        handle.write("\n".join(out))
    unreal.SystemLibrary.quit_editor()


main()
