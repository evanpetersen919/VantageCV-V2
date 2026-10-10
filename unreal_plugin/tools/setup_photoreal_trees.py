"""Give the imported Poly Haven trees their materials and turn Nanite on.

Run in a headless editor session after ``prepare_photoreal_trees.py`` (the game/editor must not be running):

    UnrealEditor-Cmd.exe <project>.uproject -d3d11 -nosplash -unattended -nullrhi
        -ExecutePythonScript=<this file>

Imports the textures ``prepare_photoreal_trees.py`` wrote (listed in each tree's ``textures.json``) into
``/Game/VantageCV/Trees/Textures`` and creates two materials:

- ``M_PH_Surface``: opaque; ``Diffuse``, ``Normal`` and ``Rough`` texture parameters times a ``Tint`` (trunk
  and branches).
- ``M_PH_Leaves``: masked, two-sided foliage shading (light shows through leaves); the diffuse texture's
  alpha is the opacity mask.

and instances per tree: ``MI_<tree>_trunk``, ``MI_<tree>_branches`` and one leaf instance per season
(``MI_<tree>_leaves_spring``, ``_summer``, ``_fall``; fall swaps in the hue-shifted leaf texture). The
mesh's own slots get the trunk, branch and summer-leaf instances, and Nanite is enabled on the mesh (the scans
have millions of triangles). A scenario swaps the leaf slot for another season's instance per tree through
``material_replacements``. Nothing shared is edited.
"""

import json

import unreal  # type: ignore[import-not-found]  # pylint: disable=import-error

CACHE = r"F:/vscode/VantageCV-V2/unreal_plugin/content/polyhaven_cache/"
LOG_PATH = r"F:/vscode/VantageCV-V2/unreal_plugin/tools/setup_photoreal_trees.log"
PACKAGE = "/Game/VantageCV/Trees"
TEXTURE_PACKAGE = PACKAGE + "/Textures"
TREES = ("jacaranda_tree",)
MESH_SUFFIX = "_2k"
# Linear multipliers on the scanned leaf colour per season; calibrated against rendered frames of the
# real vegetation colour (docs/experiments/34_*.md), not guessed.
LEAF_TINTS = {
    "spring": (0.50, 0.70, 0.56),
    "summer": (0.41, 0.60, 0.63),
    "fall": (0.60, 0.58, 0.52),
}
OUT = open(LOG_PATH, "w", encoding="utf-8")  # pylint: disable=consider-using-with


def say(*parts):
    """Write one line to the log file next to this script."""
    OUT.write(" ".join(str(part) for part in parts) + chr(10))
    OUT.flush()


def rebuild(package, name):
    """Delete an existing project asset so it is created fresh."""
    path = f"{package}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)


def import_texture(name, filename, kind):
    """Import one image with the settings its ``kind`` ("colour", "normal" or "data") needs."""
    rebuild(TEXTURE_PACKAGE, name)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", filename)
    task.set_editor_property("destination_path", TEXTURE_PACKAGE)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", False)
    task.set_editor_property("replace_existing", True)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture = unreal.EditorAssetLibrary.load_asset(f"{TEXTURE_PACKAGE}/{name}")
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


def parameter(library, material, name, default, x, y):
    """A texture parameter node."""
    node = library.create_material_expression(
        material, unreal.MaterialExpressionTextureSampleParameter2D, x, y
    )
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("texture", default)
    return node


def create_materials(placeholder):
    """The opaque and the masked-foliage parent materials (``placeholder`` fills the texture slots)."""
    library = unreal.MaterialEditingLibrary
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    made = {}
    for name, leaves in (("M_PH_Surface", False), ("M_PH_Leaves", True)):
        rebuild(PACKAGE, name)
        material = tools.create_asset(name, PACKAGE, unreal.Material, unreal.MaterialFactoryNew())
        if leaves:
            material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
            material.set_editor_property("two_sided", True)
            material.set_editor_property(
                "shading_model", unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE
            )
        diffuse = parameter(library, material, "Diffuse", placeholder, -900, 0)
        normal = parameter(library, material, "Normal", placeholder, -900, 300)
        rough = parameter(library, material, "Rough", placeholder, -900, 600)
        tint = library.create_material_expression(
            material, unreal.MaterialExpressionVectorParameter, -900, 900
        )
        tint.set_editor_property("parameter_name", "Tint")
        tint.set_editor_property("default_value", unreal.LinearColor(1.0, 1.0, 1.0, 1.0))
        product = library.create_material_expression(
            material, unreal.MaterialExpressionMultiply, -550, 100
        )
        library.connect_material_expressions(diffuse, "RGB", product, "A")
        library.connect_material_expressions(tint, "", product, "B")
        library.connect_material_property(product, "", unreal.MaterialProperty.MP_BASE_COLOR)
        library.connect_material_property(normal, "RGB", unreal.MaterialProperty.MP_NORMAL)
        library.connect_material_property(rough, "R", unreal.MaterialProperty.MP_ROUGHNESS)
        if leaves:
            library.connect_material_property(
                product, "", unreal.MaterialProperty.MP_SUBSURFACE_COLOR
            )
            library.connect_material_property(diffuse, "A", unreal.MaterialProperty.MP_OPACITY_MASK)
        library.recompile_material(material)
        unreal.EditorAssetLibrary.save_loaded_asset(material)
        say("MATERIAL", material.get_path_name())
        made[name] = material
    return made


def make_instance(name, parent, textures, tint=None):
    """A material instance with texture (and optionally tint) overrides."""
    library = unreal.MaterialEditingLibrary
    rebuild(PACKAGE, name)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    instance = tools.create_asset(
        name, PACKAGE, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew()
    )
    instance.set_editor_property("parent", parent)
    for parameter_name, texture in textures.items():
        library.set_material_instance_texture_parameter_value(instance, parameter_name, texture)
    if tint is not None:
        library.set_material_instance_vector_parameter_value(
            instance, "Tint", unreal.LinearColor(*tint, 1.0)
        )
    library.update_material_instance(instance)
    unreal.EditorAssetLibrary.save_loaded_asset(instance)
    say("INSTANCE", name)
    return instance


def setup_tree(name, parents):
    """Textures, instances, slot assignment and Nanite for one tree."""
    paths = json.load(open(CACHE + f"{name}/textures.json", encoding="utf-8"))
    tex = {
        "leaves_diff": import_texture(f"T_{name}_leaves_diff", paths["leaves_diff"], "colour"),
        "leaves_fall": import_texture(
            f"T_{name}_leaves_diff_fall", paths["leaves_diff_fall"], "colour"
        ),
        "leaves_nor": import_texture(f"T_{name}_leaves_nor", paths["leaves_nor"], "normal"),
        "leaves_rough": import_texture(f"T_{name}_leaves_rough", paths["leaves_rough"], "data"),
    }
    for part in ("branches", "trunk"):
        tex[f"{part}_diff"] = import_texture(
            f"T_{name}_{part}_diff", paths[f"{part}_diff"], "colour"
        )
        tex[f"{part}_nor"] = import_texture(f"T_{name}_{part}_nor", paths[f"{part}_nor"], "normal")
        tex[f"{part}_rough"] = import_texture(
            f"T_{name}_{part}_rough", paths[f"{part}_rough"], "data"
        )

    instances = {}
    for part in ("trunk", "branches"):
        instances[part] = make_instance(
            f"MI_{name}_{part}",
            parents["M_PH_Surface"],
            {
                "Diffuse": tex[f"{part}_diff"],
                "Normal": tex[f"{part}_nor"],
                "Rough": tex[f"{part}_rough"],
            },
            (0.6, 0.6, 0.6),
        )
    for season, tint in LEAF_TINTS.items():
        diffuse = tex["leaves_fall"] if season == "fall" else tex["leaves_diff"]
        instances[f"leaves_{season}"] = make_instance(
            f"MI_{name}_leaves_{season}",
            parents["M_PH_Leaves"],
            {"Diffuse": diffuse, "Normal": tex["leaves_nor"], "Rough": tex["leaves_rough"]},
            tint,
        )

    mesh = unreal.EditorAssetLibrary.load_asset(f"{PACKAGE}/{name}{MESH_SUFFIX}")
    slots = mesh.static_materials
    for index, slot in enumerate(slots):
        slot_name = str(slot.material_slot_name)
        key = (
            "leaves_summer"
            if "leaves" in slot_name
            else ("trunk" if "trunk" in slot_name else "branches")
        )
        mesh.set_material(index, instances[key])
        say("SLOT", index, slot_name, "->", key)
    settings = mesh.get_editor_property("nanite_settings")
    settings.set_editor_property("enabled", True)
    mesh.set_editor_property("nanite_settings", settings)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh)
    say("NANITE", name, mesh.get_editor_property("nanite_settings").get_editor_property("enabled"))


def main():
    """Set up every tree, then quit the editor."""
    try:
        first = json.load(open(CACHE + f"{TREES[0]}/textures.json", encoding="utf-8"))["trunk_diff"]
        placeholder = import_texture("T_PH_Placeholder", first, "colour")
        parents = create_materials(placeholder)
        for name in TREES:
            setup_tree(name, parents)
    except Exception as error:  # pylint: disable=broad-exception-caught
        say("ERROR", repr(error))
    say("DONE")
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


main()
