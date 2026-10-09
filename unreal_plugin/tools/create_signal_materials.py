"""Create project-owned copies of the City Sample signal-face materials, one per lit state.

Run once in a headless editor session (the game/editor must not be running):

    UnrealEditor-Cmd.exe <project>.uproject -d3d11 -nosplash -unattended -nullrhi
        -ExecutePythonScript=<this file>

The signal poles (``SM_StreetLamp_A_StopLight_*``) use three emissive materials: the vehicle
heads (``M_Prop_Emissive_Traffic_StopLight``, slot ``Prop_Emissive_StopLight``) and the pedestrian
heads (``..._Walk_FrontSide`` on slot ``Prop_Emissive_Walk_01``, ``..._Walk_RightSide`` on slots
``Prop_Emissive_Walk_02`` and ``_03``). Their instances choose the shown state through the
``MassTraffic Controlled`` static switch, a Mass-AI packed parameter this project never sets, so
every head renders red and a pedestrian head shows its hand (measured: ``MassTraffic PackedParam1``
has no effect on a rendered frame).

Each original is DUPLICATED into ``/Game/VantageCV/Signals`` and the copy is changed: the switch is
turned off, which makes the ``Crosswalk Control`` scalar pick the state (measured by sweeping it
from 0 to 1 in the live game, docs/experiments/31_*.md): below 0.5 the vehicle head lights red and
a pedestrian head shows the walking figure; at 0.5 the vehicle head lights yellow; above 0.5 it
lights green and a pedestrian head shows the hand. The originals are never opened for writing: an
earlier attempt that flipped the switch on the shared Epic instance broke other content
(docs/known_gaps/resolved/37_*.md). Copies that already exist are rebuilt, they are this
project's own.
"""

import unreal  # type: ignore[import-not-found]  # pylint: disable=import-error

SOURCE = "/Game/Prop/Kit_StreetLamp_A/Material/"
TARGET = "/Game/VantageCV/Signals/"
VEHICLE = "M_Prop_Emissive_Traffic_StopLight"
FRONT = "M_Prop_Emissive_Traffic_Walk_FrontSide"
RIGHT = "M_Prop_Emissive_Traffic_Walk_RightSide"
STATES = {  # name: (original, Crosswalk Control)
    "MI_Signal_Red": (VEHICLE, 0.0),
    "MI_Signal_Yellow": (VEHICLE, 0.5),
    "MI_Signal_Green": (VEHICLE, 1.0),
    "MI_Ped_Front_Walk": (FRONT, 0.0),
    "MI_Ped_Front_Stop": (FRONT, 1.0),
    "MI_Ped_Right_Walk": (RIGHT, 0.0),
    "MI_Ped_Right_Stop": (RIGHT, 1.0),
}
LOG_PATH = r"F:/vscode/VantageCV-V2/unreal_plugin/tools/create_signal_materials.log"
OUT = open(LOG_PATH, "w", encoding="utf-8")  # pylint: disable=consider-using-with


def say(*parts):
    """Write one line to the log file next to this script."""
    OUT.write(" ".join(str(part) for part in parts) + chr(10))
    OUT.flush()


def make(name, source_name, control):
    """(Re)build one project-owned copy that shows the state selected by ``control``."""
    destination = TARGET + name
    if unreal.EditorAssetLibrary.does_asset_exist(destination):
        unreal.EditorAssetLibrary.delete_asset(destination)
    copy = unreal.EditorAssetLibrary.duplicate_asset(SOURCE + source_name, destination)
    library = unreal.MaterialEditingLibrary
    library.set_material_instance_static_switch_parameter_value(
        copy, "MassTraffic Controlled", False
    )
    library.set_material_instance_scalar_parameter_value(copy, "Crosswalk Control", control)
    library.update_material_instance(copy)
    unreal.EditorAssetLibrary.save_loaded_asset(copy)
    say("CREATED", name, "from", source_name, "Crosswalk Control", control)


def main():
    """Build every state copy, then quit the editor."""
    for name, (source_name, control) in STATES.items():
        make(name, source_name, control)
    say("DONE")
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


main()
