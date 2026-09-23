"""Real curved sidewalk/curb corners at every intersection, replacing
``block_pavement.py``'s flat rectangular corner fill with Epic's actual
rounded-corner kit pieces.

**Real assets** (already migrated into ``VantageCV_UE5``, measured live via
``GetStaticMeshBounds``): ``Kit_Sidewalk_A``'s ``SM_Sidewalk_A_Corner_01``
(the curved pavement piece) + ``SM_Sidewalk_A_Corner_Fill_01`` (a flat
companion that completes the paved area the curve's own bbox doesn't cover),
and ``Kit_Small_Curb_A``'s ``SM_Small_Curb_A_Corner_01`` (the matching curb,
same footprint). Confirmed live: placing ``Corner_01`` + ``Corner_Fill_01``
at the identical position/rotation produces one correct, seamless, fully
paved rounded corner. All three pieces share an 8m x 8m bounding footprint
(``GetStaticMeshBounds``: origin (400, 400)cm, extent (400, 400)cm -> local
(0,0)-(800,800)cm), pivoted at one corner of that square -- the theoretical
SHARP corner before rounding, not the curve itself.

**Rotation mapping** (derived, not guessed, from two independent sources
that agree exactly): (1) a live, world-axis-aligned test placement in a
prior session established that at ``rotation_rad = 0`` the paved bulk
extends from the pivot toward python/world ``(+x, +y)``; (2) the same
meters->centimeters + Y-flip + yaw-negation convention
``ProceduralScenarioLoader.cpp``'s ``ParseAssetData``/``ApplyCoordinateConvention``
applies to every asset (already independently confirmed correct for the
curb/sidewalk pieces in ``road_edge_kit.py``: local +X -> python
``(cos r, sin r)``, local +Y -> python ``(sin r, -cos r)``) gives the
general rule for how the ``(+x, +y)``-bulk direction rotates: at rotation
``r``, the bulk points toward python ``(cos r - sin r, sin r + cos r)``.
Solving this for each of a block's 4 corners' own real interior direction
(e.g. the SW corner's block interior is toward ``(+x, +y)``) yields exact
solutions, not approximations, for all 4 corners simultaneously:

- SW corner (interior toward ``(+x, +y)``): ``rotation_rad = 0``
- SE corner (interior toward ``(-x, +y)``): ``rotation_rad = +pi/2``
- NE corner (interior toward ``(-x, -y)``): ``rotation_rad = pi``
- NW corner (interior toward ``(+x, -y)``): ``rotation_rad = -pi/2``

Live-verified (2026-09-22): placed all 4 rotations at a real 20m x 20m test
block's inset corners, cross-checked each piece's actual in-engine position
via ``DebugListActorsWithMesh`` against the intended python coordinates
(exact match), and confirmed via an oblique screenshot that the 4 pieces
occupy the expected relative screen positions for those world coordinates.
Then verified in a real, full generated city scenario (299 buildings, 16
blocks) in the live editor: the curb piece visibly faced the wrong way
(into the road instead of hugging the sidewalk edge) despite sharing the
sidewalk corner's exact footprint -- fixed with ``CURB_CORNER_ROTATION_
OFFSET_RAD`` (see its own comment).

**Why no notch is needed in ``block_pavement.py``**: that module's flat
fill sits deliberately a hair BELOW the real sidewalk slabs' top (its own
docstring: "the real slabs stay visible on top of it"). These corner
pieces are placed at the same height as the real sidewalk slabs
(``road_edge_kit.DEFAULT_ROAD_EDGE_KIT.sidewalk_z_m`` / ``curb_z_m``), so
they simply render on top of the flat filler in the same way the straight
slabs already do -- no overlap/z-fight avoidance logic needed.

**Why the straight runs need trimming**: since ``UNIFORM_LANE_COUNT`` means
every road in a scenario has the same width (see
``KNOWN_GAPS_AND_ISSUES.md``), a block's inset corner (this module's
placement point) is always exactly the same point ``road_edge_kit.py``'s
per-edge runs already stop at (both trace back to the same node
clearance). Since this corner piece's footprint reaches 8m into the block
interior along both edges from that point, the straight curb/sidewalk runs
must stop ``CURVED_CORNER_SIZE_METERS`` short of it or they'd overlap the
curve -- see ``road_edge_kit.edge_runs``'s own trim.
"""

import math
from typing import Dict, List, Tuple

import numpy as np

from src.procedural.building_facade import FacadePiece
from src.procedural.building_placement import identify_city_blocks
from src.procedural.lane_topology import LANE_WIDTH_METERS
from src.procedural.road_edge_kit import DEFAULT_ROAD_EDGE_KIT
from src.procedural.road_network import RoadEdge, RoadNode

_SIDEWALK_DIR = "/Game/Road/Kit_Sidewalk_A/Mesh/"
_CURB_DIR = "/Game/Road/Kit_Small_Curb_A/Mesh/"

CORNER_ASSET_PATH = _SIDEWALK_DIR + "SM_Sidewalk_A_Corner_01"
CORNER_FILL_ASSET_PATH = _SIDEWALK_DIR + "SM_Sidewalk_A_Corner_Fill_01"
CURB_CORNER_ASSET_PATH = _CURB_DIR + "SM_Small_Curb_A_Corner_01"

# A real, live-observed authoring-convention mismatch (not guessed, same
# class of fix as the traffic-light mast arm and building corner pieces
# needing their own +pi offsets elsewhere in this project): despite
# sharing the sidewalk corner's exact 8m x 8m footprint/pivot, the curb
# kit's own corner mesh is authored facing the opposite way, so it needs
# an extra half-turn on top of the sidewalk/fill pieces' own rotation to
# actually hug the sidewalk edge instead of facing into the road.
CURB_CORNER_ROTATION_OFFSET_RAD = math.pi

# rotation_rad for each of a block's 4 corners, keyed the same way
# block_pavement.py already names them (SW/SE/NE/NW = min/max x, min/max
# y) -- see module docstring for the derivation.
_CORNER_ROTATIONS: Tuple[Tuple[str, float], ...] = (
    ("SW", 0.0),
    ("SE", math.pi / 2.0),
    ("NE", math.pi),
    ("NW", -math.pi / 2.0),
)


def _corner_offset(name: str, inset: float) -> Tuple[float, float]:
    """The (dx, dy) offset from a block's (x_min, y_min) to the named
    corner, inset from the block's own bounds by the road's pavement
    half-width -- identical math to ``block_pavement.py``'s own inset
    rectangle, so the two always agree exactly."""
    dx = inset if name in ("SW", "NW") else -inset
    dy = inset if name in ("SW", "SE") else -inset
    return dx, dy


def build_curved_corner_pieces(  # pylint: disable=too-many-locals
    nodes: Dict[int, RoadNode], edges: Dict[int, RoadEdge]
) -> List[FacadePiece]:
    """Real curved sidewalk + curb pieces at each of every city block's 4
    real inset corners (see module docstring)."""
    if not edges:
        return []
    inset = max(edge.num_lanes for edge in edges.values()) * LANE_WIDTH_METERS
    kit = DEFAULT_ROAD_EDGE_KIT

    pieces: List[FacadePiece] = []
    for block in identify_city_blocks(nodes, edges):
        x_min, y_min = block.min(axis=0)
        x_max, y_max = block.max(axis=0)
        corners = {
            "SW": (x_min, y_min),
            "SE": (x_max, y_min),
            "NE": (x_max, y_max),
            "NW": (x_min, y_max),
        }
        for name, rotation_rad in _CORNER_ROTATIONS:
            base_x, base_y = corners[name]
            dx, dy = _corner_offset(name, inset)
            x, y = base_x + dx, base_y + dy
            pieces.append(
                FacadePiece(
                    asset_path=CORNER_ASSET_PATH,
                    position=np.array([x, y, kit.sidewalk_z_m]),
                    rotation_rad=rotation_rad,
                )
            )
            pieces.append(
                FacadePiece(
                    asset_path=CORNER_FILL_ASSET_PATH,
                    position=np.array([x, y, kit.sidewalk_z_m]),
                    rotation_rad=rotation_rad,
                )
            )
            pieces.append(
                FacadePiece(
                    asset_path=CURB_CORNER_ASSET_PATH,
                    position=np.array([x, y, kit.curb_z_m]),
                    rotation_rad=rotation_rad + CURB_CORNER_ROTATION_OFFSET_RAD,
                )
            )
    return pieces
