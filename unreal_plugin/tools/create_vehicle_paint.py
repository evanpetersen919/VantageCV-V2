"""Create project-owned car-paint material instances that take a runtime colour.

Run once in a headless editor session (the game/editor must not be running):

    UnrealEditor.exe <project>.uproject -d3d11 -nosplash -unattended -nullrhi
        -ExecutePythonScript=<this file>

City Sample's car paint (``M_Veh_CarPaint``) picks a colour from a gradient
texture using a per-instance random value when its ``Paint Variation`` static
switch is on, which every ordinary car's paint instance has. That random value
is always 0 for individually spawned actors, so every car renders the same
cream white and the ``BaseColor`` parameter is ignored (the taxi, whose switch
is off, does use ``BaseColor``). A static switch is baked per material
instance, so a runtime override cannot flip it (the same limit as the window
and pedestrian switches). This duplicates each recolourable model's
``veh_carPaint`` instance into ``/Game/VantageCV/VehiclePaint/<model folder>``
with ``Paint Variation`` off; the scenario payload swaps it in and sets
``BaseColor``. Nothing shared is edited.

``MODEL_FOLDERS`` must match ``RECOLORABLE_MODELS`` in
``src/procedural/vehicle_colors.py``.
"""

import unreal  # type: ignore[import-not-found]  # pylint: disable=import-error

OUTPUT_FOLDER = "/Game/VantageCV/VehiclePaint"
PAINT_SLOT = "veh_carPaint"
SWITCH_OFF = "Paint Variation"
MODEL_FOLDERS = (
    "vehCar_vehicle02",
    "vehCar_vehicle03",
    "vehCar_vehicle05",
    "vehCar_vehicle06",
    "vehCar_vehicle07",
    "vehVan_vehicle01",
    "vehTruck_vehicle04",
)


def main() -> None:
    """Duplicate each model's paint instance with the switch off, then quit."""
    library = unreal.MaterialEditingLibrary
    assets = unreal.EditorAssetLibrary
    if assets.does_directory_exist(OUTPUT_FOLDER):
        assets.delete_directory(OUTPUT_FOLDER)
    assets.make_directory(OUTPUT_FOLDER)
    created = 0
    for folder in MODEL_FOLDERS:
        path = f"/Game/Vehicle/{folder}/Mesh/SM_Frame_{folder}"
        mesh = unreal.load_object(None, f"{path}.SM_Frame_{folder}")
        source = None
        for slot in mesh.get_editor_property("static_materials"):
            if str(slot.get_editor_property("material_slot_name")) == PAINT_SLOT:
                source = slot.get_editor_property("material_interface")
        if source is None:
            print("NO_PAINT_SLOT", folder)
            continue
        instance = assets.duplicate_asset(source.get_path_name().split(".")[0], f"{OUTPUT_FOLDER}/{folder}")
        library.set_material_instance_static_switch_parameter_value(instance, SWITCH_OFF, False)
        library.update_material_instance(instance)
        assets.save_loaded_asset(instance)
        created += 1
    print("VEHICLE_PAINT_DONE", created)
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


main()
