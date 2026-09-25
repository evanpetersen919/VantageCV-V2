"""Create the project-owned rain post-process material.

Run once in a headless editor session (the game/editor must not be running):

    UnrealEditor.exe <project>.uproject -d3d11 -nosplash -unattended -nullrhi
        -ExecutePythonScript=<this file>

Creates ``/Game/VantageCV/M_RainStreaks``: a post-process material (applied
after tone mapping) that draws rain over the frame with real depth. The engine
ships no rain effect or texture, and City Sample has none, so this is drawn
from scratch.

The rain is a set of depth layers (2.5 m to 100 m). Each layer is a grid of
cells whose size is fixed in METRES at that layer's distance, converted to
screen size with the camera's field of view, so a near layer has a few large
streaks and a far layer many fine ones, as in a real photograph. A layer's
streaks are shown only where the scene behind that pixel is farther than the
layer (the scene depth buffer), so a nearer object hides farther rain and rain
shows in front of anything behind it. Streaks are thin, slightly slanted,
tapered at both ends and fade with distance.

Ripples: where rain lands on flat wet ground, expanding rings are drawn on a
35 cm world-space grid. Each pixel's ground position is rebuilt from the depth
buffer, flat surfaces are found from the depth gradient (so roads, paving and
roofs get rings, walls do not), and rings fade out with distance.

Scalar parameters: ``Intensity`` (streak opacity, 0 turns streaks off), ``Slant``
(horizontal shear per unit height), ``Density`` (share of cells holding a
streak), ``Seed`` (changes the pattern), ``RippleIntensity`` and
``RippleDensity``. Nothing shared is edited.
"""

import unreal  # type: ignore[import-not-found]  # pylint: disable=import-error

PACKAGE_PATH = "/Game/VantageCV"
ASSET_NAME = "M_RainStreaks"

# Streak geometry in metres: cell footprint, streak half length and width.
CELL_WIDTH_M = 0.30
CELL_HEIGHT_M = 1.5
HALF_LENGTH_M = 0.28
WIDTH_M = 0.004

HLSL = """
float aspect = ViewSize.x / ViewSize.y;
float2 p = float2(UV.x * aspect, UV.y);
p.x += p.y * Slant;
float minWidth = 0.7 / ViewSize.y;
float depths[7] = {2.5, 5.0, 9.0, 16.0, 30.0, 55.0, 100.0};
float weights[7] = {0.35, 0.5, 0.7, 0.9, 0.9, 0.7, 0.5};
float acc = 0.0;
for (int i = 0; i < 7; i++)
{
    float dm = depths[i];
    float s = 1.0 / (2.0 * dm * TanHalfFov);
    float cellW = @CELL_W@ * s;
    float cellH = @CELL_H@ * s;
    float2 q = float2(p.x / cellW, p.y / cellH);
    float2 id = floor(q);
    float2 f = frac(q);
    float ls = Seed + i * 17.0;
    float h1 = frac(sin(dot(id + ls, float2(12.9898, 78.233))) * 43758.5453);
    float h2 = frac(sin(dot(id + ls + 3.1, float2(39.3468, 11.135))) * 24634.6345);
    float h3 = frac(sin(dot(id + ls + 7.7, float2(73.156, 41.923))) * 12345.6789);
    float h4 = frac(sin(dot(id + ls + 11.3, float2(26.651, 94.673))) * 31415.9265);
    float present = step(h1, Density);
    float cx = 0.15 + 0.7 * h2;
    float cy = 0.25 + 0.5 * h3;
    float halfLen = @HALF_LEN@ * (0.6 + 0.8 * h4) * s;
    float trueW = @WIDTH@ * s;
    float w = max(trueW, minWidth);
    float dx = (f.x - cx) * cellW;
    float dy = (f.y - cy) * cellH;
    float across = smoothstep(w, 0.0, abs(dx));
    float along = smoothstep(halfLen, halfLen * 0.35, abs(dy));
    float thin = min(1.0, trueW / minWidth);
    float lenFade = saturate((halfLen * ViewSize.y - 2.0) / 5.0);
    float visible = saturate((SceneDepthCm - dm * 100.0) / (dm * 10.0));
    float a = across * along * present * visible * weights[i] * lenFade * lerp(0.5, 1.0, thin);
    acc = 1.0 - (1.0 - acc) * (1.0 - a);
}
return acc;
"""
RIPPLE_HLSL = """
float2 o = 3.0 / ViewSize;
float dl = CalcSceneDepth(UV - float2(o.x, 0.0));
float dr = CalcSceneDepth(UV + float2(o.x, 0.0));
float du = CalcSceneDepth(UV - float2(0.0, o.y));
float dd = CalcSceneDepth(UV + float2(0.0, o.y));
float3 pl = SvPositionToTranslatedWorld(float4((UV - float2(o.x, 0.0)) * ViewSize, ConvertToDeviceZ(dl), 1.0));
float3 pr = SvPositionToTranslatedWorld(float4((UV + float2(o.x, 0.0)) * ViewSize, ConvertToDeviceZ(dr), 1.0));
float3 pu = SvPositionToTranslatedWorld(float4((UV - float2(0.0, o.y)) * ViewSize, ConvertToDeviceZ(du), 1.0));
float3 pd = SvPositionToTranslatedWorld(float4((UV + float2(0.0, o.y)) * ViewSize, ConvertToDeviceZ(dd), 1.0));
float3 n = normalize(cross(pr - pl, pd - pu));
float flatSurface = smoothstep(0.85, 0.97, abs(n.z));
float3 wp = SvPositionToTranslatedWorld(float4(UV * ViewSize, ConvertToDeviceZ(SceneDepthCm), 1.0));
float2 g = wp.xy / 35.0;
float2 id = floor(g);
float2 f = frac(g);
float h1 = frac(sin(dot(id + Seed, float2(12.9898, 78.233))) * 43758.5453);
float h2 = frac(sin(dot(id + Seed + 3.1, float2(39.3468, 11.135))) * 24634.6345);
float h3 = frac(sin(dot(id + Seed + 7.7, float2(73.156, 41.923))) * 12345.6789);
float h4 = frac(sin(dot(id + Seed + 11.3, float2(26.651, 94.673))) * 31415.9265);
float present = step(h1, RippleDensity);
float2 c = float2(0.2 + 0.6 * h2, 0.2 + 0.6 * h3);
float d = length(f - c);
float r = 0.05 + h4 * 0.4;
float life = 1.0 - h4;
float ring = smoothstep(0.075, 0.0, abs(d - r)) * life;
float ring2 = smoothstep(0.06, 0.0, abs(d - r * 0.62)) * life * 0.6;
float fade = saturate(1.0 - SceneDepthCm / 3500.0);
return saturate(max(ring, ring2) * 1.5) * present * flatSurface * fade;
"""

HLSL = (
    HLSL.replace("@CELL_W@", str(CELL_WIDTH_M))
    .replace("@CELL_H@", str(CELL_HEIGHT_M))
    .replace("@HALF_LEN@", str(HALF_LENGTH_M))
    .replace("@WIDTH@", str(WIDTH_M))
)


def _node(library, material, cls, x, y):
    return library.create_material_expression(material, cls, x, y)


def _scalar(library, material, name, default, x, y):
    node = _node(library, material, unreal.MaterialExpressionScalarParameter, x, y)
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("default_value", default)
    return node


def main() -> None:  # pylint: disable=too-many-locals
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

    uv = _node(library, material, unreal.MaterialExpressionTextureCoordinate, -1100, 0)
    view_size = _node(library, material, unreal.MaterialExpressionViewProperty, -1100, 150)
    view_size.set_editor_property("property", unreal.MaterialExposedViewProperty.MEVP_VIEW_SIZE)
    tan_fov = _node(library, material, unreal.MaterialExpressionViewProperty, -1100, 300)
    tan_fov.set_editor_property(
        "property", unreal.MaterialExposedViewProperty.MEVP_TAN_HALF_FIELD_OF_VIEW
    )
    tan_y = _node(library, material, unreal.MaterialExpressionComponentMask, -900, 300)
    tan_y.set_editor_property("g", True)
    library.connect_material_expressions(tan_fov, "", tan_y, "")

    depth = _node(library, material, unreal.MaterialExpressionSceneTexture, -1100, 450)
    depth.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_SCENE_DEPTH)
    depth_r = _node(library, material, unreal.MaterialExpressionComponentMask, -900, 450)
    depth_r.set_editor_property("r", True)
    library.connect_material_expressions(depth, "Color", depth_r, "")

    ripple_intensity = _scalar(library, material, "RippleIntensity", 0.5, -1100, 1080)
    ripple_density = _scalar(library, material, "RippleDensity", 0.35, -1100, 1200)
    slant = _scalar(library, material, "Slant", 0.12, -1100, 600)
    seed = _scalar(library, material, "Seed", 1.0, -1100, 720)
    density = _scalar(library, material, "Density", 0.5, -1100, 840)
    intensity = _scalar(library, material, "Intensity", 0.6, -1100, 960)

    custom = _node(library, material, unreal.MaterialExpressionCustom, -500, 300)
    custom.set_editor_property("code", HLSL)
    custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    wiring = (
        ("UV", uv),
        ("ViewSize", view_size),
        ("TanHalfFov", tan_y),
        ("SceneDepthCm", depth_r),
        ("Slant", slant),
        ("Seed", seed),
        ("Density", density),
    )
    inputs = []
    for input_name, _ in wiring:
        entry = unreal.CustomInput()
        entry.set_editor_property("input_name", input_name)
        inputs.append(entry)
    custom.set_editor_property("inputs", inputs)
    for input_name, source in wiring:
        library.connect_material_expressions(source, "", custom, input_name)

    scale = _node(library, material, unreal.MaterialExpressionMultiply, -200, 300)
    library.connect_material_expressions(custom, "", scale, "A")
    library.connect_material_expressions(intensity, "", scale, "B")

    ripples = _node(library, material, unreal.MaterialExpressionCustom, -500, 700)
    ripples.set_editor_property("code", RIPPLE_HLSL)
    ripples.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    ripple_wiring = (
        ("UV", uv),
        ("ViewSize", view_size),
        ("SceneDepthCm", depth_r),
        ("Seed", seed),
        ("RippleDensity", ripple_density),
    )
    ripple_inputs = []
    for input_name, _ in ripple_wiring:
        entry = unreal.CustomInput()
        entry.set_editor_property("input_name", input_name)
        ripple_inputs.append(entry)
    ripples.set_editor_property("inputs", ripple_inputs)
    for input_name, source in ripple_wiring:
        library.connect_material_expressions(source, "", ripples, input_name)
    ripple_scale = _node(library, material, unreal.MaterialExpressionMultiply, -200, 700)
    library.connect_material_expressions(ripples, "", ripple_scale, "A")
    library.connect_material_expressions(ripple_intensity, "", ripple_scale, "B")
    combined = _node(library, material, unreal.MaterialExpressionMax, 0, 500)
    library.connect_material_expressions(scale, "", combined, "A")
    library.connect_material_expressions(ripple_scale, "", combined, "B")

    scene = _node(library, material, unreal.MaterialExpressionSceneTexture, -500, -200)
    scene.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0)
    rgb = _node(library, material, unreal.MaterialExpressionComponentMask, -250, -200)
    rgb.set_editor_property("r", True)
    rgb.set_editor_property("g", True)
    rgb.set_editor_property("b", True)
    library.connect_material_expressions(scene, "Color", rgb, "")
    streak_color = _node(library, material, unreal.MaterialExpressionConstant3Vector, -250, -50)
    streak_color.set_editor_property("constant", unreal.LinearColor(0.78, 0.82, 0.88, 1.0))

    blend = _node(library, material, unreal.MaterialExpressionLinearInterpolate, 100, -50)
    library.connect_material_expressions(rgb, "", blend, "A")
    library.connect_material_expressions(streak_color, "", blend, "B")
    library.connect_material_expressions(combined, "", blend, "Alpha")
    library.connect_material_property(blend, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    library.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    print("RAIN_MATERIAL_DONE", material.get_path_name())
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


main()
