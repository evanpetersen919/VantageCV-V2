"""Create the project-owned lit-window glass materials used at night.

Run once in a headless editor session (the game/editor must not be running):

    UnrealEditor.exe <project>.uproject -d3d11 -nosplash -unattended -nullrhi
        -ExecutePythonScript=<this file>

City Sample's building glass (``M_Window``) already renders real
interior-mapped rooms and per-window lights, but that branch is behind the
``UseLightOverride`` static switch, which is off in every shipped kit glass
instance. A static switch is baked per material instance, so a runtime
material override cannot flip it (the same limit as the pedestrian
``Animate`` switch). Turning on ``ManualRoom``/``UseManualID`` makes the
material show the single room named by its ``CubeMap`` / ``InteriorColor`` /
``InteriorDepth`` texture parameters (measured live: ``ManualRoomID`` does not
choose a room). So this duplicates each kit's ``M_Bldg_glass`` instance once
per room into ``/Game/VantageCV/NightGlass/<room>/<Kit>_M_Bldg_glass``, each
copy pointing at that room's textures; the scenario payload picks one copy per
wall module. Nothing shared is edited.

``ROOMS`` must match ``ROOM_KEYS`` in ``src/procedural/building_lights.py``.
"""

import unreal  # type: ignore[import-not-found]  # pylint: disable=import-error

OUTPUT_FOLDER = "/Game/VantageCV/NightGlass"
SOURCE_ROOT = "/Game/Building"
SOURCE_NAME = "M_Bldg_glass"
ROOM_TEXTURES = "/Game/Building/Material/Window/Texture/RoomInteriors"
EMISSION_TINT = 1.5
LIGHT_SWITCHES = ("UseLightOverride", "ManualRoom", "UseManualID")
STALE_FOLDERS = tuple(f"/Game/VantageCV/NightGlass_V{n}" for n in (1, 2, 3)) + tuple(
    f"/Game/VantageCV/NightGlassTest_{name}" for name in ("MR1", "MR2")
)

# room key -> (cube texture, interior capture, interior depth). The 1x1x1 rooms
# that read as a room seen through an ordinary window; supermarkets are left out.
BLACK = ("black1x1x1_Capture", "black1x1x1_Depth")
ROOMS = {
    "bedroom_a": ("CaptureCube_Tex_Bedroom1x1x1a1", "bedroom1x1x1a_CaptureFG", "bedroom1x1x1a_DepthFG"),
    "bedroom_b": ("CaptureCube_Tex_Bedroom1x1x1b1", "bedroom1x1x1b_CaptureFG", "bedroom1x1x1b_DepthFG"),
    "bedroom_c": ("CaptureCube_Tex_Bedroom1x1x1c", "bedroom1x1x1c_CaptureFG", "bedroom1x1x1c_DepthFG"),
    "living_a": ("CaptureCube_Tex_LivingRoom1x1x1a", "livingRoom1x1x1a_CaptureFG", "livingRoom1x1x1a_DepthFG"),
    "living_b": ("CaptureCube_Tex_LivingRoom1x1x1b2", "livingRoom1x1x1b_CaptureFG", "livingRoom1x1x1b_DepthFG"),
    "office_b": ("CaptureCube_Tex_Office1x1x1b2", "office1x1x1b_CaptureFG", "office1x1x1b_DepthFG"),
    "office_c": ("CaptureCube_Tex_Office1x1x1c3", "office1x1x1c_CaptureFG", "office1x1x1c_DepthFG"),
    "office_d": ("CaptureCube_Tex_Office1x1x1d2", "office1x1x1d_CaptureFG", "office1x1x1d_DepthFG"),
    "office_e": ("CaptureCube_Tex_Office1x1x1e3", "office1x1x1e_CaptureFG", "office1x1x1e_DepthFG"),
    "restaurant_a": ("CaptureCube_Tex_Restaurant1x1x1a3", "restaurant1x1x1a_CaptureFG", "restaurant1x1x1a_DepthFG"),
    "restaurant_b": ("CaptureCube_Tex_Restaurant1x1x1b", "restaurant1x1x1b_CaptureFG", "restaurant1x1x1b_DepthFG"),
    "restaurant_c": ("CaptureCube_Tex_Restaurant1x1x1c", "restaurant1x1x1c_CaptureFG", "restaurant1x1x1c_DepthFG"),
    "lobby_a": ("CaptureCube_Tex_Lobby1x1x1a",) + BLACK,
    "lobby_b": ("CaptureCube_Tex_Lobby1x1x1b1",) + BLACK,
}


def _texture(folder: str, name: str):
    return unreal.load_asset(f"{ROOM_TEXTURES}/{folder}/{name}")


def main() -> None:
    """Build the lit copies (one per kit per room), clear old ones, quit."""
    library = unreal.MaterialEditingLibrary
    assets = unreal.EditorAssetLibrary
    for stale in STALE_FOLDERS + (OUTPUT_FOLDER,):
        if assets.does_directory_exist(stale):
            assets.delete_directory(stale)
    kits = []
    for path in assets.list_assets(SOURCE_ROOT, recursive=True, include_folder=False):
        package = path.split(".")[0]
        if package.split("/")[-1] == SOURCE_NAME:
            kits.append(package)
    created = 0
    for key, (cube, capture, depth) in ROOMS.items():
        textures = {
            "CubeMap": _texture("Cubes", cube),
            "InteriorColor": _texture("Interiors", capture),
            "InteriorDepth": _texture("Interiors", depth),
        }
        assets.make_directory(f"{OUTPUT_FOLDER}/{key}")
        for package in kits:
            kit = package.split("/")[-3]
            instance = assets.duplicate_asset(package, f"{OUTPUT_FOLDER}/{key}/{kit}_{SOURCE_NAME}")
            for switch in LIGHT_SWITCHES:
                library.set_material_instance_static_switch_parameter_value(instance, switch, True)
            library.set_material_instance_vector_parameter_value(
                instance, "Tint", unreal.LinearColor(EMISSION_TINT, EMISSION_TINT, EMISSION_TINT, 1.0)
            )
            for name, texture in textures.items():
                library.set_material_instance_texture_parameter_value(instance, name, texture)
            library.update_material_instance(instance)
            assets.save_loaded_asset(instance)
            created += 1
    print("NIGHT_GLASS_DONE", created)
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


main()
