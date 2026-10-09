### [DEFERRED] City-block identification approximates blocks as individual surviving Delaunay triangles
`BuildingPlacementGenerator._identify_blocks` reuses the same Delaunay
triangulation `RoadNetworkGenerator` computes internally and treats each
triangle whose 3 edges all survived length-filtering as one "block."
Real city blocks are usually quadrilateral-ish regions spanning several
adjacent triangles, not single triangles -- a general planar-graph
face-finding algorithm (walking the graph to recover actual bounded faces)
would be more realistic but is substantially more work than anything else
specified for this phase (which gives no algorithm at all -- see above).
This approximation is geometrically valid (triangles are simple,
non-overlapping polygons that correctly partition the interior) but will
produce visibly triangular block shapes rather than rectangular ones.
Revisit if/when a mesh-rendering phase makes block shape visually matter.

