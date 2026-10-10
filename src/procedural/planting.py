"""Grass strips, shrubs and hedges along the curb.

The generated streets had paving from the curb to the buildings and nothing growing at street
level; real street frames (Cityscapes) show lawn verges, bushes and hedges as well as trees. This
module lays intermittent grass patches on the sidewalk beside the curb, and plants some of them with
spaced shrubs or a dense hedge. The patch layout, sizes and mix are design choices, not
measurements; only the result is compared with real frames (experiment 33).

A patch is a flat grass quad a centimetre above the sidewalk slab (the ``grass`` material, class
``terrain``), 1.0 m wide, starting 0.3 m out from the curb line so it clears the curb. Patches keep
the same distance from run ends as street furniture (crosswalks and corners live there) and avoid
driveway keep-out rectangles. Shrubs and hedges reuse the tree generator's leaf-card lumps, smaller,
with the season's foliage material; none in winter (no leaves). Everything is generated from the
scenario seed on its own random stream.
"""

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np

from src.procedural.building_facade import FacadePiece
from src.procedural.environment import Season
from src.procedural.foliage import FOLIAGE_MATERIALS, MeshPart, canopy_cards, merge_parts
from src.procedural.lane_topology import Lane
from src.procedural.mesh_factory import Mesh
from src.procedural.photoreal_trees import SHRUBS, plant_piece
from src.procedural.road_edge_kit import EdgeRun, Rect, edge_runs
from src.procedural.road_network import RoadEdge
from src.procedural.street_furniture import END_MARGIN_METERS

Point = Tuple[float, float]

GRASS_MATERIAL = "grass"
GRASS_Z_M = 0.118  # one centimetre above the sidewalk slab top (0.108 m)
STRIP_OFFSET_M = (0.3, 1.3)  # from the curb line, outward
PATCH_LENGTH_M = (8.0, 18.0)
PATCH_GAP_M = (3.0, 8.0)
KEEP_OUT_BUFFER_M = 1.0
STYLES = ("lawn", "shrubs", "hedge")
STYLE_WEIGHTS = (0.35, 0.4, 0.25)
SHRUB_SPACING_M = (1.6, 2.6)
SHRUB_PROBABILITY = 0.65
HEDGE_SPACING_M = 0.7
SHRUB_RADIUS_M = (0.5, 0.8)
SHRUB_HEIGHT_M = (0.8, 1.4)
HEDGE_HEIGHT_M = (0.9, 1.2)
SHRUB_CARDS = 30
SHRUB_CARD_SIZE_M = (0.4, 0.7)
GRASS_UV_TILE_M = 2.0
PLANT_HEDGE_SPACING_M = 1.1  # scanned columnar shrubs are wider than the card lumps
FERN_PROBABILITY = 0.4


@dataclass(frozen=True)
class Patch:
    """One grass patch: its axis-aligned footprint and how it is planted."""

    rect: Rect
    style: str
    centre_line: Tuple[Point, Point]  # patch start and end, mid-strip


def rect_gap(first: Rect, second: Rect) -> float:
    """Distance between two axis-aligned rectangles (zero when they touch or overlap)."""
    dx = max(first[0] - second[2], second[0] - first[2], 0.0)
    dy = max(first[1] - second[3], second[1] - first[3], 0.0)
    return float(np.hypot(dx, dy))


def _patch_at(run: EdgeRun, start: float, length: float) -> Tuple[Rect, Tuple[Point, Point]]:
    """The footprint of a patch ``length`` long from ``start`` metres along ``run``, and its centre
    line (the middle of the strip, where shrubs stand)."""
    near = run.start + run.run_direction * start
    far = run.start + run.run_direction * (start + length)
    corners = [p + run.outward * offset for p in (near, far) for offset in STRIP_OFFSET_M]
    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
    mid = run.outward * (0.5 * (STRIP_OFFSET_M[0] + STRIP_OFFSET_M[1]))
    line = (
        (float(near[0] + mid[0]), float(near[1] + mid[1])),
        (float(far[0] + mid[0]), float(far[1] + mid[1])),
    )
    return (min(xs), min(ys), max(xs), max(ys)), line


def plan_patches(
    lanes: Dict[int, Lane],
    edges: Dict[int, RoadEdge],
    keep_out_rects: Sequence[Rect],
    seed: int,
) -> List[Patch]:
    """The grass patches of every curb run, deterministic from ``seed``."""
    rng = np.random.Generator(np.random.PCG64([seed, 0x91A7]))
    patches: List[Patch] = []
    for run in edge_runs(lanes, edges):
        s = END_MARGIN_METERS + 1.0 + float(rng.uniform(0.0, PATCH_GAP_M[1]))
        while True:
            length = float(rng.uniform(*PATCH_LENGTH_M))
            if s + length > run.length - END_MARGIN_METERS - 1.0:
                break
            rect, line = _patch_at(run, s, length)
            # Drawn before the keep-out test, so a keep-out only removes patches and never
            # changes the layout of the others.
            style = str(rng.choice(STYLES, p=STYLE_WEIGHTS))
            if not any(rect_gap(rect, other) < KEEP_OUT_BUFFER_M for other in keep_out_rects):
                patches.append(Patch(rect, style, line))
            s += length + float(rng.uniform(*PATCH_GAP_M))
    return patches


def grass_mesh(patches: Sequence[Patch]) -> List[Mesh]:
    """All patches as one upward-facing grass mesh (empty without patches)."""
    if not patches:
        return []
    vertices, triangles, uvs = [], [], []
    for index, patch in enumerate(patches):
        x_min, y_min, x_max, y_max = patch.rect
        base = 4 * index
        vertices += [
            [x_min, y_min, GRASS_Z_M],
            [x_max, y_min, GRASS_Z_M],
            [x_max, y_max, GRASS_Z_M],
            [x_min, y_max, GRASS_Z_M],
        ]
        uvs += [
            [x_min / GRASS_UV_TILE_M, y_min / GRASS_UV_TILE_M],
            [x_max / GRASS_UV_TILE_M, y_min / GRASS_UV_TILE_M],
            [x_max / GRASS_UV_TILE_M, y_max / GRASS_UV_TILE_M],
            [x_min / GRASS_UV_TILE_M, y_max / GRASS_UV_TILE_M],
        ]
        triangles += [base, base + 1, base + 2, base, base + 2, base + 3]
    return [
        Mesh(
            vertices=np.array(vertices, dtype=np.float64),
            triangles=np.array(triangles, dtype=np.int64),
            uvs=np.array(uvs, dtype=np.float64),
            material=GRASS_MATERIAL,
            normals=np.tile(np.array([0.0, 0.0, 1.0]), (len(vertices), 1)),
        )
    ]


def _shrub_spots(
    patch: Patch, rng: np.random.Generator, hedge_spacing: float = HEDGE_SPACING_M
) -> List[Tuple[float, float]]:
    """Where a patch's shrubs or hedge lumps stand along its centre line."""
    if patch.style == "lawn":
        return []
    (x0, y0), (x1, y1) = patch.centre_line
    length = float(np.hypot(x1 - x0, y1 - y0))
    spots = []
    position = 0.8
    while position < length - 0.8:
        if patch.style == "hedge" or rng.random() < SHRUB_PROBABILITY:
            fraction = position / length
            spots.append((x0 + (x1 - x0) * fraction, y0 + (y1 - y0) * fraction))
        position += (
            hedge_spacing if patch.style == "hedge" else float(rng.uniform(*SHRUB_SPACING_M))
        )
    return spots


def shrub_meshes(patches: Sequence[Patch], season: Season, seed: int) -> List[Mesh]:
    """Shrubs and hedges of the patches as one foliage mesh; empty in winter or without any."""
    material = FOLIAGE_MATERIALS.get(season)
    if material is None:
        return []
    rng = np.random.Generator(np.random.PCG64([seed, 0x5B2B]))
    parts: List[MeshPart] = []
    for patch in patches:
        for x, y in _shrub_spots(patch, rng):
            height = float(
                rng.uniform(*(HEDGE_HEIGHT_M if patch.style == "hedge" else SHRUB_HEIGHT_M))
            )
            radius = float(rng.uniform(*SHRUB_RADIUS_M))
            centre = np.array([x, y, GRASS_Z_M + 0.5 * height])
            parts.append(
                canopy_cards(centre, (radius, 0.5 * height), SHRUB_CARDS, rng, SHRUB_CARD_SIZE_M)
            )
    if not parts:
        return []
    merged = merge_parts(parts)
    return [
        Mesh(
            vertices=merged.vertices,
            triangles=merged.triangles,
            uvs=merged.uvs,
            material=material,
            normals=merged.normals,
            colors=merged.colors,
        )
    ]


def shrub_pieces(patches: Sequence[Patch], season: Season, seed: int) -> List[FacadePiece]:
    """Scanned shrubs and hedges of the patches (``photoreal_trees.py``), evergreen in every season.

    Shrub patches get searsia bushes, hedge patches a row of columnar othonna, lawn patches
    sometimes a fern."""
    rng = np.random.Generator(np.random.PCG64([seed, 0x5B2C]))
    pieces: List[FacadePiece] = []
    for patch in patches:
        if patch.style == "lawn":
            if rng.random() < FERN_PROBABILITY:
                (x0, y0), (x1, y1) = patch.centre_line
                fraction = float(rng.uniform(0.2, 0.8))
                spot = (x0 + (x1 - x0) * fraction, y0 + (y1 - y0) * fraction)
                pieces.append(plant_piece(SHRUBS["fern_02"], spot, season, rng))
            continue
        model = SHRUBS["othonna_cerarioides" if patch.style == "hedge" else "searsia_lucida"]
        for spot in _shrub_spots(patch, rng, PLANT_HEDGE_SPACING_M):
            pieces.append(plant_piece(model, spot, season, rng))
    return pieces


def planting_meshes(
    lanes: Dict[int, Lane],
    edges: Dict[int, RoadEdge],
    keep_out_rects: Sequence[Rect],
    season: Season,
    seed: int,
) -> List[Mesh]:
    """The scene's grass patches and, in leafy seasons, their shrubs and hedges."""
    patches = plan_patches(lanes, edges, keep_out_rects, seed)
    return grass_mesh(patches) + shrub_meshes(patches, season, seed)
