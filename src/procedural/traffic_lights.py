"""Real Epic traffic signal poles facing each intersection approach.

Uses ``SM_StreetLamp_A_StopLight_{A,C,D}``, from the same real, already-
migrated ``Kit_StreetLamp_A`` kit this project's regular street lamps come
from (``street_furniture.py``'s ``LAMP_STYLES``). Measured live via this
project's own ``GetStaticMeshBounds`` RPC:

- All three share the exact same z-bounds (0 to about 931cm/9.3m) as the
  regular ``SM_StreetLamp_A_Pole_Large`` streetlamp -- Epic modeled these
  as a combined light-and-signal pole (a real, common fixture in dense US
  cities), not a separate small signal head, so each is placed unscaled,
  exactly like the regular lamps, with no separate pole/head composition.
- They differ only in how far the mast arm reaches (local-Y extent):
  ``A`` about 2.4m, ``C`` about 6.2m, ``D`` about 10.2m. Real, Epic-
  authored variants (presumably meant for narrower/wider real road
  classes) -- but this project's own road PAVEMENT width is currently
  ``UNIFORM_LANE_COUNT``-based and does not vary by ``RoadEdge.road_type``
  (a deliberate simplification in ``road_network.py``: varying lane count
  per edge previously caused a real, documented bug -- 76 of 118 edges
  got mismatched forward/reverse lane counts -- touching lane geometry,
  curbs, sidewalks, block corners and intersection sizing everywhere
  downstream; making road width itself vary by hierarchy is a separate,
  bigger, carefully-scoped project, not bundled in here). Since every
  road today has the same real width, only the long arm (``D``) actually
  reaches across it every time -- the short/medium arms would fall short
  of the real lanes, not a matter of taste. So every pole uses ``D`` for
  now; once road width varies by ``road_type``, the short/medium arms
  have a real place to attach to residential/minor streets and this
  should be revisited (``TRAFFIC_LIGHT_STYLE_SHORT``/``_MEDIUM`` are kept
  defined, just unused, for exactly that).
- Two more real variants exist, ``B``/``E``, on a visibly shorter pole
  (about 4.2m, no combined streetlight) -- not used here to avoid mixing
  pole heights that look inconsistent next to the regular lamps; a real,
  documented option for later, not a silently dropped one.
- The kit also ships modular ``TrafficLight``/``TrafficLight_Pole`` pieces
  and ``WalkSignal_01``/``02`` pedestrian heads for a hand-composed
  assembly, plus emissive materials for lit red/yellow/green and walk/
  don't-walk states -- not used here either (the self-contained poles are
  simpler and already correct height); a real, documented follow-up.

Placement reuses ``road_edge_kit.edge_runs`` -- the exact same curb-line
geometry ``street_furniture.py`` places lamps along -- but one pole per
DIRECTED edge (not per physical road): a real traffic signal faces one
direction of travel, so each incoming approach gets its own pole, offset
onto the sidewalk by the same real 0.40m lamp offset already measured for
this kit's poles.

**Far-side mounting, not stop-line-overhead mounting**: a real US mast-arm
signal for a given approach is mounted at the FAR corner of the
intersection (diagonally across the box from that approach's stop line),
with the arm reaching back over the near/approaching lanes -- not
directly above the car already stopped at the line. Found from live
feedback: a pole planted at the stop line itself sits right over the
driver's head, which isn't how real signals are placed (a driver at the
stop line looks up and across the box to see their own light).

Since this project's intersections are modeled as a single symmetric
`node_clearance` value per node (the widest incident road's half-width,
already used to trim every lane short of the node and to size the
intersection-pavement fill -- see ``lane_topology.compute_node_clearance``),
the box is treated as square/symmetric around the node: the far corner
sits exactly `2 * node_clearance[end_node]` further along the same
`run_direction`, past the run's own (already-clearance-trimmed) end --
i.e. past the node, continuing in a straight line, still on the same
(right-hand/outward) side of the road. ``TRAFFIC_LIGHT_END_MARGIN_M``
still keeps the pole clear of the crosswalk bar at that corner, just
added past the far boundary instead of subtracted before the near one.
The mast-arm rotation itself is unchanged: it reaches laterally across
the lanes (``-outward``), which is correct at either the near or far
mounting point.

**A real orientation bug, found from live feedback and derived, not
guessed**: the mast arm grows along the mesh's own local Y axis. Under
this kit's own rotation convention (verified for the regular streetlamp:
local Y at ``rotation_rad = r`` is ``(sin r, -cos r)``), placing a piece
at ``rotation_rad = run.rotation_rad`` (no offset, what an earlier
version of this module did) makes local Y exactly equal to ``run.
outward`` -- provable algebraically from how ``edge_runs`` derives
``run_direction`` from ``outward`` (see ``road_edge_kit.edge_runs``), not
just observed. Since ``outward`` points from the road onto the sidewalk
by definition, that put every mast arm reaching further onto the
sidewalk instead of over the travel lanes -- confirmed live with an
isolated top-down test spawn. Fixed with the same ``+ pi`` rotation
offset the regular kit's cobra-head lamp already needed for the same
reason (``street_furniture.LAMP_STYLES``), which flips local Y to
``-outward``, back over the road.
"""

from typing import Dict, List

import numpy as np

from src.procedural.building_facade import FacadePiece
from src.procedural.lane_topology import Lane, compute_node_clearance
from src.procedural.road_edge_kit import edge_runs
from src.procedural.road_network import RoadEdge

_KIT_DIR = "/Game/Prop/Kit_StreetLamp_A/Mesh/SM_StreetLamp_A_StopLight_"

# Real Epic variants sharing the regular streetlamp's pole height, differing
# only in real mast-arm reach (~2.4m / ~6.2m / ~10.2m) -- see module docstring.
TRAFFIC_LIGHT_STYLE_SHORT = _KIT_DIR + "A"
TRAFFIC_LIGHT_STYLE_MEDIUM = _KIT_DIR + "C"
TRAFFIC_LIGHT_STYLE_LONG = _KIT_DIR + "D"
TRAFFIC_LIGHT_STYLES = (
    TRAFFIC_LIGHT_STYLE_SHORT,
    TRAFFIC_LIGHT_STYLE_MEDIUM,
    TRAFFIC_LIGHT_STYLE_LONG,
)

# Every road today has the same real width, so only the long arm actually
# reaches across it -- see module docstring's "Not done, on purpose" note.
_CURRENT_STYLE = TRAFFIC_LIGHT_STYLE_LONG

# Same real offset from the curb line as the regular street lamps use
# (street_furniture.py's own measured lamp rule).
TRAFFIC_LIGHT_OFFSET_M = 0.40

# Keep the pole clear of the crosswalk bars sitting at the same corner.
TRAFFIC_LIGHT_END_MARGIN_M = 1.0

# The mast arm grows along local Y = outward at rotation_rad = run.rotation_rad
# (see module docstring); + pi flips it to -outward, back over the road.
_ARM_OVER_ROAD_ROTATION_OFFSET_RAD = np.pi


def generate_traffic_light_pieces(
    lanes: Dict[int, Lane], edges: Dict[int, RoadEdge]
) -> List[FacadePiece]:
    """One real traffic signal pole per directed road edge long enough to
    hold one clear of the intersection, mounted at the FAR corner of the
    intersection box (not directly over that approach's own stop line --
    see module docstring), its mast arm reaching back over the near
    lanes. Every pole uses the long-arm variant (see module docstring:
    every road has the same real width today, so only that arm actually
    reaches across it)."""
    node_clearance = compute_node_clearance(edges)
    pieces: List[FacadePiece] = []
    for run in edge_runs(lanes, edges):
        if run.length <= TRAFFIC_LIGHT_END_MARGIN_M:
            continue
        end_node_id = edges[run.edge_id].end_node_id
        far_side_shift = 2.0 * node_clearance.get(end_node_id, 0.0)
        spot = run.length + far_side_shift + TRAFFIC_LIGHT_END_MARGIN_M
        position = run.start + run.run_direction * spot + run.outward * TRAFFIC_LIGHT_OFFSET_M
        pieces.append(
            FacadePiece(
                asset_path=_CURRENT_STYLE,
                position=np.array([position[0], position[1], 0.0]),
                rotation_rad=run.rotation_rad + _ARM_OVER_ROAD_ROTATION_OFFSET_RAD,
            )
        )
    return pieces
