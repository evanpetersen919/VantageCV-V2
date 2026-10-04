"""Read-only: for each bus/truck model, list what differs between its numbered material
instances (``MI_<model>_0`` ... ``_22``): parent material and every parameter an instance
overrides (scalar, vector, texture). Tells whether the unused instances are real livery
variants (different graphic textures) or only paint/wear states.

Run in a headless editor session (the game/editor must not be running):

    UnrealEditor.exe <project>.uproject -d3d11 -nosplash -unattended -nullrhi
        -ExecutePythonScript=<this file>

Writes the report to ``VANTAGECV_INSTANCE_REPORT`` (default
``C:/Temp/vehicle_instances.txt``); makes no change to any asset.
"""

import os

import unreal  # type: ignore[import-not-found]  # pylint: disable=import-error

MODELS = ("vehBus_vehicle10", "vehTruck_vehicle04", "vehTruck_vehicle08", "vehTruck_vehicle11")
REPORT = os.environ.get("VANTAGECV_INSTANCE_REPORT", "C:/Temp/vehicle_instances.txt")


def _params(instance: "unreal.MaterialInstanceConstant") -> str:
    """One line per overridden parameter of ``instance``."""
    lines = []
    for kind in ("scalar", "vector", "texture"):
        for entry in instance.get_editor_property(f"{kind}_parameter_values"):
            name = str(entry.get_editor_property("parameter_info").get_editor_property("name"))
            value = entry.get_editor_property("parameter_value")
            lines.append(f"    {kind}: {name} = {value}")
    return "\n".join(lines) if lines else "    (no overrides)"


def main() -> None:
    """Write the report, then quit the editor."""
    out = []
    for model in MODELS:
        out.append(f"== {model}")
        for index in range(0, 40):
            path = f"/Game/Vehicle/{model}/Material/MI/MI_{model}_{index}"
            if not unreal.EditorAssetLibrary.does_asset_exist(path):
                continue
            asset = unreal.EditorAssetLibrary.load_asset(path)
            parent = asset.get_editor_property("parent")
            out.append(f"  MI_{model}_{index}  parent={parent.get_name() if parent else None}")
            out.append(_params(asset))
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as handle:
        handle.write("\n".join(out))
    unreal.SystemLibrary.quit_editor()


main()
