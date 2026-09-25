"""Create the project-owned emissive material the plugin's ``"glows"``
(headlight/tail-light lenses, lit windows) are drawn with.

Run once in a headless editor session (the game/editor must not be running):

    UnrealEditor.exe <project>.uproject -d3d11 -nosplash -unattended -nullrhi
        -ExecutePythonScript=<this file>

Creates ``/Game/VantageCV/M_EmissiveGlow``: an unlit, opaque material whose
emissive colour is one vector parameter, ``GlowColor`` (already multiplied
by brightness, so values above 1 are fine). It replaces the engine's own
``EmissiveMeshMaterial``, whose ``Color`` parameter had no effect on the
spawned glows (found live: pure green rendered white) and whose white-grid
texture showed as a pattern on every window. Nothing shared is edited.
"""

import unreal  # type: ignore[import-not-found]  # pylint: disable=import-error

PACKAGE_PATH = "/Game/VantageCV"
ASSET_NAME = "M_EmissiveGlow"


def main() -> None:
    """Create and save the material, then quit the editor."""
    library = unreal.MaterialEditingLibrary
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    material = tools.create_asset(
        ASSET_NAME, PACKAGE_PATH, unreal.Material, unreal.MaterialFactoryNew()
    )
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)

    color = library.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, -400, 0
    )
    color.set_editor_property("parameter_name", "GlowColor")
    color.set_editor_property("default_value", unreal.LinearColor(1.0, 1.0, 1.0, 1.0))
    library.connect_material_property(color, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    library.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    print("GLOW_MATERIAL_DONE", material.get_path_name())
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


main()
