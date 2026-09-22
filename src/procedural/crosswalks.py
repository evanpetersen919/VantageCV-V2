"""Real Epic crosswalk tiles at every road approach to an intersection.

Uses ``SM_ROAD_19_3_0_19_crosswalk`` from the real ``Kit_City_Road`` kit
(already migrated into this project as part of the earlier road-tile
measurement work, but unused until now) -- a real crosswalk mesh: the
pedestrian-crossing pad itself. Measured live via this project's own
``GetStaticMeshBounds`` RPC (no separate CitySample launch needed, since
the asset was already migrated):

- **Cross-road width**: bounds gave ``origin_x=0, extent_x=1002.0``, i.e.
  the mesh spans exactly [-1002, 1002] cm = 20.04m, centered -- the real
  width of Epic's own "19" road class, matching the plain road tile's own
  measured width (``SM_ROAD_19_20_0_0_road``, same ``extent_x``). Our
  roads aren't snapped to that real class, so each crosswalk is stretched
  along its own local X (a real per-instance ``FacadePiece.scale``, same
  mechanism curbs/sidewalks already use to stretch-fill) to exactly the
  physical road's own real pavement width: ``(edge.num_lanes +
  reverse.num_lanes) * LANE_WIDTH_METERS`` -- not a separate guess, it is
  the same width value the lane meshes themselves are built to.
- **Along-road depth**: bounds gave ``origin_y=150, extent_y=202``, i.e.
  the mesh spans [-52, 352] cm: a 300cm (3.0m) nominal band (matching the
  "3" in the real asset's own name) plus a 52cm skirt on each end -- the
  exact same skirt convention already measured on the plain road tile
  (``SM_ROAD_19_20_0_0_road``: 2000cm nominal + 52cm skirt each end, see
  ``road_edge_kit.py``'s module docstring / project memory). This 3.0m
  depth is used unscaled -- a real, Epic-authored value.
- **Height**: bounds gave the same z-range as the plain road tile (crown
  top ~56cm above the pivot). That crown is real geometry, not a flat
  decal -- Epic's own roads are crowned. This project's own road mesh is
  deliberately flat (``mesh_factory.build_road_mesh``'s own docstring:
  "roads are flat -- elevation/grade is not modeled"), so placing the
  real crowned mesh unscaled put a visible ~56cm ridge across every
  crosswalk, confirmed live (screenshot showed a raised mound spanning
  the road). Flattened via a small local-Z scale (``CROSSWALK_Z_SCALE``)
  so the crosswalk lies flush with our flat road, consistent with the
  project's own flat-road decision rather than a separate guess about
  how the crosswalk itself should look.

Placement: the mesh's pivot is at the depth-band's start (local Y=0),
extending across the 3.0m band toward local Y+, which (mesh-local-axis
convention verified live and documented in ``road_edge_kit.py``'s module
docstring: local Y = ``(sin r, -cos r)`` in the python frame) is set to
point toward the node. The pivot sits ``compute_node_clearance()``'s own
clearance value plus 3.0m out from the node along the road -- the exact
same clearance the lane trim (``lane_topology.py``) and the paved
intersection fill (``intersection_pavement.py``) already use, so the
crosswalk's node-side edge lands exactly flush against the intersection
pavement's own boundary, with no separate measurement or guess.

**No painted zebra stripes**: the mesh's own material
(``M_Asphalt_Master_Inst_Crosswalk``) was checked directly (its texture
references dumped from the migrated ``.uasset``) and carries only generic
asphalt/concrete/debris/puddle textures -- no stripe texture at all, and
an isolated unscaled test spawn in-engine confirmed it renders as a
plain, distinctly-toned pad, not a zebra pattern. This was cross-checked
against real placement data, not just this one material: a headless
CitySample query of the real ``CITY_ground`` point cloud (566 real
crosswalk pad instances) and ``CITY_decals`` point cloud (11,103 nearby
line-decal instances, ``SM_White_Line_00_inst``/``SM_White_Road_Line_00_
inst``) found no repeating perpendicular-stripe pattern coincident with
any real pad's own footprint -- only a scatter of short dash segments
clustered right at the pad's own road-side pivot edge (local Y close to
0), i.e. a real stop/give-way line, not a zebra ladder across the
crossing's depth.

**Real stop-line marking** (``generate_crosswalk_pieces`` emits a second
piece per end, using ``SM_White_Line_00_inst``): the irregular dash
count/spacing Epic's own instances use couldn't be pinned to a reliable
formula (looked hand-placed/jittered per intersection, not procedural),
so this doesn't try to replicate that exactly -- an honest simplification
rather than a guessed formula. What IS reliable, real and reused
directly: across every one of those real dash instances found near a pad
edge, ``scale_y`` (14 samples) was ``0.12`` in 12 of them (the clear
mode) -- combined with the mesh's own measured unscaled size (a flat
512x512cm square, ``GetStaticMeshBounds``: origin 0, extent 256x256,
zero height), that gives a real stripe thickness of ``512cm * 0.12 =
61.4cm`` -- within a centimetre of the standard real-world 24in
(~61cm) crosswalk stripe width, not a coincidence. This module builds
one continuous bar (not Epic's own irregular dashes) at that real
thickness, stretched (same real per-instance ``FacadePiece.scale``
mechanism as the pad) across the crossing's own real width, positioned
at the exact same pivot/rotation as its pad -- the same point real
instances clustered around -- lifted 1cm above the pad to avoid
z-fighting.
"""

import math
from typing import Dict, List, Set, Tuple

import numpy as np

from src.procedural.building_facade import FacadePiece
from src.procedural.lane_topology import LANE_WIDTH_METERS, compute_node_clearance
from src.procedural.road_network import RoadEdge, RoadNode

CROSSWALK_ASSET_PATH = (
    "/Game/Road/Kit_City_Road/SM_ROAD_19_3_0_19_crosswalk.SM_ROAD_19_3_0_19_crosswalk"
)
STOP_LINE_ASSET_PATH = (
    "/Game/Road/Kit_MeshDecals_A/Mesh/SM_White_Line_00_inst.SM_White_Line_00_inst"
)

# Real measured dimensions (GetStaticMeshBounds against the migrated
# asset) -- see this module's own docstring for the derivation.
CROSSWALK_REAL_WIDTH_M = 20.04
CROSSWALK_DEPTH_M = 3.0

# Flattens the mesh's real ~58cm road crown down to about 1cm of relief
# so it lies flush with this project's own flat road surface instead of
# standing up as a visible ridge -- see this module's own docstring.
CROSSWALK_Z_SCALE = 0.02

# Real unscaled size of the stop-line mesh (a flat, symmetric square) and
# the real thickness scale Epic itself uses on it -- see the module
# docstring's "Real stop-line marking" section.
STOP_LINE_REAL_SIZE_M = 5.12
STOP_LINE_THICKNESS_SCALE = 0.12
STOP_LINE_Z_LIFT_M = 0.01


def _physical_road_pairs(edges: Dict[int, RoadEdge]) -> List[Tuple[RoadEdge, int]]:
    """Every physical road (a directed edge plus its combined lane count
    across both directions), each returned once, not once per directed
    edge -- a crosswalk spans the full road, both directions at once."""
    seen: Set[Tuple[int, int]] = set()
    result: List[Tuple[RoadEdge, int]] = []
    for edge in edges.values():
        pair_key: Tuple[int, int]
        if edge.reverse_edge_id is not None:
            low, high = sorted((edge.edge_id, edge.reverse_edge_id))
            pair_key = (low, high)
        else:
            pair_key = (edge.edge_id, edge.edge_id)
        if pair_key in seen:
            continue
        seen.add(pair_key)
        reverse = edges.get(edge.reverse_edge_id) if edge.reverse_edge_id is not None else None
        total_lanes = edge.num_lanes + (reverse.num_lanes if reverse is not None else 0)
        result.append((edge, total_lanes))
    return result


def generate_crosswalk_pieces(  # pylint: disable=too-many-locals
    nodes: Dict[int, RoadNode], edges: Dict[int, RoadEdge]
) -> List[FacadePiece]:
    """One real crosswalk pad plus one real stop-line piece at each end of
    every physical road, both stretched to that road's own real pavement
    width and positioned flush against the paved intersection surface at
    that end."""
    clearance = compute_node_clearance(edges)
    pieces: List[FacadePiece] = []

    for edge, total_lanes in _physical_road_pairs(edges):
        road_width_m = total_lanes * LANE_WIDTH_METERS
        scale_x = road_width_m / CROSSWALK_REAL_WIDTH_M

        start, end = edge.centerline[0], edge.centerline[-1]
        direction = end - start
        edge_length = float(np.linalg.norm(direction))
        if edge_length < 1e-9:
            continue
        unit_direction = direction / edge_length

        for node_id, away_from_node in (
            (edge.start_node_id, unit_direction),
            (edge.end_node_id, -unit_direction),
        ):
            depth_end = clearance.get(node_id, 0.0) + CROSSWALK_DEPTH_M
            if depth_end > edge_length:
                continue  # road too short to hold a non-overlapping crosswalk here
            pivot = nodes[node_id].position + away_from_node * depth_end
            toward_node = -away_from_node
            rotation_rad = math.atan2(float(toward_node[0]), -float(toward_node[1]))
            pieces.append(
                FacadePiece(
                    asset_path=CROSSWALK_ASSET_PATH,
                    position=np.array([pivot[0], pivot[1], 0.0]),
                    rotation_rad=rotation_rad,
                    scale=(scale_x, 1.0, CROSSWALK_Z_SCALE),
                )
            )
            pieces.append(
                FacadePiece(
                    asset_path=STOP_LINE_ASSET_PATH,
                    position=np.array([pivot[0], pivot[1], STOP_LINE_Z_LIFT_M]),
                    rotation_rad=rotation_rad,
                    scale=(road_width_m / STOP_LINE_REAL_SIZE_M, STOP_LINE_THICKNESS_SCALE, 1.0),
                )
            )
    return pieces
