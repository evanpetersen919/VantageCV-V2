### [RESOLVED] Paved intersection surface closes the lane-trim gap
Follow-up to the "lane geometry overlapped itself at every intersection"
fix above (`compute_node_clearance`, then named
`LaneTopologyGenerator._compute_node_clearance`): trimming every lane
short of each node it touches removed the overlap, but left every
intersection's own footprint uncovered by any lane mesh -- only the
ground plane (a different material/height) showed through, a real,
visible gap at every one of the (thousands of) intersections in a full
scenario, not a cosmetic nit.

**Fix** (`src/procedural/intersection_pavement.py`,
`build_intersection_pavement_meshes`): one flat quad per node, tagged
with the roads' own `"asphalt"` material, at road height (z=0). The
quad is centred on the node and sized to exactly the same `clearance`
value `compute_node_clearance` already computes for the lane trim --
not a separate measurement or guess. `_compute_node_clearance` was
promoted from a `LaneTopologyGenerator` static method to a public
module-level function (`lane_topology.compute_node_clearance`) so both
callers share one implementation (avoided a pylint duplicate-code
finding, and, more importantly, guarantees the fill and the trim can
never drift apart).

**Why an axis-aligned square is exact, not approximate, here**: road
network generation only ever produces axis-aligned grid edges
(diagonal/organic roads were scrapped early -- see `road_network.py`'s
module docstring, no exact fix existed for acute-angle lane
self-overlap). Every lane's near-node boundary point therefore sits
within `clearance` metres of the node along both the node-local
longitudinal axis (capped by the same `min(clearance, max_trim)` used
to trim it) and lateral axis (offset strictly less than its own edge's
half-width, which is at most `clearance`, the max over all incident
edges) -- and because every incident edge runs along global X or
global Y, those two per-edge axes are always the global X/Y axes too.
A global-axis-aligned square of half-width `clearance` centred on the
node is thus guaranteed to contain every incident lane's near-node
boundary corner. Proven, not just asserted: a dedicated unit test
(`test_quad_covers_every_incident_lane_near_node_boundary_point`)
checks every lane's near-node boundary point against the built quad on
a real generated scenario and passed on the first run.

Wired into `scenario_serializer.serialize_scenario` alongside the
ground plane, block pavement and roof slabs (only added when an
`EnvironmentConfig` is given). Verified live: loaded a real generated
scenario into a running UE5 editor over the WebSocket RPC bridge and
screenshotted an intersection from multiple angles -- a single,
continuous, correctly lit paved surface with no dark gap, pit or
height seam between the road, the new intersection fill and the
surrounding block pavement.

**Not done**: this is still a flat, generic-asphalt fill, not the real
`Kit_City_Road` intersection tiles (`M_Asphalt_Master_Inst_Intersection`
material, already migrated but unused) or real crosswalk/lane-marking
decals (`Kit_MeshDecals_A`, also migrated but unused) -- see the
"[RESOLVED, real curbs and sidewalks]" entry above's "Not done" note,
which still applies to lane-class snapping and decals; only the paved
surface itself (no visible gap) is what this entry closes.

