"""Give the imported Poly Haven trees and plants their materials and turn Nanite on.

Run in a headless editor session after ``prepare_photoreal_trees.py`` (the game/editor must not be running):

    UnrealEditor-Cmd.exe <project>.uproject -d3d11 -nosplash -unattended -nullrhi
        -ExecutePythonScript=<this file>

Imports the textures ``prepare_photoreal_trees.py`` wrote (listed in each asset's ``textures.json``) into
``/Game/VantageCV/Trees/Textures`` and creates two materials:

- ``M_PH_Surface``: opaque; ``Diffuse``, ``Normal`` and ``Rough`` texture parameters times a ``Tint``.
- ``M_PH_Leaves``: masked, two-sided foliage shading (light shows through leaves); the diffuse texture's
  alpha is the opacity mask.

Per asset and material part there is an instance: ``MI_<asset>_<part>`` for an opaque part, and for a part
with an opacity map one per season (``MI_<asset>_<part>_spring``, ``_summer``, ``_fall``; fall swaps in the
hue-shifted texture). Each mesh slot is matched to the part whose name it contains (else ``main``) and given
the summer instance; Nanite is switched off (the game runs on D3D11) and every mesh above ``LOD_MIN_VERTS``
vertices gets reduced LODs. A scenario
swaps a slot for another season's instance per tree through ``material_replacements``.

Writes ``ue_info.json`` next to the textures: every static mesh imported for the asset with its height, slot
names, and which part each slot uses, for ``src/procedural/photoreal_trees.py``. Nothing shared is edited.
"""

import json

import unreal  # type: ignore[import-not-found]  # pylint: disable=import-error

CACHE = r"F:/vscode/VantageCV-V2/unreal_plugin/content/polyhaven_cache/"
LOG_PATH = r"F:/vscode/VantageCV-V2/unreal_plugin/tools/setup_photoreal_trees.log"
PACKAGE = "/Game/VantageCV/Trees"
TEXTURE_PACKAGE = PACKAGE + "/Textures"
ASSETS = ("jacaranda_tree", "tree_small_02", "searsia_lucida", "othonna_cerarioides", "fern_02")
LOD_MIN_VERTS = 20000
OPACITY_CLIP = 0.08
# (fraction of triangles kept, screen size at which the LOD takes over) for LOD0 to LOD3.
LOD_STEPS = ((0.40, 1.0), (0.15, 0.30), (0.05, 0.15), (0.015, 0.06))
SEASONS = ("spring", "summer", "fall")
# Linear multipliers on the scanned leaf colour per season; calibrated against rendered frames of the
# real vegetation colour (docs/experiments/34_*.md), not guessed.
LEAF_TINTS = {"spring": (0.50, 0.85, 0.95), "summer": (0.41, 0.73, 1.07), "fall": (0.60, 0.58, 0.52)}
SURFACE_TINT = (0.6, 0.6, 0.6)
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
        texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        texture.set_editor_property("srgb", False)
    elif kind == "data":
        texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
        texture.set_editor_property("srgb", False)
    unreal.EditorAssetLibrary.save_loaded_asset(texture)
    return texture


def parameter(library, material, name, default, x, y):
    """A texture parameter node."""
    node = library.create_material_expression(
        material, unreal.MaterialExpressionTextureSampleParameter2D, x, y
    )
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("texture", default)
    return node


def create_materials(defaults):
    """The opaque and the masked-foliage parent materials; ``defaults`` maps Diffuse, Normal and
    Rough to the placeholder textures their parameters fall back to."""
    library = unreal.MaterialEditingLibrary
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    made = {}
    for name, leaves in (("M_PH_Surface", False), ("M_PH_Leaves", True)):
        rebuild(PACKAGE, name)
        material = tools.create_asset(name, PACKAGE, unreal.Material, unreal.MaterialFactoryNew())
        if leaves:
            material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
            material.set_editor_property("two_sided", True)
            material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
            # The scans model every leaflet as geometry, so the alpha only trims edges; a low clip keeps
            # small leaflets from being thinned out by mip-averaged alpha at distance.
            material.set_editor_property("opaque_mask_clip_value" if False else "opacity_mask_clip_value", OPACITY_CLIP)
        diffuse = parameter(library, material, "Diffuse", defaults["Diffuse"], -900, 0)
        normal = parameter(library, material, "Normal", defaults["Normal"], -900, 300)
        rough = parameter(library, material, "Rough", defaults["Rough"], -900, 600)
        tint = library.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -900, 900)
        tint.set_editor_property("parameter_name", "Tint")
        tint.set_editor_property("default_value", unreal.LinearColor(1.0, 1.0, 1.0, 1.0))
        product = library.create_material_expression(material, unreal.MaterialExpressionMultiply, -550, 100)
        library.connect_material_expressions(diffuse, "RGB", product, "A")
        library.connect_material_expressions(tint, "", product, "B")
        library.connect_material_property(product, "", unreal.MaterialProperty.MP_BASE_COLOR)
        library.connect_material_property(normal, "RGB", unreal.MaterialProperty.MP_NORMAL)
        library.connect_material_property(rough, "R", unreal.MaterialProperty.MP_ROUGHNESS)
        if leaves:
            library.connect_material_property(product, "", unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
            library.connect_material_property(diffuse, "A", unreal.MaterialProperty.MP_OPACITY_MASK)
        library.recompile_material(material)
        unreal.EditorAssetLibrary.save_loaded_asset(material)
        say("MATERIAL", material.get_path_name())
        made[name] = material
    return made


def make_instance(name, parent, textures, tint):
    """A material instance with texture and tint overrides."""
    library = unreal.MaterialEditingLibrary
    rebuild(PACKAGE, name)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    instance = tools.create_asset(
        name, PACKAGE, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew()
    )
    instance.set_editor_property("parent", parent)
    for parameter_name, texture in textures.items():
        library.set_material_instance_texture_parameter_value(instance, parameter_name, texture)
    library.set_material_instance_vector_parameter_value(instance, "Tint", unreal.LinearColor(*tint, 1.0))
    library.update_material_instance(instance)
    unreal.EditorAssetLibrary.save_loaded_asset(instance)
    return instance


def build_instances(asset, spec, parents):
    """Import one asset's textures and make its instances; return ``{part: {variant: instance}}``."""
    instances = {}
    placeholders = spec["placeholders"]
    for part, files in spec["parts"].items():
        base = f"T_{asset}_{part}"
        normal = import_texture(base + "_nor", files.get("nor", placeholders["nor"]), "normal")
        rough = import_texture(base + "_rough", files.get("rough", placeholders["rough"]), "data")
        diffuse = import_texture(base + "_diff", files["diff"], "colour")
        shared = {"Normal": normal, "Rough": rough}
        if "diff_fall" in files:
            fall = import_texture(base + "_diff_fall", files["diff_fall"], "colour")
            instances[part] = {}
            for season in SEASONS:
                texture = fall if season == "fall" else diffuse
                instances[part][season] = make_instance(
                    f"MI_{asset}_{part}_{season}",
                    parents["M_PH_Leaves"],
                    dict(shared, Diffuse=texture),
                    LEAF_TINTS[season],
                )
        else:
            instances[part] = {
                "opaque": make_instance(
                    f"MI_{asset}_{part}", parents["M_PH_Surface"], dict(shared, Diffuse=diffuse), SURFACE_TINT
                )
            }
        say("PART", asset, part, sorted(instances[part]))
    return instances


def lod_options():
    """Reduction options that build LOD0 to LOD3 from the source mesh by ``LOD_STEPS``."""
    options = unreal.EditorScriptingMeshReductionOptions()
    options.set_editor_property("auto_compute_lod_screen_size", False)
    settings = []
    for percent, screen_size in LOD_STEPS:
        step = unreal.EditorScriptingMeshReductionSettings()
        step.set_editor_property("percent_triangles", percent)
        step.set_editor_property("screen_size", screen_size)
        settings.append(step)
    options.set_editor_property("reduction_settings", settings)
    return options


def part_for_slot(slot_name, parts):
    """The material part a mesh slot uses: the part whose name the slot contains, else ``main``."""
    for part in sorted(parts, key=len, reverse=True):
        if part != "main" and part in slot_name:
            return part
    return "main" if "main" in parts else sorted(parts)[0]


def assign_meshes(asset, spec, instances):
    """Give every static mesh of ``asset`` its summer instances and Nanite; return the manifest rows."""
    rows = []
    library = unreal.EditorStaticMeshLibrary
    for path in unreal.EditorAssetLibrary.list_assets(PACKAGE, recursive=False):
        name = path.split("/")[-1].split(".")[0]
        if not name.startswith(asset):
            continue
        mesh = unreal.EditorAssetLibrary.load_asset(path)
        if not isinstance(mesh, unreal.StaticMesh):
            continue
        slots = {}
        for index, slot in enumerate(mesh.static_materials):
            slot_name = str(slot.material_slot_name)
            part = part_for_slot(slot_name, spec["parts"])
            variants = instances[part]
            mesh.set_material(index, variants.get("summer", variants.get("opaque")))
            slots[slot_name] = {"part": part, "seasonal": "summer" in variants}
        # The live pipeline runs on D3D11 (D3D12 crashes in shader compilation), which cannot draw Nanite:
        # a Nanite mesh falls back to a heavily reduced proxy there (3.6 million vertices became 22,000
        # and the crowns thinned out). So Nanite stays off and heavy meshes get classic reduced LODs.
        settings = mesh.get_editor_property("nanite_settings")
        settings.set_editor_property("enabled", False)
        mesh.set_editor_property("nanite_settings", settings)
        source_vertices = library.get_number_verts(mesh, 0)
        if source_vertices >= LOD_MIN_VERTS and library.get_lod_count(mesh) == 1:
            library.set_lods(mesh, lod_options())
        vertices = library.get_number_verts(mesh, 0)
        lods = library.get_lod_count(mesh)
        unreal.EditorAssetLibrary.save_loaded_asset(mesh)
        bounds = mesh.get_bounds()
        rows.append(
            {
                "mesh": name,
                "path": f"{PACKAGE}/{name}",
                "height_m": round((bounds.origin.z + bounds.box_extent.z) / 100.0, 3),
                "width_m": round(2.0 * max(bounds.box_extent.x, bounds.box_extent.y) / 100.0, 3),
                "vertices": vertices,
                "lods": lods,
                "lod_vertices": [library.get_number_verts(mesh, lod) for lod in range(lods)],
                "slots": slots,
            }
        )
        say("MESH", name, rows[-1]["lod_vertices"], rows[-1]["height_m"])
    return rows


def main():
    """Set up every asset, then quit the editor."""
    try:
        first = json.load(open(CACHE + f"{ASSETS[0]}/textures.json", encoding="utf-8"))
        holders = first["placeholders"]
        defaults = {
            "Diffuse": import_texture("T_PH_Diffuse", holders["diff"], "colour"),
            "Normal": import_texture("T_PH_Normal", holders["nor"], "normal"),
            "Rough": import_texture("T_PH_Rough", holders["rough"], "data"),
        }
        parents = create_materials(defaults)
        manifest = {}
        for asset in ASSETS:
            spec = json.load(open(CACHE + f"{asset}/textures.json", encoding="utf-8"))
            instances = build_instances(asset, spec, parents)
            manifest[asset] = assign_meshes(asset, spec, instances)
        with open(CACHE + "ue_info.json", "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=1)
    except Exception as error:  # pylint: disable=broad-exception-caught
        say("ERROR", repr(error))
    say("DONE")
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


main()
