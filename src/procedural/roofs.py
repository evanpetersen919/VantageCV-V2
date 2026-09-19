"""Flat roof slabs that close the open tops of every building.

City Sample has no roof mesh: Epic's generator extrudes a thin roof plane
at the top of the last floor (measured from its real roof-prop points: the
plane sits within 5cm of the top of the last floor, and a roof-cap kit's
parapet rises around it) and gives it a bitumen/pebble-tar material. This
builds the same thing: one upward-facing quad per building at the top of
its last floor, inset from the walls by the family's BDF ``Roof_Inset``.

The material is the ``"roof"`` tag. Epic's own roof materials
(``MI_Rooftop_*``, 71MB+ of 8K textures) are not migrated, so it maps to
the already-migrated matte asphalt, which reads as tar roofing.
"""

from typing import List

from src.procedural.building_placement import Building
from src.procedural.city_sample_assets import BUILDING_STYLES
from src.procedural.mesh_factory import Mesh, flat_quad_mesh

# Epic's roof plane sits this far above the top of the last floor.
ROOF_PLANE_LIFT_METERS = 0.05

# Metres of world space per texture repeat.
ROOF_UV_TILE_METERS = 3.0


def build_roof_meshes(buildings: List[Building]) -> List[Mesh]:
    """One roof quad per building, at the top of its last floor."""
    meshes: List[Mesh] = []
    for building in buildings:
        style = BUILDING_STYLES[building.style_name]
        floor_count = style.floor_count_for_height(building.height)
        z = style.roof_plane_height(floor_count) + ROOF_PLANE_LIFT_METERS

        x_min, y_min, x_max, y_max = building.aabb
        inset = style.roof_inset_m
        x_min, y_min, x_max, y_max = x_min + inset, y_min + inset, x_max - inset, y_max - inset
        if x_max <= x_min or y_max <= y_min:
            continue

        meshes.append(flat_quad_mesh(x_min, y_min, x_max, y_max, z, ROOF_UV_TILE_METERS, "roof"))
    return meshes
