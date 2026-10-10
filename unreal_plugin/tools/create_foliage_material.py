"""Create the project-owned vegetation materials and import their photographic textures.

Run once in a headless editor session (the game/editor must not be running):

    UnrealEditor-Cmd.exe <project>.uproject -d3d11 -nosplash -unattended -nullrhi
        -ExecutePythonScript=<this file>

Imports the textures in ``unreal_plugin/content`` (leaf-cluster cards built by
``build_foliage_textures.py``) and ``content/photo`` (ambientCG CC0 maps fetched by
``fetch_photo_textures.py``) and creates, in ``/Game/VantageCV/Foliage``:

- ``M_Foliage``: masked, two-sided foliage shading; base colour = the ``Leaf`` texture parameter times a
  ``Tint`` vector parameter times the mesh's vertex colour, opacity mask = the texture's alpha, the same
  colour as subsurface colour so light shows through leaves.
- ``MI_Foliage_Spring``, ``MI_Foliage_Summer``, ``MI_Foliage_Fall``: instances that differ in ``Tint``;
  fall also swaps ``Leaf`` for the autumn cluster.
- ``M_Bark`` and ``M_Grass``: photographic colour, normal and roughness maps times a brightness tint.

The mesh tags ``foliage_*``, ``bark`` and ``grass`` resolve to them (``MaterialResolver.cpp``).
Existing assets are rebuilt, they are this project's own. Nothing shared is edited.
"""

import unreal  # type: ignore[import-not-found]  # pylint: disable=import-error

PACKAGE_PATH = "/Game/VantageCV/Foliage"
CONTENT_DIR = r"F:/vscode/VantageCV-V2/unreal_plugin/content/"
LOG_PATH = r"F:/vscode/VantageCV-V2/unreal_plugin/tools/create_foliage_material.log"
# Linear multipliers on the photographs, calibrated against rendered frames of the real vegetation
# colour (docs/experiments/34_*.md), not guessed.
TINTS = {
    "MI_Foliage_Spring": (0.26, 0.28, 0.19),
    "MI_Foliage_Summer": (0.21, 0.23, 0.18),
    "MI_Foliage_Fall": (0.27, 0.25, 0.22),
}
GRASS_TINT = (0.26, 0.27, 0.22)
BARK_TINT = (0.30, 0.30, 0.30)
# (asset name, file, kind): kind picks the import settings.
TEXTURES = (
    ("T_LeafCluster", "T_LeafCluster.png", "colour"),
    ("T_LeafClusterFall", "T_LeafClusterFall.png", "colour"),
    ("T_Bark", "photo/Bark012_Color.jpg", "colour"),
    ("T_Bark_N", "photo/Bark012_NormalDX.jpg", "normal"),
    ("T_Bark_R", "photo/Bark012_Roughness.jpg", "data"),
    ("T_Grass", "photo/Grass005_Color.jpg", "colour"),
    ("T_Grass_N", "photo/Grass005_NormalDX.jpg", "normal"),
    ("T_Grass_R", "photo/Grass005_Roughness.jpg", "data"),
)
OUT = open(LOG_PATH, "w", encoding="utf-8")  # pylint: disable=consider-using-with


def say(*parts):
    """Write one line to the log file next to this script."""
    OUT.write(" ".join(str(part) for part in parts) + chr(10))
    OUT.flush()


def rebuild(name):
    """Delete an existing project asset so it is created fresh."""
    path = f"{PACKAGE_PATH}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)


def import_texture(name, filename, kind):
    """Import one image as a texture asset with the settings its ``kind`` needs."""
    rebuild(name)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", CONTENT_DIR + filename)
    task.set_editor_property("destination_path", PACKAGE_PATH)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", False)
    task.set_editor_property("replace_existing", True)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture = unreal.EditorAssetLibrary.load_asset(f"{PACKAGE_PATH}/{name}")
    if kind == "normal":
        texture.set_editor_property(
            "compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP
        )
        texture.set_editor_property("srgb", False)
    elif kind == "data":
        texture.set_editor_property(
            "compression_settings", unreal.TextureCompressionSettings.TC_MASKS
        )
        texture.set_editor_property("srgb", False)
    unreal.EditorAssetLibrary.save_loaded_asset(texture)
    say("TEXTURE", name, kind)
    return texture


def sample(library, material, texture, x, y, parameter=None):
    """A texture sample node (a texture parameter when ``parameter`` names it)."""
    if parameter is None:
        node = library.create_material_expression(
            material, unreal.MaterialExpressionTextureSample, x, y
        )
    else:
        node = library.create_material_expression(
            material, unreal.MaterialExpressionTextureSampleParameter2D, x, y
        )
        node.set_editor_property("parameter_name", parameter)
    node.set_editor_property("texture", texture)
    return node


def multiply(library, material, first, second, x, y, first_output="", second_output=""):
    """A multiply node of two outputs."""
    node = library.create_material_expression(material, unreal.MaterialExpressionMultiply, x, y)
    library.connect_material_expressions(first, first_output, node, "A")
    library.connect_material_expressions(second, second_output, node, "B")
    return node


def constant3(library, material, colour, x, y):
    """A constant colour node."""
    node = library.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, x, y
    )
    node.set_editor_property("constant", unreal.LinearColor(*colour, 1.0))
    return node


def new_material(name):
    """An empty project material."""
    rebuild(name)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    return tools.create_asset(name, PACKAGE_PATH, unreal.Material, unreal.MaterialFactoryNew())


def finish(library, material, label):
    """Compile and save a material."""
    library.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    say(label, material.get_path_name())


def create_foliage_material(textures):
    """The masked, two-sided-foliage parent material."""
    library = unreal.MaterialEditingLibrary
    material = new_material("M_Foliage")
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    material.set_editor_property("two_sided", True)
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)

    leaf = sample(library, material, textures["T_LeafCluster"], -1000, 0, "Leaf")
    tint = library.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, -1000, 300
    )
    tint.set_editor_property("parameter_name", "Tint")
    tint.set_editor_property("default_value", unreal.LinearColor(*TINTS["MI_Foliage_Summer"], 1.0))
    vertex = library.create_material_expression(
        material, unreal.MaterialExpressionVertexColor, -1000, 500
    )
    first = multiply(library, material, leaf, tint, -700, 100, "RGB")
    colour = multiply(library, material, first, vertex, -450, 200, "", "RGB")
    library.connect_material_property(colour, "", unreal.MaterialProperty.MP_BASE_COLOR)
    library.connect_material_property(colour, "", unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
    library.connect_material_property(leaf, "A", unreal.MaterialProperty.MP_OPACITY_MASK)
    roughness = library.create_material_expression(
        material, unreal.MaterialExpressionConstant, -450, 400
    )
    roughness.set_editor_property("r", 0.6)
    library.connect_material_property(roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)
    specular = library.create_material_expression(
        material, unreal.MaterialExpressionConstant, -450, 500
    )
    specular.set_editor_property("r", 0.15)
    library.connect_material_property(specular, "", unreal.MaterialProperty.MP_SPECULAR)
    finish(library, material, "MATERIAL")
    return material


def create_instances(parent, textures):
    """One instance per season tint; fall swaps in the autumn leaf cluster."""
    library = unreal.MaterialEditingLibrary
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    for name, colour in TINTS.items():
        rebuild(name)
        instance = tools.create_asset(
            name,
            PACKAGE_PATH,
            unreal.MaterialInstanceConstant,
            unreal.MaterialInstanceConstantFactoryNew(),
        )
        instance.set_editor_property("parent", parent)
        library.set_material_instance_vector_parameter_value(
            instance, "Tint", unreal.LinearColor(*colour, 1.0)
        )
        if name.endswith("Fall"):
            library.set_material_instance_texture_parameter_value(
                instance, "Leaf", textures["T_LeafClusterFall"]
            )
        library.update_material_instance(instance)
        unreal.EditorAssetLibrary.save_loaded_asset(instance)
        say("INSTANCE", name, colour)


def create_surface(name, prefix, tint, textures):
    """A photographic surface: colour x tint, with normal and roughness maps."""
    library = unreal.MaterialEditingLibrary
    material = new_material(name)
    colour = sample(library, material, textures[prefix], -900, 0)
    brightness = constant3(library, material, tint, -900, 250)
    base = multiply(library, material, colour, brightness, -550, 100, "RGB")
    library.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    normal = sample(library, material, textures[prefix + "_N"], -900, 450)
    library.connect_material_property(normal, "RGB", unreal.MaterialProperty.MP_NORMAL)
    rough = sample(library, material, textures[prefix + "_R"], -900, 700)
    library.connect_material_property(rough, "R", unreal.MaterialProperty.MP_ROUGHNESS)
    finish(library, material, name.upper())


def main():
    """Build every vegetation asset, then quit the editor."""
    try:
        textures = {name: import_texture(name, filename, kind) for name, filename, kind in TEXTURES}
        create_instances(create_foliage_material(textures), textures)
        create_surface("M_Bark", "T_Bark", BARK_TINT, textures)
        create_surface("M_Grass", "T_Grass", GRASS_TINT, textures)
    except Exception as error:  # pylint: disable=broad-exception-caught
        say("ERROR", repr(error))
    say("DONE")
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


main()
