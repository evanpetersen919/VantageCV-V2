## Tractor-trailer rigs (the City Sample semi), built and checked by rendering

The truck gap against equal-count real data (-3.0 AP) sits on large vehicles, and the generator had
no articulated truck: the comment in `city_sample_assets.py` said no asset could couple the bare
trailer to a cab. The full City Sample pack disagrees: the cab `vehTruck_vehicle08` has a
`Trailer_Socket`, read with the read-only editor script `unreal_plugin/tools/inspect_trailer_socket.py`:
root bone, **(-158.0, 0.000061, 149.0) cm, no rotation**. The trailer's origin is its hitch, so the
trailer goes 1.58 m behind the cab's placement point on the same heading, on the ground (149 cm is
the fifth-wheel height). The trailer's front face then sits 0.82 m ahead of the cab's rear face,
over the tractor's rear chassis.

**Implementation (Python only, no engine change):** a rig is one `Vehicle` (`trailer=True`) with one
box that holds both parts (16.57 x 2.62 x 4.00 m, from the two measured boxes), one mesh (cab plus
trailer, so occlusion, silhouettes and the visible-part box use the whole rig) and one label, as
BDD100K and Cityscapes box a tractor-trailer as one truck. The trailer reaches the engine as a
second static-mesh actor with its axle wheels, in the cab's paint. Rig tail lights sit at the
trailer's rear; this also fixed the generic lamp placement, which assumed every box was centred on
the mesh origin. The v7 fleet's truck list is now the rig and the large rigid truck; the bare
tractor (no trailer) is gone. In 60 test scenarios none was rejected and 356 of 649 trucks were rigs
(55%). Six new tests; the full suite passes (870).

![Six rendered frames with a tractor-trailer rig: the trailer sits behind the cab on the same heading, the 3D box (magenta) and the 2D box and silhouette cover the whole rig as one truck](../images/tractor_trailer_rigs.jpg)

*Overlay frames from five single-scenario probe renders (seeds 90076, 90081, 90094, 90121, 90150),
picked offline for a rig clearly in view, not for how they look. Boxes: magenta 3D, white 2D,
cyan silhouette.*

**What is and is not checked.** Checked by rendering: the trailer attaches at the cab's rear with
no visible gap or overlap, faces the same way, and one box and one silhouette cover the whole rig
in views from the side, the front quarter and the rear. Not done: trailer tail lamps are carried
from the box end, not measured; rigs stay straight (no articulation on a turn); only the one
trailer (a box trailer with a green graphic) exists, so rig diversity is one shape in many
paints. **Nothing has been trained on rigs**, so there is no result yet on truck AP.

### Correction: the trailer was placed 3 m too far back; the hitch is now measured

The tractor-trailer entry above placed the trailer's origin at the cab's `Trailer_Socket`
(1.58 m behind the cab's origin), on the reading that the trailer's origin is its hitch. A visible
gap between cab and trailer in the renders showed that was wrong. The mesh data explains it: the
cab's body above the chassis ends at about x = +0.2 to +0.6 m, the chassis runs back to -3.0 m, and
the trailer's front face is 0.56 m *behind its own origin* with its flat underside (the apron that
rides on the fifth wheel, 1.44 m up, the same height as the cab's fifth-wheel plate at 1.49 m) running
back about 2.9 m: the socket marks the fifth wheel on the cab, and the trailer's origin is not its
kingpin.

The placement was then measured, not argued. `bin/measure_rig_gap.py` renders the rig alone on flat
ground from the side at body height and reads the gap between the cab's rear wall and the trailer's
front wall from a silhouette against an empty render (sky and ground texture change between renders,
so only runs within 16 m of the cab count):

| Trailer origin behind the cab's origin (m) | Measured gap, cab rear wall to trailer front wall |
|---|---|
| -1.58 (the socket, as first built) | about 3.0 m |
| -0.50 | 1.9 m |
| -0.11 (kingpin 36 in behind the trailer front, the usual US setback) | 1.6 m |
| 0.00 | 1.45 m |
| **+0.90 (chosen)** | **0.55 m** (0.52 at a 30 m camera, 0.59 at 40 m) |
| +1.20 | 0.22 m |

![Side views of the rig at five trailer offsets: -1.58 m leaves a cab-width gap, +0.9 m tucks the trailer in just behind the cab, +1.2 m nearly touches it](../images/tractor_trailer_hitch_candidates.jpg)

The target gap (about 0.5 to 0.6 m) is a design choice, inside the 0.3 to 0.9 m a straight rig has in
practice; that range is a general observation, not a measured statistic. At +0.90 m the trailer's
apron (world x -2.51 to +0.33) covers the fifth-wheel plate (about -2.2 to -1.0), the wheels stand on
the ground, and the whole rig box is now 14.09 m long (it was 16.57 m). A 36 in kingpin setback by
itself would give a 1.6 m gap with this long-framed tractor, which looks open, so the visual target
wins over the mechanical one. Checked on rendered street scenes as well as the isolated rig.

![Zoom on the cab-trailer junction in a rendered street frame: the trailer's front wall sits just behind the cab with a narrow gap, its underside overhangs the tractor's rear tandem](../images/tractor_trailer_junction.jpg)

### The trailer has no tail-lamp geometry to measure; the generic lamps land on its rear corners

Question: are the trailer's tail lights placed where a real one has them? Cars get measured lamp
positions from their separate `SM_Taillight_*` meshes (`bin/measure_vehicle_lamps.py`); the
trailer's part list has only wheels (`SM_Wheel_Axel1-3_L/R`), so there was nothing to measure.
The rear face was rendered from 3.2 m behind (`docs/images/tractor_trailer_rear.jpg`): it shows
the double doors, a rear ledge, a step and a bumper bar, and no lenses at all. The lamps are not
a mesh and not a texture: **this trailer model has no tail lamps**, so any lamp position is a
choice, not a measurement.

The lights the generator uses for a rig (`_generic_lamp_positions`, box end + 0.25 m, 0.995 m
either side of the centreline, 0.9 m high; the 0.9 m height is inside FMVSS 108's 0.38-1.83 m
range) project, at the render's 225 px/m, to the lower corners of the rear face, on the ledge
beside the step: where a trailer's marker lamps are on a real one. They are point lights
without a visible lens (no measured lens size, so no glow is drawn, by the module's own rule).
Left unchanged. Not measured: whether the missing lens looks wrong in a night frame (the light
spill lights the rear face; a lens would add a red disc).

### Per-box outcomes of truck and bus (real BDD100K val, 3 seeds, confidence 0.25)

Rule (hpc/README.md section 16, fixed before the results): mostly mislabelled -> appearance confusion
with cars or buses; mostly missed or low-confidence -> the detector does not find them (visibility or
scale); read the size bins before the totals. Arms: real-only `hpc_real25r`, `hpc_rand25`,
`hpc_v7p25`, `hpc_v8a25`. 4,231 truck boxes, 1,597 bus boxes; percent of boxes, mean over seeds.

| Truck | correct | mislabelled | low conf. | missed |
|---|---|---|---|---|
| real-only | 25.2 | 27.7 | 14.9 | 32.3 |
| rand25 | 28.6 | 28.9 | 12.4 | 30.2 |
| v7p25 | 27.6 | 29.9 | 11.3 | 31.3 |
| v8a25 | 26.8 | 30.1 | 11.9 | 31.2 |

By size (v7p25): small 4% correct, 63% missed; medium 24% correct, 30% mislabelled; large 42% correct,
32% mislabelled. Mislabelled trucks are called car 77-81%, bus 19-23%. Bus: 22-24% correct in the
synthetic arms (19% real-only), 33-35% mislabelled (as truck 51%, car 49%), 33% missed; small buses
65% missed.

Reading: the failure splits two ways by size, and the rule's two branches both hold. Small boxes
(a quarter of trucks, 17% of buses) are not found at all, 63-67% missed, in every arm: scale.
Medium and large boxes are found but about a third are given the wrong class, mostly car for a truck
and a truck/car split for a bus: appearance confusion. The real-only arm shows the same pattern with
the same mislabel rate (27.7%), so it is not something synthetic data introduces. Synthetic data
adds about 2-3 points of correct truck boxes and 3-5 of bus, mostly on large boxes; it does not
reduce mislabelling (28 -> 30%) and does not touch small-box misses. v8a is no better than v7p25 on
medium trucks (20.4% against 23.7% correct) and worse on large buses (34.8 against 39.5). Cars
and persons improve in v7p25 against real-only (car 63.0 -> 65.9% correct, person 30.7 -> 37.9%),
which agrees with the AP results. Not established: how much of the car/truck confusion is
ambiguity in BDD's own labels rather than detector error; that needs a look at a sample of the
mislabelled real boxes.

#### What the mislabelled real truck boxes are (looked at, not measured)

Local `runs/real_control` weights on the first 1,500 BDD val images: 683 truck boxes, 166 medium or
large ones called another class (car 8 in 10, bus the rest). A random 48 of them were cropped into a
contact sheet and read by eye (counts are my reading, rough, not a labelled audit): about 15 are
pickups (Ram, Silverado, F-series) or van-like pickups, 5 are cargo vans, about 15 are real trucks
(box trucks, dump and garbage trucks, an ice-cream truck, a semi cab), the rest are dark, blurred or
cut-off boxes where the type cannot be judged. So about a third of the confusion is BDD calling pickups
and vans "truck" where the detector says car, which a car-versus-truck appearance rule cannot settle;
another third are real trucks (box, dump, garbage) that the detector does call car. Not done: a
counted audit of more boxes, or asking how many pickups the synthetic fleet contains (v8b adds
10% pickup and 10% van).

### v8b result: labelling pickups and vans as truck lowered truck AP; the truck/bus mix is closed as a lever

`train_v8b` (v8a plus 10% pickup and 5% + 5% vans labelled truck; 256 scenarios, 3 seeds) against
`hpc_v8a25` and `hpc_v7p25`. Batch statistics matched v8a (8.07 cars, 0.30 trucks, 0.16 buses, 3.32
persons per image; the truck rate is under the 0.39 target for the same rig reason).

| BDD100K val (n = 3) | v7p25 | v8a25 | v8b25 |
|---|---|---|---|
| AP | 20.99 | 20.65 | 20.44 |
| truck AP | 16.12 | 15.62 | 15.42 |
| bus AP | 13.51 | 12.34 | 11.93 |
| car AP | 38.11 | 38.24 | 38.20 |
| person AP | 16.24 | 16.42 | 16.18 |
| night AP | 17.88 | 17.27 | 17.22 |

Cityscapes truck AP: 14.41 / 13.09 / 12.55; AP 21.34 / 21.40 / 20.78.

Rules as logged: rule 2 (adopt v8b only if truck AP +0.5 over v8a, car AP not down 0.5): truck is
-0.20 against v8a, so no. Rule 3 (stop tuning the mix if neither beats v7p25 by +1.0 on truck AP):
v8a is -0.50 and v8b -0.69 (p = 0.062), so the mix is closed as a lever. Guardrails: overall AP -0.56
(p = 0.12), car and person within 0.1; night AP -0.66; none decisive, all within noise except the
truck direction, which is consistently negative.

Together with the per-box result (truck mislabelling the same 28-30% in the real-only arm, and a third
of it pickups and vans that BDD calls truck), the reading is: changing what the synthetic fleet
contains does not move truck AP with the models we own. The remaining levers are small trucks (63%
missed in every arm) and the truck models' appearance. v7p25 stays the best synthetic arm.

### Small trucks: the synthetic data has almost none (box sizes against BDD100K val)

Share of boxes by COCO size, in 1280x720 equivalent (synthetic 1920x1080 scaled by 2/3), real
BDD100K val against `train_v7p` and `train_v8a`:

| class | real small / medium / large | v7p | v8a |
|---|---|---|---|
| truck | 18 / 43 / 39 % (4,247 boxes) | 3 / 55 / 42 (214) | 3 / 58 / 39 (157) |
| bus | 17 / 41 / 42 % (1,597) | 0 / 44 / 56 (55) | 4 / 46 / 50 (82) |
| car | 44 / 38 / 19 % (102,540) | 41 / 40 / 19 (4,076) | 41 / 40 / 19 (4,120) |

Cars match the real shape; trucks and buses do not: real trucks are small 18% of the time, synthetic
3%, and per-box outcomes show 63-67% of small real trucks missed in every arm. Cause, from the
annotation policy (`src/export/annotation_policy.py`) and the manifest: labels are dropped beyond
`max_distance_m` (truck 53 m, bus 41 m, car 54 m), and these cutoffs were fit so the *median* box
height matches the real benchmarks. Camera: vertical FOV 73.74 deg, so at 1280x720 equivalent a
truck (about 3 m effective size) falls under 32 px beyond roughly 45 m; a 53 m cutoff leaves a
sliver of distances that can be small, while real trucks are seen far past that. A median fit
matches the middle of the distribution and cuts its tail. Cars look right only because they are
small at the same distance. Not yet done: the cutoff that reproduces the real small share, and
whether the unlabelled distant trucks (still drawn in the frame, no box) act as background noise.
Both are testable with `bin/fit_max_annotation_distance.py` fitted to the size shares instead of
the median, then a re-render of one batch and a v7p-versus-new comparison.

#### Refit of the distance cutoffs to the size shares (`bin/fit_max_annotation_distance.py`)

The script now also reports, per class, the cutoff whose small / medium / large shares are closest to
the real BDD100K val shares (areas at 720 px height; 1 m steps, 15-150 m). 150 regenerated `train_v7p`
scenarios (config `urban_dense_v7_peds.yaml`; the script forces `parking_lot_fraction` 0.3, so this is
a close regeneration, not an exact replay: at the current 54 m it gives 30% small cars where the
dataset itself has 41%). Small / medium / large, percent:

| class | real | at the current cutoff | share fit |
|---|---|---|---|
| truck (n 363) | 18 / 43 / 39 | 0 / 47 / 53 (53 m) | 18 / 51 / 31 at 96 m |
| bus (n 114) | 17 / 41 / 42 | 0 / 29 / 71 (41 m) | 13 / 51 / 37 at 72 m |
| car (n 5707) | 44 / 38 / 19 | 30 / 51 / 19 (54 m) | 44 / 41 / 15 at 71 m |

Trucks and buses are the clear case: at the current cutoffs there are no small boxes at all, and the
share fit asks for about 96 m (truck) and 72 m (bus). Counts are small (363 and 114 boxes), so
the exact metres carry that uncertainty; the direction does not. Cars would also gain small boxes
(the regeneration under-counts them), so cars are left alone in a first test. Median fit (the old
method) gives person 28, car 43, bus 47, truck 64 m with this config: the old 53 m for trucks was
not even the median fit for this camera.

### v9a: label trucks and buses farther out (small-truck test), rules fixed before the render

Question: do small trucks missing from the training data cause the 63-67% miss rate on small real
trucks? `train_v9a` is `train_v7p` (same config `urban_dense_v7_peds.yaml`, profile v7, 256 scenarios,
seeds 70000-70255, same fleet) with only the labelling cutoffs changed, using the new
`--max-distance` flag: truck 80 m (v7p 53 m) and bus 60 m (v7p 41 m); cars and persons unchanged.
Choice of metres: the share fit above says 96 m (truck) and 72 m (bus), but the same regeneration
puts cars at 30% small at their 54 m where the dataset itself has 41%, so the dataset's boxes are
about 1.2x smaller in distance terms than the regeneration's (modal boxes, probably); dividing by that
gives about 80 m and 60 m. This is one class's calibration applied to two others, so the batch's own
small share is measured before any training (target 18% small for trucks, 17% for buses, within
about 5 points); if it is off, the cutoffs are adjusted and the batch re-rendered before training.
Arms: `hpc_v9a25` (25% real, AdamW, 3 seeds) against `hpc_v7p25`.

Rules: (1) a lever if truck AP rises by at least +1.0 over v7p25 on BDD100K val (p < 0.1 over 3
seeds); (2) guardrails: overall, car and person AP not down by more than 0.5; (3) the per-box
outcome check must show small-truck misses falling (the cause, not only the effect): small
trucks missed below 63% (v7p25) and "correct" above 4%. If AP moves but small-truck misses do not,
the gain came from something else and is not read as support. If neither rule 1 nor 3 is met, small
trucks are closed as a lever too, leaving truck appearance (box, dump and garbage trucks) as the
remaining one. Bus AP is reported (1-2 AP noise).

#### v9a batch statistics (measured before training, as the rule required)

512 frames, 0 rejected, calibration 0.55 px. Small / medium / large shares (1280x720 areas), real
BDD100K val in brackets: truck 20 / 53 / 28 [18 / 43 / 39] on 329 boxes (v7p 3 / 55 / 42 on 214);
bus 11 / 51 / 39 [17 / 41 / 42] on 85 boxes (v7p 0 / 44 / 56 on 55). Cars (4,076 boxes, 41 / 40 / 19) and
persons (1,690, 55 / 39 / 6) are identical to v7p, so the comparison changes only the truck and bus
labels. Trucks per image 0.64 (v7p 0.42), buses 0.17 (0.11). The truck small share is within the
5-point tolerance (20 against 18); the bus small share is 6 points under (11 against 17) on only 85
boxes, about the sampling noise of that count, so the batch is accepted without re-rendering. The
large-truck share is lower than real (28 against 39) because the added boxes are all distant.

### v9a result: labelling trucks and buses out to 80 m and 60 m did not raise truck AP (rule 1: no)

`hpc_v9a25` (3 seeds) against `hpc_v7p25`, BDD100K val: truck AP 15.74 against 16.12 (-0.38,
p = 0.48); bus 12.59 against 13.51 (-0.92); overall AP 20.65 against 20.99 (-0.34, p = 0.32); car 38.11
(0.00); person 16.16 (-0.07); night AP 17.71 (-0.18). Cityscapes: truck 15.36 against 14.41 (+0.95,
p = 0.67, seed spread 2.7), bus +1.5, AP +0.41, person -0.45 (p = 0.10), car -0.37 (p = 0.12); nothing
there is distinguishable from noise. Rule 1 (truck AP +1.0 on BDD100K): not met; guardrails hold.
Rule 3 (small-truck misses must fall, the per-box check) is read when the per-box files for v9a are in;
until then the cause is not settled, since AP is a mix of small and larger boxes.

#### v9a per-box outcomes (rule 3): small-truck misses did not fall

BDD100K val, 3 seeds, confidence 0.25, `hpc_v9a25` against `hpc_v7p25` (percent of boxes).
Small trucks (730 boxes): correct 4.7 (v7p 4.2), missed 63.4 (63.0), mislabelled 21.1 (23.1), low
confidence 10.8 (9.7). Small buses (267): correct 2.0 (0.7), missed 64.8 (64.8). Medium and large
trucks and buses move by one or two points either way (large trucks correct 41.0 against 42.1; large
buses 41.9 against 39.5), within the seed spread. Rule 3 asked for small-truck misses below 63% and
correct above 4%: missed is 63.4%, so it is not met.

Reading: putting 20% small trucks (and 11% small buses) into the training data, matching the real
share, changed neither the small-box outcomes nor AP. Together with v8a and v8b this closes three
generator levers for trucks and buses with Epic's own models: the vehicle mix (v8a), labelling
pickups and vans as trucks (v8b), and the size distribution of the boxes (v9a). Small real boxes of
every class are hard for this detector (real-only: small cars 42% correct, small persons 14%,
small trucks 2%), so the small-truck miss rate looks like a resolution and visibility limit of the
detector at 960 px, not a gap in what the synthetic data shows. Not tested: a higher training image
size (this changes the detector, not the generator), and truck appearance (box, dump and garbage
trucks), which needs models City Sample does not have.

### v10n: the same batch with no synthetic pedestrians (insurance against the Epic ruling)

Why: Epic's EULA restricts training or testing AI on MetaHuman characters or renders of them, and City
Sample's crowd is adapted from MetaHumans (see the README status note). If Epic rules that the crowd
cannot be used, every result that depends on synthetic pedestrians is in question. This batch asks how
much of the vehicle results needs the crowd at all.

`train_v10n` is `train_v7p` with `pedestrian_density_fraction` 0 (`urban_dense_v7_nopeds.yaml`; the
test checks that this is the only config difference), 256 scenarios, seeds 70000-70255, same labelling
cutoffs. Checked before rendering: for seeds 70000-70003 all 1,468 vehicles are identical to the v7p
scenarios (position, model, heading), and pedestrians are 0 against about 300 per scenario, so the
only change in the scene is the missing crowd. Arm `hpc_v10n25` (25% real, AdamW, 3 seeds) against
`hpc_v7p25`.

Reading rules, fixed first: (1) vehicle results stand without the crowd if car and truck AP on BDD100K
val are each within 0.5 of v7p25 (bus is reported, noise 1-2 AP); (2) person AP is expected to fall
(the supply test showed person AP follows the number of synthetic persons), and is reported as the size
of the crowd's contribution, not a failure; (3) overall AP is reported with the person drop explained,
not read as a vehicle effect. If rule 1 holds, the vehicle findings of 1.1 (the closed levers) and the
car gain from synthetic data stay publishable without the pedestrians. If a car gain over real-only
disappears, the crowd was helping vehicles too, and that is a finding on its own.

### Resolution test (imgsz 1280 against 960), rules fixed before the jobs

Why: the per-box check shows 63-67% of small real trucks and buses missed in every arm, and v9a showed
that adding small synthetic trucks does not change that. If the limit is the detector's input size,
small real boxes (a COCO-small box is under 32 px at the 1280-wide source; at imgsz 960 it is shrunk
to 24 px or less) should be found more often at 1280 for every class, with or without synthetic data.

Arms: `hpc_real25r_i1280` (460 real images, `real_25pct`) and `hpc_v7p25_i1280` (`mixed_25pct_v7p`),
imgsz 1280 for training and evaluation, AdamW, 200 epochs, seeds 0-2, otherwise the recipe of the 960
arms `hpc_real25r` and `hpc_v7p25`. BDD100K val and Cityscapes val, then the per-box check at 1280.

Rules: (1) imgsz is a lever for small boxes if small-truck "correct" rises from 4% by at least 5 points
in either arm, and small-car correct (42% real-only) rises too, so the cause is the input size and not
something truck-specific; (2) overall, truck and bus AP are read for the same pair of arms, in each arm
against its own 960 run, so the size effect is separated from the synthetic effect; (3) the synthetic
gain (v7p25 over real25r) is compared between 960 and 1280: if it shrinks at 1280, part of what
synthetic data adds at 960 is resolution the detector lacks, and that is a finding for the README's
claims about it. The cost (about 1.8x memory and time per job) is reported. If nothing moves, input
size is closed too, and the remaining explanation is the appearance of the objects, not their pixels.

#### v10n batch statistics (measured before training)

512 frames, 0 rejected, calibration 0.54 px. Boxes: 0 persons (v7p 1,690), 214 trucks and 55 buses
(identical to v7p), 4,123 cars (v7p 4,076; the 47 extra are cars that pedestrians stood in front of
in v7p and that now pass the visibility threshold). The YOLO label files hold no class-0 lines. The
batch is the v7p scenes minus the crowd, as intended.

### Resolution test result (imgsz 1280 against 960): AP side, per-box side still to come

12 new result files (`hpc_real25r_i1280`, `hpc_v7p25_i1280`, 3 seeds, BDD100K and Cityscapes). All six jobs
completed without memory problems (real-only 1 h 14 min, v7p 2 h 13 min each). Baselines are the 960 arms
`hpc_real25` (identical to the retrained `real25r`) and `hpc_v7p25`. BDD100K val, mean of 3 seeds:

| AP | real 960 | real 1280 | v7p 960 | v7p 1280 | synthetic gain at 960 / 1280 |
|---|---|---|---|---|---|
| overall | 18.23 | 19.27 | 20.99 | 21.38 | +2.77 / +2.11 |
| person | 12.41 | 14.43 | 16.24 | 17.82 | +3.83 / +3.39 |
| car | 36.35 | 38.11 | 38.11 | 39.45 | +1.76 / +1.34 |
| bus | 10.13 | 10.84 | 13.51 | 12.04 | +3.38 / +1.20 |
| truck | 14.02 | 13.72 | 16.12 | 16.21 | +2.10 / +2.49 |

For v7p, 1280 against 960: person +1.58 (p = 0.039), car +1.34 (p = 0.014), truck +0.10 (p = 0.80),
bus -1.47 (p = 0.15), overall +0.38 (p = 0.24), night AP -0.40. Cityscapes shows the same direction:
person +1.71 (p = 0.009), car +1.10 (p = 0.003), truck -1.90 (p = 0.27, seed spread 0.6 to 2.2).

Reading, AP only (rule 1 needs the per-box small-truck numbers, not yet in): larger input size raises
person and car AP by 1-2 points in both arms, so small persons and cars were resolution-limited at 960.
Truck AP does not move (real-only 14.02 to 13.72, v7p 16.12 to 16.21) and bus does not improve, so
resolution is not what limits trucks at the AP level. Rule 3: the synthetic gain shrinks at 1280 for
overall AP (+2.77 to +2.11), car (+1.76 to +1.34) and bus (+3.38 to +1.20, noisy), and holds for person
(+3.83 to +3.39) and truck (+2.10 to +2.49). So about a quarter of what synthetic data adds overall at
960 is resolution that a larger input recovers for free; the README's synthetic gain should be stated at
both sizes. Cost: 1280 takes about 1.8x the time of 960.

#### Resolution test, per-box side (rule 1)

BDD100K val, 3 seeds, confidence 0.25; percent of boxes, 960 then 1280.

| small boxes | real-only correct | real-only missed | v7p correct | v7p missed |
|---|---|---|---|---|
| truck (730) | 2.3 to 5.2 | 66.8 to 57.8 | 4.2 to 8.6 | 63.0 to 57.4 |
| bus (267) | 1.9 to 4.0 | 66.0 to 57.9 | 0.7 to 1.9 | 64.8 to 60.2 |
| car (43,680) | 41.9 to 48.2 | 35.0 to 28.4 | 46.4 to 49.5 | 32.7 to 26.9 |
| person (6,377) | 14.2 to 21.9 | 59.0 to 52.0 | 22.4 to 26.0 | 52.6 to 48.2 |

Rule 1 asked for small-truck correct to rise by at least 5 points from about 4% in either arm, and small
cars to rise too. Cars do (+6.3 real-only, +3.1 v7p), trucks rise by +2.9 and +4.4: the letter of the rule is
not met (it needed +5), but the direction is the one the resolution reading predicts, and the effect is
the same size on every class: small boxes are missed 5-9 points less often at 1280, in both arms, for
trucks, buses, cars and persons. Larger boxes do not gain: large trucks +3.0 for v7p but -4.1 real-only,
large buses -6.8 for v7p, so the extra input size is not a uniform gain for trucks and buses. The
mislabel rate (about 28-30% of trucks, 34-38% of buses) does not move with resolution.

Reading: input size trades some small-box misses for found-but-low-confidence or mislabelled boxes,
which is why truck and bus AP do not move although small cars and persons gain. The truck/bus gap is two
things, neither of which the generator's mix, labels, box sizes or the image size changes: small boxes
that are hard for every class, and a car/bus/truck appearance confusion that is the same in the
real-only arm. The remaining lever is the appearance of trucks themselves (box, dump and garbage
trucks, pickups), for which City Sample has no models.

### Box-truck pilot (Vehicle Variety Pack Volume 2), plan and rules fixed first

Why: every generator lever for trucks and buses is closed (mix v8a/v8b, size distribution v9a, input size at
1280), and the per-box check shows about 30% of medium and large trucks called cars with the same rate in
the real-only arm. The one lever left is what trucks look like: the real truck population is box, dump and
garbage trucks, and City Sample has one 3-axle truck (vehicle11) and a tractor-trailer cab.

Source: the Delivery box truck of Vehicle Variety Pack Volume 2 (Fab, free; "Allows usage with AI: No", the
same class as City Sample's vehicles; evidence in demo/LICENSING_EVIDENCE.md, not committed). Structure read
from the files: one static mesh `SM_BoxTruck_01a` (4 MB) with exterior, detailing, two interior and glass
sections, three exterior colour variants, and a skeletal version whose wheels are bones. Integrated as one
piece (wheels part of the body), unlike the City Sample vehicles, whose wheels and doors are separate meshes.

Steps, each checked before the next: (1) import into a new folder of a copy of the project and verify no
existing asset changed (hash the existing Content tree before and after); (2) measure its size and ground
contact and add a bounds entry; (3) render a handful of frames to check it looks like a box truck on the
road, at the right scale and orientation; (4) a fleet option `v11` that adds it to the truck pool (weight
chosen from the evidence for the box-truck share of real trucks, not guessed; none exists yet), everything
else as v7p, 256 scenarios, seeds 70000-70255; (5) `hpc_v11_25`, 25% real, AdamW, 3 seeds, against
`hpc_v7p25`.

Rules: (1) the box truck is a lever if truck AP rises by at least +1.0 on BDD100K val (p < 0.1) with overall,
car and person AP not down by more than 0.5; (2) the per-box check must show truck mislabelling (28-30% in
every arm) falling, not only AP rising; (3) if neither holds, appearance of one added model is not enough
and the truck work for 1.1 ends with the closed levers recorded above. One model is a thin test: a null
result is read as "one box truck does not do it", not as "appearance does not matter".

#### Box-truck pilot: integration checked, comparison arm fixed

Done: the pack's box truck (meshes, skeleton, materials and textures of the truck only, 44 files, 427 MB) is
copied into `Content/VehicleVarietyVol2` of `VantageCV_UE5` with the editor closed; a before/after listing of
all 7,299 existing Content files (size and modified time) is identical, so no existing asset changed. It
loads in the game; measured live: 5.47 m long, 2.71 m wide, 2.87 m high, wheels on the ground. Rendered on
the road from four sides it looks like a white delivery step-van, correct way round and at a believable
scale (frames in `demo/boxtruck/`, not committed). A 10-scenario probe with the v11 config rendered through
the full pipeline (20 frames, none rejected, calibration 0.51 px) with box trucks labelled truck. Real
sizes against what is in the data: the 3-axle City Sample truck (vehicle11) is a refuse (garbage) truck, so
the box and delivery trucks that are about 30% of real BDD100K trucks have, until now, been represented by
a garbage truck and tractor-trailers.

Fleet `v11` (config `urban_dense_v11.yaml`, which is `urban_dense_v8a.yaml` with the fleet changed): trucks
10% rig, 60% garbage truck, 30% box truck. It differs from `v8a` only in the box truck, so the comparison is
`hpc_v11_25` against `hpc_v8a25` (same scenes, seeds 70000-70255, mix and pedestrians); `hpc_v7p25` is
the second comparison. This replaces "everything else as v7p" in the plan above, which would have mixed
the box truck with the v8a mix change.

Caveats known before the result: the box truck's labels are the projected measured box (it has no
occlusion mesh, unlike the City Sample vehicles, whose labels are refined against their meshes), so
they are a little looser; its wheels are part of the body; and only the pack's default paint is used (white),
the pack's other two exterior colours are not wired. Rules as above, now against `hpc_v8a25` first.

### v10n result: the vehicle results stand without the crowd; the crowd is where the person gain comes from

`hpc_v10n25` (v7p scenes and vehicles, no synthetic pedestrians; 3 seeds, 25% real, AdamW) against
`hpc_v7p25` and the real-only arm `hpc_real25`, BDD100K val, mean of 3 seeds:

| AP | real-only | v7p25 | v10n25 | v10n minus v7p25 | gain over real-only: v7p / v10n |
|---|---|---|---|---|---|
| overall | 18.23 | 20.99 | 19.80 | -1.19 (p = 0.022) | +2.77 / +1.58 |
| person | 12.41 | 16.24 | 13.27 | -2.97 (p = 0.002) | +3.83 / +0.86 |
| car | 36.35 | 38.11 | 38.19 | +0.08 (p = 0.52) | +1.76 / +1.84 |
| truck | 14.02 | 16.12 | 16.02 | -0.09 (p = 0.77) | +2.10 / +2.01 |
| bus | 10.13 | 13.51 | 11.74 | -1.77 (p = 0.12) | +3.38 / +1.61 |
| night AP | 15.34 | 17.88 | 16.93 | -0.95 (p = 0.023) | |

Cityscapes: person -2.93 (p = 0.007), car -0.02, truck -0.41 (seed spread up to 2.2), bus +1.07, overall AP
-0.57 (p = 0.12).

Rules as logged before the render: (1) car and truck AP within 0.5 of v7p25: car +0.08 and truck -0.09,
met; (2) person AP expected to fall, reported as the crowd's contribution: -2.97, of the +3.83 the
v7p batch added over real-only about three quarters; (3) overall AP is read with the person drop
explained: the -1.19 overall is mostly the person class (a quarter of the classes at -3 AP) with night AP
following. Bus is reported only: -1.77 (p = 0.12) is inside its 1-2 AP noise, and its gain over real-only
is smaller without pedestrians (+1.61 against +3.38), which is not read as a crowd effect.

Reading: every vehicle finding of 1.1 (the closed levers for trucks and buses, the car gain from
synthetic data, the 1280 comparison) stands without the MetaHuman-derived crowd; the car gain over real-only
is identical with and without it (+1.84 against +1.76), and so is the truck gain (+2.01 against +2.10). What
the crowd contributes is the person gain (+3.83 to +0.86). If Epic rules the crowd cannot be used, the
published claims narrow to vehicles, and the person results would need a replacement pedestrian source
(Rocketbox pilot, with a realism check) to be reproduced. The +0.86 person gain remaining without any
synthetic persons is inside the roughly 0.4 seed spread of two arms plus whatever the road, lots and
vehicles teach the person class; it is not explained here.

#### v11 batch statistics (measured before training)

512 frames, 0 rejected, calibration 0.51 px; the tar is 1.44 GB. Against `train_v8a` (same scenes and seeds):
cars 4,127 against 4,120, persons 1,689 against 1,689 (identical), buses 83 against 82, trucks 167 against
157 (0.33 per image, 0.31 in v8a; the 0.39 target is still missed for the rig reason logged under v8a).
Truck size shares (small / medium / large, 1280x720 areas): 13 / 55 / 32 against 3 / 58 / 39 in v8a: the
box truck is a smaller vehicle than the garbage truck and the rig, so the batch also has more small
trucks. That is a second change riding on the first: the v9a test showed that small trucks alone do not
move truck AP, so it is not expected to matter, but a positive result is read with it in mind.

### v11 result: adding a box truck (30% of trucks) did not raise truck AP (rule 1: no)

`hpc_v11_25` (v8a scenes and mix, 30% of trucks drawn from the Vehicle Variety Pack box truck; 3 seeds,
25% real, AdamW). BDD100K val, mean of 3 seeds, against `hpc_v8a25` (the comparison fixed in the plan) and
`hpc_v7p25`:

| AP | v8a25 | v11_25 | v11 minus v8a25 | v11 minus v7p25 |
|---|---|---|---|---|
| truck | 15.62 | 15.31 | -0.31 (p = 0.65) | -0.81 (p = 0.23) |
| overall | 20.65 | 20.62 | -0.03 (p = 0.92) | -0.37 (p = 0.22) |
| car | 38.24 | 38.15 | -0.09 (p = 0.59) | +0.04 (p = 0.83) |
| person | 16.42 | 16.14 | -0.28 (p = 0.49) | -0.10 (p = 0.79) |
| bus | 12.34 | 12.90 | +0.56 (p = 0.52) | -0.61 (p = 0.46) |
| night AP | 17.27 | 17.57 | +0.30 (p = 0.36) | -0.31 (p = 0.34) |

Cityscapes: truck 12.06 against 13.09 (v8a25), -1.03 (p = 0.39, seed spread 1.3), overall AP -0.44.

Rule 1 (truck AP +1.0 over the comparison, guardrails within 0.5): not met, the truck difference is
-0.31 against v8a25 and -0.81 against v7p25, and every guardrail is within 0.3 of v8a25. Rule 2 (the
per-box check must show mislabelling falling) only applies when AP rises, so it is not read. Rule 3
applies: one box truck is not enough, and it is not a proof that appearance does not matter. The batch
also carried more small trucks (13% against 3%), which v9a had already shown not to matter.

Summary of the truck and bus work of 1.1: five generator levers tested with rules written first, none
raised truck AP: the vehicle mix (v8a), pickups and vans labelled truck (v8b), the box-size
distribution (v9a), the input size (1280), and a real box-truck model (v11). The per-box outcomes explain
what is left: about 30% of medium and large trucks are called cars in every arm including the real-only
one, and small boxes are missed by every class. The pedestrian-free arm (v10n) shows that none of this
depends on the MetaHuman-derived crowd. What remains open is a larger and more varied truck population
(dump, utility and delivery trucks of several makes), which needs more than one added model.

### CARLA side project, step 1: how a detector trained on VantageCV data sees CARLA's vehicles

Context: CARLA 0.9.16 (UE4.26, Town10HD, 40 other vehicles) is being set up as a closed-loop test of whether a
perception gain changes driving (`carla_loop/`, separate from the generator, no VantageCV code touched). Step 0
is the ground-truth baseline: CARLA's BasicAgent with exact knowledge of every vehicle drove 3 routes (1.24 km)
with 0 collisions, all 3 reached the goal (`results/carla/baseline_gt.json`). Anything that goes wrong later
is therefore perception.

Step 1 (this entry) asks how well the two trained detectors find CARLA's vehicles from a front camera
(1280x720, 90 degree field of view, depth-checked for visibility), with the agent still driving on ground truth.
Weights: `hpc_real25r` seed 0 and `hpc_v7p25` seed 0, one weights file each; 3 routes of 60 s, 3,603 frames per
detector, same routes. A true vehicle within 50 m and visible counts as found if a vehicle box overlaps it at
IoU 0.5. Nothing is tuned to CARLA.

| kind, distance | true | found, real-only | found, v7p | called, real-only | called, v7p |
|---|---|---|---|---|---|
| car 0-15 m | 2,804 | 91% | 97% | car 80%, truck 20% | car 100% |
| car 15-30 m | 1,727 | 82% | 93% | car 98% | car 100% |
| car 30-50 m | 1,907 | 75% | 84% | car 100% | car 100% |
| truck 0-15 m | 84 | 81% | 43% | truck 60%, car 29% | truck 58%, car 25% |
| truck 15-30 m | 83 | 75% | 86% | truck 74%, car 15% | truck 46%, car 45% |
| truck 30-50 m | 124 | 76% | 82% | car 62%, truck 21% | car 78%, truck 19% |
| van 0-15 m | 64 | 84% | 73% | truck 63%, car 35% | truck 43%, car 34% |
| van 30-50 m | 232 | 52% | 62% | car 96% | car 99% |

Reading: on CARLA's cars the synthetic supplement finds 6-9 points more vehicles at every distance (97 / 93 /
84% against 91 / 82 / 75%), the same direction as the real-photo AP gain, in a third visual domain. Trucks
are where the detectors disagree and where each is weak: at 30-50 m most trucks are called cars by both
(62% and 78%), and at 15-30 m the synthetic arm calls 45% of trucks cars against 15% for the real-only arm,
the same medium-range truck-as-car confusion the per-box check found on real photos. Counts for trucks are
small (84, 83 and 124 true trucks) and each row is one weights file on 3 routes, so differences of 10
points or so between the two detectors are not interpreted; the car rows (about 2,000 per row) are.
Unmatched vehicle boxes are not reported: Town10's parked cars are static map props, not vehicles in the
simulator's list, so the detector finds objects that have no ground truth.

Step 2 (next, rules fixed first): put each detector in the driving loop (detections plus depth become the
agent's only view of other vehicles; heading assumed to be the ego's own, sizes fixed per class) and compare
collisions per kilometre and route completion on the same 20 routes and seeds. The ground-truth agent is
the ceiling (0 collisions). A difference between the detectors is read as an effect only if the collision
counts differ by a factor of two or more and by at least 5 events over the 20 routes; anything less is
reported as "no detectable effect at this sample size". Known approximations: the agent only brakes for
vehicles (no pedestrians are spawned), and the detections replace the simulator's list but the agent keeps
reading true traffic lights.

#### CARLA step 2: secondary metric added before any result

After seeing the car jerk in the server window, a count of hard-brake events was added to each episode
(`hard_brake_events`: the agent's emergency stop, a brake of 0.5 or more, counted when it starts, and
`hard_brake_seconds`), as a secondary metric of how steady the detector's view is. The primary metric is
still collisions per kilometre, with the rule above unchanged. The spectator camera now follows every
step (it jumped every half second, which made the car look jerky on screen; it has no effect on results).
The three episodes run before this change were discarded and are re-run.

### CARLA step 2 result: with the detector as the car's eyes, collisions rise from 3 to 10-14 over 20 routes; the two detectors cannot be told apart

20 routes (Town10HD, 40 other vehicles, 30 km/h target, 150 s cap), each driven by the ground-truth agent and
with each detector (`hpc_real25r` seed 0 and `hpc_v7p25` seed 0, one weights file each) as the agent's only view
of other vehicles (`results/carla/driving.json`, `carla_loop/compare.py`). Same agent, routes, seeds and traffic
seeds in all three arms.

| arm | reached | stuck | collisions | per km | routes with a collision | hard-brake events per km |
|---|---|---|---|---|---|---|
| ground truth | 18 | 2 | 3 | 0.46 | 3 | 264 |
| real-only detector | 17 | 3 | 14 | 2.21 | 7 | 177 |
| v7p detector | 18 | 2 | 10 | 1.54 | 7 | 208 |

Total distance 6.3-6.5 km per arm. Every collision in every arm is with another vehicle.

Rule as logged before the run: a difference between the detectors is read as an effect only if collision counts
differ by a factor of two or more and by at least 5 events. They are 14 and 10 (a factor of 1.4, a difference
of 4), and 7 routes each: the rule is not met, so the result is "no detectable effect between the detectors at
this sample size". The difference is also one route: seed 11 holds 5 of the real-only arm's 14 collisions (and
a stuck run) against 1 for v7p; without it the two arms have 9 and 9. On routes the two arms agree too: each has a collision on 7 routes, 6 of them the same (6, 9, 10, 11, 14, 17);
routes 2 and 7 differ.

What the run does show, outside the rule, since it is a comparison with the ceiling: replacing exact knowledge
of other vehicles with either detector raises collisions from 3 to 10 or 14, a factor of 3 to 5 and a
difference of 7 to 11 events, all with vehicles. So perception errors are what the agent crashes on, and a
detector with about 3 AP points more on real photos (v7p25 against real-only, +2.8) does not, on these routes, change
that. The hard-brake count does not support the flicker explanation for the jerky motion: the detector arms
brake less than ground truth (177 and 208 against 264 per km), probably because ground truth reacts to every
vehicle, including ones the camera cannot see. Two routes (3, 16) are stuck in all three arms, so they are route
or agent problems, not perception.

Caveats: one weights file per detector; 20 routes in a single town; the detectors were never trained on CARLA
frames (a different look from the training data); collisions cluster on a few routes; the agent assumes every
detected vehicle is heading the way the ego is and has no tracking, so a missed vehicle in one frame is a
missed vehicle for that step. What would settle it: more routes and detector seeds (the v7p25 and real25r seeds
1 and 2), and a collision breakdown by what kind of vehicle was hit (truck, van, car) to connect it back to the
truck and bus findings. Neither is done.

#### CARLA step 2, extension: the other two weights seeds of each detector (plan, before the run)

Why: the first run used seed 0 of each detector, so one training seed could be luck (the AP spread between
seeds of one arm is 0.3-0.5, comparable to the effect being looked for). Same 20 routes, agent and traffic
seeds; `real25r` and `v7p25` seeds 1 and 2 are added to the same results file, so each detector has 3 weights
x 20 routes = 60 route-runs and the ground-truth arm stays as it is (20 routes).

Rule, unchanged from above and applied to the pooled totals per detector: the detectors differ if their collision
counts differ by a factor of two or more and by at least 5 events; otherwise no detectable effect at this sample
size. Also reported, as descriptive and not as a rule: per-weights-seed collisions (to see whether any one
seed drives a total), the share of routes with a collision, and what kind of vehicle was hit (car, van, truck,
bus, by the simulator's own vehicle type), to connect the result back to the truck and bus findings.

### CARLA step 2, extended result: three weights seeds per detector, 20 routes each (rule applied to the pooled totals)

`results/carla/driving.json` now holds 140 episodes: ground truth (20 routes) and `real25r` and `v7p25` weights
seeds 0, 1 and 2, each on the same 20 routes (60 route-runs per detector). The CARLA server crashed twice during the
run (a restart loop resumed it each time; every finished episode was kept, none lost or repeated).

| arm | route-runs | reached | stuck | km | collisions | per km | with a collision | hard brakes per km |
|---|---|---|---|---|---|---|---|---|
| ground truth | 20 | 18 | 2 | 6.5 | 3 | 0.46 | 3 | 264 |
| real-only, 3 weights seeds | 60 | 53 | 7 | 19.3 | 35 | 1.81 | 21 | 175 |
| v7p, 3 weights seeds | 60 | 53 | 7 | 19.3 | 29 | 1.50 | 20 | 170 |

Per weights seed (collisions): real-only 14 / 10 / 11, v7p 10 / 9 / 10. The v7p detector has the same or fewer
collisions than the real-only one at each seed, by 0 to 4.

Rule (set above, before the extension): the detectors differ if collision counts differ by a factor of two or
more and by at least 5 events. Pooled they are 35 and 29: a factor of 1.2 and a difference of 6. The factor is
not met, so there is no detectable effect between the detectors at this sample size. The gap lies on two
routes: routes 11 (8 against 3) and 2 (2 against 0) hold 10 of the real-only arm's 35 collisions and 3 of v7p's
29; on the other 18 routes the totals are 25 and 26.

Against the ceiling: either detector raises collisions from 3 (0.46 per km) to 29-35 (1.5-1.8 per km), a factor of
3 to 4 even after the pooling, and 20-21 of 60 route-runs have a collision against 3 of 20 for ground truth.
What was hit (by the simulator's own vehicle type): real-only car 12, truck 8, van 4, no type recorded 11;
v7p car 11, truck 5, van 4, no type recorded 9; trucks and vans together are 12 of the 35 and 9 of the 29
(about a third), which this entry does not compare with their share of the traffic, so it is not read as
trucks being over-hit. The 11 and 9 untyped collisions (a vehicle model with no base type in the blueprint
library) are not classified.

Reading: in this setup the gains that show on real photos (about 3 AP overall, 6-9 points of car recall in CARLA
frames) do not show as a detectable change in driving; both detectors drive about 3 to 4 times worse than the
agent with exact knowledge, and what separates them from it is a handful of routes where a vehicle is missed or
placed wrongly. Not established: whether more routes would separate them (the sign is in v7p's favour on
every weights seed, and the sample is too small for the rule); whether a detector trained on CARLA frames, with
tracking, or with a better heading estimate would close the gap to ground truth (that is the next obvious
change, and a different experiment).

### 1.2 plan: 3D box export (KITTI format) and instance / semantic masks, with the checks fixed first

Not an AP experiment: a feature whose correctness is checked geometrically, before it is written. Scope
change from the roadmap: KITTI-format labels and calibration, and a camera-frame `box3d` field in every COCO
annotation, are in 1.2; nuScenes- and Waymo-style files need ego poses and sequence tables the generator does
not have (frames are single scenes), so they are left out and the roadmap is corrected rather than faked.

Conventions: this project's camera frame (x right, y down, z forward, `p_cam = R (p_world - t)`) is KITTI's
camera frame. KITTI's `location` is the bottom centre of the box, `dimensions` are height, width, length,
`rotation_y` is the heading about the camera's down axis (an object that moves away from the camera along its
line of sight has rotation_y of -pi/2), and `alpha` is rotation_y minus the viewing angle atan2(x, z).

Checks, all automatic, none involving a detector:
1. Round trip: from the exported `location`, `dimensions` and `rotation_y` alone, rebuild the 8 corners with the
   KITTI devkit formula and project them with the exported calibration matrix; they must equal the projection of
   the original `BoundingBox3D` corners to within 1e-6 px on every exported object of rendered scenarios (the
   formula is written separately from the exporter, in the test).
2. Hand-built cases: a vehicle straight ahead, heading away, gives rotation_y = -pi/2 and alpha = -pi/2; a vehicle
   to the camera's left and right gives alpha different from rotation_y by the viewing angle; heading reversed
   shifts both by pi.
3. Each label line has exactly 15 fields (16 with a score), numeric where KITTI says so; calibration files
   hold P0-P3, R0_rect and Tr matrices of the right shapes.
4. Masks: instance and semantic PNGs, objects drawn far to near by camera depth, so a nearer object covers a
   farther one; pixel count of an unoccluded instance within 2% of its polygon's area.
Not claimed: anything about detector accuracy; masks are polygon-based (mesh silhouettes where a real mesh
exists, box hulls otherwise), not render-pass pixel-exact masks (that needs a UE capture pass, a later step).
Limits stated up front: KITTI's rotation_y assumes a level camera; for a pitched camera the heading is the
projection onto the camera's x-z plane. `occluded` is derived from visibility_fraction (0: above 0.9; 1: above
0.6; 2: otherwise), a mapping this project chose. Bus maps to `Misc` (KITTI has no bus class). The
`Tr_velo_to_cam` and `Tr_imu_to_velo` entries are identity placeholders (no LiDAR is generated).

#### 1.2 result: the checks fixed above, all passed

1. Round trip (rule: equal to within 1e-6 px): met. 15 hand-built level-camera cases (3 positions x 5 headings), 3
   pitched cameras (3, 8 and 15 degrees), and more than 20 exported objects from generated scenarios viewed
   from a camera tilted down about 4 degrees, all reproduce the original corner projection from the exported
   `location`, `dimensions` and `rotation_y` alone, using the KITTI devkit's corner formula and the exported
   projection matrix. A first version wrote the label in the camera's own frame, and measured against a pitched
   camera it was off by up to 30 px (8 degrees, 10 m, 2D rectangle IoU 0.67); the level frame with
   `P = K R R_level^T` removed that error, which is why the export is in the level frame.
2. Hand-built cases: met (rotation_y = -pi/2 and alpha = -pi/2 for a car driving straight away, flipped by pi for
   the opposite heading, alpha = rotation_y - atan2(x, z) off axis).
3. Text formats: met (15 fields, 16 with a score; calibration with P0-P3, R0_rect, Tr_velo_to_cam, Tr_imu_to_velo of
   12, 12, 12, 12, 9, 12, 12 numbers).
4. Masks: met on a real frame. 11 of 11 instances present; for the three largest unoccluded objects the mask pixel
   count is 1.003 to 1.006 times the polygon area (rule: within 2%); nearer objects cover farther ones.

Real render: 6 scenarios from the game (12 images, calibration 0.54 px) exported to a KITTI folder: 131 boxes, 0
skipped, labels such as `Car 0.00 2 1.96 ... 1.54 1.99 5.40 -9.21 1.63 16.04 1.44` (the box bottom 1.63 m below the
camera, a 5.4 m long car 16 m ahead). Drawing the exported 3D boxes back onto the images with the exported
calibration puts every box on its vehicle (cars, the semi-trailer, pedestrians), heading included (checked by eye
on four images; the overlay is not committed).

Not claimed: nothing about detector accuracy, and the masks are polygon-based, not render-pass pixel-exact.
KITTI's bus class does not exist, so buses are written as `Misc`. nuScenes- and Waymo-style files are not written
(they need ego poses and sequence tables the generator does not have). Overview (top-down) cameras get no 3D
labels, since KITTI has no frame for them.

#### 1.2 correction: the "semantic" mask is an object-class mask, not full-scene segmentation

The 1.2 mask export paints only the labelled objects (person, car, bus, truck); everything else, including road,
sidewalk, buildings, vegetation and sky, is 0. Full semantic segmentation (Cityscapes style) labels every pixel, so
the name overclaimed. It is now described as an object-class mask in the README, the code and the roadmap. Full-scene
labels need either a Unreal custom-stencil capture pass (pixel-exact; needs the same untested D3D11 capture spike as
depth, estimated 4 to 6 days) or rasterising the generator's own road and building geometry (approximate, and
vegetation and sky have no geometry in the labels). Neither is built.

### Matched comparison with another synthetic dataset (SHIFT), plan and rule fixed before any data

Question (roadmap step 3, first control): does this pipeline matter, or does any 512-image synthetic supplement
add the same AP? `hpc_v7p25` (25% real BDD100K + the 512 `train_v7p` images, AdamW, 200 epochs, imgsz 960, three
seeds) is compared with the same recipe on 25% real + 512 images of SHIFT (Sun et al., CVPR 2022), a
CARLA-rendered driving dataset with 2D boxes, chosen because it has pedestrians, cars, trucks and buses (Virtual
KITTI 2 has no pedestrians or buses) and a 1 fps image release.

Data: the `front` camera, `img` and `det_2d` groups, discrete-shift images (1 fps), from the SHIFT file server
(`download.py` in SysCV/shift-dev). 512 images are sampled with a fixed seed from the downloaded split; classes are
mapped to this project's four (pedestrian to person, car, bus, truck; other classes such as bicycle and motorcycle
are dropped, as in this project's own labels). The licence is CC BY-NC-SA 4.0 for the data (the MIT licence in
the repository is for its code): research use only, nothing built from it is released.

Rule: the pipeline is credited with a difference if `hpc_v7p25` exceeds the SHIFT arm by 0.5 AP or more on
BDD100K val overall (p below 0.1 over three seeds); if SHIFT is ahead by 0.5 or more, SHIFT's data is better for
this task and the generator has something to learn from it; if the two are within 0.5, the AP gain is not specific
to this generator at this size, and what the City Sample renders add is not shown by AP. Per class (person, car,
truck, bus) and Cityscapes are reported but do not decide.

Known confounds, stated before the result: SHIFT's images are CARLA's UE4 render at a different resolution and
camera; its label conventions (what counts as truck, how occluded boxes are drawn) are its own; its weather and
time-of-day mix and its object counts per image differ from `train_v7p`. The count of boxes per class in the 512
images is reported next to the result, since the person and truck counts moved AP in the supply test. If the
class counts differ a lot, a second arm with the SHIFT images chosen to match the v7p person and truck counts is
worth running before reading the result.

#### SHIFT is not downloadable (2026-10-07)

The SHIFT file server (`dl.cv.ethz.ch`) and project page (`www.vis.xyz`) do not resolve, from this PC or from the
cluster. SysCV/shift-dev has open issues about it from 2025-02 to 2026-03 ("Project page is down", "download page and
file server return 502", "dataset download website not reachable"), with no mirror or answer. The matched comparison
above therefore cannot use SHIFT; the question and the rule stand, and the comparison dataset must change.

#### Matched comparison: RealDriveSim replaces SHIFT (amendment before any result)

RealDriveSim (Jadon et al., 2025; project page states CC BY 4.0, to be re-checked on the page itself) is already on this
PC: 133,820 front-camera frames at 2048x1024 with LiDAR, from another study. A COCO file with 7,539 of its images and
2D boxes exists (`F:\realdrivesim\train_coco.json`, made in that study from the raw label JSONs), and all 7,539
images are present under `Sensor_Fusion_Study/data/realDriveSim/raw/`. It replaces SHIFT; the question and the
reading rule above are unchanged.

What the labels are, stated before use: three classes only (car, pedestrian, truck); the dataset has buses (class
ids 4 and 47) that the COCO leaves out, and that study found 467 unlabelled buses in 454 of the 7,539 frames for
large buses near the frame edge alone, so the real number of frames with an unlabelled bus is larger. Boxes include
heavily occluded objects (median car visibility 0.57; 22% of cars under 20% visible), unlike this project's rule of
at least 10% visible. Density differs sharply from `train_v7p`: 9.1 pedestrians, 6.7 cars and 1.76 trucks per
image against 3.3, 8.0 and 0.4. Since person and truck counts moved AP in the supply test, a random 512-image
sample would not be a fair match.

Arms (each 25% real BDD100K + 512 RealDriveSim images, AdamW, 200 epochs, imgsz 960, three seeds):
 * matched (decides the rule): 512 frames chosen so the counts of persons, cars and trucks are within 10% of
   `train_v7p` (1,690 / 4,076 / 214), excluding every frame in which the raw labels contain a bus;
 * random (reported only): 512 frames at random, the same bus exclusion, with the raw counts reported.
Bus AP is not compared (the RealDriveSim arm has no bus labels). The rule is as logged above; it compares
`hpc_v7p25` with the matched arm.

#### Matched comparison: boxes only from the official RealDriveSim annotations (decision, 2026-10-07)

Decision: no annotation from another study's pipeline is used. The 7,539-frame COCO made in the other study (its
three classes, its visibility filters, no buses) is dropped from this experiment. The labels will be built only from
the dataset's own official 2D detection annotations (download from the RealDriveSim project page, to be placed in
`Sensor_Fusion_Study/data/realDriveSim/`), together with its frames and its per-frame segmentation images, which
are used only to find frames containing a bus. This also gives bus labels, so a bus class and a bus AP can be part
of the comparison if the official annotations carry it. The arms, the matching rule and the reading rule above are
otherwise unchanged. A draft frame selection run on the old COCO was stopped and its output deleted before any
use. The selection script (`bin/select_realdrivesim.py`) is not committed until it reads the official format.

#### Matched comparison: class mapping and frame selection rules, fixed before the frames are chosen

Data (all inside this repository folder, git-ignored): the official RealDriveSim 2D annotations,
`external_data/realdrivesim/annotations_2d/{normal,adverse_1,adverse_2}` (133,820 per-frame files, every one matched to
a frame, none orphaned), and the official class table `external_data/realdrivesim/class_mapping.json` (83 ids). The
frames stay in the dataset's own folder (about 410 GB of RGB for the normal set alone). Licence stated on the project
page: CC BY 4.0.

Class mapping, from the official table, into this project's four classes:
 * person: Pedestrian (22);
 * car: Car (5) and Van (103), since this project counts vans as cars and BDD100K annotators did;
 * truck: Truck (36) and ConstructionVehicle(Truck) (104);
 * bus: Bus (4) and SchoolBus (47).
Everything else is dropped, as in this project's own labels: riders (2, 14, 18), motorcycle (13), bicycle (1), animals,
Caravan/RV (6), ConstructionVehicle (7), TowedObject (32), WheeledSlow (39), Train (35), OtherMovable (17) and all
non-object classes.

Box rules, the same as this project's annotation policy: an object counts only if its box is at least 8 px high and 4 px
wide and the dataset's own visibility attribute is at least 0.1; `iscrowd` boxes are skipped. This aligns the labels
with `train_v7p` (which drops objects under 10% visible).

Pool and selection: one frame per scene, chosen with a seeded draw from that scene's 20 frames, from the normal and the
two adverse sets together. `matched` (decides the rule): the 512 frames whose counts of persons, cars, trucks and
buses are each within 10% of `train_v7p` (1,690 / 4,076 / 214 / 55), and whose night share is within 5 points of
`train_v7p`'s (39%). Night is not given for RealDriveSim, so it is measured: the mean luminance of each frame, with the
threshold chosen to best separate `train_v7p`'s own day and night frames (the threshold and the resulting accuracy on
`train_v7p` are reported). `random` (reported only): 512 random frames from the same pool.
The reading rule is unchanged. Bus AP is now part of the per-class report.

#### Segmentation polygons are convex hulls: measured (2026-10-07)

Observation (the owner's): the segmentation outline of a vehicle has sharp corners and does not wrap the vehicle.
Cause, from the code (`src/ground_truth/mesh_labels.py`, `segmentation.py`): each polygon is the convex hull of the
object's projected mesh vertices (or of its eight box corners where there is no mesh), so it is straight-edged and
cannot be concave. Measured against the true outline (the union of the projected mesh triangles, rasterised) on 20
views per model (two distances, five directions, two headings), camera 1920x1080:

| model | IoU of hull with true outline, mean (min) | hull area / true area |
|---|---|---|
| sedan | 0.887 (0.866) | 1.12 |
| pickup | 0.857 (0.823) | 1.16 |
| 3-axle (garbage) truck | 0.894 (0.860) | 1.12 |
| bus | 0.941 (0.909) | 1.06 |

The 2D boxes are not affected (a box is the extent of the projected mesh, which the hull does not change), so no
detection result in this log changes. Masks, and any claim about segmentation, are approximate by this much. The
polygons are also full silhouettes: they are not cut where another object stands in front (the 1.2 mask exporter
resolves overlaps by painting far to near, but the COCO polygons themselves keep the hidden part).
Not measured: label accuracy against a render-pass ground truth (Unreal stencil or object-id capture). The vehicle
footprints were checked against the engine (`bin/verify_vehicle_boxes.py`, seven models, from above), and the
camera against known squares (about 0.5 px), but no dataset-level, pixel-exact audit of the ego-view boxes has
been run. That needs the capture pass of the roadmap's depth spike, and it would also give true masks.

#### Matched comparison: the batches as built (before any training)

`bin/select_realdrivesim.py` (29 tests) builds both arms from the official annotations under the rules fixed above. The
pool is 6,691 frames (one per scene, 6,343 + 258 + 90 scenes); 21% of it is night by the brightness rule. The night
rule is the mean luma of the top 70% of the frame below 66.0, which labels 97.5% of `train_v7p`'s 512 ego frames
correctly (day against night, by their recorded time of day).

| | person | car | bus | truck | night share | adverse frames |
|---|---|---|---|---|---|---|
| `train_v7p` (target) | 1,690 | 4,076 | 55 | 214 | 0.39 | n/a |
| `train_rdsm` (matched) | 1,690 | 4,076 | 55 | 214 | 0.391 | 35 of 512 |
| `train_rdsr` (random) | 4,374 | 2,918 | 159 | 447 | 0.225 | 28 of 512 |

The matched arm reaches every count exactly (error 0.0) and the night share to 0.1 point; the random arm has 2.6 times
the persons, 2.9 times the buses and 2.1 times the trucks, which is why only the matched arm decides the rule. Both
batches are 512 frames (461 train, 51 val lists, as for the other batches), RGB PNG at 2048x1024 (about 0.9 GB each).
Labels drawn on six frames and looked at: boxes sit on the cars, pedestrians, a bus and a truck; riders and
motorcycles are unlabelled by design. Not yet known: how many of the matched frames contain unlabelled classes
(motorcycles, bicycles), which are background for the detector as they are in `train_v7p`'s scenes (which have none).
Arms to train: `hpc_rdsm25` and `hpc_rdsr25` (25% real, AdamW, 200 epochs, imgsz 960, seeds 0-2), compared with
`hpc_v7p25` by the rule above.

### Ground-truth spike: engine-exact depth and object masks under D3D11, and the first label-accuracy audit (2026-10-07)

Question: can this project capture exact per-pixel ground truth from Unreal on this machine (D3D11 `-game`, since D3D12
crashes), and how accurate are the labels computed from geometry when measured against it?

Built (plugin, `unreal_plugin/SyntheticDataGen`, rebuilt in under 30 s with the pinned 14.38 compiler): `CaptureDepth` (a
scene-capture camera at the player camera's pose renders scene depth into a float render target, read back to a file);
`CaptureObjectMasks` (renders the full-scene depth once and each object alone with a show-only list: an object's pixels are
visible where its own depth equals the full-scene depth within 2 cm or 0.2%, and its full extent is wherever it renders at all;
output: one uint16 visible-instance map and per-object visible and full extents and pixel counts); every spawned asset
actor is tagged `vcv_asset_<index>` (its position in the payload's `assets`) so an object can be found. No material, stencil
or project setting is needed, and occlusion is handled by the engine.

Checkpoint 1 (depth at all under D3D11): passed. The capture works; the field of view needs this project's fixed vertical
FOV passed explicitly (the first version used the camera manager's 90 degrees and looked zoomed in), after which depth
discontinuities trace the outlines in the screenshot (a blue car's wheel arches, poles, pedestrians) to the pixel by eye.

Audit (8 scenarios x 3 camera views, `urban_dense_v7_peds.yaml`, ego-like camera at 1.6 m 10-18 m from a sedan, 404
objects in the frames; one pedestrian rendered nothing). IoU of this project's label against the engine, mean (median):

| class | n | full box vs full extent | visible-part box vs visible extent | polygon vs visible mask (unoccluded only) |
|---|---|---|---|---|
| sedan | 182 | 0.958 (0.971) | 0.765 (0.809) | 0.723 (0.794) (0.853, n=55) |
| pickup / van | 40 | 0.954 (0.978) | 0.790 (0.834) | 0.747 (0.797) (0.834, n=16) |
| bus | 4 | 0.822 (0.986) | 0.700 (0.814) | 0.813 (0.831) |
| truck | 1 | 0.990 | 0.969 | 0.604 |
| person | 176 | **0.782 (0.801)** | **0.588 (0.639)** | **0.365 (0.390)** (0.459, n=67) |

Reading: (1) vehicles' standard 2D boxes are accurate (median 0.97), so every vehicle result in this log rests on good boxes.
(2) The visible-part (modal) boxes and the polygons are materially looser (0.77-0.79 and 0.72-0.85), as the convex-hull
measurement predicted. (3) Pedestrian labels are the weak class: on an image (green = ours, magenta = engine) the label box
is about twice as wide as the person and slightly taller; the full-box IoU is 0.78. This matters because the person class is
where the synthetic supplement helps most (+3.8 AP over real-only, and it vanishes with the crowd removed), and BDD100K
boxes are tight. Not yet shown: that tight pedestrian boxes would raise person AP; that is a hypothesis, to be tested with a
pre-registered rule, not a finding. Bus (4) and truck (1) are too few to read; the audit needs trucks and buses in view.
Caveats: one town layout style, day only, ego-like views from near a sedan; the engine masks come from the depth of
the whole actor (so a vehicle's wheels and glass count); the plain pedestrian meshes use vertex animation, which renders
in the single-object pass (the extents agree with the screenshot overlay).

Decision: go. Depth and exact masks work here. Next: (a) a measured fix for the pedestrian box (take extents from the engine
per frame, or a tighter proxy), then a batch with tight pedestrian boxes against `train_v7p`; (b) exact masks and depth in the
export. The label-accuracy audit becomes a tool (`bin/audit_labels.py`) so any batch can be audited.


### v12e: every label from the engine (`--exact-labels`), rules fixed before the render

Question: do tight, engine-exact labels raise person AP (and not hurt the rest)? The audit above found person boxes loose
(full-box IoU 0.78, against 0.96 for vehicles) while BDD100K person boxes are tight, and the person class is where the
synthetic supplement helps most. `train_v12e` is `train_v7p` exactly (config `urban_dense_v7_peds.yaml`, profile v7,
256 scenarios, seeds 70000-70255, same fleet, same cutoffs) rendered with `--exact-labels`: for every vehicle and pedestrian the
box is the extent of the pixels the game draws for it (visible part, the modal convention of the other batches), the
visible fraction is visible over full in-frame pixels, an object with no visible pixel is dropped, and the visible mask is
saved. Objects the game cannot find keep their geometric label. Arms: `hpc_v12e25` (25% real, AdamW, 3 seeds) against `hpc_v7p25`.

What this does and does not test: the change is for vehicles too (their modal box was 0.77 IoU, now exact), so a result is
"engine labels versus proxy labels", read per class; person AP is the primary question, but a gain cannot be attributed to
persons alone without a persons-only arm (not planned unless the primary rule is met and the cause is worth isolating).
Truncation stays geometric, 3D boxes are unchanged, `segmentation` stays the convex hull (masks are in `mask_rle`);
YOLO training uses boxes only, so masks do not enter this test.

Checks before training: (a) the scenes must match `train_v7p`'s (same seeds; the labels are the only intended difference). Checked on the
first four frames: objects and layout are in the same places, but the pixels are not identical (about 3% differ by more than
10 levels, in the clouds, window reflections and fine noise, from a difference map; cause not confirmed, cloud drift
between renders is the likely one). So the scenes are the same and the sky and shading vary, as a re-render of `train_v7p` would; (b) the batch's person box width-to-height should fall toward the real
BDD100K's (measured, reported with the result).

Rules: (1) person AP on BDD100K val up by at least +1.0 over v7p25 at p < 0.1 (Welch, 3 seeds) is a lever; (2) guardrails:
overall and car AP not down by more than 0.5; (3) bus and truck, Cityscapes val per class and the per-box outcomes are
reported, not part of the rule. Person AP down by 1.0 or more at p < 0.1 would be a finding too (the looseness helps, for
instance by covering the person's context) and would be reported as such. Between those, tight labels do not matter at
this scale and are closed as a lever (the exact labels stay as a feature for the mask and 3D exports).


### RealDriveSim matched comparison: result (2026-10-07)

Arms (25% real BDD100K + 512 images, AdamW, 200 epochs, imgsz 960, seeds 0-2, mean ± sd, AP in points, Welch p against
`hpc_v7p25`): `hpc_rdsm25` (RealDriveSim, official 2D annotations, counts matched to `train_v7p`) and `hpc_rdsr25` (512 random
RealDriveSim frames; reported only). Scored with an unversioned helper (`demo/score_arms.py`, not tracked).

BDD100K val:

| | v7p25 | rdsm25 (matched) | rdsr25 (random) |
|---|---|---|---|
| overall | 20.99 ± 0.38 | 20.92 ± 0.23 (-0.07, p=0.79) | 22.03 ± 0.21 (+1.04, p=0.022) |
| person | 16.24 | 15.61 (-0.63, p=0.21) | 17.15 (+0.91, p=0.005) |
| car | 38.11 | 37.96 (-0.15, p=0.07) | 38.05 (-0.06) |
| truck | 16.12 | 16.37 (+0.25) | 17.09 (+0.97, p=0.024) |
| bus (not compared: RealDriveSim arms have no bus labels) | 13.51 | 13.74 | 15.85 |

Cityscapes val (reported, does not decide): overall v7p25 21.34, rdsm25 22.72 (+1.38, p=0.060), rdsr25 24.18 (+2.84, p=0.001);
person +1.32 / +3.05, car +1.18 / +1.20 for rdsm25 / rdsr25.

Rule as logged (matched arm, BDD100K val overall): v7p25 minus rdsm25 = +0.07, within 0.5. Reading: the AP gain of
this pipeline's data is **not specific to this generator at this size**; on BDD100K, a count-matched 512-image
supplement from another synthetic dataset (a different engine, resolution and annotation style) gives the same AP, so
BDD100K AP does not show what the City Sample renders add over another source. It does not show that they are equal in
every respect: Cityscapes is ahead for RealDriveSim by 1.4 (p=0.06), person and car, which is a reason to look, not a
rule outcome.

What this does not support: the random arm's +1.04 over v7p25 is not a verdict that RealDriveSim is better (more
persons per image, 9.1 against 3.3, and trucks, which moved AP before; objects are also much denser and the labels
include heavily occluded ones); the matched arm exists to remove that, and it shows no difference. Caveats: three seeds,
sd 0.2-0.4 on overall AP, so differences under about 0.5 are not resolved; bus is out of the comparison; RealDriveSim's
unlabelled motorcycles and bicycles are background to the detector here.

Consequence: claims about the data's value should rest on what AP can show (a gain over real-only, which holds for
both sources) and on the label and structure features that a mixed-source supplement does not have (3D boxes, exact
masks, per-object truncation), not on a claim of better detection AP than another synthetic source.


### Label audit on trucks and buses (`bin/audit_labels.py`, 2026-10-07)

The first audit had one truck and four buses. The probe is now a tool (`bin/audit_labels.py`, a hero vehicle of the focus type
in each scenario, three ego-height views at 12-22 m, the scene cut to 50 m around it, day, `urban_dense_v7_peds.yaml`, seeds
70010 onward); rows are in `results/label_audit_truck.json` and `results/label_audit_bus.json`. Mean IoU of this project's
label against the game's render (the rows also contain the other classes in view):

| class | n | full box vs full extent | visible-part box vs visible extent | polygon vs visible mask |
|---|---|---|---|---|
| truck (truck run / bus run) | 37 / 12 | 0.976 / 0.871 | 0.861 / 0.710 | 0.782 / 0.705 |
| bus (bus run) | 34 | 0.989 | 0.880 | 0.837 |
| sedan (both runs) | 156 / 179 | 0.938 / 0.952 | 0.71 / 0.72 | 0.61 / 0.65 |
| person (both runs) | 174 / 224 | 0.800 / 0.791 | 0.65 / 0.64 | 0.39 / 0.40 |

Reading: the truck and bus labels are as accurate as the car labels (full box 0.97-0.99 where they are the hero), so the
earlier truck and bus findings do not rest on bad boxes. The 12 trucks seen in the bus run score lower (0.871), which is a
small sample of trucks at varied distance, not read further. Pedestrians reproduce the first audit (0.79-0.80, 0.64-0.65).
Caveats as before: day, ego-like views near the hero, one config.


### v12e result: engine-exact labels (2026-10-08)

`hpc_v12e25` against `hpc_v7p25` (25% real, 512 images of the same scenes, AdamW, 200 epochs, imgsz 960, seeds 0-2; mean ± sd,
Welch p). The batch: person, car, bus and truck counts within 2% of `train_v7p`; person box width/height 0.414 -> 0.339, truck
box height 107 -> 120 px (median).

| BDD100K val | v7p25 | v12e25 | difference (p) |
|---|---|---|---|
| overall | 20.99 ± 0.38 | 21.09 ± 0.16 | +0.09 (0.73) |
| **person** | 16.24 ± 0.17 | 16.96 ± 0.52 | **+0.72 (0.128)** |
| car | 38.11 ± 0.07 | 38.59 ± 0.18 | +0.47 (0.032) |
| bus | 13.51 ± 1.11 | 12.33 ± 0.47 | -1.18 (0.20) |
| truck | 16.12 ± 0.36 | 16.47 ± 0.42 | +0.35 (0.33) |

Cityscapes val (reported): overall 21.34 -> 21.71 (+0.37, p=0.64); person +0.66 (0.135); car +0.77 (0.010); bus +1.25; truck -1.20 (sd 2-3).

Rules as registered: (1) person AP up at least +1.0 at p<0.1: **not met** (+0.72, p=0.128). (2) Guardrails (overall and car
not down by more than 0.5): met. Person AP down by 1.0 or more: no. So the result falls in the registered middle band: tight
labels do not move person AP by a resolvable amount at this scale, and by the rule they are closed as a lever (the exact labels
stay as a feature for the mask and 3D exports).

What the data allow beyond that, stated without upgrading it: the person difference points the right way on both benchmarks
(+0.72, +0.66) but with sd 0.5 and three seeds a true effect of about 0.7 could not be told from zero, and the registered
threshold was +1.0. Car AP is up 0.47 (BDD p=0.03, Cityscapes +0.77, p=0.01); it was not the primary question and several
classes were examined, so it is a lead, not a finding. Bus and truck move within their noise (bus sd 1.1 and 0.5). Overall AP
is unchanged. Not tested: a persons-only change, more seeds, or a larger supplement, where tighter labels might matter more.


### Epic's reply (2026-10-08)

Asked 2026-10-05 whether City Sample's crowd characters (adapted from MetaHumans) may be used to train models. Reply: Epic cannot
give custom legal or EULA interpretations for specific distribution models and recommends the developer's own legal counsel and
the standard EULA. Nothing is settled: there is no yes and no no. Standing position: no datasets or trained weights are
published; results that rely on synthetic pedestrians stay provisional; options are legal advice on the EULA wording, or code and
metrics only with a clean-room pedestrian source (Rocketbox pilot) for any released data. The 2026-10-19 follow-up and the
2026-12-04 deadline no longer apply as a wait for Epic.


### Pedestrian replacement spike: Microsoft Rocketbox in the pipeline (2026-10-08)

Why: Epic would not interpret the EULA (see above), so the City Sample crowd cannot be cleared for publication of datasets or
weights. A replacement source is needed whose licence text is clear. What was checked, and what was not:

* Rocketbox (`microsoft/Microsoft-Rocketbox`, 115 rigged avatars, 40 adults in `Assets/Avatars/Adults`): `LICENSE.md` is the plain MIT
  licence (Copyright 2020 Microsoft), no added terms and no mention of machine learning; the README says "The library of avatars is now
  released under MIT License" (12/2020). The repository was archived on 2026-10-02 (read-only, still downloadable; last push 2022).
  MIT places no field-of-use restriction, but it also does not name ML training, so this is a reading of permissive text, not an
  explicit grant; whether that is enough is a question for counsel, as for City Sample.
* CARLA walkers: the catalogue page (48 blueprints) states no origin or licence for them; the CARLA README states its own assets are
  CC-BY but not who made the walkers. Unverified; also they live in a packaged UE4 build and would have to be extracted. Not pursued.
* Not checked: RenderPeople, Daz, Fab, Quixel, SMPL-family (licence text not read).

Pipeline spike (Blender 5.2.2 installed with scoop, user scope; Rocketbox cloned sparse into the git-ignored `external_data/rocketbox`):

1. Posing: Blender imports the avatar and a walking clip. Applying the clip's curves directly is wrong (the two files' rest poses
   differ: the body leaned back 21 degrees against 4 degrees in the clip's own skeleton). Copying the clip's bone orientations onto
   the avatar's bones matches the clip's skeleton to 0.5 degrees mean bone-direction error (26 degrees for direct curves, 28 for
   rest-pose-relative), measured on 12 bone pairs. Result: an upright, textured walking pose, 1.725 m tall, feet on z=0, facing +Y.
2. Import: Unreal's `ImportAssets` commandlet (absolute `.uproject` path required) brought the posed mesh, materials and textures into
   our own `Content/VantageCV/Pedestrians/Rocketbox`; no Epic asset was touched.
3. Render: a Rocketbox pedestrian is a plain `static_asset` entry (path, position, rotation), the same as a City Sample pedestrian;
   no plugin change. Rendered in a real scene next to cars and next to a City Sample pedestrian at the same distance: lit by the scene,
   correct scale and ground contact. Comparable realism at 4.5 m by eye; the Rocketbox cloth is somewhat glossier. One avatar and one
   frame only, a feasibility result, not a realism measurement.

Not done: poses for many avatars, a pedestrian type in the generator (clothing/gender/pose variety, standing and walking), exact
labels for the new pedestrians (`object_asset_indices` finds pedestrians by their City Sample asset key), a realism check, and the
person-AP comparison against `train_v7p`. That experiment needs its rule written before any render.


### v13r: Rocketbox pedestrians in place of City Sample's crowd, rules fixed before the render (2026-10-08)

Question: if the City Sample crowd characters cannot be cleared for publication, does an MIT-licensed replacement keep what the
synthetic pedestrians give (person AP, where the supplement's gain lives: about +3.8 over real-only, and -3.0 with the crowd removed)?

Built: 38 adult Rocketbox avatars (the two party-dress avatars left out), each baked into 6 walking poses (3 neutral walk clips at
15% and 60% of their frames) and 3 standing poses (3 neutral idle clips at their midpoint): 342 static meshes, imported into our own
`Content/VantageCV/Pedestrians/Rocketbox` (`bin/bake_rocketbox.py`, `scripts/rocketbox_bake_poses.py`, measured extents in
`configs/rocketbox_catalog.json`: heights women 1.71-1.78 m standing, men 1.78-1.86 m, no outliers). `pedestrian_source: rocketbox`
(`urban_dense_v13r.yaml`) swaps each placed pedestrian after the scenario is generated, with its own random stream: placement,
heading, gender and walking-or-standing are those of the City Sample scenario with the same seed (tested), so the scenes of
`train_v13r` are those of `train_v12e`; only avatar and pose differ. Orientation was checked in the game: `rotation_rad =
heading - pi/2` makes an avatar face its heading (toward, away from and across the camera). A 4-scenario probe rendered with
exact labels showed varied, naturally posed pedestrians with tight boxes and masks.

Batch: `train_v13r` = `urban_dense_v13r.yaml`, profile v7, 256 scenarios, seeds 70000-70255, `--exact-labels`, split by
scenario as the others. Arms: `hpc_v13r25` (25% real, AdamW, 200 epochs, imgsz 960, seeds 0-2). Comparison: `hpc_v12e25`
(same scenes and exact labels, City Sample crowd), so the swap is the only intended difference; `hpc_v7p25` and
`hpc_real25r` (real only) are reported alongside.

Rules, before any result:
1. The swap keeps the person gain if person AP on BDD100K val is within 1.0 of `hpc_v12e25` (v13r25 not lower by 1.0 or more).
   Reported with the share of the gain over real-only that is kept: (v13r25 - real25r) / (v12e25 - real25r).
2. It loses it if person AP is lower by 1.0 or more at p < 0.1 (Welch, 3 seeds); the loss is then reported, and a larger,
   more varied Rocketbox set (children, professions) or realism work is the next question, not a conclusion that the swap fails.
3. It is better if person AP is higher by 1.0 or more at p < 0.1.
4. Guardrails (all rules): overall and car AP not down by more than 0.5 against `hpc_v12e25`.
5. Reported, not decisive: bus, truck, Cityscapes, per-box outcomes, and the batch's person counts and box shapes.

Limits stated now: AP with a different crowd does not by itself clear publication. Even if rule 1 holds, Rocketbox's MIT text does
not name ML training (a counsel question, see above), the scenes still use other City Sample assets (buildings, vehicles, props;
analysed earlier under the project licence, not re-checked today), and the avatars were not checked against a realism measure beyond
the renders. Only adults are used, so children are absent from this crowd.


### Person-crop realism: City Sample against Rocketbox (`scripts/person_crop_realism.py`, 2026-10-08)

Before the v13r arms report, how far are the two sources' person crops from real ones? Method: clearly visible persons (visible
fraction at least 0.7, not truncated) 40 to 140 px tall at 1280 x 720 (the synthetic frames scaled to that size), cropped as a
square 1.3 x the longer box side, embedded with an ImageNet ResNet-50 (2048-d), Frechet distance (the FID formula with this network)
to real BDD100K val person crops (not occluded or truncated, same size range, matched to each dataset's day/night mix), five real
resamples; the noise floor is real against real at the same sample size.

| | crops (night) | Frechet distance to real, mean +- sd over resamples |
|---|---|---|
| `train_v12e` (City Sample crowd) | 681 (293) | 163.6 +- 1.8 |
| `train_v13r` (Rocketbox) | 673 (288) | 165.7 +- 1.2 |
| real against real (two disjoint samples of 673) | | 34.3 +- 0.3 |

Reading: both sources are about five times farther from real person crops than real is from itself, and they are close to each
other (Rocketbox 2.1 farther, about 1%, in all five resamples; the sd covers only the real resampling, not the variation of the
synthetic crops themselves, so a 1% gap is not resolved). So by this measure the swap neither closes nor widens the gap to real
people. Caveats: ImageNet features, crops include 30% context so scene, lighting and rendering style enter the distance as much as the
person; squashed square crops; one number does not say what a detector needs. It is a context for the v13r AP result, not a
substitute for it.


### v13r result: Rocketbox pedestrians keep the person gain (2026-10-08)

`hpc_v13r25` against `hpc_v12e25` (same scenes and exact labels; only the crowd avatars differ), 25% real, AdamW, 200 epochs, imgsz 960,
seeds 0-2, mean +- sd, Welch p. The batch: persons 1706 against 1694, vehicles within 0.2%, person box width/height 0.385 against 0.339.

| BDD100K val | real-only (`hpc_real25`) | v12e25 (City Sample) | v13r25 (Rocketbox) | v13r25 - v12e25 (p) |
|---|---|---|---|---|
| overall | 18.23 | 21.09 +- 0.16 | 21.20 +- 0.22 | +0.12 (0.51) |
| **person** | 12.41 | 16.96 +- 0.52 | 16.95 +- 0.42 | **-0.01 (0.98)** |
| car | | 38.59 | 38.55 | -0.04 (0.76) |
| bus | | 12.33 | 13.47 | +1.14 (0.037) |
| truck | | 16.47 | 15.85 | -0.62 (0.18) |

Cityscapes val: overall 21.71 -> 22.21 (+0.50, p=0.56); person 14.65 -> 15.40 (+0.75, p=0.24); car -0.47 (p=0.025); bus +0.86; truck +0.86.

Rules as registered: (1) person AP within 1.0 of v12e25: **met** (-0.01); share of the gain over real-only kept (16.95 - 12.41) / (16.96 -
12.41) = 99.8%. (2) not lower by 1.0 at p<0.1: no. (3) not higher by 1.0: no. (4) guardrails: overall +0.12, car -0.04, both met.
(5) reported: bus +1.14 (p=0.037) is the one class that moved by more than its noise, with 55 bus boxes in the batch and sd 0.4-1.1 in the arms;
not read as an effect (not a registered question, several classes examined). Cityscapes car is 0.47 lower (p=0.025) with the others
flat, same caution.

Reading: replacing City Sample's crowd characters with MIT-licensed Rocketbox avatars leaves person AP where it was, on both benchmarks,
and the person gain over real-only (+4.5 AP) is intact. With the Frechet distance of person crops (163.6 against 165.7, both about five
times the real-against-real floor) the two crowds are indistinguishable to this pipeline by both measures. What this does not settle:
publication. Rocketbox's MIT text does not name ML training and the scenes still use other City Sample assets (see the limits above);
the avatars are adults only; three seeds resolve differences of about 0.5 AP or more.


### Rocketbox licence provenance (checked 2026-10-08, from the paper and the repository's own history)

* The library's paper (Gonzalez-Franco et al., Frontiers in Virtual Reality, published 2020-11-03, DOI 10.3389/frvir.2020.561558) states in
  its data availability statement and its Table 1 that the library is "publicly available for research and academic use" and "free for
  research and academic use". It does not mention commercial use or machine learning, and it predates the licence change below.
* The repository (`microsoft/Microsoft-Rocketbox`, created 2020-03-13) first carried the **Microsoft Research License Terms**: use
  "for non-commercial, non-revenue generating, research purposes", analysis and testing, publishing results, no distribution of the
  Dataset. On **2020-11-16** (13 days after the paper), commit `1eeb280` / `accbe42` by the paper's first author (Microsoft Research)
  replaced it with the **MIT License** (Copyright 2020 Microsoft); the README records the change ("Updated license to MIT"; the page
  shows it as 12/2020, the commits are dated 2020-11-16/17). The repository was archived on 2026-10-02 (read-only, last content
  push 2022).
* What this means: the current licence text is MIT with no added terms, but the avatars were first released under a non-commercial
  research licence and described as research-only in the paper. Whether the later MIT grant is effective for this use (who could
  grant it, whether it reaches every texture and mesh, whether the earlier framing matters) is a counsel question, together with
  the earlier one that MIT does not name ML training. The local clone (`external_data/rocketbox`, commit `0943055`) is of the MIT
  version; the history above is in its git log (`git log --follow -- LICENSE.md`).


### Decision (2026-10-08): no more MetaHuman-derived pedestrians in new work; Rocketbox only

* Published prior use of Rocketbox in synthetic-data pipelines: Kerim et al., "Leveraging Synthetic Data to Learn Video Stabilization Under
  Adverse Conditions" (WACV 2024, arXiv 2208.12763) states (Section 4, "Dynamic Elements") that "The Microsoft Rocketbox Avatar
  Library" defines its character avatars, with character animations from Mixamo, in a Unity simulator, and says the simulator and the
  datasets are available on GitHub; the model is trained only on that synthetic data. It states no licence terms for any asset, so it is
  evidence of use and release by others, not of permission, and its Mixamo animations carry their own terms.
* Given Epic's non-answer (above), the MetaHuman-derived City Sample crowd is no longer used for new datasets, experiments or
  releases. New batches use `pedestrian_source: rocketbox`. The option `city_sample` stays in the code, only so that earlier batches
  (`train_v7p`, `train_v12e` and the arms trained on them) can be reproduced; it logs a warning when used, and the results that rest on
  it stay in this log as history. Datasets and weights remain unpublished; the first candidates for release would be Rocketbox
  batches, still subject to counsel (Rocketbox's licence history and the other City Sample assets in the scenes).


### Correction (2026-10-08): what the Rocketbox swap does and does not clear

An earlier statement in this session called the City Sample vehicles and props the lower-risk part and implied the third-party
"Allows usage with AI: No" tag applied only to the Vehicle Variety Pack. That was incomplete. The record shows:

* City Sample's own Fab page carries "Allows usage with AI: No". The question put to Epic (what that tag means for training a
  detection model on renders) was not answered; Epic's reply (2026-10-08) declined to interpret the EULA for this use. So the tag
  question stands for all City Sample content in the scenes (vehicles, buildings, props, road kit), not only for the crowd.
* The working reading, unconfirmed: the AI clause concerns generative AI (programs that create new content), and a detector is not one;
  the Content License Agreement section on rendered output allows publishing renders. This is a reading of text, not Epic's answer
  and not legal advice.
* Megascans/Quixel content in the project (road curbs, street furniture) has no verified licence in this record.
* The Rocketbox swap removes the MetaHuman-derived crowd (the EULA clause on training AI with MetaHuman content). It does not remove
  the City Sample tag question or the Megascans question. A scene with no City Sample or Megascans assets would need its own
  vehicles, buildings and props from permissively licensed sources; that has not been scoped.
* Standing position unchanged: no datasets or weights published; code, metrics and this log are what is public.


### Licensing verification pass (2026-10-08)

Every licence the project depends on was looked up and the findings recorded in `LICENSING.md` (one place, with sources, quoted text and
what could not be read). What was newly established: the Fab library cache marks City Sample and the Vehicle Variety Pack as AI-forbidden
(flag 1) and has no separate Megascans entry; Cityscapes (non-commercial; abstract derivatives such as trained models may be
distributed) and RealDriveSim (CC BY 4.0) read from their official pages; BDD100K's data licence is a UC Regents licence (research and
not-for-profit use free; commercial use for BDD/BAIR Commons members), read from a mirror because the official site was unreachable;
ultralytics is AGPL-3.0 and states trained models are AGPL-3.0 too unless an Enterprise License is bought (secondary reports; this bears on
any release of weights); MetaHuman and NoAI clause wording corroborated by third-party mirrors. Not resolvable by search: Fab EULA
Section 16(l), the exact acceptance dates, Epic's own interpretation, and every question of law. These need the owner's paste or counsel.


### Release goal (2026-10-08): the dataset on Kaggle, no weights

The owner's aim is to publish a rendered dataset on Kaggle and not to publish trained weights. `LICENSING.md` now has the checklist for that:
only Rocketbox batches (`train_v13r` and later; checked: no Crowd/MetaHuman asset in any of its 256 scenarios), custom Kaggle terms that
forbid generative-AI use (the NoAI clause on datasets), third-party notices, and the open points (Epic's reading of the NoAI clause,
Megascans in 5.5% of asset entries, Rocketbox's licence history). The weights-only concerns (ultralytics AGPL, BDD100K commercial
restriction) are moot for a dataset-only release.


### COCO segmentation now follows the exact mask (2026-10-08)

Gap found by the owner: with `--exact-labels` the boxes and the `mask_rle` were exact, but the standard COCO `segmentation` field still
held the old convex hull (IoU 0.39 against the visible mask for persons). `src/export/mask_polygons.py` now traces the mask's outline
along pixel edges (numpy only, 4-connectivity; holes are not representable in a COCO polygon and are covered by the outer polygon;
the exact mask stays in `mask_rle`), and the exporter writes it into `segmentation` for every annotation that has an exact mask.
Measured on 3,000 annotations of `train_v13r`: polygon against the exact mask IoU 0.997 for persons (min 0.94), 0.997 cars, 0.998
buses, 0.992 trucks; median 122 vertices (max 2,902); 19 ms per annotation. Tests: pixel-exact on solid shapes, corner-touching
regions kept apart, an exported exact annotation's polygon rasterises to its mask. The batches rendered before this change
(`train_v12e`, `train_v13r`) keep hull polygons in `segmentation` and exact masks in `mask_rle`; the Kaggle release batch
(`kaggle_v1`) was restarted after the change so it carries the traced polygons from the start.


### Full annotation set before the release render (2026-10-08)

Decision (owner): all annotations are built and checked before the Kaggle batch is rendered, so it is rendered once. The release render
(`kaggle_v1`, 1,024 scenarios, seeds 80000-81023, Rocketbox pedestrians) was stopped after 13 scenarios and discarded.

What was built: (1) COCO `segmentation` traced from the exact mask (see above); (2) full-scene class map and depth map per frame
(`--semantic-maps`): the plugin's `CaptureObjectMasks` now takes groups of assets, procedural meshes (tagged `vcv_mesh_<i>`) and lamp glows
(`vcv_glow_<i>`), resolves overlaps first-match, and can write the engine depth; the class table is Cityscapes label ids
(`src/ground_truth/semantic_classes.py`), every asset and mesh type of the generator mapped by rule, with a test that fails on an unmapped
part; (3) the painted hood: `hood_mask`, exact masks and boxes trimmed to it, class map `ego vehicle` there; (4) the release package
(`bin/package_dataset.py`): relative paths, YOLO detection and segmentation labels, KITTI, instance masks, ultralytics-resolvable
`data.yaml`, validation, and a dataset card with draft terms and notices.

Checks on a 6-scenario probe (12 frames, day and night, rain, clear, golden hour): class map against the exact instance masks: 100% of
the mask pixels of cars (2.37 M px), persons (113 k) and trucks (248 k) carry the matching class, no mismatch; unlabeled pixels 0
(first probe: 0.02% at night, the emissive headlight discs, now tagged and given their vehicle's class); pickups are `car` in the class
map as in the annotations (a path rule had said truck: found by looking at the picture); 0 of 125 masks overlap the hood; depth against
the KITTI 3D boxes of 63 unoccluded vehicles: median depth inside [box centre - half extent - 0.6 m, box centre + 0.6 m] for 95.2%,
depth/z median ratio 0.918. Render cost with every annotation on: about 37 s per scenario (two frames). Not included: surface normals,
optical flow, LiDAR, riders and two-wheelers, lane-level semantics.


### Night taillights: the pink wash, measured and reduced (2026-10-08)

Observation (owner): rear lights and the vehicles around them read pink. Measurement (`scripts/taillight_colour.py`, 1280 x 720, 300 BDD100K
night frames against 214 night frames of `train_v13r`; inside the lower 70% of car boxes, bright (V >= 0.7), red-hue (within 25 degrees),
non-white (S >= 0.15) pixels; and the mean chromaticity of mid-tone pixels (0.10 <= V <= 0.50) of the frame):

| | red-light px per 10k box px | their saturation, median (10-90%) | scene chromaticity r, g, b |
|---|---|---|---|
| BDD100K night | 275 | 0.47 (0.20-0.79) | 0.403, 0.324, 0.273 |
| ours before | 595 (434 on the sweep scenes) | 0.28 (0.18-0.38) | 0.421, 0.302, 0.277 |

Sweep on 6 identical night scenes (12 frames) varying one thing at a time: glow-disc intensity x1 to x0.25 changed nothing that mattered
(saturation 0.29 to 0.30); the taillight **point lights** drove the wash (autoexposure brightens the dark scene, so even a quarter of the
strength still washed a white bus pink; with them off the lamps read red on a neutral scene):

| point lights | red-light px/10k | saturation median | chromaticity r, g, b |
|---|---|---|---|
| x1.00 (earlier) | 434 | 0.29 | 0.421, 0.302, 0.277 |
| x0.50 | 282 | 0.30 | 0.416, 0.305, 0.279 |
| x0.25 | 193 | 0.27 | 0.410, 0.309, 0.281 |
| x0.15 | 162 | 0.26 | 0.403, 0.314, 0.283 |
| x0.10 | 144 | 0.26 | 0.397, 0.317, 0.286 |
| off | 75 | 0.23 | 0.381, 0.326, 0.293 |

Chosen: point lights x0.15 (`RUNNING_TAILLIGHT_INTENSITY_CD` 1.8, `BRAKE_LIGHT_INTENSITY_CD` 7.5): scene red chromaticity equals real
(0.403), the L1 distance to real falls from 0.044 to 0.020, and the body wash is gone. At x0.15 the glow strength (x1 to x0.10) and a pure-red
colour moved the lamp saturation only between 0.26 and 0.31. **Remaining gap, not closed:** the lamp pixels are paler than real (median
saturation 0.26 against 0.47, and 117-162 red-light pixels per 10k against 275); no lever tried (glow intensity, glow colour, point-light
strength) raises it, so it is probably the tonemapper and bloom of the engine's post-process, which was not changed. Day frames are
unaffected. The release render (`kaggle_v1`) was stopped and restarted with this change.


### Taillights against real: the lamps are camera glare, now added and fitted (2026-10-08)

After the point-light fix the lamps themselves still looked wrong (small, pale pink; real brake lights are saturated red with a halo). The cause
is the night colour grading: the v7 night preset sets global saturation 0.4 and the tonemapper then pales every bright emissive disc, so no glow
intensity or colour reaches a deep red (pure red at four strengths: 2-10% of cars with deep-red lamps; `scripts/lamp_profile.py`).

Real reference (`scripts/lamp_profile.py`, 300 night frames of BDD100K val, 2,100 cars 30-220 px tall at 1280 x 720; deep red = red hue within 25
degrees, S >= 0.55, V >= 0.45, lower 70% of the car box): 44.5% of cars show deep-red lamps; among those the lamp area has median 10.7 per mille of the
car width squared (IQR 2.7-35.1), V median 0.59, S median 0.65, largest blob radius 0.042 car widths. Ours (engine only, 118 night ego cars):
2.5% of cars, area 2.0, V 0.46, S 0.55, radius 0.007.

Fix: `src/orchestration/lamp_bloom.py`, an image-space glare added at night to every lamp that the engine's depth map shows (a lamp behind a car adds
nothing; pixels under the painted hood are kept): three Gaussians (widths 0.4, 1.0 and 2.8 lamp radii; weights 1, 0.35, 0.08) added in linear light in
the lamp's colour (tail red, head warm white) and clipped, so a lamp has a near-clipped core in a deep red halo. Fitted offline on 16 night
scenarios (32 ego frames) by grid search against the real numbers above; first grids were too strong (area 85-145, radius 0.14-0.18) and one had a
defect found by looking (a 60 px cap on the glare window cut large halos into squares; removed, then refitted with unchanged optimum):

| | with deep-red lamps | area median (IQR) | V | S | radius |
|---|---|---|---|---|---|
| BDD100K night | 44.5% | 10.7 (2.7-35.1) | 0.59 | 0.65 | 0.042 |
| engine only | 2.5% | 2.0 (1.9-2.7) | 0.46 | 0.55 | 0.007 |
| + bloom (brake peak 2.0, running 0.5) | 58.5% | 11.2 (3.8-22.1) | 0.55 | 0.64 | 0.041 |

Reading: among cars that show lamps, size, spread, saturation and radius match real closely; brightness is a little low (0.55 against 0.59); the upper
tail of lamp sizes is shorter (75th percentile 22 against 35); the share of cars with visible lamps (58% against 44.5%) is a property of our scene
layout (how many cars face away at night), not something the bloom controls. Headlamp glare is not fitted (peak 0.4, chosen conservative after a
first value of 2.0 made a white haze over close cars). Day frames and labels are unaffected; `--lamp-bloom` (needs `--semantic-maps`) records
`lamps_bloomed` per image, and the dataset card states that the glare is added in image space. 4 unit tests. The release render restarts with it.


### Headlights: the white ovals on the road (2026-10-09)

Observation (owner): two crisp white circles on the road directly in front of each car's headlights. Isolation on identical night frames (3 seeds): removing
the headlight glow discs leaves the ovals; removing the headlight spot lights removes them; so they are the spot lights' ground pools, whose sharp edge is where the
cone ends (a 16 degree outer cone aimed almost level from 0.7 m lands its lower edge about 2.5 m ahead). Not the lamp reflection, not the glow discs.

Sweeps (same frames; judged on zoomed crops of the road in front of the cars; an automatic peak-to-median measure was tried and discarded, it picked up windows and lamps
in the road band): narrower cones (10, 8, 6 degrees) shrank the ovals but did not remove them; soft cones with no flat inner cone (20-24 degrees, intensity 0.4-0.6)
and the current cone at 0.35 x only faded them; cones aimed above the horizon (+2 to +4 degrees, outer 16-24) left them at the same place on the road; wide faint
cones removed the edge: outer 45 (inner 0, x0.3) gave a broad soft pool, outer 35 (inner 5, x0.3) still showed two ovals, **outer 60, inner 10, x0.25** gave a
smooth wide faint glow and no oval, in both test frames. Applied: `HEADLIGHT_OUTER_CONE_DEG` 60, `HEADLIGHT_INNER_CONE_DEG` 10, `HEADLIGHT_DIP` -0.02,
`HEADLIGHT_INTENSITY` 1.5 (was 16, 4, -0.01, 6). The strong headlamp appearance comes from the glow discs and the (unfitted) headlamp glare, not from the road
pool. Not measured against real road pools; judged by eye only. The release render restarts with it.
