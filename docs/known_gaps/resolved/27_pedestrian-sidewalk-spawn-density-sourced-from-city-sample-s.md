### [RESOLVED] Pedestrian sidewalk spawn density, sourced from City Sample's own real crowd config
Follow-up to the pedestrian-asset entry above. Fixed the flagged gap:
pedestrian spawn zones were capped at exactly one per directed edge
regardless of edge length. Explicitly refused to invent a spacing
number for this -- instead found real evidence in City Sample itself:
`Content/AI/AgentConfig/MassCrowdZoneGraphSpawnPointGenerator_Density{0-3}`
are real, Epic-authored Blueprint configs that generate candidate
pedestrian spawn points along a ZoneGraph sidewalk lane. Queried all 4
live via a headless CitySample Python session (`UnrealEditor.exe
CitySample.uproject -nullrhi -unattended -nosplash -nosound
-ExecutePythonScript=...`, using the `obj dump <CDO path>` console
command since Blueprint-defined properties aren't enumerable through
`dir()`/`get_editor_property` alone the way native UPROPERTYs are):
all 4 presets (which otherwise differ only by ZoneGraph tag filter, not
spacing) share the identical
`MassEntityZoneGraphSpawnPointsGenerator::MinGap = MaxGap = 300.0`
(centimeters) -- a fixed, non-randomized 3.0m gap between candidate
points, real evidence straight from the reference city's own shipped
config, not a new literature citation or a guess.

`traffic_network.py::_generate_spawn_zones` now tiles pedestrian
`SpawnZone`s along each edge's sidewalk at that same real
`PEDESTRIAN_SPAWN_GAP_METERS = 3.0` interval (one zone per whole
3m-multiple of the edge's length, same "no guessing, count real
distance" approach `road_edge_kit.py`'s stretch-fill already uses
elsewhere), instead of one fixed point. Each candidate zone still goes
through the existing independent occupancy roll
(`PEDESTRIAN_DENSITY_FRACTION_OF_TRAFFIC`), so overall pedestrian count
scales with how much sidewalk exists, not a hardcoded per-edge count.

**Real, checked consequence, not silently accepted**: this multiplies
typical pedestrian counts substantially (one `urban_dense`-style test
scenario went from ~13 pedestrians to 914). Worked through the math
before accepting it: the existing occupancy formula effectively means
a real placed pedestrian appears roughly every
`PEDESTRIAN_SPAWN_GAP_METERS / (occupancy * PEDESTRIAN_DENSITY_
FRACTION_OF_TRAFFIC)` meters of sidewalk -- at typical `traffic_density`
values this comes out to roughly one person per 10-30m of sidewalk per
side, which is an ordinary moderate urban pedestrian density, not a
runaway explosion; the earlier ~13-pedestrian count was simply an
artifact of the one-slot-per-edge cap, not a more "correct" density.

Live-verified: a real generated scenario (112 pedestrians) showed
multiple people genuinely clustered together near a sidewalk corner and
scattered naturally along blocks, instead of the previous strict
one-per-edge pattern. New test
(`test_pedestrian_spawn_zones_tiled_along_each_edge`) checks the real
tiled count and gap distance per edge against the edge's own real
length, not just a total-count sanity check.

Full suite green (557/557).

