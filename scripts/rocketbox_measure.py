"""Blender script: limb lengths, height and facing of every Rocketbox adult avatar.

    blender -b -P scripts/rocketbox_measure.py -- ROCKETBOX_ROOT OUT.json

Imports each ``Assets/Avatars/Adults/<name>/Export/<name>.fbx`` into an empty scene and writes, per avatar,
the mesh height, pelvis height, segment lengths (thigh, calf, upper arm, forearm, hand), shoulder and hip width,
pelvis-to-neck length, bone count and which way the face points. The result for the 40 adults is committed as
``docs/riders/rocketbox_dims.json``; ``docs/riders/step0_findings.md`` reads it.
"""

import glob
import json
import os
import sys

import bpy
import mathutils


def measure(name: str, fbx: str) -> dict:
    """Measurements of one imported avatar (metres, world space)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=fbx)
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    world = arm.matrix_world

    def head(bone: str) -> mathutils.Vector:
        return world @ arm.data.bones[bone].head_local

    def length(a: str, b: str) -> float:
        return (head(a) - head(b)).length

    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    corners = [m.matrix_world @ mathutils.Vector(c) for m in meshes for c in m.bound_box]
    zs = [c.z for c in corners]
    return {
        "height": max(zs) - min(zs),
        "pelvis_z": head("Bip01 Pelvis").z,
        "thigh": length("Bip01 L Thigh", "Bip01 L Calf"),
        "calf": length("Bip01 L Calf", "Bip01 L Foot"),
        "foot_h": head("Bip01 L Foot").z,
        "toe_fwd": abs(head("Bip01 L Toe0").y - head("Bip01 L Foot").y),
        "upperarm": length("Bip01 L UpperArm", "Bip01 L Forearm"),
        "forearm": length("Bip01 L Forearm", "Bip01 L Hand"),
        "hand": length("Bip01 L Hand", "Bip01 L Finger2"),
        "shoulder_w": abs(head("Bip01 L UpperArm").x - head("Bip01 R UpperArm").x),
        "hip_w": abs(head("Bip01 L Thigh").x - head("Bip01 R Thigh").x),
        "torso": length("Bip01 Pelvis", "Bip01 Neck"),
        "facing_y_sign": 1 if head("Bip01 REye").y > head("Bip01 Head").y else -1,
        "bones": len(arm.data.bones),
        "meshes": len(meshes),
    }


def main() -> None:
    """Measure every adult avatar under the given Rocketbox root."""
    root, out = sys.argv[sys.argv.index("--") + 1 :][:2]
    result = {}
    for folder in sorted(glob.glob(os.path.join(root, "Assets", "Avatars", "Adults", "*"))):
        name = os.path.basename(folder)
        fbx = os.path.join(folder, "Export", name + ".fbx")
        if os.path.exists(fbx):
            result[name] = measure(name, fbx)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=1)
    print("measured", len(result), "avatars")


main()
