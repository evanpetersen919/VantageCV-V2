"""Tile a building's quantized footprint with real City Sample modular
building-kit pieces (wall/corner/column), instead of a flat procedural
box.

**Module spacing and placement convention are converged from THREE
independent real sources in the actual CitySample project** (not
inferred from bounding boxes -- see ``building_placement.py``'s own
module-constants comment for the full derivation, including this
session's rigorous re-query of source 2 across every real building):

1. ``CHA_primary.bdf``, Epic's real Houdini building-definition config.
2. ``All_Buildings_Lineup_pc``, the real per-instance transform point
   cloud behind Epic's actual generator output, read directly via the
   ``unreal.PointCloud``/``PointCloudView`` Python API.
3. ``Kit_Ref_Bldg/CHA_Ref_N1``, a hand-placed reference assembly.

A corner's pivot IS the building's true rectangle vertex (no
pivot-to-vertex offset), and no perpendicular offset is needed for
either walls or corners (source 3, cross-checked against source 2).

**One plain corner piece per vertex** (``kit.corner_asset_path``,
rotated to match the edge that starts there). An earlier version of this
module emitted a stacked ``CornerExL``+``CornerExR`` pair at every
vertex instead, reasoning from a single real point-cloud vertex where
Epic's own generator did exactly that. This session re-queried the point
cloud rigorously across every real ``Kit_Bldg_CHA_L1_A`` instance in the
whole point cloud (4 real buildings, 16 real corner-vertex instances,
332 real points total -- not one cherry-picked sample) and found the
plain ``CornerEx`` asset is what Epic's generator actually uses 15/16
of the time; ``CornerExR`` appears only once, ``CornerExL`` never, and
no real vertex stacks two corner pieces. The earlier "single CornerEx
can't flush-match both edges, proven via least-squares" conclusion is
therefore very likely an artifact of a wrong/incomplete local-bounds
measurement, not a real geometric fact about the asset -- reverted back
to the single-piece placement that matches the real majority usage.
``BuildingKit.corner_l_asset_path``/``corner_r_asset_path`` are kept
(real asset paths, real evidence that Epic uses them at least
occasionally) for a future session that gets enough real samples to
determine what actually distinguishes the rare non-plain case -- not
enough evidence exists yet to guess a rule for when to use them, so this
module does not.

**The corner's STORED (rendered) rotation is its own-edge tiling
rotation plus one extra quarter turn** (see the inline comment at this
piece's construction below for the full reasoning) -- a real,
live-screenshot-confirmed fix (user-reported: "the corners are the only
thing that's not perfect", visually verified via a top-down shot showing
the corner's outer trim not wrapping flush around the vertex without
this offset, and wrapping exactly flush with it) for the ``CornerEx``
mesh's own local orientation convention being a quarter turn off from
the tiling-direction convention the rest of this module uses. This is
the same class of fix as the wall's own ``+ math.pi`` below, just a
different real offset for a different mesh's own local convention.

**A real Column piece (``kit.column_asset_path``, BDF module "P1") is
now placed between every pair of consecutive same-edge wall pieces.**
This session's real point-cloud re-measurement found that the "450cm
wall-to-wall spacing, ~125cm larger than the wall mesh's own 325cm
bounding box" figure earlier sessions had written off as "a deliberate
reveal/gap... not a bug to close up" (see git history / this module's
own prior revisions) was based on an incomplete reading: real Epic
buildings do not leave that 125cm empty. They fill it with a real
Column mesh, at an exact, zero-exception 325cm(wall)/125cm(column)
alternation across 128 real column instances and 152 real wall
instances (see ``building_placement.py``'s own module-constants comment
for the full real numbers). Omitting that Column was very likely
contributing to this project's own generated buildings looking visibly
"unfinished" along straight wall runs even where the corner-to-wall
join itself was already exact (see below) -- fixed here by placing one
``kit.column_asset_path`` piece after every wall except the last one on
each edge (no real vertex ever showed a column directly adjacent to a
corner).

**The corner-to-first-wall join was NOT the bug.** This session's
specific re-measurement task was to check whether the visible top-down
gap at every corner turn (reported after live screenshot verification)
was because ``BuildingKit.corner_to_first_wall_m`` (1.5m for CHA_L1) didn't match
real data. It does, exactly: 16/16 real corner-vertex-to-first-owned-
wall measurements in the point cloud came back at precisely 150cm, zero
exceptions, fully independent of building footprint size. The real,
evidenced fix for the visible gap is the corner-stacking and Column
changes above, not a constant change here.

Our own generator eliminates the far-corner reservation remainder
(present in Epic's real buildings, since each edge otherwise tiles
independently from its own corner) by quantizing footprint sides to
exact ``corner_to_first_wall_m + N*wall_pitch_m``
multiples (see ``building_placement.py``'s ``_quantize_footprint_side``),
so every edge here closes exactly on its far corner's true vertex.

The corner-index-to-rotation formula is ``+edge_index * 90`` degrees,
and every position offset (corner placement, wall tiling-direction
stepping) is computed via ``_rotate_2d`` applying the rotation directly
(not negated) -- see that function's own docstring for a separate, real
rotation-sign bug this session found and fixed: UE5's Yaw for the
rendered mesh genuinely is ``-rotation_rad`` degrees (per
``ProceduralScenarioLoader.cpp``), but that governs how the MESH
rotates, not how a python-space POSITION offset for placing it should
be computed -- conflating the two was the bug.

No roof cap is generated -- the wall module's own top coping forms the
roofline; open-top from directly above is a real, separate, deliberate
v1 gap (street-level AV camera framing won't see it).

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
``BuildingStyle`` grid multiples (``corner_to_first_wall_m + N*wall_pitch_m``)
and whole-floor-stack heights (BuildingPlacementGenerator does
this at generation time -- see that module) for the tiling below to close
without a gap or overlap.

**Wall pieces store ``rotation_rad + pi``, not the plain per-edge
rotation.** Confirmed live via a marker placed at the building's true
geometric center: with the plain (un-flipped) rotation, every wall's
window/trim face pointed INWARD, toward that center marker, not outward
toward the street. The wall MESH's decorative face is on the opposite
local side from what the position-tiling convention above assumes, so
only the piece's final, RENDERED rotation needs the extra ``pi`` --
``direction``/``wall_position`` above must keep using the original,
unmodified ``rotation_rad``, since that math (tiling step direction,
which edge a wall belongs to) was independently validated and the flip
would silently break closure if applied there too. A follow-up close-up
screenshot at a corner-wall junction (flipped wall next to an unflipped
corner) showed no seam or orientation mismatch, so corner pieces are not
flipped -- their own local geometry already faces outward as placed.
"""

import math
from dataclasses import dataclass
from typing import List

import numpy as np
import numpy.typing as npt

from src.procedural.building_placement import Building
from src.procedural.city_sample_assets import BuildingStyle


def _rotate_2d(vector: npt.NDArray[np.float64], rotation_rad: float) -> npt.NDArray[np.float64]:
    """Rotates a python-world-space POSITION offset (e.g. a piece's own
    local outer-point/tiling-step vector) by ``rotation_rad``, matching
    how that same ``rotation_rad`` value rotates the piece's rendered
    mesh once it goes through ``ProceduralScenarioLoader.cpp``.

    Uses the standard CCW rotation matrix applied directly to
    ``rotation_rad`` (no extra negation). An earlier version of this
    function applied the rotation matrix to ``-rotation_rad`` instead,
    reasoning from ``ParseAssetData``'s ``Yaw = -RadiansToDegrees
    (rotation_rad)`` -- that Yaw-sign fact is real, but it governs how
    UE5 rotates the MESH's own vertices, not how a python-space offset
    for POSITIONING that mesh should be computed; treating those as the
    same transform was a real, separate bug, found via a precise,
    falsifiable live test very late in this session: a corner + wall
    pair confirmed flush at ``rotation_rad=0`` was rigidly rotated (both
    pieces' own ``rotation_rad`` AND the wall's position-offset-from-
    corner recomputed at the new angle) to ``rotation_rad=-pi/2``. Rigid
    rotation must preserve flushness. Using the OLD (negated) formula for
    the position offset produced a large, visible gap; using this
    DIRECT (non-negated) formula reproduced a perfectly seamless join --
    confirmed via live screenshot, not assumed. (The much earlier
    "two-wall 472cm vs 147cm" test, that had motivated the old negated
    formula, only validated a coarse "closer vs farther" comparison, not
    which of the two sign conventions was actually correct -- both
    conventions predict a similar-order-of-magnitude gap difference
    between rotation 0 and rotation pi/2, so that earlier test could not
    actually distinguish between them. This rigid-rotation test can, and
    does.)
    """
    cos_r, sin_r = math.cos(rotation_rad), math.sin(rotation_rad)
    rotation_matrix = np.array([[cos_r, -sin_r], [sin_r, cos_r]])
    return rotation_matrix @ vector


# Perimeter traversal order: corner i gets rotation_rad = i * (pi / 2)
# (POSITIVE, not negative -- re-derived from the corrected _rotate_2d
# above: solving _rotate_2d(_BASE_TILING_DIRECTION, rotation_rad) == the
# real geometric edge direction (corners[edge_index+1] -
# corners[edge_index], always correct by construction) for each
# edge_index gives +edge_index * 90 degrees exactly, verified numerically
# for all 4 edges, not assumed by symmetry). A wall/entrance piece placed
# with that same rotation tiles along edge_direction. The base direction
# (0, -1) is the real, live-confirmed tiling-advance direction at
# rotation_rad=0 (see module docstring).
_QUARTER_TURN_RAD = math.pi / 2.0
_BASE_TILING_DIRECTION = np.array([0.0, -1.0])


def _corner_points(building: Building) -> List[npt.NDArray[np.float64]]:
    """The 4 real footprint corners in perimeter-traversal order
    (top-left -> bottom-left -> bottom-right -> top-right), matching the
    edge directions each corner index's rotation implies via
    ``_rotate_2d(_BASE_TILING_DIRECTION, ...)``."""
    x_min, y_min, x_max, y_max = building.aabb
    return [
        np.array([x_min, y_max]),
        np.array([x_min, y_min]),
        np.array([x_max, y_min]),
        np.array([x_max, y_max]),
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
    building: Building, style: BuildingStyle
) -> List[FacadePiece]:
    """Tile ``building``'s quantized footprint, per floor, with the real
    wall/corner/column pieces of each floor's kit
    (``kit.entrance_asset_path`` is deliberately not used yet -- see this
    module's own docstring).

    Deterministic and RNG-free: footprint/height already fully determine
    every piece's position once quantized (see ``building_placement.py``).
    Floor ``i`` uses ``style.kit_for_floor(i)`` and sits at
    ``style.floor_base_z(i)``; every level of a style shares one
    horizontal grid, so the same footprint tiles on every floor.

    Parameters
    ----------
    building : Building
        Must already have footprint and height quantized to ``style``
        (true for every Building produced by a
        BuildingPlacementGenerator built with the same ``style``).
    style : BuildingStyle
        Real per-floor kits, whose grid/heights the building was
        quantized to.

    Returns
    -------
    List[FacadePiece]
    """
    corners = _corner_points(building)
    num_floors = style.floor_count_for_height(building.height)
    corner_reach = style.corner_to_first_wall_m
    wall_pitch = style.wall_pitch_m

    pieces: List[FacadePiece] = []
    for floor_index in range(num_floors):
        kit = style.kit_for_floor(floor_index)
        z = style.floor_base_z(floor_index)

        for edge_index in range(4):
            start = corners[edge_index]
            # -edge_index, not +edge_index: solving
            # _rotate_2d(_BASE_TILING_DIRECTION, rotation_rad) == the real
            # geometric edge direction (corners[edge_index+1] -
            # corners[edge_index], always correct by construction) for
            # rotation_rad gives +edge_index * 90 degrees -- verified
            # numerically for all 4 edges against the corrected
            # (non-negated) _rotate_2d above, not assumed by symmetry.
            rotation_rad = edge_index * _QUARTER_TURN_RAD
            direction = _rotate_2d(_BASE_TILING_DIRECTION, rotation_rad)

            # ONE plain corner piece per vertex, rotated to match the
            # edge that starts there -- reverted this session from an
            # earlier version that stacked CornerExL+CornerExR at every
            # vertex. That stacking was real (Epic's generator does do
            # it, at least once), but was generalized from a single
            # cherry-picked real point-cloud vertex without checking how
            # common it actually is. A rigorous re-query this session
            # (see building_placement.py's own module-constants comment
            # for the full real numbers) found the plain ``CornerEx``
            # asset used at 15 of 16 real corner-vertex instances across
            # 4 real buildings, ``CornerExR`` at only 1/16, and
            # ``CornerExL`` at 0/16 -- no real vertex ever stacks two
            # corner pieces. The pivot IS the true rectangle vertex --
            # no pivot-to-vertex offset (real reference-building
            # evidence, this module's own docstring).
            #
            # The extra `+ kit.corner_yaw_offset_rad` (pi/2 for CHA_L1) on the STORED (rendered)
            # rotation is the same class of fix as the wall's own
            # `+ kit.wall_yaw_offset_rad` above: the corner mesh's own local orientation
            # convention is a quarter turn off from the own-edge tiling
            # rotation this loop otherwise computes. Live-screenshot-
            # confirmed: without this offset, a top-down shot showed the
            # corner's outer trim NOT wrapping flush around the true
            # vertex (a visible seam against both adjoining walls); with
            # it, the same shot shows the trim wrapping the corner
            # exactly flush, matching real Epic buildings. There is no
            # separate position computation for a corner piece (its
            # position is always just the vertex itself), so unlike the
            # wall's `direction`/`wall_position` split, this offset is
            # safe to apply directly to `rotation_rad` here with no
            # separate quantity left unflipped.
            pieces.append(
                FacadePiece(
                    asset_path=kit.corner_asset_path,
                    position=np.array([start[0], start[1], z]),
                    rotation_rad=rotation_rad + kit.corner_yaw_offset_rad,
                )
            )

            edge_vector = corners[(edge_index + 1) % 4] - start
            edge_length = float(np.linalg.norm(edge_vector))
            # Reserve corner_to_first_wall_m only at THIS
            # edge's own start corner (see this module's own docstring:
            # the real point-cloud evidence shows a corner only
            # guarantees flush connection to the edge that starts at it,
            # matching its own rotation -- the far corner is reached
            # exactly, zero remainder, because
            # BuildingPlacementGenerator quantizes footprint sides to
            # exact corner_to_first_wall_m + N*wall_pitch_m
            # multiples).
            usable_length = edge_length - corner_reach
            wall_count = max(0, round(usable_length / wall_pitch))

            for wall_index in range(wall_count):
                # Real, measured wall-to-wall spacing (this module's own
                # docstring) -- wall_index=0 sits
                # corner_to_first_wall_m from the corner; no
                # perpendicular offset, matching the real reference
                # building's own consistent per-edge perpendicular
                # coordinate.
                offset = corner_reach + wall_index * wall_pitch
                wall_position = start + direction * offset
                # The wall mesh's decorative/window face is on the OPPOSITE
                # local side from the tiling-direction convention validated
                # above: rendering it at plain `rotation_rad` puts that face
                # toward the building's interior instead of the exterior --
                # confirmed live (a marker placed at the building's true
                # center showed every wall's window recess facing that
                # center, not away from it). Adding pi to the RENDERED
                # rotation only (not to `direction`/`wall_position` above,
                # which must keep using the validated, unmodified
                # rotation_rad to preserve correct tiling/closure) flips
                # only which face is outward, confirmed live: windows and
                # trim now face away from the building's interior, with
                # closure unaffected since position math is untouched.
                pieces.append(
                    FacadePiece(
                        asset_path=kit.wall_asset_path,
                        position=np.array([wall_position[0], wall_position[1], z]),
                        rotation_rad=rotation_rad + kit.wall_yaw_offset_rad,
                    )
                )

                # A real Column piece fills the real 125cm gap between
                # THIS wall and the next one on the same edge (BDF module
                # "P1", real evidence: an exact, zero-exception 325cm/
                # 125cm Wall/Column alternation across 128 real column +
                # 152 real wall point-cloud instances -- see
                # building_placement.py's own module-constants comment).
                # No column after the LAST wall on this edge: real data
                # never shows a column immediately before a corner (the
                # real join there is either a plain corner-owned 150cm
                # gap or a stretchy, non-uniformly-scaled wall this
                # project's data model does not represent -- see the
                # same comment). Uses the same rendered
                # (rotation_rad + pi) as the wall it follows -- real data
                # shows a real Column's own yaw always matches its
                # neighboring walls' yaw on that edge.
                if wall_index < wall_count - 1:
                    column_position = wall_position + direction * kit.wall_width_m
                    pieces.append(
                        FacadePiece(
                            asset_path=kit.column_asset_path,
                            position=np.array([column_position[0], column_position[1], z]),
                            rotation_rad=rotation_rad + kit.wall_yaw_offset_rad,
                        )
                    )

    return pieces
