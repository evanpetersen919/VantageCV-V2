"""Leafy street trees built from procedural meshes (no imported models).

Epic's City Sample tree kits are bare branch skeletons, so before this module spring and summer
streets had no trees at all and winter and fall had leafless ones: vegetation was 0 to 2% of
pixels in our class maps against 17.1% in Cityscapes validation (``demo/veg_share.py``,
experiment 32). Each tree here is a flared, tapered trunk, forked branches and a canopy of leaf
cards: flat quads textured with a cluster of leaves, masked by the texture's alpha (the
``foliage_*`` materials, ``unreal_plugin/tools/create_foliage_material.py``). Everything is
generated, so no third-party asset is involved.

What makes flat cards read as a crown rather than paper (experiment 33): every card vertex carries
the outward normal of its lump (the card's own normal is only a small part), so light falls off
across the whole crown, not card by card; every card carries a vertex colour that darkens cards deep
inside a lump and underneath it and jitters brightness and hue; and the card's texture is turned by
a random quarter turn and mirror so no two neighbours repeat.

The size ranges are design choices for a mature street tree (about 7 to 11 m tall, a clear trunk
of 3.0 to 4.0 m so vehicles and pedestrians pass under, a canopy 5 to 7 m wide), not measurements.
The spots are the street-tree spots ``street_furniture.py`` places; this module only replaces the
tree mesh standing at each.

One mesh per material is returned (all trunks together, all canopies together) so a scene adds
two draw items, not hundreds.
"""

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple

import numpy as np
import numpy.typing as npt

from src.procedural.environment import Season
from src.procedural.mesh_factory import Mesh

BARK_MATERIAL = "bark"
# Season -> the canopy's material tag; winter has no leaves (the bare Epic trees stay).
FOLIAGE_MATERIALS = {
    Season.SPRING: "foliage_spring",
    Season.SUMMER: "foliage_summer",
    Season.FALL: "foliage_fall",
}

TOTAL_HEIGHT_M = (7.0, 11.0)
CLEAR_TRUNK_M = (3.0, 4.0)
CANOPY_RADIUS_M = (2.4, 3.6)
TRUNK_RADIUS_M = (0.12, 0.20)
LEAF_CARDS = 240
LOBES = (3, 5)  # a canopy is this many overlapping lumps (inclusive range), not one ball
CARD_SIZE_M = (1.0, 1.5)
BRANCHES_PER_LOBE = 2
# How strongly a card vertex's normal follows its lump's outward direction (the rest is the card's).
LUMP_NORMAL_WEIGHT = 0.8
# Brightness of the darkest (deepest, lowest) cards relative to the brightest, and the spread added.
DEEP_CARD_BRIGHTNESS = 0.4
MAX_CARD_BRIGHTNESS = (
    0.88  # sunlit leaves are not white: keeps the brightest cards from blowing out
)
BRIGHTNESS_JITTER = 0.12
WIDTH_VARIATION = (0.75, 1.3)  # per-tree factor on the crown's width: narrow ovals to wide spreads
LEAN_M = 0.6  # the crown sits off the trunk's foot by up to this much, so trees are not plumb
HUE_JITTER = 0.08
BARK_UV_METERS = 0.8  # trunk length covered by one repeat of the bark texture
_TRUNK_SIDES = 8
_BRANCH_SIDES = 4

Vec = npt.NDArray[np.float64]
Ints = npt.NDArray[np.int64]
Bytes = npt.NDArray[np.uint8]


@dataclass
class MeshPart:
    """Buffers of one piece of geometry."""

    vertices: Vec
    triangles: Ints
    uvs: Vec
    normals: Vec
    colors: Bytes


def _frustum(  # pylint: disable=too-many-locals
    bottom: Vec, top: Vec, radii: Tuple[float, float], sides: int
) -> MeshPart:
    """A tapered prism from ``bottom`` to ``top`` (smooth-shaded, bark texture along its length)."""
    axis = top - bottom
    length = float(np.linalg.norm(axis))
    axis = axis / length
    helper = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    side_a = np.cross(axis, helper)
    side_a /= np.linalg.norm(side_a)
    side_b = np.cross(axis, side_a)
    fractions = np.arange(sides + 1) / sides  # one extra seam vertex so the texture wraps cleanly
    angles = 2.0 * math.pi * fractions
    ring = np.outer(np.cos(angles), side_a) + np.outer(np.sin(angles), side_b)
    vertices = np.vstack([bottom + ring * radii[0], top + ring * radii[1]])
    normals = np.vstack([ring, ring])
    rise = length / BARK_UV_METERS
    uvs = np.vstack(
        [
            np.column_stack([fractions * 2.0, np.zeros(sides + 1)]),
            np.column_stack([fractions * 2.0, np.full(sides + 1, rise)]),
        ]
    )
    stride = sides + 1
    triangles: List[int] = []
    for i in range(sides):
        triangles += [i, i + 1, stride + i, i + 1, stride + i + 1, stride + i]
    colors = np.full((len(vertices), 3), 255, dtype=np.uint8)
    return MeshPart(vertices, np.array(triangles, dtype=np.int64), uvs, normals, colors)


def _orthonormal_frame(normals: Vec) -> Tuple[Vec, Vec]:
    """Two unit vectors perpendicular to each row of ``normals`` and to each other."""
    helper = np.where(np.abs(normals[:, :1]) < 0.9, [[1.0, 0.0, 0.0]], [[0.0, 1.0, 0.0]])
    tangent = np.cross(normals, helper)
    tangent /= np.linalg.norm(tangent, axis=1, keepdims=True)
    return tangent, np.cross(normals, tangent)


def canopy_cards(  # pylint: disable=too-many-locals
    centre: Vec,
    radii: Tuple[float, float],
    count: int,
    rng: np.random.Generator,
    card_size: Tuple[float, float] = CARD_SIZE_M,
) -> MeshPart:
    """``count`` leaf-cluster quads (``card_size`` metres) scattered through one ellipsoid lump,
    outer shell favoured; ``radii`` is (horizontal, vertical)."""
    scale = np.array([radii[0], radii[0], radii[1]])
    directions = rng.normal(size=(count, 3))
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    reach = 0.55 + 0.45 * rng.random(count) ** (1.0 / 3.0)
    spots = centre + directions * scale * reach[:, None]
    # A card faces roughly outward (up to a quarter turn off), spun about its own normal.
    card_normals = directions + 0.6 * rng.normal(size=(count, 3))
    card_normals /= np.linalg.norm(card_normals, axis=1, keepdims=True)
    tangent, bitangent = _orthonormal_frame(card_normals)
    roll = rng.uniform(0.0, 2.0 * math.pi, count)[:, None]
    along = np.cos(roll) * tangent + np.sin(roll) * bitangent
    across = np.cross(card_normals, along)
    half = (0.5 * rng.uniform(card_size[0], card_size[1], count))[:, None]
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    # Card-major: each card's four corners are adjacent.
    vertices = np.stack([spots + along * half * a + across * half * b for a, b in corners], axis=1)

    # Smooth shading: the lump's outward normal at each vertex, with a little of the card's own.
    outward = (vertices - centre) / scale**2
    outward /= np.linalg.norm(outward, axis=2, keepdims=True)
    facing = np.sign(np.sum(card_normals[:, None, :] * outward, axis=2, keepdims=True))
    own = facing * card_normals[:, None, :]
    normals = LUMP_NORMAL_WEIGHT * outward + (1.0 - LUMP_NORMAL_WEIGHT) * own
    normals /= np.linalg.norm(normals, axis=2, keepdims=True)

    # Cards deep in the lump and low in it are shaded; brightness and hue vary card to card.
    depth = (reach - 0.55) / 0.45
    height = 0.5 + 0.5 * directions[:, 2]
    span = 1.0 - DEEP_CARD_BRIGHTNESS
    brightness = DEEP_CARD_BRIGHTNESS + span * (0.65 * depth + 0.35 * height)
    jittered = brightness * rng.normal(1.0, BRIGHTNESS_JITTER, count)
    brightness = np.clip(jittered, 0.1, MAX_CARD_BRIGHTNESS)
    hue = rng.normal(0.0, HUE_JITTER, count)
    tint = np.stack([1.0 + hue, np.ones(count), 1.0 - hue], axis=1)
    rgb = np.clip(brightness[:, None] * tint, 0.0, 1.0)
    colors = np.repeat((rgb * 255.0).astype(np.uint8)[:, None, :], 4, axis=1)

    # The texture is turned by a random quarter turn and mirrored per card.
    base_uv = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    turns = rng.integers(0, 4, count)
    mirrored = rng.random(count) < 0.5
    uvs = np.empty((count, 4, 2))
    for i in range(count):
        uv = np.roll(base_uv, int(turns[i]), axis=0)
        uvs[i] = uv[::-1] if mirrored[i] else uv
    base = 4 * np.arange(count)[:, None]
    triangles = (base + np.array([[0, 1, 2, 0, 2, 3]])).reshape(-1).astype(np.int64)
    return MeshPart(
        vertices.reshape(-1, 3),
        triangles,
        uvs.reshape(-1, 2),
        normals.reshape(-1, 3),
        colors.reshape(-1, 3),
    )


def merge_parts(parts: Sequence[MeshPart]) -> MeshPart:
    """Concatenate parts, shifting each one's triangle indices past the vertices before it."""
    offsets = np.cumsum([0] + [len(part.vertices) for part in parts[:-1]])
    return MeshPart(
        np.concatenate([part.vertices for part in parts]),
        np.concatenate([part.triangles + offset for part, offset in zip(parts, offsets)]),
        np.concatenate([part.uvs for part in parts]),
        np.concatenate([part.normals for part in parts]),
        np.concatenate([part.colors for part in parts]),
    )


def tree_geometry(  # pylint: disable=too-many-locals
    at: Tuple[float, float], rng: np.random.Generator
) -> Tuple[MeshPart, MeshPart]:
    """One tree at ground point ``at``: ``(trunk and branches, canopy)``."""
    total = float(rng.uniform(*TOTAL_HEIGHT_M))
    clear = float(rng.uniform(*CLEAR_TRUNK_M))
    horizontal = float(rng.uniform(*CANOPY_RADIUS_M) * rng.uniform(*WIDTH_VARIATION))
    vertical = 0.5 * (total - clear)
    root = np.array([at[0], at[1], 0.0])
    lean = np.array([rng.uniform(-LEAN_M, LEAN_M), rng.uniform(-LEAN_M, LEAN_M), 0.0])
    centre = root + lean + np.array([0.0, 0.0, clear + vertical])
    radius = float(rng.uniform(*TRUNK_RADIUS_M))

    lobe_count = int(rng.integers(LOBES[0], LOBES[1] + 1))
    lobes = []
    for _ in range(lobe_count):
        offset = np.array(
            [
                rng.uniform(-0.45, 0.45) * horizontal,
                rng.uniform(-0.45, 0.45) * horizontal,
                rng.uniform(-0.1, 0.35) * vertical,
            ]
        )
        radii = (horizontal * rng.uniform(0.55, 0.8), vertical * rng.uniform(0.6, 0.8))
        lobes.append((centre + offset, radii))

    flare = root + [0.0, 0.0, 0.7]
    trunk_top = root + 0.8 * lean + [0.0, 0.0, clear + 0.6 * vertical]
    parts = [
        _frustum(root, flare, (1.6 * radius, 1.05 * radius), _TRUNK_SIDES),
        _frustum(flare, trunk_top, (1.05 * radius, 0.45 * radius), _TRUNK_SIDES),
    ]
    for index in range(BRANCHES_PER_LOBE * lobe_count):
        lobe_centre = lobes[index % lobe_count][0]
        start = root + [0.0, 0.0, clear + float(rng.uniform(0.0, 0.5)) * vertical]
        parts.append(_frustum(start, lobe_centre, (0.45 * radius, 0.15 * radius), _BRANCH_SIDES))
    cards = [
        canopy_cards(lobe_centre, radii, LEAF_CARDS // lobe_count, rng)
        for lobe_centre, radii in lobes
    ]
    return merge_parts(parts), merge_parts(cards)


def foliage_meshes(  # pylint: disable=too-many-locals
    spots: Sequence[Tuple[float, float]], season: Season, seed: int
) -> List[Mesh]:
    """One leafy tree per ground spot as two meshes: the bark, then the foliage.

    Empty in winter (no leaves; the bare Epic trees stay) or with no spots. Deterministic from
    ``seed``, on its own random stream so no other generator's draws change."""
    material = FOLIAGE_MATERIALS.get(season)
    if material is None or not spots:
        return []
    rng = np.random.Generator(np.random.PCG64([seed, 0xF011]))
    bark_parts = []
    leaf_parts = []
    for spot in spots:
        bark, leaves = tree_geometry(spot, rng)
        bark_parts.append(bark)
        leaf_parts.append(leaves)
    meshes = []
    for tag, parts in ((BARK_MATERIAL, bark_parts), (material, leaf_parts)):
        merged = merge_parts(parts)
        meshes.append(
            Mesh(
                vertices=merged.vertices,
                triangles=merged.triangles,
                uvs=merged.uvs,
                material=tag,
                normals=merged.normals,
                colors=merged.colors,
            )
        )
    return meshes
