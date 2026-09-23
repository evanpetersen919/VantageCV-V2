"""Real City Sample curbs and sidewalks along the outer edge of every road.

Each directed road edge already has its outermost lane's outer boundary,
trimmed short of the intersections (``Lane.left_boundary`` of the lane with
the highest ``lane_index``: offset ``num_lanes * LANE_WIDTH_METERS`` to the
right of the centerline). That line IS the pavement's outer edge and the
curb line. Since each edge's lanes occupy only its own right-hand half of
the road, doing this for every directed edge covers both sides of every
road.

Pieces and numbers (all measured live in the engine, then hand-placed and
screenshot-verified on a straight road before being coded here):

- **Curb**: Megascans ``Modular_Curb_5_M_*``, 5.0m long, placed at scale
  ``(sx, -0.75, 0.75)`` exactly as Epic's own generator places every curb
  (a mirror plus a shrink; measured from 14,551 real placements). The
  mirrored profile puts the curb on the road side of the line.
- **Sidewalk**: ``SM_Sidewalk_6_3_A..E``, 6.0m x 3.0m, pivot at a corner,
  extending 3.0m outward from the curb line (real ``sidewalk_width`` is 3.0m
  in Epic's Houdini config).
- **Stretch**: a run is tiled with ``round(length / tile)`` pieces, each
  stretched along the run by the same factor so the run is filled exactly
  (Epic stretches its last piece the same way; real sidewalk stretch is
  0.75-1.0, real curb stretch 1.0-1.2).
- **Heights** (z, meters, relative to our flat z=0 road surface): the
  sidewalk top sits about 10.8cm and the curb top about 11cm above the
  road's crown, from Epic's own placement heights (sidewalk top 73.4cm vs
  road crown 62.6cm).

Mesh-local conventions (verified live): in the python frame a piece at
``rotation_rad = r`` has its local X along ``(cos r, sin r)`` and its local
Y along ``(sin r, -cos r)``. A run therefore walks along ``u`` where
``u`` is the outward normal rotated +90 degrees, with ``r = atan2(u)``.

Not done (a deliberate first stage): intersection corners get no sidewalk
pieces (each road's sidewalks simply stop where its lanes stop), and our
lane geometry (14m of pavement per road) is not yet snapped to Epic's real
19/27/37m road classes.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import numpy.typing as npt

from src.procedural.building_facade import FacadePiece
from src.procedural.lane_topology import SIDEWALK_WIDTH_METERS, Lane
from src.procedural.math_utils import compute_perpendicular
from src.procedural.road_network import RoadEdge

_CURB_DIR = "/Game/Megascans/3D_Assets/Modular_Curb_5_M_"

# The real, measured top-of-sidewalk height above the flat z=0 road
# surface (see this module's own docstring: "sidewalk top sits about
# 10.8cm above the road's crown"). Exported so anything that needs to
# stand something ON the real sidewalk surface (e.g. pedestrians) uses
# the same real number instead of a fresh guess -- distinct from
# ``RoadEdgeKit.sidewalk_z_m``, which is that mesh piece's own
# pivot-to-top offset, not the walking-surface height itself.
SIDEWALK_TOP_HEIGHT_METERS = 0.108


@dataclass(frozen=True)
class RoadEdgeKit:  # pylint: disable=too-many-instance-attributes
    """Asset paths and measured dimensions for the curb and sidewalk."""

    curb_asset_paths: Tuple[str, ...]
    sidewalk_asset_paths: Tuple[str, ...]
    curb_length_m: float = 5.0
    sidewalk_length_m: float = 6.0
    sidewalk_width_m: float = SIDEWALK_WIDTH_METERS
    curb_scale_yz: Tuple[float, float] = (-0.75, 0.75)
    curb_z_m: float = -0.036
    sidewalk_z_m: float = -0.096


DEFAULT_ROAD_EDGE_KIT = RoadEdgeKit(
    curb_asset_paths=(
        _CURB_DIR + "00/Modular_Curb_5_M_LOD0_vcflbc0dw",
        _CURB_DIR + "01/Modular_Curb_5_M_LOD0_vcjmecpdw",
        _CURB_DIR + "02/Modular_Curb_5_M_LOD0_vccgfazdw",
    ),
    sidewalk_asset_paths=tuple(
        f"/Game/Road/Kit_Sidewalk_A/Mesh/SM_Sidewalk_6_3_{v}" for v in "ABCDE"
    ),
)

# Runs shorter than this get no pieces (a stub between two intersections).
MIN_RUN_LENGTH_METERS = 1.0


def _outer_boundaries(lanes: Dict[int, Lane]) -> Dict[int, npt.NDArray[np.float64]]:
    """Per edge, the outer boundary of its outermost lane (the pavement's
    outer edge / curb line), as a 2-point polyline."""
    outermost: Dict[int, Lane] = {}
    for lane in lanes.values():
        best = outermost.get(lane.edge_id)
        if best is None or lane.lane_index > best.lane_index:
            outermost[lane.edge_id] = lane
    return {edge_id: lane.left_boundary for edge_id, lane in outermost.items()}


@dataclass(frozen=True)
class EdgeRun:
    """One straight run along a directed road edge's outer pavement edge
    (the curb line): where it starts, which way it runs, how long it is,
    and the outward direction (away from the road, onto the sidewalk)."""

    edge_id: int
    start: npt.NDArray[np.float64]
    run_direction: npt.NDArray[np.float64]
    outward: npt.NDArray[np.float64]
    length: float

    @property
    def rotation_rad(self) -> float:
        """Rotation of a piece whose local X runs along the road."""
        return math.atan2(float(self.run_direction[1]), float(self.run_direction[0]))


def edge_runs(lanes: Dict[int, Lane], edges: Dict[int, RoadEdge]) -> List[EdgeRun]:
    """Every directed edge's curb-line run, in edge-id order. Each directed
    edge's lanes occupy only its own right-hand half of the road, so these
    cover both sides of every road."""
    runs: List[EdgeRun] = []
    for edge_id, boundary in sorted(_outer_boundaries(lanes).items()):
        edge = edges[edge_id]
        direction = edge.centerline[-1] - edge.centerline[0]
        if float(np.linalg.norm(direction)) < 1e-9:
            continue
        outward = compute_perpendicular(direction)
        run_direction = np.array([-outward[1], outward[0]])

        first, last = boundary[0], boundary[-1]
        length = float(np.linalg.norm(last - first))
        if length < MIN_RUN_LENGTH_METERS:
            continue
        start = first if float(np.dot(last - first, run_direction)) >= 0.0 else last
        runs.append(EdgeRun(edge_id, start, run_direction, outward, length))
    return runs


def _run_pieces(  # pylint: disable=too-many-arguments,too-many-locals
    start: npt.NDArray[np.float64],
    run_direction: npt.NDArray[np.float64],
    length: float,
    tile_length: float,
    asset_path: str,
    z: float,
    scale_yz: Tuple[float, float],
) -> List[FacadePiece]:
    """Tile one straight run with ``round(length / tile_length)`` pieces,
    each stretched by the same factor so the run is filled exactly."""
    count = max(1, round(length / tile_length))
    stretch = length / (count * tile_length)
    rotation = math.atan2(float(run_direction[1]), float(run_direction[0]))
    step = tile_length * stretch
    pieces: List[FacadePiece] = []
    for index in range(count):
        position = start + run_direction * (index * step)
        pieces.append(
            FacadePiece(
                asset_path=asset_path,
                position=np.array([position[0], position[1], z]),
                rotation_rad=rotation,
                scale=(stretch, scale_yz[0], scale_yz[1]),
            )
        )
    return pieces


def generate_road_edge_pieces(  # pylint: disable=too-many-locals
    lanes: Dict[int, Lane],
    edges: Dict[int, RoadEdge],
    kit: RoadEdgeKit = DEFAULT_ROAD_EDGE_KIT,
    curb_variant: int = 0,
    sidewalk_variant: int = 0,
) -> List[FacadePiece]:
    """Curb and sidewalk pieces along the outer edge of every directed
    road edge, on straight stretches only (see this module's docstring).

    Deterministic and RNG-free. One curb style and one sidewalk style are
    used for the WHOLE scenario (``curb_variant``/``sidewalk_variant``
    index into the kit's asset paths): a real city uses a single sidewalk
    type, so tiles must match each other. Varying the variant between
    scenarios (chosen by the caller from the scenario seed) is the domain
    randomization knob.
    """
    curb_asset = kit.curb_asset_paths[curb_variant % len(kit.curb_asset_paths)]
    sidewalk_asset = kit.sidewalk_asset_paths[sidewalk_variant % len(kit.sidewalk_asset_paths)]
    pieces: List[FacadePiece] = []
    for run in edge_runs(lanes, edges):
        pieces += _run_pieces(
            run.start,
            run.run_direction,
            run.length,
            kit.curb_length_m,
            curb_asset,
            kit.curb_z_m,
            kit.curb_scale_yz,
        )
        pieces += _run_pieces(
            run.start,
            run.run_direction,
            run.length,
            kit.sidewalk_length_m,
            sidewalk_asset,
            kit.sidewalk_z_m,
            (1.0, 1.0),
        )
    return pieces
