"""Procedural mesh geometry generation from road and building footprints.

Implements MASTER_PROMPT Section 3.4's "Procedural Meshes" bullets:
convert road geometry to mesh, convert building geometry to mesh. The
master prompt labels this sub-phase "(C++ in UE5)" -- meshes generated
at runtime by UE5's ProceduralMeshComponent -- but Section 1.1's own
architecture diagram lists a "Procedural Mesh Factory (Geometry)" as part
of the Python-side "PROCEDURAL GENERATION ENGINE", separate from UE5's
"Procedural Mesh Component (Real-time Generation)" in the C++ simulation
backend. These two sections of the same document disagree about which
language owns mesh geometry generation -- a real inconsistency in the
spec, not a design choice made here. See KNOWN_GAPS_AND_ISSUES.md.

Resolved in favor of the testable interpretation: this module computes
vertex/triangle buffers in Python from already-generated road lane
boundaries and building footprints. This is not wasted effort even under
the "(C++ in UE5)" reading -- it is exactly the mesh data Phase 4's
JSON-RPC layer would need to hand to UE5's real ProceduralMeshComponent at
scenario-load time, whichever side ultimately renders it. A minimal,
unverified C++ skeleton for the UE5-side consumer of this data also exists
under unreal_plugin/SyntheticDataGen/.../ProceduralMesh/ (flagged there as
uncompiled -- no UE5 install in this environment).

Winding order convention: MASTER_PROMPT/QOL_RESEARCH_CHECKLIST.md
Section D.1 calls for counter-clockwise (CCW) winding "for UE5" citing a
positive-Z cross product. This assumes a right-handed coordinate frame
(x right, y up, z out of the screen), matching the 2D geometry used
throughout this codebase (road_network.py etc. all use plain [x, y]
positions with no frame conversion). UE5 itself is left-handed
(x forward, y right, z up) with clockwise-for-front-face winding as seen
from outside -- reconciling the two is Phase 4's job (the coordinate
transform happens at the JSON-RPC boundary when loading into UE5, not
here). This module's own tests check CCW-with-positive-Z in the frame it
actually operates in, consistent with the checklist's own test.
"""

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import numpy.typing as npt

from src.procedural.building_placement import Building
from src.procedural.lane_topology import Lane

# Building footprints are extruded straight up by their height; no roof
# geometry (pitched/flat detail) is generated -- see KNOWN_GAPS_AND_ISSUES.md.
_BUILDING_BASE_Z = 0.0

# Degenerate-triangle threshold, matching
# QOL_RESEARCH_CHECKLIST.md Section D.1's own example test.
MIN_TRIANGLE_AREA_SQ_METERS = 1e-6

# A box's 6 quad faces as (corner, corner, corner, corner) vertex-index
# tuples, given vertices laid out as [4 base corners, 4 top corners] (see
# MeshFactory.build_building_mesh). The 4 walls connect base_i -> base_j
# -> top_j -> top_i for each edge (i, j) of the base quad; floor and roof
# are the base/top quads themselves, wound to face outward (down/up).
_BOX_FACES: Tuple[Tuple[int, int, int, int], ...] = (
    (0, 1, 5, 4),  # wall
    (1, 2, 6, 5),  # wall
    (2, 3, 7, 6),  # wall
    (3, 0, 4, 7),  # wall
    (0, 1, 2, 3),  # floor, viewed from below
    (7, 6, 5, 4),  # roof, viewed from above
)


def _box_quad_faces_to_triangles(
    faces: Tuple[Tuple[int, int, int, int], ...],
) -> npt.NDArray[np.int64]:
    """Fan-triangulate each (a, b, c, d) quad face into 2 triangles
    (a, b, c) and (a, c, d), flattened into one triangle index buffer."""
    triangles: List[int] = []
    for corner_a, corner_b, corner_c, corner_d in faces:
        triangles.extend([corner_a, corner_b, corner_c, corner_a, corner_c, corner_d])
    return np.array(triangles, dtype=np.int64)


@dataclass(eq=False)
class Mesh:
    """A single mesh's vertex/triangle/UV buffers, in the flat [x, y, z]
    layout a UE5 ProceduralMeshComponent (or any standard renderer) would
    consume directly."""

    vertices: npt.NDArray[np.float64]  # [N, 3]
    triangles: npt.NDArray[np.int64]  # [M * 3] flat vertex-index list
    uvs: npt.NDArray[np.float64]  # [N, 2]
    material: str


def _triangle_area_2d(
    v0: npt.NDArray[np.float64], v1: npt.NDArray[np.float64], v2: npt.NDArray[np.float64]
) -> float:
    """Signed 2D triangle area (x, y only) via the cross-product formula;
    positive for CCW winding, matching QOL_RESEARCH_CHECKLIST.md Section
    D.1's own convention."""
    return float(0.5 * ((v1[0] - v0[0]) * (v2[1] - v0[1]) - (v2[0] - v0[0]) * (v1[1] - v0[1])))


def _quad_indices_ccw(
    vertices_2d: npt.NDArray[np.float64], idx_a: int, idx_b: int, idx_c: int, idx_d: int
) -> List[Tuple[int, int, int]]:
    """Split a quad (vertex indices a, b, c, d in order around its
    perimeter) into two triangles, each re-ordered to wind
    counter-clockwise (positive signed 2D area) if it wasn't already."""

    def _ccw(idx0: int, idx1: int, idx2: int) -> Tuple[int, int, int]:
        area = _triangle_area_2d(vertices_2d[idx0], vertices_2d[idx1], vertices_2d[idx2])
        return (idx0, idx1, idx2) if area >= 0 else (idx0, idx2, idx1)

    return [_ccw(idx_a, idx_b, idx_c), _ccw(idx_a, idx_c, idx_d)]


class MeshFactory:
    """Convert road lane geometry and building footprints into meshes.

    Both methods are stateless (``@staticmethod``, no constructor args) --
    grouped into one class purely as a namespace, mirroring
    MASTER_PROMPT's file tree (``mesh_factory.py`` holding both
    conversions).
    """

    @staticmethod
    def build_road_mesh(lane: Lane) -> Mesh:
        """Build a flat road-surface mesh strip for one lane, from its
        left/right boundary polylines.

        Each consecutive pair of boundary points forms one quad (2
        triangles); the lane's 3D vertices sit at z=0 (roads are flat --
        elevation/grade is not modeled, see KNOWN_GAPS_AND_ISSUES.md). UVs
        run [0, 1] across the lane's width and increase along its length
        proportionally to distance traveled, for seamless asphalt texture
        tiling.

        Parameters
        ----------
        lane : Lane
            Must have >= 2 boundary points (true for every Lane produced
            by LaneTopologyGenerator).

        Returns
        -------
        Mesh
        """
        n_points = len(lane.left_boundary)
        vertices = np.zeros((n_points * 2, 3))
        uvs = np.zeros((n_points * 2, 2))

        cumulative_length = 0.0
        for i in range(n_points):
            if i > 0:
                cumulative_length += float(
                    np.linalg.norm(lane.centerline[i] - lane.centerline[i - 1])
                )

            vertices[2 * i] = [lane.left_boundary[i][0], lane.left_boundary[i][1], 0.0]
            vertices[2 * i + 1] = [lane.right_boundary[i][0], lane.right_boundary[i][1], 0.0]
            uvs[2 * i] = [0.0, cumulative_length]
            uvs[2 * i + 1] = [1.0, cumulative_length]

        vertices_2d = vertices[:, :2]
        triangle_indices: List[int] = []
        for i in range(n_points - 1):
            left_near, right_near = 2 * i, 2 * i + 1
            left_far, right_far = 2 * (i + 1), 2 * (i + 1) + 1
            for tri in _quad_indices_ccw(vertices_2d, left_near, right_near, right_far, left_far):
                triangle_indices.extend(tri)

        triangles = np.array(triangle_indices, dtype=np.int64)

        return Mesh(vertices=vertices, triangles=triangles, uvs=uvs, material="asphalt")

    @staticmethod
    def build_building_mesh(building: Building) -> Mesh:
        """Build a simple box mesh for one building: a rectangular
        footprint extruded straight up by ``building.height``.

        No roof geometry beyond a flat top cap; see module docstring.

        Returns
        -------
        Mesh
            8 vertices (4 base corners + 4 top corners), 12 triangles (2
            per face x 6 faces: 4 walls + floor + roof cap).
        """
        x_min, y_min, x_max, y_max = building.aabb
        base_z = _BUILDING_BASE_Z
        top_z = _BUILDING_BASE_Z + building.height

        base_corners = np.array(
            [
                [x_min, y_min, base_z],
                [x_max, y_min, base_z],
                [x_max, y_max, base_z],
                [x_min, y_max, base_z],
            ]
        )
        top_corners = base_corners.copy()
        top_corners[:, 2] = top_z

        vertices = np.vstack([base_corners, top_corners])
        uvs = np.zeros((8, 2))
        triangles = _box_quad_faces_to_triangles(_BOX_FACES)

        return Mesh(
            vertices=vertices,
            triangles=triangles,
            uvs=uvs,
            material="concrete",
        )
