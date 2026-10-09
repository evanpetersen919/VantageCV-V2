"""Blender script: bake static posed meshes of one Microsoft Rocketbox avatar.

    blender -b -P scripts/rocketbox_bake_poses.py -- ROCKETBOX_ROOT AVATAR_NAME OUT_DIR

Run it through ``bin/bake_rocketbox.py`` (all avatars). For the avatar's gender, three walking clips and three
idle clips are loaded; per clip, frames at fixed fractions of its length are baked:

    walking ``w0``..``w5``: ``*_walk_neutral_01``, ``_02``, ``_03`` at 15% and 60% of their frames
    standing ``s0``..``s2``: ``*_idle_neutral_01``, ``_02``, ``_03`` at 50% of their frames

The clip's bone orientations are copied onto the avatar's bones (mean direction error 0.5 degrees against the
clip's own skeleton; applying the clip's curves directly leaves the body leaning back, see EXPERIMENT_LOG.md).
Each static mesh is turned to face +Y (from the hip line), put on z = 0 and centred on x, y, and exported with
the avatar's textures copied beside the meshes (the FBX keeps bare file names, which Unreal's importer resolves). ``poses.json`` in OUT_DIR/AVATAR_NAME lists the
measured extents (x, y, z in metres) of every mesh.
"""

import json
import math
import os
import shutil
import sys

import bpy
from mathutils import Matrix, Vector

WALK_CLIPS = ("walk_neutral_01", "walk_neutral_02", "walk_neutral_03")
WALK_FRACTIONS = (0.15, 0.60)
STAND_CLIPS = ("idle_neutral_01", "idle_neutral_02", "idle_neutral_03")
STAND_FRACTIONS = (0.50,)


def bones_in_order(arm):
    """Bone names, parents before children."""
    out = []

    def walk(bone):
        out.append(bone.name)
        for child in bone.children:
            walk(child)

    for root in [b for b in arm.data.bones if b.parent is None]:
        walk(root)
    return out


def import_clip(path, known):
    """Import an animation FBX and return its armature (the one object not in ``known``)."""
    bpy.ops.import_scene.fbx(filepath=path)
    return next(o for o in bpy.context.scene.objects if o.type == "ARMATURE" and o not in known)


def pose_from_clip(avatar, clip, frame):
    """Copy the clip's bone orientations at ``frame`` onto the avatar's bones."""
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    for name in bones_in_order(avatar):
        if name in clip.pose.bones:
            bone = avatar.pose.bones[name]
            target = clip.pose.bones[name].matrix.to_3x3().normalized()
            bone.matrix = Matrix.Translation(bone.matrix.to_translation()) @ target.to_4x4()
            bpy.context.view_layer.update()


def facing_turn(avatar):
    """The rotation about Z that turns the avatar's facing direction onto +Y (from the hip line)."""
    left = avatar.matrix_world @ avatar.pose.bones["Bip01 L Thigh"].head
    right = avatar.matrix_world @ avatar.pose.bones["Bip01 R Thigh"].head
    side = left - right
    forward = Vector((side.y, -side.x, 0.0))
    forward.normalize()
    return Matrix.Rotation(-math.atan2(forward.x, forward.y), 4, "Z")


def bake(avatar, meshes, out_fbx):
    """Export the avatar's current pose as a static mesh; return its extents (x, y, z) in metres."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    turn = facing_turn(avatar)
    baked = []
    for obj in meshes:
        mesh = bpy.data.meshes.new_from_object(
            obj.evaluated_get(depsgraph), preserve_all_data_layers=True, depsgraph=depsgraph
        )
        mesh.transform(turn @ obj.matrix_world)
        new = bpy.data.objects.new(obj.name, mesh)
        for slot in obj.material_slots:
            mesh.materials.append(slot.material)
        bpy.context.scene.collection.objects.link(new)
        baked.append(new)
    xs = [v.co.x for o in baked for v in o.data.vertices]
    ys = [v.co.y for o in baked for v in o.data.vertices]
    zs = [v.co.z for o in baked for v in o.data.vertices]
    shift = Vector((-(min(xs) + max(xs)) / 2, -(min(ys) + max(ys)) / 2, -min(zs)))
    for obj in baked:
        obj.data.transform(Matrix.Translation(shift))
    bpy.ops.object.select_all(action="DESELECT")
    for obj in baked:
        obj.select_set(True)
    bpy.ops.export_scene.fbx(
        filepath=out_fbx,
        use_selection=True,
        path_mode="STRIP",
        object_types={"MESH"},
        apply_unit_scale=True,
        bake_anim=False,
        axis_forward="-Y",
        axis_up="Z",
    )
    for obj in baked:
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(data)
    return [max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)]


def main():
    """Bake every planned pose of one avatar."""
    root, name, out_dir = sys.argv[sys.argv.index("--") + 1 :][:3]
    gender = "f" if name.startswith("Female") else "m"
    out = os.path.join(out_dir, name)
    os.makedirs(out, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    avatar_fbx = os.path.join(root, "Assets", "Avatars", "Adults", name, "Export", name + ".fbx")
    bpy.ops.import_scene.fbx(filepath=avatar_fbx)
    objects = list(bpy.context.scene.objects)
    avatar = next(o for o in objects if o.type == "ARMATURE")
    meshes = [o for o in objects if o.type == "MESH"]
    # textures: the FBX names the artist's disk; point every image at this avatar's Textures folder
    textures = os.path.join(root, "Assets", "Avatars", "Adults", name, "Textures")
    for image in bpy.data.images:
        candidate = os.path.join(textures, os.path.basename(image.filepath.replace("\\", "/")))
        if os.path.exists(candidate):
            image.filepath = candidate
            image.reload()
    for image in bpy.data.images:
        if image.type == "IMAGE" and os.path.exists(bpy.path.abspath(image.filepath)):
            shutil.copy(bpy.path.abspath(image.filepath), out)
    plan = [
        ("w", "xy", WALK_CLIPS, WALK_FRACTIONS),
        ("s", "static", STAND_CLIPS, STAND_FRACTIONS),
    ]
    rows = []
    for kind, folder, clips, fractions in plan:
        index = 0
        for clip_name in clips:
            clip_path = os.path.join(
                root,
                "Assets",
                "Animations",
                f"all_animations_max_motextr_{folder}",
                f"{gender}_{clip_name}.max.fbx",
            )
            known = set(bpy.context.scene.objects)
            clip = import_clip(clip_path, known)
            first, last = clip.animation_data.action.frame_range
            for fraction in fractions:
                frame = int(round(first + fraction * (last - first)))
                pose_from_clip(avatar, clip, frame)
                pose_name = f"{kind}{index}"
                extents = bake(avatar, meshes, os.path.join(out, f"{name}_{pose_name}.fbx"))
                rows.append(
                    {
                        "pose": pose_name,
                        "kind": "walking" if kind == "w" else "standing",
                        "clip": f"{gender}_{clip_name}",
                        "frame": frame,
                        "x": extents[0],
                        "y": extents[1],
                        "z": extents[2],
                    }
                )
                index += 1
            for obj in [o for o in bpy.context.scene.objects if o not in known]:
                bpy.data.objects.remove(obj, do_unlink=True)
    with open(os.path.join(out, "poses.json"), "w", encoding="utf-8") as handle:
        json.dump({"avatar": name, "gender": gender, "poses": rows}, handle, indent=1)
    print("baked", name, len(rows), "poses")


main()
