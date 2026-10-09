### [RESOLVED] Occasional pedestrians standing in the road at intersections
User reported occasional pedestrians appearing on the road near
intersections. Real, found bug (not a rare fluke): `_generate_spawn_zones`
tiled pedestrian points starting from the lane's own already-trimmed
sidewalk start (`outermost_lane.left_boundary[0]`, which correctly stops
short of the intersection via `LaneTopologyGenerator`'s own
`compute_node_clearance` trim) but walked out to the **untrimmed**
`edge_length` -- the full node-to-node distance -- instead of the real
trimmed/usable length. That mismatch meant tiling routinely overshot
past the sidewalk's real (trimmed) far end, landing candidate points
inside the intersection's own paved box/crosswalk area at the FAR end of
edges, not just "occasionally" by chance.

Fixed by computing `usable_length = edge_length - start_trim - end_trim`
using the exact same `compute_node_clearance` value and
`MAX_TRIM_FRACTION_OF_EDGE_LENGTH` clamp `LaneTopologyGenerator` already
uses to trim lane geometry itself -- reusing the established real
quantity, not a new invented margin. Verified two ways: mathematically,
checked every pedestrian in a real generated scenario against every
node's own real clearance radius (0 violations out of 88); visually, a
live screenshot at a real intersection shows pedestrians approaching on
the sidewalk and stopping there, none standing in the crosswalk/road
box. New test assertion checks the first zone's along-edge distance from
its start node exactly equals the real trim value.

Full suite green (557/557).

