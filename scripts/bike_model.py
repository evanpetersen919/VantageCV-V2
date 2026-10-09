"""Blender module: a parametric city bicycle built from published Trek FX 2 Disc geometry.

Imported by ``scripts/rider_bake.py`` (run through Blender). Frame of reference: origin on the ground below the
bottom bracket, +Y forward, +X to the rider's right, +Z up, metres.

Geometry sources (docs/riders/step0_findings.md): size L of the 2021/2022 FX 2 Disc as transcribed by BikeInsights
(Trek's own page was unreachable): wheelbase 1,070 mm, stack 586, reach 398, head angle 71.5, seat angle 73.5, BB drop
65, chainstay 450, seat-tube length 508, fork offset 50, crank 170, handlebar width 660, stem 90, seatpost 27.2,
700c wheel (ISO 622) with a 35 mm tyre. ``check_geometry`` recomputes the BB height (281 mm published) and the fork
offset (50 mm published) from the others, so a transcription error would show.

Not published, so modelling choices (marked MODEL below): head-tube length, spacer height under the stem, grip length,
saddle size, pedal size and lateral position, tube diameters, spoke count and thickness.
"""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

# published (or derived from published) values, metres and degrees
WHEELBASE = 1.070
STACK = 0.586
REACH = 0.398
HEAD_ANGLE_DEG = 71.5
SEAT_ANGLE_DEG = 73.5
BB_DROP = 0.065
CHAINSTAY = 0.450
SEAT_TUBE_LENGTH = 0.508
FORK_OFFSET = 0.050
CRANK = 0.170
BAR_WIDTH = 0.660
STEM_LENGTH = 0.090
SEATPOST_DIAMETER = 0.0272
BEAD_SEAT_RADIUS = 0.622 / 2.0
TYRE_SECTION = 0.035
# MODEL (not published)
HEAD_TUBE_LENGTH = 0.150
SPACER_HEIGHT = 0.045
GRIP_LENGTH = 0.130
PEDAL_SIZE = (0.100, 0.100, 0.020)  # forward, lateral, thickness
PEDAL_LATERAL = 0.085
SADDLE_SIZE = (0.270, 0.140, 0.060)  # forward, lateral, height
TUBE_RADIUS = 0.017
SPOKE_COUNT = 32

TYRE_RADIUS = (
    BEAD_SEAT_RADIUS + TYRE_SECTION
)  # outer radius, derived from ISO 622 and the 35 mm tyre
BB_HEIGHT = TYRE_RADIUS - BB_DROP
CHAINSTAY_HORIZONTAL = math.sqrt(CHAINSTAY**2 - BB_DROP**2)


def point(fwd, up, lat=0.0):
    """A point in the bike frame from (forward, up, lateral-right) coordinates."""
    return Vector((lat, fwd, up))


def key_points(saddle_height):
    """The named points the rider is fitted to, in the bike frame. ``saddle_height`` is the distance from the
    bottom bracket along the seat tube to the saddle top."""
    bb = point(0.0, BB_HEIGHT)
    head = math.radians(HEAD_ANGLE_DEG)
    seat = math.radians(SEAT_ANGLE_DEG)
    up_axis = (-math.cos(head), math.sin(head))  # steering axis direction, bottom to top (fwd, up)
    normal = (math.sin(head), math.cos(head))  # forward, perpendicular to the steering axis
    head_top = (REACH, BB_HEIGHT + STACK)
    bar = (
        head_top[0] + SPACER_HEIGHT * up_axis[0] + STEM_LENGTH * normal[0],
        head_top[1] + SPACER_HEIGHT * up_axis[1] + STEM_LENGTH * normal[1],
    )
    seat_dir = (-math.cos(seat), math.sin(seat))
    return {
        "bb": bb,
        "rear_axle": point(-CHAINSTAY_HORIZONTAL, TYRE_RADIUS),
        "front_axle": point(WHEELBASE - CHAINSTAY_HORIZONTAL, TYRE_RADIUS),
        "head_top": point(*head_top),
        "head_bottom": point(
            head_top[0] - HEAD_TUBE_LENGTH * up_axis[0], head_top[1] - HEAD_TUBE_LENGTH * up_axis[1]
        ),
        "seat_tube_top": point(
            SEAT_TUBE_LENGTH * seat_dir[0], BB_HEIGHT + SEAT_TUBE_LENGTH * seat_dir[1]
        ),
        "saddle_top": point(saddle_height * seat_dir[0], BB_HEIGHT + saddle_height * seat_dir[1]),
        "bar_center": point(*bar),
        "grip_right": point(bar[0], bar[1], BAR_WIDTH / 2.0 - GRIP_LENGTH / 2.0),
        "grip_left": point(bar[0], bar[1], -(BAR_WIDTH / 2.0 - GRIP_LENGTH / 2.0)),
    }


def pedal_spindles(crank_deg):
    """Right and left pedal spindle points for a right-crank angle (0 = pointing down, 90 = forward)."""
    angle = math.radians(crank_deg)
    out = []
    for sign, turn in ((1.0, 0.0), (-1.0, math.pi)):
        a = angle + turn
        out.append(
            point(CRANK * math.sin(a), BB_HEIGHT - CRANK * math.cos(a), sign * PEDAL_LATERAL)
        )
    return out[0], out[1]


def check_geometry():
    """Recompute two published numbers from the others: BB height and fork offset (millimetres)."""
    kp = key_points(0.7)
    head = math.radians(HEAD_ANGLE_DEG)
    axis = (-math.cos(head), math.sin(head))
    to_axle = (kp["front_axle"].y - kp["head_top"].y, kp["front_axle"].z - kp["head_top"].z)
    offset = abs(axis[0] * to_axle[1] - axis[1] * to_axle[0])
    return {"bb_height_mm": BB_HEIGHT * 1000, "fork_offset_mm": offset * 1000}


# ---------------------------------------------------------------- mesh helpers
def _material(name, colour):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.diffuse_color = (*colour, 1.0)
    material.use_nodes = True
    node = material.node_tree.nodes.get("Principled BSDF")
    if node is not None:
        node.inputs["Base Color"].default_value = (*colour, 1.0)
    return material


MATERIALS = {
    "frame": (0.12, 0.13, 0.15),
    "metal": (0.65, 0.66, 0.68),
    "rubber": (0.02, 0.02, 0.02),
    "saddle": (0.05, 0.04, 0.04),
}


def _add(name, bm, material):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(_material(material, MATERIALS[material]))
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _tube(bm, p0, p1, radius, segments=12):
    """A closed cylinder between two points."""
    direction = p1 - p0
    length = direction.length
    rotation = Vector((0, 0, 1)).rotation_difference(direction.normalized()).to_matrix().to_4x4()
    matrix = Matrix.Translation((p0 + p1) / 2.0) @ rotation
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        segments=segments,
        radius1=radius,
        radius2=radius,
        depth=length,
        matrix=matrix,
    )


def _torus(bm, major, minor, centre, major_segments=64, minor_segments=12):
    """A torus whose axis is the X axis (a wheel rolling along +Y)."""
    rings = []
    for i in range(major_segments):
        a = 2.0 * math.pi * i / major_segments
        ring = []
        for j in range(minor_segments):
            b = 2.0 * math.pi * j / minor_segments
            radial = major + minor * math.cos(b)
            ring.append(
                bm.verts.new(
                    centre
                    + Vector((minor * math.sin(b), radial * math.sin(a), radial * math.cos(a)))
                )
            )
        rings.append(ring)
    for i in range(major_segments):
        for j in range(minor_segments):
            bm.faces.new(
                (
                    rings[i][j],
                    rings[(i + 1) % major_segments][j],
                    rings[(i + 1) % major_segments][(j + 1) % minor_segments],
                    rings[i][(j + 1) % minor_segments],
                )
            )


def _ellipsoid(bm, centre, size):
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.5)
    for vert in bm.verts:
        vert.co = Vector((vert.co.x * size[1], vert.co.y * size[0], vert.co.z * size[2])) + centre


def wheel(centre, spoke_radius, name):
    """A wheel at ``centre``: tyre, rim, hub and ``SPOKE_COUNT`` spokes of ``spoke_radius``."""
    tyre = bmesh.new()
    _torus(tyre, TYRE_RADIUS - TYRE_SECTION / 2.0, TYRE_SECTION / 2.0, centre)
    parts = [_add(name + "_tyre", tyre, "rubber")]
    rim = bmesh.new()
    _torus(rim, BEAD_SEAT_RADIUS + 0.008, 0.009, centre, 64, 8)
    parts.append(_add(name + "_rim", rim, "metal"))
    hub = bmesh.new()
    _tube(hub, centre + Vector((-0.05, 0, 0)), centre + Vector((0.05, 0, 0)), 0.02)
    parts.append(_add(name + "_hub", hub, "metal"))
    spokes = bmesh.new()
    for k in range(SPOKE_COUNT):
        a = 2.0 * math.pi * k / SPOKE_COUNT
        side = 1.0 if k % 2 == 0 else -1.0
        rim_point = centre + Vector(
            (
                0.0,
                (BEAD_SEAT_RADIUS - 0.002) * math.sin(a),
                (BEAD_SEAT_RADIUS - 0.002) * math.cos(a),
            )
        )
        hub_point = centre + Vector(
            (side * 0.03, 0.025 * math.sin(a + 0.4 * side), 0.025 * math.cos(a + 0.4 * side))
        )
        _tube(spokes, hub_point, rim_point, spoke_radius, 6)
    parts.append(_add(name + "_spokes", spokes, "metal"))
    return parts


def build_bike(saddle_height, crank_deg, spoke_radius=0.001):
    """Create the bicycle's objects (frame, fork and bars, wheels, saddle, cranks and pedals); return them with
    the key points."""
    kp = key_points(saddle_height)
    objects = []
    frame = bmesh.new()
    seat_tube_top = kp["seat_tube_top"]
    for p0, p1 in (
        (kp["bb"], seat_tube_top),  # seat tube
        (kp["bb"], kp["head_bottom"]),  # down tube
        (
            seat_tube_top - (seat_tube_top - kp["bb"]).normalized() * 0.04,
            kp["head_top"] - (kp["head_top"] - kp["head_bottom"]).normalized() * 0.03,
        ),  # top tube
        (kp["head_bottom"], kp["head_top"]),  # head tube
    ):
        _tube(frame, p0, p1, TUBE_RADIUS)
    for side in (-0.05, 0.05):
        _tube(
            frame,
            kp["bb"] + Vector((side * 0.6, 0, 0)),
            kp["rear_axle"] + Vector((side, 0, 0)),
            0.011,
        )  # chain stay
        _tube(
            frame,
            seat_tube_top
            - (seat_tube_top - kp["bb"]).normalized() * 0.03
            + Vector((side * 0.3, 0, 0)),
            kp["rear_axle"] + Vector((side, 0, 0)),
            0.009,
        )  # seat stay
    post_top = kp["saddle_top"] - (kp["saddle_top"] - kp["bb"]).normalized() * 0.03
    _tube(
        frame,
        seat_tube_top - (seat_tube_top - kp["bb"]).normalized() * 0.08,
        post_top,
        SEATPOST_DIAMETER / 2.0,
    )
    objects.append(_add("frame", frame, "frame"))
    saddle = bmesh.new()
    _ellipsoid(saddle, kp["saddle_top"] - Vector((0, 0, SADDLE_SIZE[2] / 2.0)), SADDLE_SIZE)
    objects.append(_add("saddle", saddle, "saddle"))
    fork = bmesh.new()
    for side in (-0.045, 0.045):
        _tube(
            fork,
            kp["head_bottom"] + Vector((side, 0, 0)),
            kp["front_axle"] + Vector((side * 1.1, 0, 0)),
            0.012,
        )
    _tube(
        fork,
        kp["head_bottom"],
        kp["head_top"] + (kp["head_top"] - kp["head_bottom"]).normalized() * SPACER_HEIGHT,
        0.014,
    )
    stem_base = kp["head_top"] + (kp["head_top"] - kp["head_bottom"]).normalized() * SPACER_HEIGHT
    _tube(fork, stem_base, kp["bar_center"], 0.016)
    _tube(
        fork,
        kp["bar_center"] + Vector((-BAR_WIDTH / 2.0, 0, 0)),
        kp["bar_center"] + Vector((BAR_WIDTH / 2.0, 0, 0)),
        0.011,
    )
    objects.append(_add("fork_bars", fork, "metal"))
    grips = bmesh.new()
    for sign in (-1.0, 1.0):
        inner = sign * (BAR_WIDTH / 2.0 - GRIP_LENGTH)
        _tube(
            grips,
            kp["bar_center"] + Vector((inner, 0, 0)),
            kp["bar_center"] + Vector((sign * BAR_WIDTH / 2.0, 0, 0)),
            0.016,
        )
    objects.append(_add("grips", grips, "rubber"))
    cranks = bmesh.new()
    right, left = pedal_spindles(crank_deg)
    for spindle, sign in ((right, 1.0), (left, -1.0)):
        _tube(
            cranks,
            kp["bb"] + Vector((sign * 0.05, 0, 0)),
            spindle - Vector((sign * 0.035, 0, 0)),
            0.012,
        )
        _tube(
            cranks,
            spindle - Vector((sign * 0.035, 0, 0)),
            spindle + Vector((sign * 0.035, 0, 0)),
            0.006,
        )
        bmesh.ops.create_cube(
            cranks,
            size=1.0,
            matrix=Matrix.Translation(spindle)
            @ Matrix.Diagonal((PEDAL_SIZE[1], PEDAL_SIZE[0], PEDAL_SIZE[2], 1.0)),
        )
    objects.append(_add("cranks_pedals", cranks, "metal"))
    for centre, name in ((kp["rear_axle"], "wheel_rear"), (kp["front_axle"], "wheel_front")):
        objects.extend(wheel(centre, spoke_radius, name))
    return objects, kp
