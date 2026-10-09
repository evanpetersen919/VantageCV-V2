"""Leafy street trees built from procedural meshes (no imported models).

Epic's City Sample tree kits are bare branch skeletons, so before this module spring and summer
streets had no trees at all and winter and fall had leafless ones: vegetation was 0 to 2% of
pixels in our class maps against 17.1% in Cityscapes validation (``demo/veg_share.py``,
experiment 32). Each tree here is a tapered trunk, a few branches and a canopy of leaf cards:
flat quads textured with a cluster of leaves, masked by the texture's alpha (the ``foliage_*``
materials, ``unreal_plugin/tools/create_foliage_material.py``). Everything is generated, so no
third-party asset is involved.

The size ranges are design choices for a mature street tree (about 7 to 11 m tall, a clear trunk
of 3.0 to 4.0 m so vehicles and pedestrians pass under, a canopy 5 to 7 m wide), not measurements.
The spots are the street-tree spots ``street_furniture.py`` places; this module only replaces the
tree mesh standing at each.

One mesh per material is returned (all trunks together, all canopies together) so a scene adds
two draw items, not hundreds.
"""

import math
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
LEAF_CARDS = 220
LOBES = (3, 5)  # a canopy is this many overlapping lumps (inclusive range), not one ball
CARD_SIZE_M = (1.1, 1.8)
BRANCHES = 4
_TRUNK_SIDES = 6
_BRANCH_SIDES = 4

Vec = npt.NDArray[np.float64]


def _frustum(  # pylint: disable=too-many-locals
    bottom: Vec, top: Vec, bottom_radius: float, top_radius: float, sides: int
) -> Tuple[Vec, npt.NDArray[np.int64], Vec]:
    """A tapered prism from ``bottom`` to ``top``: vertices, flat triangle list, UVs."""
    axis = top - bottom
    axis = axis / np.linalg.norm(axis)
    helper = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    side_a = np.cross(axis, helper)
    side_a /= np.linalg.norm(side_a)
    side_b = np.cross(axis, side_a)
    angles = np.linspace(0.0, 2.0 * math.pi, sides, endpoint=False)
    ring = np.outer(np.cos(angles), side_a) + np.outer(np.sin(angles), side_b)
    vertices = np.vstack([bottom + ring * bottom_radius, top + ring * top_radius])
    uvs = np.vstack(
        [
            np.column_stack([np.linspace(0.0, 1.0, sides, endpoint=False), np.zeros(sides)]),
            np.column_stack([np.linspace(0.0, 1.0, sides, endpoint=False), np.ones(sides)]),
        ]
    )
    triangles: List[int] = []
    for i in range(sides):
        j = (i + 1) % sides
        triangles += [i, j, sides + i, j, sides + j, sides + i]
    return vertices, np.array(triangles, dtype=np.int64), uvs


def _canopy_cards(  # pylint: disable=too-many-locals
    centre: Vec, radii: Tuple[float, float], count: int, rng: np.random.Generator
) -> Tuple[Vec, npt.NDArray[np.int64], Vec]:
    """``count`` leaf-cluster quads scattered through an ellipsoid lump, outer shell favoured."""
    horizontal, vertical = radii
    directions = rng.normal(size=(count, 3))
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    reach = 0.55 + 0.45 * rng.random(count) ** (1.0 / 3.0)
    scale = np.array([horizontal, horizontal, vertical])
    spots = centre + directions * scale * reach[:, None]
    # A card faces roughly outward (up to a quarter turn off), spun about its own normal.
    normals = directions + 0.6 * rng.normal(size=(count, 3))
    normals /= np.linalg.norm(normals, axis=1, keepdims=True)
    helper = np.where(np.abs(normals[:, :1]) < 0.9, [[1.0, 0.0, 0.0]], [[0.0, 1.0, 0.0]])
    tangent = np.cross(normals, helper)
    tangent /= np.linalg.norm(tangent, axis=1, keepdims=True)
    bitangent = np.cross(normals, tangent)
    roll = rng.uniform(0.0, 2.0 * math.pi, count)[:, None]
    along = np.cos(roll) * tangent + np.sin(roll) * bitangent
    across = np.cross(normals, along)
    half = (0.5 * rng.uniform(CARD_SIZE_M[0], CARD_SIZE_M[1], count))[:, None]
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    vertices = np.concatenate(
        [spots + along * half * a + across * half * b for a, b in corners], axis=0
    )
    # The concatenation is corner-major; reorder to card-major (a card's corners adjacent).
    vertices = np.reshape(np.transpose(np.reshape(vertices, (4, count, 3)), (1, 0, 2)), (-1, 3))
    uvs = np.tile(np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]), (count, 1))
    base = 4 * np.arange(count)[:, None]
    triangles = (base + np.array([[0, 1, 2, 0, 2, 3]])).reshape(-1).astype(np.int64)
    return vertices, triangles, uvs


def tree_geometry(  # pylint: disable=too-many-locals
    at: Tuple[float, float], rng: np.random.Generator
) -> Tuple[Tuple[Vec, npt.NDArray[np.int64], Vec], Tuple[Vec, npt.NDArray[np.int64], Vec]]:
    """One tree at ground point ``at``: ``(trunk and branches, canopy)`` as buffers."""
    total = float(rng.uniform(*TOTAL_HEIGHT_M))
    clear = float(rng.uniform(*CLEAR_TRUNK_M))
    horizontal = float(rng.uniform(*CANOPY_RADIUS_M))
    vertical = 0.5 * (total - clear)
    root = np.array([at[0], at[1], 0.0])
    centre = root + np.array([0.0, 0.0, clear + vertical])
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

    parts = [
        _frustum(
            root, root + [0.0, 0.0, clear + 0.6 * vertical], radius, 0.45 * radius, _TRUNK_SIDES
        )
    ]
    for index in range(BRANCHES):
        start = root + [0.0, 0.0, clear + float(rng.uniform(0.0, 0.5)) * vertical]
        lobe_centre = lobes[index % lobe_count][0]
        parts.append(_frustum(start, lobe_centre, 0.45 * radius, 0.15 * radius, _BRANCH_SIDES))
    cards = [
        _canopy_cards(lobe_centre, radii, LEAF_CARDS // lobe_count, rng)
        for lobe_centre, radii in lobes
    ]
    return _merge(parts), _merge(cards)


def _merge(
    parts: Sequence[Tuple[Vec, npt.NDArray[np.int64], Vec]]
) -> Tuple[Vec, npt.NDArray[np.int64], Vec]:
    """Concatenate meshes, shifting each one's triangle indices past the vertices before it."""
    offsets = np.cumsum([0] + [len(vertices) for vertices, _, _ in parts[:-1]])
    return (
        np.concatenate([vertices for vertices, _, _ in parts]),
        np.concatenate([triangles + offset for (_, triangles, _), offset in zip(parts, offsets)]),
        np.concatenate([uvs for _, _, uvs in parts]),
    )


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
        vertices, triangles, uvs = _merge(parts)
        meshes.append(Mesh(vertices=vertices, triangles=triangles, uvs=uvs, material=tag))
    return meshes
