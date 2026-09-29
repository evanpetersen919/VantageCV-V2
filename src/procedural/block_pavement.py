"""Sidewalk-height paving that fills the inside of every city block.

The real curb and sidewalk pieces (``road_edge_kit.py``) only cover a 3m
band along each road, and the buildings are set back from the road by a
random distance beyond that. Without a fill, the ground between the
sidewalk and a building's front sits at road height, so the raised
sidewalk visibly "drops back down" before the building. Real streets run
flush from the curb to the building front.

Each block (a rectangular grid cell, see ``identify_city_blocks``) is
bounded by road centerlines, so the pavement's outer edge is the block
inset by the road's half-width (``num_lanes * LANE_WIDTH_METERS``), which
is exactly where the curb line runs. That inset rectangle is filled with
one quad at sidewalk height. The quad is a hair below the sidewalk slabs'
top so the real slabs stay visible on top of it, and it also fills the
gaps at intersection corners where the per-edge sidewalks stop.

Each block gets one of 6 migrated sidewalk material variants (``pavement`` ..
``pavement_5``, real City Sample content), chosen deterministically by the block's
position in ``identify_city_blocks``' own ordering, instead of every block sharing the
one fixed material.
"""

from typing import Dict, List

from src.procedural.building_placement import identify_city_blocks
from src.procedural.lane_topology import LANE_WIDTH_METERS
from src.procedural.mesh_factory import Mesh, flat_quad_mesh
from src.procedural.road_network import RoadEdge, RoadNode

# Top of the fill in metres: just under the sidewalk slabs' top (about
# 10.8cm above the road crown, see road_edge_kit.py) so slabs never
# z-fight with it.
BLOCK_PAVEMENT_Z_METERS = 0.10

# Metres of world space per texture repeat.
BLOCK_PAVEMENT_UV_TILE_METERS = 3.0

# Number of migrated sidewalk materials (pavement, pavement_1 .. pavement_5) -- every
# block used the same single sidewalk material regardless of scenario or position, an
# easy shortcut a detector could latch onto that real streets (dozens of real sidewalk
# finishes) don't offer. Mirrors roofs.py's identical building_id % ROOF_MATERIAL_COUNT
# pattern, using each block's position in identify_city_blocks' own deterministic
# ordering as its id.
PAVEMENT_MATERIAL_COUNT = 6

# Every material tag build_block_pavement_meshes can emit, in variant order.
PAVEMENT_MATERIAL_TAGS = (
    "pavement",
    "pavement_1",
    "pavement_2",
    "pavement_3",
    "pavement_4",
    "pavement_5",
)


def _pavement_material(block_index: int) -> str:
    """The migrated sidewalk material tag for the ``block_index``-th city block."""
    variant = block_index % PAVEMENT_MATERIAL_COUNT
    return "pavement" if variant == 0 else f"pavement_{variant}"


def build_block_pavement_meshes(
    nodes: Dict[int, RoadNode], edges: Dict[int, RoadEdge]
) -> List[Mesh]:
    """One upward-facing quad per city block, inset from the block by the
    roads' pavement half-width, tagged with the ``"pavement"`` material."""
    if not edges:
        return []
    inset = max(edge.num_lanes for edge in edges.values()) * LANE_WIDTH_METERS

    meshes: List[Mesh] = []
    for block_index, block in enumerate(identify_city_blocks(nodes, edges)):
        x_min, y_min = block.min(axis=0) + inset
        x_max, y_max = block.max(axis=0) - inset
        if x_max <= x_min or y_max <= y_min:
            continue  # the roads' pavement leaves nothing of this block
        meshes.append(
            flat_quad_mesh(
                x_min,
                y_min,
                x_max,
                y_max,
                BLOCK_PAVEMENT_Z_METERS,
                BLOCK_PAVEMENT_UV_TILE_METERS,
                _pavement_material(block_index),
            )
        )
    return meshes
