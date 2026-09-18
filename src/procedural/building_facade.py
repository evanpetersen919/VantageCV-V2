"""Tile a building's quantized footprint with real City Sample modular
building-kit pieces (wall/corner), instead of a flat procedural box.

Real, working proof-of-concept confirmed live in UE5 before this module was
written (see KNOWN_GAPS_AND_ISSUES.md): 4 wall pieces tiled via pure
position math (no UE5 PCG, no Houdini) produced a seamless real facade;
corner pieces placed at a rectangle's 4 corners with a 90-degrees-per-corner
rotation scheme showed correct L-shaped corner geometry. A full generated
building (multiple floors, real footprint) was then verified live too: real
windows/concrete trim/floor slabs tiling correctly across an entire
multi-story facade. The rotation/tiling-direction formula below is derived
from that confirmed behavior: at ``rotation_rad=0`` a wall piece's own
tiling direction (pivot at one width-edge, extending toward the other)
empirically advances along python ``-y`` once converted through
``ProceduralScenarioLoader.cpp``'s ``ApplyCoordinateConvention``
(``FVector(X, -Y, Z) * 100``) -- confirmed via a live screenshot, not
assumed. Rotating that advance direction by the standard CCW rotation
matrix already used elsewhere in this codebase (see
``mesh_factory._oriented_box_vertices``) for each 90-degree corner step
reproduces the exact corner rotation scheme already confirmed live.

Deliberately NOT tiled here (real, accepted v1 gap, not silently dropped):
``BuildingKit.entrance_asset_path``. The same live verification pass found
that specific mesh renders with a visibly wrong material (a flat gold/tan
color, not the glass/concrete finish every wall/corner piece correctly
shows) -- confirmed isolated to that one asset by spawning it alone, and
confirmed not a logged material-resolution failure (no "Missing Material"/
"failed to load" warning), so the real cause (a genuine unfinished/
construction-state asset variant, vs. an incomplete migration) isn't
diagnosed yet. Shipping a visibly broken entrance looked worse than a
building with no distinct entrance at all, so this module never selects
``entrance_asset_path`` -- see KNOWN_GAPS_AND_ISSUES.md for the real path
to revisit this once the material issue is actually diagnosed.

Building.aabb/.height must already be quantized to exact
``FACADE_WALL_MODULE_METERS``/``FACADE_CORNER_MODULE_METERS``/
``FACADE_FLOOR_HEIGHT_METERS`` multiples (BuildingPlacementGenerator does
this at generation time -- see that module) for the tiling below to close
without a gap or overlap.
"""

import math
from dataclasses import dataclass
from typing import List

import numpy as np
import numpy.typing as npt

from src.procedural.building_placement import (
    FACADE_CORNER_MODULE_METERS,
    FACADE_FLOOR_HEIGHT_METERS,
    FACADE_WALL_MODULE_METERS,
    Building,
)
from src.procedural.city_sample_assets import BuildingKit

# Perimeter traversal order, each a (start_corner, edge_direction) pair in
# python (x, y) space -- edge_direction is also each edge's own wall/corner
# rotation's tiling-advance direction (see module docstring). Matches the
# exact scheme already confirmed live: corner i gets rotation_rad = i *
# (pi / 2); a wall/entrance piece placed with that same rotation tiles
# along edge_direction.
_QUARTER_TURN_RAD = math.pi / 2.0


def _corner_points(building: Building) -> List[npt.NDArray[np.float64]]:
    """The 4 real footprint corners in perimeter-traversal order
    (top-left -> bottom-left -> bottom-right -> top-right), matching the
    edge directions in ``_EDGE_DIRECTIONS``."""
    x_min, y_min, x_max, y_max = building.aabb
    return [
        np.array([x_min, y_max]),
        np.array([x_min, y_min]),
        np.array([x_max, y_min]),
        np.array([x_max, y_max]),
    ]


_EDGE_DIRECTIONS: List[npt.NDArray[np.float64]] = [
    np.array([0.0, -1.0]),
    np.array([1.0, 0.0]),
    np.array([0.0, 1.0]),
    np.array([-1.0, 0.0]),
]


@dataclass(eq=False)
class FacadePiece:
    """One real building-kit static mesh's placement: asset reference +
    transform, matching the same asset-reference-plus-transform shape
    ``Vehicle`` already carries (see ``scenario_serializer.py``'s
    ``"static_asset"`` entries)."""

    asset_path: str
    position: npt.NDArray[np.float64]  # [x, y, z] meters
    rotation_rad: float


def generate_building_facade_pieces(  # pylint: disable=too-many-locals
    building: Building, kit: BuildingKit
) -> List[FacadePiece]:
    """Tile ``building``'s quantized footprint, per floor, with ``kit``'s
    real wall/corner pieces (``kit.entrance_asset_path`` is deliberately
    not used yet -- see this module's own docstring).

    Deterministic and RNG-free: footprint/height already fully determine
    every piece's position once quantized (see ``building_placement.py``).
    Every floor reuses the same ``kit`` -- a real, accepted v1 limitation
    since only one City Sample floor style is migrated so far (see this
    module's own docstring and KNOWN_GAPS_AND_ISSUES.md).

    Parameters
    ----------
    building : Building
        Must already have quantized width/depth/height (true for every
        Building produced by BuildingPlacementGenerator).
    kit : BuildingKit
        Real asset paths, dimensioned to match
        FACADE_WALL_MODULE_METERS/FACADE_CORNER_MODULE_METERS exactly.

    Returns
    -------
    List[FacadePiece]
    """
    corners = _corner_points(building)
    num_floors = max(1, round(building.height / FACADE_FLOOR_HEIGHT_METERS))

    pieces: List[FacadePiece] = []
    for floor_index in range(num_floors):
        z = floor_index * FACADE_FLOOR_HEIGHT_METERS

        for edge_index in range(4):
            start = corners[edge_index]
            direction = _EDGE_DIRECTIONS[edge_index]
            rotation_rad = edge_index * _QUARTER_TURN_RAD

            pieces.append(
                FacadePiece(
                    asset_path=kit.corner_asset_path,
                    position=np.array([start[0], start[1], z]),
                    rotation_rad=rotation_rad,
                )
            )

            edge_vector = corners[(edge_index + 1) % 4] - start
            edge_length = float(np.linalg.norm(edge_vector))
            usable_length = edge_length - 2.0 * FACADE_CORNER_MODULE_METERS
            wall_count = max(0, round(usable_length / FACADE_WALL_MODULE_METERS))

            for wall_index in range(wall_count):
                offset = FACADE_CORNER_MODULE_METERS + wall_index * FACADE_WALL_MODULE_METERS
                wall_position = start + direction * offset
                pieces.append(
                    FacadePiece(
                        asset_path=kit.wall_asset_path,
                        position=np.array([wall_position[0], wall_position[1], z]),
                        rotation_rad=rotation_rad,
                    )
                )

    return pieces
