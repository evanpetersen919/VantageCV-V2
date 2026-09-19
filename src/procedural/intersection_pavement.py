"""Real paved intersection surface, closing the gap left by lane trimming.

``lane_topology.compute_node_clearance`` trims every lane short of each
node it touches by that node's ``clearance`` --
the widest incident road's own half-width -- so lanes from different edges
never overlap at an intersection. That trim leaves a real, untextured gap
at every intersection: no lane mesh covers the node's own footprint, only
whatever sits underneath (the ground plane, at a different height/material
than the road).

This module closes that gap exactly, not approximately. Road network
generation only ever produces axis-aligned edges (grid streets; diagonal/
organic roads were scrapped -- see road_network.py's module docstring, no
exact fix for acute-angle lane self-overlap), so every lane's near-node
boundary point sits within ``clearance`` metres of the node along BOTH the
node-local longitudinal axis (capped by the very same ``min(clearance,
max_trim)`` used to trim it) and lateral axis (offset distance strictly
less than its own edge's half-width, which is at most ``clearance``, the
max over all incident edges). Because every incident edge runs along
global X or global Y, those two per-edge axes are always the global X/Y
axes too, so a global-axis-aligned square of half-width ``clearance``
centred on the node is guaranteed to contain every incident lane's
near-node boundary corner -- the exact same clearance value already
computed for trimming, not a separate guess.
"""

from typing import Dict, List

from src.procedural.lane_topology import compute_node_clearance
from src.procedural.mesh_factory import Mesh, flat_quad_mesh
from src.procedural.road_network import RoadEdge, RoadNode

# Metres of world space per texture repeat; matches build_road_mesh's own
# asphalt UV scale closely enough that the seam at each lane's near-node
# edge isn't a jarring texel-size mismatch.
INTERSECTION_PAVEMENT_UV_TILE_METERS = 4.0


def build_intersection_pavement_meshes(
    nodes: Dict[int, RoadNode], edges: Dict[int, RoadEdge]
) -> List[Mesh]:
    """One upward-facing quad per intersection node, sized to exactly the
    same ``clearance`` distance every incident lane is already trimmed by,
    at road height (z=0) and tagged with the roads' own ``"asphalt"``
    material so the surface is visually continuous with the lanes feeding
    into it."""
    clearance = compute_node_clearance(edges)

    meshes: List[Mesh] = []
    for node_id, half_extent in clearance.items():
        node = nodes[node_id]
        x_center, y_center = float(node.position[0]), float(node.position[1])
        meshes.append(
            flat_quad_mesh(
                x_center - half_extent,
                y_center - half_extent,
                x_center + half_extent,
                y_center + half_extent,
                0.0,
                INTERSECTION_PAVEMENT_UV_TILE_METERS,
                "asphalt",
            )
        )
    return meshes
