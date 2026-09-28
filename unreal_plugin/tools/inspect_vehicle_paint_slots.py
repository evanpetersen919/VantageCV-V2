"""Read-only: list every material slot (and its static switch parameters) on the
vehicle models that currently have no project-owned paint copy, so a real fix can
target their actual slot/parameter names instead of assuming they match the
already-handled models' ``veh_carPaint`` / ``Paint Variation``.

Run once in a headless editor session (the game/editor must not be running):

    UnrealEditor.exe <project>.uproject -d3d11 -nosplash -unattended -nullrhi
        -ExecutePythonScript=<this file>

Makes no changes: no asset is created, duplicated or saved.
"""

import unreal  # type: ignore[import-not-found]  # pylint: disable=import-error

TARGET_FOLDERS = (
    "vehCar_vehicle12",
    "vehCar_vehicle13",
    "vehVan_vehicle09",
    "vehTruck_vehicle08",
    "vehTruck_vehicle11",
    "vehTruck_trailer01",
    "vehBus_vehicle10",
)


def main() -> None:
    """Print each target model's material slots, and each slot material's static
    switch parameter names, then quit."""
    library = unreal.MaterialEditingLibrary
    for folder in TARGET_FOLDERS:
        path = f"/Game/Vehicle/{folder}/Mesh/SM_Frame_{folder}"
        mesh = unreal.load_object(None, f"{path}.SM_Frame_{folder}")
        if mesh is None:
            print("NO_MESH", folder)
            continue
        for slot in mesh.get_editor_property("static_materials"):
            slot_name = str(slot.get_editor_property("material_slot_name"))
            material = slot.get_editor_property("material_interface")
            if material is None:
                print("SLOT", folder, slot_name, "NO_MATERIAL")
                continue
            switches = library.get_static_switch_parameter_names(material)
            scalars = library.get_scalar_parameter_names(material)
            print("SLOT", folder, slot_name, material.get_path_name())
            print("  switches:", [str(s) for s in switches])
            print("  scalars:", [str(s) for s in scalars])
    print("INSPECT_DONE")
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


main()
