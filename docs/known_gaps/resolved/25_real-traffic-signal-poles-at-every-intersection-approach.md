### [RESOLVED] Real traffic signal poles at every intersection approach
User asked for road realism research (traffic lights, curved sidewalk
corners, yellow center lines) mimicking real cities like NYC/Chicago,
and to check whether Kit City Sample's own assets could help before
implementing. Traffic lights first: `Kit_StreetLamp_A` (the same kit
this project's regular street lamps already use) turned out to ship a
complete, already-migrated traffic-signal kit -- `SM_StreetLamp_A_
StopLight_A` through `_E`, modular `TrafficLight`/`TrafficLight_Pole`
pieces, `WalkSignal_01`/`02` pedestrian heads, and real emissive
materials for lit red/yellow/green and walk/don't-walk states.

New `src/procedural/traffic_lights.py`: places `StopLight_{A,C,D}`
(measured via `GetStaticMeshBounds`: all three share the regular
`Pole_Large` streetlamp's z-bounds to sub-millimetre precision -- Epic
modeled them as combined light-and-signal poles, a real, common US city
fixture, not a separate small head, differing only in real mast-arm
reach: ~2.4m/6.2m/10.2m) at the far end of every directed edge's own
curb-line run (reusing `road_edge_kit.edge_runs`, the same geometry
`street_furniture.py` already places lamps along), one pole per
direction of travel since a real signal faces one approach. Unscaled,
same real 0.40m curb offset already measured for this kit's lamps.

**A real orientation bug, found from live feedback, not a guess**: the
first version placed poles at `run.rotation_rad` (no offset), which
live testing showed sent the mast arm reaching further onto the
sidewalk instead of over the road. Derived algebraically, not just
patched by trial: the arm grows along the mesh's local Y axis, and at
`rotation_rad = run.rotation_rad`, local Y is exactly equal to `run.
outward` (provable from how `edge_runs` derives `run_direction` from
`outward`) -- and `outward` points onto the sidewalk by definition.
Fixed with the same `+ pi` rotation offset this kit's own cobra-head
streetlamp already needed for the identical reason. Confirmed with an
isolated top-down test spawn before and after, then live in a real
scenario.

**Style selection**: initially picked one of the three arm-length
variants at random per pole for visual variety. Follow-up review asked
whether the short pole belonged on a "non-main road", surfacing that
`RoadEdge.road_type` (`RESIDENTIAL`/`MINOR`/`MAJOR`, already computed by
`road_network.py`) could drive this instead of randomness. But this
project's own road PAVEMENT width doesn't vary by `road_type` --
`UNIFORM_LANE_COUNT` is a deliberate simplification (varying lane count
per edge previously caused a real bug: 76 of 118 edges got mismatched
forward/reverse lane counts) -- so every road today has the same real
width, and only the long arm (`D`) actually reaches across it; the
short/medium arms would fall short of the real lanes regardless of
`road_type`. Simplified to always use `D` for now (`SHORT`/`MEDIUM` kept
defined, unused, for whenever road width does vary by hierarchy).

Verified live: the pole spawns correctly with its pedestrian signal
actually lit (a glowing red "don't walk" hand, not just static
geometry), positioned right at the stop line beside the crosswalk, mast
arm correctly reaching over the road.

**Not done, real and documented rather than silently skipped**: the
modular `TrafficLight`/`TrafficLight_Pole`/`WalkSignal` pieces (for a
custom composed assembly, e.g. a shorter mast-arm-only pole without the
combined streetlamp) and driving the emissive materials to cycle
red/yellow/green programmatically -- the signal is currently always lit
in whatever state its baked material defaults to, not a live simulated
state. Yellow center-line road paint was investigated in the same
research pass: no distinct yellow-line asset exists in Epic's own
`Kit_MeshDecals_A` (only white line/dash variants), though the white
line's own master material (`Decal_MasterMaterial_CitySample`) exposes
a `Color Overlay` vector parameter that could plausibly tint it yellow
without new texture art -- untested, not implemented. Real-world
research note: NYC's numbered Manhattan streets/avenues are largely
one-way (no centerline needed at all), which the MUTCD-standard yellow
line by itself would understate -- modeling one-way streets would need
a real change to the road-network generator (every edge currently
always has a `reverse_edge_id`), a separate, bigger feature, not
attempted here.

(Curved sidewalk corners were prototyped in a later session -- fully
correct, live-verified twice, but reverted via `git revert` at the
user's explicit request to delay the feature; the work is fully
recoverable from git history, not lost -- see commits `858ead1`
through `66f8e7b` and their revert commits.)

