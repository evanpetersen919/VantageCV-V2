## Visible-part labels and the first v7 batch (cluster, 3 seeds each, AdamW)

Read with the rule written before the results (previous entry): the label test isolates the box
convention; `hpc_v7a25` is compared with `hpc_rand25` (972 vs 970 training images).

**Label test: no effect.** The v5 images with regenerated visible-part labels (half of the boxes
shrink, median remaining area 56%) against the original full-extent labels, same recipe and seeds.

| | BDD100K AP | Cityscapes AP |
|---|---|---|
| 25% real: modal vs full-extent | 22.78 vs 22.93 (-0.15, p = 0.74) | 22.88 vs 23.17 (-0.29, p = 0.59) |
| 100% real: modal vs full-extent | 30.21 vs 29.99 (+0.21, p = 0.053) | 28.13 vs 29.06 (**-0.93**, p = 0.017; bus -3.5) |

Per class and at night nothing moves beyond seed spread at 25% (car +0.33, p = 0.055; night +0.68,
p = 0.23). The box convention was a real mismatch with BDD100K (overlapping boxes 33% against 8%),
and correcting it changes labels a lot, but **detection AP does not respond**: the fix is neutral at
25% real and mixed (+0.2 BDD, -0.9 Cityscapes) at 100%. This is consistent with the v4b entry (whose
labels were in fact unchanged). The switch stays in v7 as a correctness fix with no measured benefit.

**First v7 batch: not better than the old generator at equal size.** 972 images (460 train + 52
val frames of the v7 batch, plus the 460 real) against 970 random v5/v5b images, 25% real:

| BDD100K AP | rand25 (old generator) | v7a25 | difference |
|---|---|---|---|
| overall | 20.84 ± 0.42 | 19.97 ± 0.29 | **-0.87 (p = 0.047)**; Cityscapes -1.71 (p = 0.11) |
| person / car / bus / truck | 15.52 / 37.64 / 13.49 / 16.70 | 14.63 / 38.10 / 11.61 / 15.52 | **-0.89 (p = 0.006)** / **+0.46 (p = 0.050)** / -1.88 (n.s.) / **-1.18 (p = 0.021)** |
| night | 17.39 | 16.87 | -0.52 (p = 0.07) |

Both still beat the real-only arm (18.23), by 1.7 and 2.6 AP. Primary result by the pre-set rule:
**the v7 profile did not improve per-image value; it is slightly worse.**

**Why (hypothesis formed after seeing this result, so it needs a confirmatory test).** The v7 batch
deliberately matched real class frequencies, which also cut its instances of the rare classes.
Training instances in the 510-image supplements: rand25 has 1,256 persons / 3,821 cars / 69 buses /
1,120 trucks, v7a has 508 / 4,201 / 57 / 209. The class that lost instances lost AP (person 0.40x
instances, -0.89 AP; truck 0.19x, -1.18) and the class that gained instances gained AP (car 1.10x,
+0.46). Across the 25%-real arms at equal image count the same holds for `notb25` (0 trucks and
buses: truck AP gain over real-only +1.4 against +2.7 for rand25). Class AP gain over the real-only
run against log10(instances) over seven 25%-real arms: person slope +3.8 AP per 10x (r = 0.98), car
+3.3 (0.99), truck +0.9 (0.83), bus +1.4 (0.75). Caveats: the arms share counts (three are the same
v5 images), total image count grows with instance count in the large arms, v7a differs in many
other ways at once (fleet, labels, night, camera, hood), and bus is noisy.

**What this means for the generator.** The supplement's value to a detector that already has real
data comes from how many instances of the *scarce* classes (person, truck, bus) it supplies, not
from matching the real class mix. Matching real frequencies (the v7 pedestrian density and truck
share) removed exactly the supply that helps. The other v7 changes are not shown to matter either
way. The measured generator-vs-real differences that remain open are the large vehicles' appearance
(truck -3.0 AP and bus -2.2 against equal-count real data) and the real-vs-synthetic gap overall,
not image statistics (null), box convention (null) or class frequencies (harmful when matched).

**Next (cheap, no rendering):** two selections from the 3,691 existing v5/v5b images, 510 each,
25% real, 3 seeds: (a) matched to v7a's person and truck totals (about 508 and 209), (b)
instance-rich (the 510 images with the most persons, trucks and buses). If (a) scores like v7a, the
v7 deficit is explained by instance supply alone and v7's other changes are neutral; if (b) beats
rand25, oversampling the scarce classes is a free gain and the generator should produce
person- and truck-rich scenes (with the labels and fleet kept correct).

### Instance-supply test result (cluster, 3 seeds each, AdamW, 25% real): half confirmed, half refuted

Pre-set reading: if poor (510 v5/v5b images with about v7a's persons and trucks) scores like v7a,
instance supply alone explains the v7 deficit; if rich (the 510 with the most persons, trucks and
buses) beats rand25, oversampling the scarce classes is a free gain. Both are numbers from the 12
new result files (BDD100K 10,000 images, Cityscapes 500, n=3 per arm, Welch p).

| BDD100K | AP | person | truck | bus |
|---|---|---|---|---|
| rand25 | 20.84 | 15.52 | 16.70 | 13.49 |
| poor25 | 20.66 | 14.78 | 16.21 | 13.86 |
| rich25 | 20.67 | 16.38 | 16.01 | 12.71 |
| v7a25 | 19.97 | 14.63 | 15.52 | 11.61 |

- **poor vs v7a: not the same.** Poor is +0.69 AP over v7a (p = 0.031) and indistinguishable from
  rand25 (-0.18, p = 0.55). Giving rand's images v7a's person and truck supply does not reproduce
  v7a's overall deficit. About 0.7 AP of v7a's -0.87 is therefore from something other than supply:
  the other v7 changes (fleet, labels, night, camera, hood, dry roads) are not neutral, or at least
  not shown to be. Which one is not known; this test cannot say.
- **Person: supply does matter, causally.** Persons in the supplement about 550 / 1,256 / about
  2,000 gave person AP 14.78 / 15.52 / 16.38 (poor -0.74, p = 0.028; rich +0.85, p = 0.018), and
  poor reproduces v7a's person AP (14.78 vs 14.63). Cityscapes agrees (-1.10, +0.96, p = 0.001 and
  0.007).
- **Truck and bus: not supported.** Truck AP 16.21 / 16.70 / 16.01 and bus 13.86 / 13.49 / 12.71
  are not monotonic in supply (rich has about 1,800 trucks and 245 buses against rand's 1,120 and
  69) and no difference is significant. The earlier dose-response slopes for truck and bus came
  from arms that differed in total image count as well; at equal image count they do not show up.
  Cityscapes bus is lower for rich (-5.45, p = 0.062, 500 images, a handful of buses).
- **Rich does not beat rand25 overall:** AP -0.17 (p = 0.63) on BDD100K, -0.78 (p = 0.36) on
  Cityscapes. Oversampling the scarce classes buys person AP and nothing else, so it is not a free
  gain.

**What this means for the generator.** (1) More pedestrians per scene is a real, measured gain for
person AP and v7's matched-to-real density gave it away; a person-richer pedestrian density is
worth rendering. (2) Truck and bus AP do not respond to how many instances there are in this data,
which fits the earlier finding that they are limited by appearance (truck -3.0 AP and bus -2.2
against equal-count real data), not count. More trucks will not fix them. (3) The 0.7 AP of v7a's
deficit that supply does not explain needs its own test before the next render adopts every v7
change together. Caveats: the poor and rich selections are chosen by instance count, so they also
differ in scene content (crowded versus sparse), and n=3 with bus/truck noise of 1 to 2 AP.

### Next render: the current v7 (`train_v7c`) and v7 with v6 pedestrians (`train_v7p`), rules fixed in advance

A correction to the previous entry's plan: `train_v7a` was rendered before the dry-road change and
before the tractor-trailer rigs (its trucks included the bare tractor), so it is not the generator
as it is now. Part of its unexplained 0.7 AP may already be fixed, so the first test is the
current v7, not an ablation of the old one. Ablating scene content versus look and camera is kept
in reserve (below).

Two batches, 512 frames each (256 scenarios, seeds 70000-70255, the seeds of `train_v7a`, so scenes
are the same layouts; pedestrians share the placement random stream with vehicles, so the traffic
is not guaranteed identical between `c` and `p`), `--profile v7`, 25% real, AdamW, 3 seeds each.
About 25 s per frame, so about 3.6 h each.

- `train_v7c`: `urban_dense_v7.yaml` as it is now.
- `train_v7p`: `urban_dense_v7_peds.yaml`: the same except the v6 pedestrian density (constant 0.3,
  which gave the v5 data its 2.5 persons per image; the measured value, not a new guess).

Reading rules, fixed before any result:

1. `c` vs `rand25` on BDD100K overall AP. If `c` is within 0.4 AP of `rand25` (not significantly
   different), the old deficit was the road and the rigs and v7 is at parity: adopt it. If `c` is
   still about 0.7 below `rand25`, run the ablation: scene content (fleet, truck share, rigs,
   views, parking lots) reverted to v6 versus look and camera (night, roads, weather, camera
   pitch and height, hood) reverted to v6, pedestrian density held at v7 in both.
2. `c` vs `v7a`: the effect of the road and rig fixes alone, same scenes. Interpreted only if
   significant (p < 0.05).
3. `p` vs `c`: expected, from the supply test, person AP about +0.7 or more. If overall AP is also
   higher than `c`, the v7 pedestrian density goes back to the v6 value (or a fitted one between).
   If person AP rises but overall AP does not, more pedestrians are not a net gain here.
4. Seed noise is about 0.3 AP, so a difference under 0.5 is not interpreted, and truck and bus AP
   (noise 1 to 2) are reported but not used for decisions.

### Result: current v7 (`v7c`) and v7 with the v6 pedestrian density (`v7p`), read by the rules fixed above

12 new result files (BDD100K 10,000 images and Cityscapes 500, 3 seeds per arm, AdamW, 25% real).

| BDD100K | AP | person | car | bus | truck | night AP |
|---|---|---|---|---|---|---|
| rand25 (older generator) | 20.84 | 15.52 | 37.64 | 13.49 | 16.70 | 17.39 |
| v7a (first v7 batch) | 19.97 | 14.63 | 38.10 | 11.61 | 15.52 | 16.87 |
| v7c (current v7) | 20.18 | 15.02 | 38.18 | 12.30 | 15.21 | 17.55 |
| v7p (current v7, v6 pedestrian density) | 20.99 | 16.24 | 38.11 | 13.51 | 16.12 | 17.88 |

1. **`c` against `rand25`:** AP -0.66 (p = 0.098), outside the 0.4 band, so by the rule v7 as it is
   now has not reached parity (not significant at n=3; the point estimate is what triggers the rule).
2. **`c` against `v7a` (interpreted only at p < 0.05):** overall AP +0.22 (p = 0.41): the dry road and
   the rigs did not move overall AP. Significant: BDD night AP +0.68 (p = 0.020) and Cityscapes truck
   AP +3.25 (p = 0.029, 500 images, a handful of trucks).
3. **`p` against `c`:** AP +0.81 (p = 0.045), person AP +1.21 (p = 0.011); Cityscapes person +1.28
   (p = 0.024). Both overall and person AP rose, so the v7 pedestrian density goes back to the v6
   value for training data. **`p` against `rand25`:** AP +0.16 (p = 0.66), person +0.71 (p = 0.006),
   car +0.47 (p = 0.051), truck -0.58 (p = 0.10), night AP +0.49 (p = 0.13).

**Reading.** Restoring the pedestrian density closes the whole remaining gap (+0.81, against a -0.66
deficit): with it v7 matches the older generator, without it v7 is about 0.7 AP behind. That is
consistent with the supply test (person AP follows the number of persons). It also means the
scene-content versus look-and-camera ablation planned for a persistent deficit is not needed now: the
deficit is accounted for by pedestrian supply. This reading changes what the earlier test said ("about
0.7 AP of the v7a deficit is not supply"): that estimate came from selecting images, this one from
rendering with a different density, and both have n=3 noise of about 0.3 AP. The direct test is the
one to believe.

**What it does not show.** v7 with the v6 pedestrian density is at parity with the older generator on
overall AP, not better. The v7 changes (calibrated night, dry roads, rigs, matched fleet) are not shown
to help overall; the only supported gains are small: night AP (+0.5 over `rand25`, +0.68 over `v7a`,
not significant against `rand25`) and car AP (+0.47). Truck and bus AP did not improve (bus -3.5 on
Cityscapes against `rand25`, p = 0.15, a handful of buses). Matching real pedestrian frequency (the v7
density) costs person AP; `p` has a person in 96% of frames against 32% (44% in city frames) in BDD100K.
Eight metrics per benchmark were compared; the decisions above use only overall and person AP.

**Decision.** Training batches use `urban_dense_v7_peds.yaml` (v7 with the v6 pedestrian density).
`urban_dense_v7.yaml` keeps the real-frequency density and stays as the record of `v7a` and `v7c`.

### v8: the truck and bus mix (version 1.1 plan), rules fixed before any batch exists

**Why.** After 1.0 the largest measured gap is trucks. From the existing result files (n = 3
seeds, BDD100K): at matched real-data size the truck AP gap to real-only data is -2.96 AP
(p < 0.001), -9.8% relative, larger than person (p < 0.001) or car (p = 0.006); it is the same
(-2.5 to -3.6) in every weather and time-of-day slice; AP and AP50 move together, so the boxes that
are found are placed as accurately and the loss is detections missed or mis-scored at IoU 0.5. At
25% real the truck gain from a synthetic supplement is the smallest of any class (+1.2 to +2.1 AP
against +2.2 to +4.0 for persons). The supply test already showed more trucks do not help. A
comparison of real and synthetic labels and crops (the 1,838-image real subset against `train_v7c`;
type shares are by eye from about 100 crops per class, so they carry that uncertainty, and about
30% of real crops could not be classified) found a different mix, not a different count (0.42 trucks
per image against 0.39 real):

| | real BDD100K | v7c |
|---|---|---|
| tractor-trailers among trucks | about 5% | about half |
| box and delivery trucks | about 30% | none (no model) |
| pickups and vans labelled truck | 15-20% | none (counted as cars) |
| trucks at night, share of truck boxes | 17% | 39% |
| buses at night | 20% | 51% |
| buses per image | 0.18 | 0.11 |
| bus types | city bus about 40%, shuttles, school buses, vans | one transit bus |

All City Sample truck, van and bus models are already in the fleet, so the box trucks and the other
bus types need new assets (see the licence question in the 1.1 notes); this entry changes only what
the models we own can express.

**Change (behind new names, so v7 and every older config draw exactly what they did).** A config
field `night_vehicle_scale` (types not listed are unchanged; used for moving traffic, as parked
vehicles are cars and pickups only) and two fleets: `v8a` has 10% tractor-trailers and 90% of the
3-axle truck (which stands in for the box, dump and utility trucks we have no model for); `v8b`
is `v8a` with 20% of trucks drawn from the pickup and the two vans, typed truck. Configs
`urban_dense_v8a.yaml` and `urban_dense_v8b.yaml`, on the v7 profile with the v6 pedestrian density.
Numbers, with their derivation, are in the configs: night factors 0.30 (truck) and 0.36 (bus) from
the real night shares; day weights raised so the per-image rates match the real ones (trucks 5.1%,
buses 3.3% of vehicles).

**Batches and arms.** `train_v8a` and `train_v8b`: 256 scenarios each, seeds 70000-70255 (the seeds
of `v7a`, `v7c` and `v7p`, so scene layouts match), 25% real, AdamW, 3 seeds. Comparison arm:
`hpc_v7p25` (20.99 AP on BDD100K).

**Reading rules (written before any result).**
1. **Does the mix matter?** `v8a25` against `v7p25` on BDD100K truck AP. A gain of at least +1.0 AP
   with p < 0.05 means the mix is a lever: keep v8a. Anything smaller means it is not, with the
   models we own.
2. **Is labelling pickups and vans as trucks worth it?** `v8b25` against `v8a25`. Adopt it only if
   truck AP gains at least +0.5 and car AP does not fall by more than 0.5 (it adds label noise by
   design).
3. **If neither beats `v7p25` by +1.0 on truck AP,** stop tuning the mix. The cause is then the
   appearance of the models (a box-truck model, if its licence allows) or how trucks are missed
   (a per-box check of missed against mislabelled), and the next step is chosen from that.
4. **Guardrails.** Overall, person and car AP must not fall by more than 0.5 against `v7p25`; night
   AP is reported. Bus AP is reported but does not decide anything (its noise is 1-2 AP).
5. Differences under about 0.5 AP are not interpreted. Per-scene scores (a separate run, see
   `hpc/README.md` section 15) decide whether scene coverage is worth building; they do not enter
   this decision.

### Per-scene scores: scene coverage is not where the models fail (rule met: no)

Rule fixed before the run (`hpc/README.md` section 15): if highway or residential trail city street by
more than about 2 AP in the synthetic arms but not in the real-only arm, build that scene type next;
otherwise scene coverage is not where the models fail. A gap is a scene's AP minus city street's in the
same run, so how hard a scene is cancels out.

Arms (25% real, AdamW, 3 seeds each, BDD100K val scored with the scene attribute; 9 new result files
plus the retrained real-only baseline `hpc_real25r`, whose original weights were lost with the old home
directory): `hpc_real25r` (460 real images only), `hpc_rand25` (older generator) and `hpc_v7p25`.

| Scene (val images) | real-only | rand25 | v7p25 | gain, rand25 / v7p25 |
|---|---|---|---|---|
| city street (61.1%) | 18.9 | 21.7 | 21.8 | +2.8 / +2.9 |
| highway (25.0%) | 15.3 | 17.4 | 17.3 | +2.1 / +2.0 |
| residential (12.5%) | 18.0 | 20.0 | 20.1 | +2.0 / +2.1 |

Gap to city street: highway -3.58 (real-only), -4.27 (rand25), -4.50 (v7p25); residential -0.87,
-1.71, -1.72. The synthetic arms trail by 0.7 to 0.9 AP more than real-only on highway (p = 0.066 and
0.149) and 0.8 to 0.9 on residential (p = 0.172 and 0.218): not significant at n = 3. Truck AP by scene
shows the same pattern (a gain of about +2 to +3 in each scene). Parking lot and tunnel are 0.5% and
0.3% of val and are not read.

**Verdict: the rule is not met.** The real-only model already trails city street by -3.6 AP on highway,
so highway is simply harder, and synthetic data helps by about the same amount in every scene. Highways,
residential streets, skyscrapers and other city variations are removed from the roadmap as AP levers (a
small, non-significant extra highway gap remains possible and would need a larger test to see). They may
still be built for realism. The remaining gap is the one found in the v8 entry: the truck and bus
appearance and mix.

Caveats: three seeds per arm; the baseline is a retrain (same recipe and seeds as the original, not
byte-identical); the check compares gap structure, not absolute AP.

### v8a result: cutting the rigs and moving trucks off the night frames did not raise truck AP (rule 1: no)

`train_v8a` (256 scenarios, seeds 70000-70255, 25% real, AdamW, 3 seeds) against `hpc_v7p25`, which has
the same scenes and pedestrians. Batch statistics against the config's targets: truck boxes at night 17%
(target 17%, v7p 39%), bus boxes at night 30% (target 20%, on 82 boxes, within about two standard
deviations), buses 0.16 per image (target 0.18, v7p 0.11), persons and cars unchanged (3.30 and 8.05 per
image). One miss: trucks fell to 0.31 per image (target 0.39, v7p 0.42), because the tractor-trailers
produced more labelled boxes per spawned vehicle than the 3-axle truck does.

| BDD100K | AP | person | car | truck | bus | night AP |
|---|---|---|---|---|---|---|
| v7p25 | 20.99 | 16.24 | 38.11 | 16.12 | 13.51 | 17.88 |
| v8a25 | 20.65 | 16.42 | 38.24 | 15.62 | 12.34 | 17.27 |
| difference (p) | -0.34 (0.34) | +0.18 (0.40) | +0.12 (0.07) | **-0.50 (0.35)** | -1.17 (0.28) | -0.62 (0.10) |

Cityscapes: truck -1.32 (p = 0.43), bus +1.46 (p = 0.30), AP +0.06.

**Rule 1 (needed truck AP +1.0 with p < 0.05): not met.** The guardrails hold (overall, person and car
within 0.5). With the models we own, a more realistic night share, fewer rigs and a bus rate at the real
level do not move truck AP. Caveat set beforehand: v8a has 26% fewer truck boxes than v7p, which could
hide a small gain; the supply test (226 against 1,800 trucks, no difference) says this matters little.
The tractor-trailers may even help (v7p truck 16.12 against v8a 15.62; rigs also helped truck AP on
Cityscapes against v7a), but that is not established.

Open: `v8b` (pickups and vans labelled truck for 20% of trucks) is still to be trained, and rule 2 and
rule 3 are read when it is in. If it also fails to beat v7p25 by +1.0, the mix is closed as a lever and the
next step is the per-box check (which truck and bus boxes are missed or mislabelled, by size).

