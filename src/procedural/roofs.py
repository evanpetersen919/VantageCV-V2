"""Flat roof slabs and rooftop equipment that finish every building top.

City Sample has no roof mesh: Epic's generator extrudes a thin roof plane
at the top of the last floor (measured from its real roof-prop points: the
plane sits within 5cm of the top of the last floor, and a roof-cap kit's
parapet rises around it) and gives it a rooftop material, picked per
building by ``Building_ID % 6`` from Bitumen, DirtyConcreteTiles,
PebbleDash, PebbleDashLines, TarPebbles and RoofTile. This builds the same
thing: one upward-facing quad per building at the top of its last floor,
inset from the walls by the family's BDF ``Roof_Inset``, with one of the
four migrated ``MI_Rooftop_*`` materials chosen by ``building_id % 4``
(tags ``roof_0`` .. ``roof_3``).

Rooftop equipment (AC units, vents, exhaust stacks: real City Sample static
meshes, sized by measurement) is scattered over the slab. Epic places whole
prop Blueprints from a 1.2GB rooftop kit whose internals were not read, so
the count and layout here are INFERRED, not measured: roughly one item per
60m^2 of roof (at most six), at least 3m apart and 1.5m clear of the edge,
with a random 90-degree yaw, all deterministic per building.
"""

from typing import List, Optional, Tuple

import numpy as np
import numpy.typing as npt

from src.procedural.building_facade import FacadePiece
from src.procedural.building_placement import Building
from src.procedural.city_sample_assets import BUILDING_STYLES
from src.procedural.mesh_factory import Mesh, flat_quad_mesh

# Epic's roof plane sits this far above the top of the last floor.
ROOF_PLANE_LIFT_METERS = 0.05

# Metres of world space per texture repeat.
ROOF_UV_TILE_METERS = 3.0

# Number of migrated roof materials (roof_0 .. roof_3).
ROOF_MATERIAL_COUNT = 4

# Rooftop equipment: (asset path, half of the footprint's larger side in m,
# relative weight). Sizes were measured in the engine (AC unit 0.92x0.96m,
# vent 3.41x2.19m, exhaust 1.0x1.16m).
ROOF_PROPS: Tuple[Tuple[str, float, float], ...] = (
    ("/Game/Prop/Kit_roof_AC_Unit_B/Mesh/SM_roof_AC_Unit_B_01_N1", 0.5, 0.5),
    ("/Game/Prop/Kit_Roof_Vent_RR/Mesh/SM_RooftopVent_N1", 1.7, 0.2),
    ("/Game/Prop/Kit_roof_exhaust_RR/Mesh/SM_roof_exhaust_a_N1", 0.6, 0.3),
)

ROOF_EDGE_CLEARANCE_METERS = 1.5
ROOF_PROP_MIN_SPACING_METERS = 3.0
SQUARE_METERS_PER_ROOF_PROP = 60.0
MAX_ROOF_PROPS = 6
_PLACEMENT_TRIES = 30


def _roof_plane_z(building: Building) -> float:
    """Height of this building's roof plane."""
    style = BUILDING_STYLES[building.style_name]
    floor_count = style.floor_count_for_height(building.height)
    return style.roof_plane_height(floor_count) + ROOF_PLANE_LIFT_METERS


def _roof_rectangle(building: Building) -> Tuple[float, float, float, float]:
    """The roof slab's (x_min, y_min, x_max, y_max), inset from the walls."""
    inset = BUILDING_STYLES[building.style_name].roof_inset_m
    x_min, y_min, x_max, y_max = building.aabb
    return x_min + inset, y_min + inset, x_max - inset, y_max - inset


def build_roof_meshes(buildings: List[Building]) -> List[Mesh]:
    """One roof quad per building, at the top of its last floor, with a
    rooftop material chosen by the building's id."""
    meshes: List[Mesh] = []
    for building in buildings:
        x_min, y_min, x_max, y_max = _roof_rectangle(building)
        if x_max <= x_min or y_max <= y_min:
            continue
        material = f"roof_{building.building_id % ROOF_MATERIAL_COUNT}"
        meshes.append(
            flat_quad_mesh(
                x_min, y_min, x_max, y_max, _roof_plane_z(building), ROOF_UV_TILE_METERS, material
            )
        )
    return meshes


def _scatter_points(
    rng: np.random.Generator,
    bounds: Tuple[float, float, float, float],
    half_size: float,
    placed: List[npt.NDArray[np.float64]],
) -> Optional[npt.NDArray[np.float64]]:
    """A random spot on the roof, clear of the edge and of ``placed`` items,
    or ``None`` if none was found."""
    x_min, y_min, x_max, y_max = bounds
    margin = ROOF_EDGE_CLEARANCE_METERS + half_size
    if x_max - x_min <= 2 * margin or y_max - y_min <= 2 * margin:
        return None
    for _ in range(_PLACEMENT_TRIES):
        point = np.array(
            [
                rng.uniform(x_min + margin, x_max - margin),
                rng.uniform(y_min + margin, y_max - margin),
            ]
        )
        if all(
            float(np.linalg.norm(point - other)) >= ROOF_PROP_MIN_SPACING_METERS for other in placed
        ):
            return point
    return None


def generate_roof_prop_pieces(buildings: List[Building]) -> List[FacadePiece]:
    """Rooftop equipment on every building's slab (see the module docstring
    for what is measured and what is inferred). Deterministic per building."""
    weights = np.array([weight for _, _, weight in ROOF_PROPS], dtype=np.float64)
    weights /= weights.sum()
    pieces: List[FacadePiece] = []
    for building in buildings:
        bounds = _roof_rectangle(building)
        area = (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])
        count = min(MAX_ROOF_PROPS, int(area / SQUARE_METERS_PER_ROOF_PROP))
        rng = np.random.Generator(
            np.random.PCG64(
                [building.building_id, int(building.width * 100), int(building.depth * 100), 0x400F]
            )
        )
        z = _roof_plane_z(building)
        placed: List[npt.NDArray[np.float64]] = []
        for _ in range(max(count, 0)):
            path, half_size, _weight = ROOF_PROPS[int(rng.choice(len(ROOF_PROPS), p=weights))]
            point = _scatter_points(rng, bounds, half_size, placed)
            if point is None:
                continue
            placed.append(point)
            yaw = float(rng.integers(4)) * np.pi / 2.0
            pieces.append(FacadePiece(path, np.array([point[0], point[1], z]), yaw))
    return pieces
