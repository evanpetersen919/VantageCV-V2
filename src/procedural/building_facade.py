"""Tile a building's quantized footprint with real City Sample modular
building-kit pieces (wall/corner), instead of a flat procedural box.

**Current, honest status (see KNOWN_GAPS_AND_ISSUES.md for the full,
up-to-date writeup)**: wall-to-wall tiling along a single straight edge,
and a corner piece's connection to the FIRST wall of its OWN edge, are
both real, verified-flush (via exact numeric bbox reconstruction AND live
screenshots) at every one of the 4 corner rotations -- not just
rotation_rad=0. Two real, separate, confirmed bugs were fixed to get
there:
1. A wall piece's own tiling-step offset had a spurious extra +1 module
   shift (leftover from testing done before the rotation fix below,
   which had confounded two separate bugs together) -- removed; verified
   against the wall's real measured local Y bounds
   (``GetStaticMeshBounds``: local Y in [-325, 0] cm, i.e. mass spans
   forward from the pivot, matching ``_BASE_TILING_DIRECTION`` directly).
2. ``_rotate_2d`` (used for every piece's position offset -- corner
   pivot-to-true-corner offset, and wall tiling-direction stepping) was
   rotating by ``-rotation_rad`` instead of ``+rotation_rad``. This is a
   DIFFERENT quantity from the mesh's own UE5 Yaw (which genuinely is
   ``-rotation_rad`` degrees, per ``ProceduralScenarioLoader.cpp``) --
   conflating "how the mesh visually rotates" with "how a position
   offset for placing it should be computed" was the real, separate bug.
   Found via a precise, falsifiable live test: a corner+wall pair
   confirmed flush at rotation 0 was rigidly rotated to rotation -pi/2
   (recomputing the wall's position-offset-from-corner at the new angle
   using each candidate formula); the un-negated formula reproduced a
   seamless join, the negated one left a large, visible gap. This also
   flips the corner-index-to-rotation formula from ``-edge_index * 90``
   to ``+edge_index * 90`` (re-derived and verified numerically against
   all 4 real edge directions, not assumed by symmetry).

**Real, remaining, NOT-yet-fixed limitation**: a corner piece's
connection to the wall run of the PERPENDICULAR (incoming) edge -- the
other one of the two edges that meet at that corner -- is not flush.
Proven mathematically, not just observed: the ``CornerEx`` asset's own
measured local bounds are asymmetric in a way that makes it geometrically
impossible for a single rigid (translation-only) pivot offset to
simultaneously flush-match both adjacent walls (confirmed via exact
least-squares bbox reconstruction -- no zero-residual solution exists).
City Sample ships ``CornerExL``/``CornerExR`` mirrored variants of this
exact asset specifically for this (found via a real content search, not
assumed), which is very likely the intended, correct fix -- alternating
L/R per corner around the rectangle so each corner's two arms are
individually right for both edges it touches. This was not completed or
shipped this session: the L variant's own "own-edge" offset was not
independently re-derived and confirmed live (only a numeric fit for its
perpendicular/incoming side), so wiring it in without that verification
would repeat the same mistake this docstring is warning against. See
KNOWN_GAPS_AND_ISSUES.md for the concrete next step.

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
    FACADE_CORNER_LOCAL_OUTER_POINT_METERS,
    FACADE_CORNER_MODULE_METERS,
    FACADE_FLOOR_HEIGHT_METERS,
    FACADE_WALL_MODULE_METERS,
    Building,
)
from src.procedural.city_sample_assets import BuildingKit

# The corner asset's real outer point, relative to its own pivot, at
# rotation_rad=0 -- see FACADE_CORNER_LOCAL_OUTER_POINT_METERS's own
# comment for the real measurement this comes from and why it's needed.
_CORNER_LOCAL_OUTER_POINT = np.array(FACADE_CORNER_LOCAL_OUTER_POINT_METERS)


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
            # -edge_index, not +edge_index: solving
            # _rotate_2d(_BASE_TILING_DIRECTION, rotation_rad) == the real
            # geometric edge direction (corners[edge_index+1] -
            # corners[edge_index], always correct by construction) for
            # rotation_rad gives +edge_index * 90 degrees -- verified
            # numerically for all 4 edges against the corrected
            # (non-negated) _rotate_2d above, not assumed by symmetry.
            rotation_rad = edge_index * _QUARTER_TURN_RAD
            direction = _rotate_2d(_BASE_TILING_DIRECTION, rotation_rad)

            # The corner piece's pivot must sit outward of the true
            # rectangle corner by its own rotated local-outer-point offset
            # (see FACADE_CORNER_LOCAL_OUTER_POINT_METERS/_CORNER_LOCAL_OUTER_POINT)
            # so that the piece's real outer point -- not its pivot --
            # lands exactly on the building's true corner.
            corner_position = start - _rotate_2d(_CORNER_LOCAL_OUTER_POINT, rotation_rad)
            pieces.append(
                FacadePiece(
                    asset_path=kit.corner_asset_path,
                    position=np.array([corner_position[0], corner_position[1], z]),
                    rotation_rad=rotation_rad,
                )
            )

            edge_vector = corners[(edge_index + 1) % 4] - start
            edge_length = float(np.linalg.norm(edge_vector))
            # Reserve FACADE_CORNER_MODULE_METERS at BOTH ends of the edge:
            # this edge's own start corner, and the far vertex's corner
            # (which belongs to the next edge but needs the same reserved
            # gap on this edge's side to connect flush -- see
            # FACADE_WALL_LOCAL_OUTER_FACE_X_METERS's own comment in
            # building_placement.py for the full, exact-numeric-bbox-
            # verified derivation of why both ends need it).
            usable_length = edge_length - 2.0 * FACADE_CORNER_MODULE_METERS
            wall_count = max(0, round(usable_length / FACADE_WALL_MODULE_METERS))

            for wall_index in range(wall_count):
                # Re-measured directly via GetStaticMeshBounds on the real
                # wall asset (not assumed): origin_y=-162.5, extent_y=162.5
                # -> local Y range [-325, 0], i.e. the wall's mass spans
                # FORWARD from its pivot (at local Y=0) to Y=-325, exactly
                # matching _BASE_TILING_DIRECTION=(0,-1). So piece i's
                # pivot at offset i*WALL_MODULE already produces mass
                # spanning [i*WALL_MODULE, (i+1)*WALL_MODULE] -- no extra
                # "+1" shift is needed; an earlier version of this module
                # added one anyway (a leftover from testing done before the
                # rotation-sign fix, which had confounded the two bugs
                # together), producing a full extra module of gap between
                # every corner and its first wall.
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
