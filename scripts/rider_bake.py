"""Blender script: pose a Rocketbox avatar on the Trek-based bicycle and export bike and rider as static meshes.

    blender -b -P scripts/rider_bake.py -- ROCKETBOX_ROOT AVATAR OUT_DIR [--calibrate] [--crank DEG ...]

Both meshes are exported in one frame (origin on the ground below the bottom bracket, +Y forward), so placing them at
the same transform in Unreal puts the rider on the bike. The pose is solved analytically on the Rocketbox biped
(``Bip01 ...`` bones): the pelvis is moved so the buttocks touch the saddle, the torso leans, each arm and leg is a
two-bone chain whose elbow or knee is placed by the law of cosines, and the hands and feet are aimed at the grips and
pedals. ``--calibrate`` first finds the saddle height at which the knee bend at the bottom of the pedal stroke is
KNEE_BEND_DEG (the published 35 to 45 degrees for recreational riding, docs/riders/step0_findings.md), on the
median-proportioned avatar. Every contact error (hand to grip, foot to pedal, buttock to saddle) is written to
``rider_<avatar>_c<crank>.json`` beside the meshes.
"""

import json
import math
import os
import shutil
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bike_model as bm  # noqa: E402  pylint: disable=wrong-import-position

KNEE_BEND_DEG = 40.0  # middle of the published 35 to 45 degrees (recreational)
TORSO_ANGLE_DEG = 55.0  # from horizontal; the published recreational range is 40 to 80
WRIST_BEHIND_GRIP = 0.05  # MODEL: wrist this far behind the grip centre and slightly above it
WRIST_ABOVE_GRIP = 0.03
FOOT_BALL_OVER_SPINDLE = (
    True  # ball of the foot over the pedal spindle (standard bike-fit practice)
)
SPINE = ("Bip01 Spine", "Bip01 Spine1", "Bip01 Spine2")
GRIP_RADIUS = 0.016  # the modelled grip's radius (bike_model: tube of 0.016)
FINGER_RADIUS = (
    0.0075  # MODEL: a finger's half thickness; the finger's centre line rides at the sum
)
FINGER_SPACING = 0.0175  # MODEL: centre-to-centre across the grip
FINGER_BONES = ("1", "2", "3", "4")  # index to little; each is Finger<n>, Finger<n>1, Finger<n>2
BUTTOCK_REST_Z = (0.78, 0.93)
BUTTOCK_REST_HALF_WIDTH = 0.13


def load_avatar(root, name):
    """Import the avatar facing +Y; return (armature, meshes, rest vertex positions of the buttock region)."""
    bpy.ops.import_scene.fbx(
        filepath=os.path.join(root, "Assets", "Avatars", "Adults", name, "Export", name + ".fbx")
    )
    objects = list(bpy.context.scene.objects)
    arm = next(o for o in objects if o.type == "ARMATURE")
    meshes = [o for o in objects if o.type == "MESH"]
    textures = os.path.join(root, "Assets", "Avatars", "Adults", name, "Textures")
    for image in bpy.data.images:
        candidate = os.path.join(textures, os.path.basename(image.filepath.replace("\\", "/")))
        if os.path.exists(candidate):
            image.filepath = candidate
            image.reload()
    bpy.context.view_layer.update()
    mesh = meshes[0]
    rest = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    # rest pose faces -Y, so the back (buttocks) is +Y
    region = [
        i
        for i, p in enumerate(rest)
        if BUTTOCK_REST_Z[0] <= p.z <= BUTTOCK_REST_Z[1]
        and abs(p.x) < BUTTOCK_REST_HALF_WIDTH
        and p.y > 0.0
    ]
    # the FBX carries an action that the renderer would re-apply over a hand-set pose
    arm.animation_data_clear()
    # turn the avatar to face +Y on top of the importer's own transform (replacing it would swap its axes)
    arm.matrix_world = Matrix.Rotation(math.pi, 4, "Z") @ arm.matrix_world
    bpy.context.view_layer.update()
    return arm, meshes, region


def world_head(arm, name):
    return arm.matrix_world @ arm.pose.bones[name].head


def segment(arm, bone, child):
    """Length in metres between a bone's joint and its child's joint."""
    return (world_head(arm, child) - world_head(arm, bone)).length


def aim(arm, bone, child, target):
    """Rotate ``bone`` about its joint so the direction to its ``child`` joint points at world point ``target``.

    The Rocketbox bones' own tails do not point along the limbs (Blender gives Biped bones a tail along the local
    X axis), so the direction to the child joint is used as the bone's direction."""
    pose_bone = arm.pose.bones[bone]
    inverse = arm.matrix_world.inverted()
    head = pose_bone.head.copy()
    current = (arm.pose.bones[child].head - head).normalized()
    wanted = ((inverse @ target) - head).normalized()
    rotation = current.rotation_difference(wanted).to_matrix().to_4x4()
    matrix = pose_bone.matrix.copy()
    pose_bone.matrix = Matrix.Translation(matrix.to_translation()) @ (
        rotation @ matrix.to_3x3().to_4x4()
    )
    bpy.context.view_layer.update()


def aim_vector(arm, bone, current_world, wanted_world):
    """Rotate ``bone`` about its joint by the rotation taking world direction ``current_world`` to ``wanted_world``."""
    pose_bone = arm.pose.bones[bone]
    rotation_world = (
        current_world.normalized().rotation_difference(wanted_world.normalized()).to_matrix()
    )
    local = (
        arm.matrix_world.to_3x3().normalized().inverted()
        @ rotation_world
        @ arm.matrix_world.to_3x3().normalized()
    )
    matrix = pose_bone.matrix.copy()
    pose_bone.matrix = Matrix.Translation(matrix.to_translation()) @ (
        local.to_4x4() @ matrix.to_3x3().to_4x4()
    )
    bpy.context.view_layer.update()


def move_root(arm, shift):
    """Translate the whole body (the Pelvis root bone) by the world vector ``shift``."""
    pose_bone = arm.pose.bones["Bip01 Pelvis"]
    inverse = arm.matrix_world.inverted().to_3x3()
    matrix = pose_bone.matrix.copy()
    pose_bone.matrix = (
        Matrix.Translation(matrix.to_translation() + inverse @ shift) @ matrix.to_3x3().to_4x4()
    )
    bpy.context.view_layer.update()


def two_bone(root, target, upper, lower, pole):
    """Joint position of a two-bone chain from ``root`` reaching ``target`` (``pole`` says which way it bends).
    Returns (joint, reachable)."""
    offset = target - root
    distance = offset.length
    direction = offset / distance
    reachable = distance <= upper + lower - 1e-6
    distance = min(distance, upper + lower - 1e-6)
    along = (upper**2 - lower**2 + distance**2) / (2.0 * distance)
    height = math.sqrt(max(upper**2 - along**2, 0.0))
    side = (pole - direction * pole.dot(direction)).normalized()
    return root + direction * along + side * height, reachable


def angle_between(a, b, c):
    """Interior angle at ``b`` in degrees."""
    u, v = (a - b).normalized(), (c - b).normalized()
    return math.degrees(math.acos(max(-1.0, min(1.0, u.dot(v)))))


def reset_pose(arm):
    for pose_bone in arm.pose.bones:
        pose_bone.matrix_basis = Matrix()
    bpy.context.view_layer.update()


def wrap_fingers(arm, side, grip, sign):
    """Close the four fingers of one hand around the grip; return the worst fingertip gap in metres.

    Each finger is three segments of the rig's own lengths. Its joints are put on a circle around the grip's
    axis (the bar runs along x), the first segment from the knuckle to the circle point at that segment's
    length, the next two a chord of their length further around, so fingers wrap over the top and down the
    front. Every bone is aimed with the same ``aim`` the arms use. The gap is the fingertip's distance to the
    grip's surface minus the finger's own half thickness (0 means the finger lies on the grip)."""
    radius = GRIP_RADIUS + FINGER_RADIUS
    gaps = []
    for index, number in enumerate(FINGER_BONES):
        names = [
            f"Bip01 {side} Finger{number}",
            f"Bip01 {side} Finger{number}1",
            f"Bip01 {side} Finger{number}2",
        ]
        knuckle = world_head(arm, names[0])
        lengths = [segment(arm, names[0], names[1]), segment(arm, names[1], names[2])]
        lengths.append(
            lengths[1] * arm.pose.bones[names[2]].length / arm.pose.bones[names[1]].length
        )
        centre = Vector((grip.x + sign * (index - 1.5) * FINGER_SPACING, grip.y, grip.z))

        def circle(theta, centre=centre):
            return centre + Vector((0.0, radius * math.sin(theta), radius * math.cos(theta)))

        # the first joint: the circle point (over the top, towards the front) at the first segment's length
        best_theta, best_error = 0.0, 1e9
        for step in range(-30, 121, 2):
            theta = math.radians(step)
            error = abs((circle(theta) - knuckle).length - lengths[0])
            if error < best_error:
                best_theta, best_error = theta, error
        thetas = [best_theta]
        for length in lengths[1:]:
            thetas.append(thetas[-1] + 2.0 * math.asin(min(1.0, length / (2.0 * radius))))
        aim(arm, names[0], names[1], circle(thetas[0]))
        aim(arm, names[1], names[2], circle(thetas[1]))
        direction = (world_head(arm, names[2]) - world_head(arm, names[1])).normalized()
        aim_vector(
            arm, names[2], direction, (circle(thetas[2]) - world_head(arm, names[2])).normalized()
        )
        tip = (
            world_head(arm, names[2])
            + (circle(thetas[2]) - world_head(arm, names[2])).normalized() * lengths[2]
        )
        axis_distance = math.hypot(tip.y - grip.y, tip.z - grip.z)
        gaps.append(abs(axis_distance - GRIP_RADIUS - FINGER_RADIUS))
    return max(gaps)


def solve(arm, kp, crank_deg, hip_target, torso_deg=TORSO_ANGLE_DEG):
    """Pose the avatar on the bike with its hip centre at ``hip_target``; return the measured contact errors."""
    reset_pose(arm)
    lean = Vector((0.0, math.cos(math.radians(torso_deg)), math.sin(math.radians(torso_deg))))
    for bone, child in (
        ("Bip01 Spine", "Bip01 Spine1"),
        ("Bip01 Spine1", "Bip01 Spine2"),
        ("Bip01 Spine2", "Bip01 Neck"),
    ):
        aim(arm, bone, child, world_head(arm, bone) + lean * segment(arm, bone, child))
    neck_dir = (lean * 0.8 + Vector((0, 0.1, 0.6))).normalized()
    aim(
        arm,
        "Bip01 Neck",
        "Bip01 Head",
        world_head(arm, "Bip01 Neck") + neck_dir * segment(arm, "Bip01 Neck", "Bip01 Head"),
    )
    eyes = (world_head(arm, "Bip01 REye") + world_head(arm, "Bip01 LEye")) / 2.0 - world_head(
        arm, "Bip01 Head"
    )
    aim_vector(arm, "Bip01 Head", eyes, Vector((0.0, 1.0, 0.25)))
    hips = (world_head(arm, "Bip01 L Thigh") + world_head(arm, "Bip01 R Thigh")) / 2.0
    if os.environ.get("DEBUG_RIDER"):
        for joint in (
            "Bip01 Pelvis",
            "Bip01 Spine",
            "Bip01 Spine1",
            "Bip01 Spine2",
            "Bip01 Neck",
            "Bip01 Head",
            "Bip01 L UpperArm",
        ):
            print("DBG", joint, tuple(round(v, 3) for v in world_head(arm, joint)))
        print(
            "DBG hips",
            tuple(round(v, 3) for v in hips),
            "target",
            tuple(round(v, 3) for v in hip_target),
        )
        for joint in (
            "Bip01 R UpperArm",
            "Bip01 L UpperArm",
            "Bip01 R Clavicle",
            "Bip01 L Clavicle",
            "Bip01 R Thigh",
            "Bip01 L Thigh",
        ):
            print("DBG", joint, tuple(round(v, 3) for v in world_head(arm, joint)))
    move_root(arm, hip_target - hips)
    report = {"unreachable": []}
    spindles = bm.pedal_spindles(crank_deg)
    for side, sign, spindle in (("R", 1.0, spindles[0]), ("L", -1.0, spindles[1])):
        # arm
        grip = kp["grip_right" if sign > 0 else "grip_left"]
        wrist = grip + Vector((0.0, -WRIST_BEHIND_GRIP, WRIST_ABOVE_GRIP))
        shoulder = world_head(arm, f"Bip01 {side} UpperArm")
        upper = segment(arm, f"Bip01 {side} UpperArm", f"Bip01 {side} Forearm")
        lower = segment(arm, f"Bip01 {side} Forearm", f"Bip01 {side} Hand")
        elbow, ok = two_bone(shoulder, wrist, upper, lower, Vector((sign * 0.4, -0.2, -1.0)))
        if not ok:
            report["unreachable"].append(f"{side} arm")
        aim(arm, f"Bip01 {side} UpperArm", f"Bip01 {side} Forearm", elbow)
        aim(arm, f"Bip01 {side} Forearm", f"Bip01 {side} Hand", wrist)
        aim(arm, f"Bip01 {side} Hand", f"Bip01 {side} Finger2", grip)
        report[f"{side}_finger_gap"] = wrap_fingers(arm, side, grip, sign)
        report[f"{side}_wrist_error"] = (world_head(arm, f"Bip01 {side} Hand") - wrist).length
        report[f"{side}_elbow_angle"] = angle_between(
            world_head(arm, f"Bip01 {side} UpperArm"),
            world_head(arm, f"Bip01 {side} Forearm"),
            world_head(arm, f"Bip01 {side} Hand"),
        )
        # leg
        ankle_height = bm.PEDAL_SIZE[2] / 2.0 + arm_foot_height(arm, side)
        toe_forward = arm_toe_forward(arm, side)
        ankle = spindle + Vector((0.0, -toe_forward, ankle_height))
        hip = world_head(arm, f"Bip01 {side} Thigh")
        thigh = segment(arm, f"Bip01 {side} Thigh", f"Bip01 {side} Calf")
        calf = segment(arm, f"Bip01 {side} Calf", f"Bip01 {side} Foot")
        knee, ok = two_bone(hip, ankle, thigh, calf, Vector((sign * 0.1, 1.0, 0.3)))
        if not ok:
            report["unreachable"].append(f"{side} leg")
        aim(arm, f"Bip01 {side} Thigh", f"Bip01 {side} Calf", knee)
        aim(arm, f"Bip01 {side} Calf", f"Bip01 {side} Foot", ankle)
        aim(
            arm,
            f"Bip01 {side} Foot",
            f"Bip01 {side} Toe0",
            ankle + Vector((0.0, toe_forward, -arm_foot_height(arm, side))),
        )
        report[f"{side}_ankle_error"] = (world_head(arm, f"Bip01 {side} Foot") - ankle).length
        report[f"{side}_knee_bend"] = 180.0 - angle_between(
            world_head(arm, f"Bip01 {side} Thigh"),
            world_head(arm, f"Bip01 {side} Calf"),
            world_head(arm, f"Bip01 {side} Foot"),
        )
    return report


FOOT_HEIGHT = {}
TOE_FORWARD = {}


def arm_foot_height(arm, side):
    """Ankle height above the sole in the rest pose (measured once per avatar)."""
    return FOOT_HEIGHT[(arm.name, side)]


def arm_toe_forward(arm, side):
    return TOE_FORWARD[(arm.name, side)]


def measure_feet(arm):
    """Record, from the rest pose, how high the ankle is above the sole and how far the ball is ahead of it."""
    reset_pose(arm)
    for side in ("L", "R"):
        ankle, toe = world_head(arm, f"Bip01 {side} Foot"), world_head(arm, f"Bip01 {side} Toe0")
        FOOT_HEIGHT[(arm.name, side)] = ankle.z - 0.0
        TOE_FORWARD[(arm.name, side)] = abs(toe.y - ankle.y)


def buttock_bottom(meshes, region):
    """Lowest world z of the buttock-region vertices of the posed mesh."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = meshes[0].evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    low = min((evaluated.matrix_world @ mesh.vertices[i].co).z for i in region)
    evaluated.to_mesh_clear()
    return low


def seat(arm, meshes, region, kp, crank_deg):
    """Solve with the hips on the saddle: lower or raise the hips until the buttocks touch the saddle top."""
    hip = Vector((0.0, kp["saddle_top"].y, kp["saddle_top"].z + 0.1))
    report = {}
    for _ in range(4):
        report = solve(arm, kp, crank_deg, hip)
        gap = buttock_bottom(meshes, region) - kp["saddle_top"].z
        hip.z -= gap
    report["buttock_to_saddle_m"] = buttock_bottom(meshes, region) - kp["saddle_top"].z
    report["hip_height_m"] = hip.z
    report["hip_forward_m"] = hip.y
    return report


def calibrate(arm, meshes, region):
    """Saddle height (from the bottom bracket along the seat tube) giving KNEE_BEND_DEG at the bottom of the stroke."""
    low, high = 0.45, 0.85
    for _ in range(12):
        mid = (low + high) / 2.0
        report = seat(arm, meshes, region, bm.key_points(mid), 0.0)
        bend = report["R_knee_bend"]
        if bend > KNEE_BEND_DEG:  # more bent than wanted: raise the saddle
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def export_fbx(objects, path):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        path_mode="STRIP",
        object_types={"MESH"},
        apply_unit_scale=True,
        bake_anim=False,
        axis_forward="-Y",
        axis_up="Z",
    )


def bake_rider(meshes, path, root_textures):
    """Export the posed avatar as one static mesh in the current world frame (no recentring)."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    baked = []
    for obj in meshes:
        mesh = bpy.data.meshes.new_from_object(
            obj.evaluated_get(depsgraph), preserve_all_data_layers=True, depsgraph=depsgraph
        )
        mesh.transform(obj.matrix_world)
        new = bpy.data.objects.new("rider", mesh)
        for slot in obj.material_slots:
            mesh.materials.append(slot.material)
        bpy.context.scene.collection.objects.link(new)
        baked.append(new)
    export_fbx(baked, path)
    for obj in baked:
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(data)


def render_preview(prefix):
    """Workbench renders of the posed scene from the side, front-quarter and above (for checking by eye)."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x, scene.render.resolution_y = 1200, 900
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    camera = bpy.data.objects.new("preview_camera", bpy.data.cameras.new("preview_camera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 2.4
    views = {
        "side": ((4.0, 0.0, 0.95), (90, 0, 90)),
        "front": ((0.0, 4.0, 0.95), (90, 0, 180)),
        "top": ((0.0, 0.0, 4.0), (0, 0, 0)),
    }
    # close-ups of the right hand on its grip (for checking the fingers by eye)
    grip = bm.key_points(0.5757)["grip_right"]
    views["hand_side"] = ((grip.x + 0.45, grip.y, grip.z + 0.02), (90, 0, 90))
    views["hand_front"] = ((grip.x, grip.y + 0.45, grip.z + 0.02), (90, 0, 180))
    views["hand_above"] = ((grip.x, grip.y, grip.z + 0.45), (0, 0, 0))
    for view, (location, rotation) in views.items():
        camera.data.ortho_scale = 0.32 if view.startswith("hand") else 2.4
        camera.location = location
        camera.rotation_euler = tuple(math.radians(v) for v in rotation)
        scene.render.filepath = f"{prefix}_{view}.png"
        bpy.ops.render.render(write_still=True)


SPOKE_VARIANTS = {
    "real": 0.001,
    "thick": 0.003,
}  # spoke radius in metres: a real 2 mm spoke and a 6 mm one


def export_bikes(out_dir, saddle_height, crank):
    """Export the bicycle once per spoke variant for this crank angle, then remove it from the scene."""
    for variant, radius in SPOKE_VARIANTS.items():
        objects, _ = bm.build_bike(saddle_height, crank, radius)
        export_fbx(objects, os.path.join(out_dir, f"bike_{variant}_c{int(crank)}.fbx"))
        for obj in objects:
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.meshes.remove(data)


def copy_textures(out_dir):
    """Copy the avatar's texture images beside the FBX (the FBX keeps bare file names)."""
    for image in bpy.data.images:
        path = bpy.path.abspath(image.filepath)
        if image.type == "IMAGE" and os.path.exists(path):
            shutil.copy(path, out_dir)


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :]
    root, name, out_dir = argv[:3]
    do_calibrate = "--calibrate" in argv
    cranks = [0.0, 90.0, 180.0, 270.0]
    if "--crank" in argv:
        tail = argv[argv.index("--crank") + 1 :]
        cranks = []
        for value in tail:
            if value.startswith("--"):
                break
            cranks.append(float(value))
    saddle_height = float(argv[argv.index("--saddle") + 1]) if "--saddle" in argv else None
    os.makedirs(out_dir, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    arm, meshes, region = load_avatar(root, name)
    measure_feet(arm)
    reset_pose(arm)
    if do_calibrate or saddle_height is None:
        saddle_height = calibrate(arm, meshes, region)
        print("SADDLE_HEIGHT", round(saddle_height, 4))
    results = {"avatar": name, "saddle_height_m": saddle_height, "poses": {}}
    for crank in cranks:
        kp = bm.key_points(saddle_height)
        report = seat(arm, meshes, region, kp, crank)
        results["poses"][f"c{int(crank)}"] = report
        bake_rider(meshes, os.path.join(out_dir, f"rider_{name}_c{int(crank)}.fbx"), None)
        if "--bikes" in argv:
            export_bikes(out_dir, saddle_height, crank)
        print(
            "POSE",
            int(crank),
            {k: (round(v, 4) if isinstance(v, float) else v) for k, v in report.items()},
        )
    if "--render" in argv:
        report = seat(arm, meshes, region, bm.key_points(saddle_height), cranks[0])
        bm.build_bike(saddle_height, cranks[0], 0.001)
        render_preview(argv[argv.index("--render") + 1])
    with open(os.path.join(out_dir, f"rider_{name}.json"), "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=1)
    copy_textures(out_dir)
    print("RIDER_DONE", name)


main()
