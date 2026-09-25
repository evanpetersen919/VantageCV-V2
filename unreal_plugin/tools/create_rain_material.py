"""Create the project-owned rain-streak post-process material.

Run once in a headless editor session (the game/editor must not be running):

    UnrealEditor.exe <project>.uproject -d3d11 -nosplash -unattended -nullrhi
        -ExecutePythonScript=<this file>

Creates ``/Game/VantageCV/M_RainStreaks``: a post-process material (applied
after tone mapping) that blends thin, slightly slanted light streaks over the
frame. The streaks are procedural: three layers of screen-space columns, each
column holding repeating short streaks at random offsets and lengths, with the
far layers finer and fainter. The engine ships no rain effect or texture, and
City Sample has none either, so this is drawn from scratch.

Scalar parameters: ``Intensity`` (overall opacity, 0 turns rain off),
``Slant`` (horizontal shear per unit height), ``Seed`` (changes the pattern).
Nothing shared is edited.
"""

import unreal  # type: ignore[import-not-found]  # pylint: disable=import-error

PACKAGE_PATH = "/Game/VantageCV"
ASSET_NAME = "M_RainStreaks"

HLSL = """
float2 p = float2(UV.x * ViewSize.x / ViewSize.y, UV.y);
float acc = 0.0;
for (int layer = 0; layer < 3; layer++)
{
    float n = 55.0 * (1.0 + layer * 1.8);
    float2 q = float2(p.x * n + p.y * n * Slant, p.y * 1.7);
    float id = floor(q.x);
    float fx = frac(q.x) - 0.5;
    float h1 = frac(sin(dot(float2(id, layer + Seed), float2(12.9898, 78.233))) * 43758.5453);
    float h2 = frac(sin(dot(float2(id, layer + Seed + 7.0), float2(39.3468, 11.135))) * 24634.6345);
    float h3 = frac(sin(dot(float2(id, layer + Seed + 13.0), float2(73.156, 41.923))) * 12345.6789);
    float y = frac(q.y * (0.7 + 0.6 * h1) + h2 * 11.0);
    float len = 0.05 + 0.07 * h1;
    float width = smoothstep(0.10, 0.0, abs(fx));
    float along = smoothstep(0.0, 0.015, y) * smoothstep(len, len - 0.03, y);
    float present = step(0.55, h3);
    float weight = lerp(0.35, 1.0, layer / 2.0);
    acc = max(acc, width * along * present * weight);
}
return acc;
"""


def main() -> None:
    """Build the material graph, save it, then quit the editor."""
    library = unreal.MaterialEditingLibrary
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    existing = f"{PACKAGE_PATH}/{ASSET_NAME}"
    if unreal.EditorAssetLibrary.does_asset_exist(existing):
        unreal.EditorAssetLibrary.delete_asset(existing)
    material = tools.create_asset(
        ASSET_NAME, PACKAGE_PATH, unreal.Material, unreal.MaterialFactoryNew()
    )
    material.set_editor_property("material_domain", unreal.MaterialDomain.MD_POST_PROCESS)
    material.set_editor_property(
        "blendable_location", unreal.BlendableLocation.BL_SCENE_COLOR_AFTER_TONEMAPPING
    )

    uv = library.create_material_expression(material, unreal.MaterialExpressionTextureCoordinate, -900, 0)
    view_size = library.create_material_expression(material, unreal.MaterialExpressionViewProperty, -900, 150)
    view_size.set_editor_property("property", unreal.MaterialExposedViewProperty.MEVP_VIEW_SIZE)

    scalars = {}
    for index, (name, default) in enumerate((("Slant", 0.15), ("Seed", 0.0), ("Intensity", 0.6))):
        node = library.create_material_expression(
            material, unreal.MaterialExpressionScalarParameter, -900, 320 + index * 120
        )
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", default)
        scalars[name] = node

    custom = library.create_material_expression(material, unreal.MaterialExpressionCustom, -400, 100)
    custom.set_editor_property("code", HLSL)
    custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    inputs = []
    for input_name in ("UV", "ViewSize", "Slant", "Seed"):
        entry = unreal.CustomInput()
        entry.set_editor_property("input_name", input_name)
        inputs.append(entry)
    custom.set_editor_property("inputs", inputs)
    library.connect_material_expressions(uv, "", custom, "UV")
    library.connect_material_expressions(view_size, "", custom, "ViewSize")
    library.connect_material_expressions(scalars["Slant"], "", custom, "Slant")
    library.connect_material_expressions(scalars["Seed"], "", custom, "Seed")

    scale = library.create_material_expression(material, unreal.MaterialExpressionMultiply, -150, 100)
    library.connect_material_expressions(custom, "", scale, "A")
    library.connect_material_expressions(scalars["Intensity"], "", scale, "B")

    scene = library.create_material_expression(material, unreal.MaterialExpressionSceneTexture, -400, -200)
    scene.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0)
    streak_color = library.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -400, -50
    )
    streak_color.set_editor_property("constant", unreal.LinearColor(0.78, 0.82, 0.88, 1.0))

    blend = library.create_material_expression(material, unreal.MaterialExpressionLinearInterpolate, 100, -50)
    rgb = library.create_material_expression(material, unreal.MaterialExpressionComponentMask, -150, -200)
    rgb.set_editor_property("r", True)
    rgb.set_editor_property("g", True)
    rgb.set_editor_property("b", True)
    rgb.set_editor_property("a", False)
    library.connect_material_expressions(scene, "Color", rgb, "")
    library.connect_material_expressions(rgb, "", blend, "A")
    library.connect_material_expressions(streak_color, "", blend, "B")
    library.connect_material_expressions(scale, "", blend, "Alpha")
    library.connect_material_property(blend, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    library.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    print("RAIN_MATERIAL_DONE", material.get_path_name())
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


main()
