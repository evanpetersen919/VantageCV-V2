"""Create the project-owned road-paint materials: white (parking stripes, lane and stop lines) and yellow.

Run once in a headless editor session (the game/editor must not be running):

    UnrealEditor.exe <project>.uproject -d3d11 -nosplash -unattended -nullrhi
        -ExecutePythonScript=<this file>

Creates ``/Game/VantageCV/M_PaintWhite`` and ``/Game/VantageCV/M_PaintYellow`` (each only if it does not exist yet):
opaque, lit, matte materials. White is a slightly warm white (thermoplastic road paint is not pure white); yellow is
a plain traffic yellow, a modelling choice (the MUTCD defines yellow by chromaticity, not by an RGB value). The
``paint_white`` and ``paint_yellow`` mesh tags resolve to them (see ``MaterialResolver.cpp``). Nothing shared is edited.
"""

import unreal  # type: ignore[import-not-found]  # pylint: disable=import-error

PACKAGE_PATH = "/Game/VantageCV"
PAINTS = {
    "M_PaintWhite": (0.82, 0.82, 0.78),
    "M_PaintYellow": (0.70, 0.45, 0.02),
}
PAINT_ROUGHNESS = 0.7


def create_paint(name: str, color: tuple) -> None:  # type: ignore[type-arg]
    """Create and save one paint material unless it already exists."""
    if unreal.EditorAssetLibrary.does_asset_exist(f"{PACKAGE_PATH}/{name}"):
        print("PAINT_MATERIAL_EXISTS", name)
        return
    library = unreal.MaterialEditingLibrary
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    material = tools.create_asset(name, PACKAGE_PATH, unreal.Material, unreal.MaterialFactoryNew())

    base = library.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -400, 0
    )
    base.set_editor_property("constant", unreal.LinearColor(*color, 1.0))
    library.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)

    roughness = library.create_material_expression(
        material, unreal.MaterialExpressionConstant, -400, 200
    )
    roughness.set_editor_property("r", PAINT_ROUGHNESS)
    library.connect_material_property(roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)

    library.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    print("PAINT_MATERIAL_DONE", material.get_path_name())


def main() -> None:
    """Create the missing paint materials, then quit the editor."""
    for name, color in PAINTS.items():
        create_paint(name, color)
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


main()
