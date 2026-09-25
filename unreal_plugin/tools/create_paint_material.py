"""Create the project-owned road-paint material used for parking-lot stripes.

Run once in a headless editor session (the game/editor must not be running):

    UnrealEditor.exe <project>.uproject -d3d11 -nosplash -unattended -nullrhi
        -ExecutePythonScript=<this file>

Creates ``/Game/VantageCV/M_PaintWhite``: an opaque, lit, matte off-white
material (thermoplastic road paint is a slightly warm white, not pure
white). The ``paint_white`` mesh tag resolves to it (see
``MaterialResolver.cpp``). Nothing shared is edited.
"""

import unreal  # type: ignore[import-not-found]  # pylint: disable=import-error

PACKAGE_PATH = "/Game/VantageCV"
ASSET_NAME = "M_PaintWhite"
PAINT_COLOR = (0.82, 0.82, 0.78)
PAINT_ROUGHNESS = 0.7


def main() -> None:
    """Create and save the material, then quit the editor."""
    library = unreal.MaterialEditingLibrary
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    material = tools.create_asset(
        ASSET_NAME, PACKAGE_PATH, unreal.Material, unreal.MaterialFactoryNew()
    )

    color = library.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -400, 0
    )
    color.set_editor_property("constant", unreal.LinearColor(*PAINT_COLOR, 1.0))
    library.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)

    roughness = library.create_material_expression(
        material, unreal.MaterialExpressionConstant, -400, 200
    )
    roughness.set_editor_property("r", PAINT_ROUGHNESS)
    library.connect_material_property(roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)

    library.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    print("PAINT_MATERIAL_DONE", material.get_path_name())
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


main()
