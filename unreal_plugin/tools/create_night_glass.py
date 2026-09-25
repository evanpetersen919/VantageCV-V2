"""Create the project-owned lit-window glass materials used at night.

Run once in a headless editor session (the game/editor must not be running):

    UnrealEditor.exe <project>.uproject -d3d11 -nosplash -unattended -nullrhi
        -ExecutePythonScript=<this file>

City Sample's building glass (``M_Window``) already renders real
interior-mapped rooms and per-window lights, but that branch is behind the
``UseLightOverride`` static switch, which is off in every shipped kit glass
instance (and per-module room variety is behind ``UseInteriorOffset``). A static switch is baked per material instance, so a runtime
material override cannot flip it (the same limit as the pedestrian
``Animate`` switch). This duplicates each kit's ``M_Bldg_glass`` instance
into ``/Game/VantageCV/NightGlass/<Kit>_M_Bldg_glass`` with the switch on;
the scenario payload swaps them in for the wall meshes' ``Bldg_glass`` slot at
night. Nothing shared is edited.
"""

import unreal  # type: ignore[import-not-found]  # pylint: disable=import-error

OUTPUT_FOLDER = "/Game/VantageCV/NightGlass"
SOURCE_ROOT = "/Game/Building"
SOURCE_NAME = "M_Bldg_glass"
STALE_FOLDERS = tuple(f"/Game/VantageCV/NightGlass_V{n}" for n in (1, 2, 3)) + tuple(
    f"/Game/VantageCV/NightGlassTest_{name}"
    for name in ("V2", "V3", "R", "RA", "RB", "RC", "RD", "RE", "RF", "RG", "RH", "RI")
)
EMISSION_TINT = 3.0


def main() -> None:
    """Build the lit copies, remove earlier experiment folders, quit."""
    library = unreal.MaterialEditingLibrary
    assets = unreal.EditorAssetLibrary
    for stale in STALE_FOLDERS:
        if assets.does_directory_exist(stale):
            assets.delete_directory(stale)
    assets.make_directory(OUTPUT_FOLDER)
    created = 0
    for path in assets.list_assets(SOURCE_ROOT, recursive=True, include_folder=False):
        package = path.split(".")[0]
        if package.split("/")[-1] != SOURCE_NAME:
            continue
        kit = package.split("/")[-3]
        destination = f"{OUTPUT_FOLDER}/{kit}_{SOURCE_NAME}"
        if assets.does_asset_exist(destination):
            assets.delete_asset(destination)
        instance = assets.duplicate_asset(package, destination)
        for switch in ("UseLightOverride", "UseInteriorOffset"):
            library.set_material_instance_static_switch_parameter_value(instance, switch, True)
        library.set_material_instance_vector_parameter_value(
            instance, "Tint", unreal.LinearColor(EMISSION_TINT, EMISSION_TINT, EMISSION_TINT, 1.0)
        )
        library.update_material_instance(instance)
        assets.save_loaded_asset(instance)
        created += 1
    print("NIGHT_GLASS_DONE", created)
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


main()
