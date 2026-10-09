## Optimizer-controlled re-runs, step-matched control, truck/bus ablation (cluster)

Follows the optimizer correction above. All new arms use AdamW (lr 0.00125, momentum 0.9,
warmup_bias_lr 0), which is what `optimizer=auto` chose for the short arms. 21 runs trained
(`hpc_adamw_mixed`, `_real3676`, `_mixed25big`, `_mixedbig`, `_real400`, `hpc_notb25`,
`hpc_rand25`, seeds 0-2); every job crashed at the very end of training in ultralytics' final
validation (`ModuleNotFoundError: ultralytics.engine.exporter`, a damaged cluster environment after
a disk-quota incident), so the trained `best.pt` files were scored separately with
`bin/evaluate_detector.py` (same settings as `hpc/run_arm.sbatch`) on the cluster. A cross-check
scored 10 of the same weights on the local PC (different torch build): AP differs by at most 0.015
(per class at most 0.08), so the scoring stack does not matter. All 42 result files checked (image
counts, ground-truth counts, settings, weights path).

**Invalid run, excluded and flagged:** `hpc_adamw_mixed_s1` ran only 43 minutes (the other mixed
seeds ran 3.8-3.9 h) and scores 25.63 BDD100K AP against 30.05 and 29.89 for seeds 0 and 2. It was
almost certainly stopped early and is undertrained. Analyses below use `--exclude
hpc_adamw_mixed_s1`, so the AdamW mixed arm has **n = 2**; it needs a re-run (verify with the epoch
count in its `results.csv`). Everything involving that arm is provisional until then.

BDD100K AP (Cityscapes in brackets), mean over seeds:

| Arm | Real | Synthetic | Optimizer | AP |
|---|---|---|---|---|
| real only (200 ep) | 1,838 | 0 | AdamW (auto) | 28.28 (26.35) |
| real only, step-matched (400 ep, early-stopped at 259) | 1,838 | 0 | AdamW | 27.98 ± 0.34 (25.87) |
| mixed, v5 only | 1,838 | 1,838 | AdamW, n = 2 | 29.97 (28.3) |
| mixed, v5 only (earlier run) | 1,838 | 1,838 | MuSGD (auto) | 28.94 ± 0.28 (27.52) |
| mixed, v5 + v5b | 1,838 | 3,691 | AdamW | 30.94 ± 0.25 (29.13) |
| real only | 3,676 | 0 | AdamW | 32.79 ± 0.42 (31.66) |
| mixed25, v5 only | 460 | 1,838 | AdamW (auto) | 22.93 ± 0.35 (23.17) |
| mixed25, v5 + v5b | 460 | 3,691 | AdamW | 23.39 ± 0.15 (23.86) |

**What changed:**
* **The optimizer matters.** Same data, AdamW vs MuSGD: real3676 +0.81 (p = 0.07), mixed v5+v5b
  +1.07 (p = 0.04). The earlier 100%-real "+0.66" understated the benefit.
* **At 100% real, synthetic data helps more than reported:** mixed (AdamW) vs the step-matched
  real-only run is **+2.00 BDD100K AP (p = 0.004)** and **+3.37 Cityscapes (p = 0.02)**; person +2.2,
  car +1.1, night +2.3. Against the 200-epoch real-only run it is +1.7. More steps do not help the
  real-only arm (400 ep: -0.31 vs 200 ep, n.s.), so this is not a compute effect. Provisional: n = 2.
* **Equal-count real data still wins** (the gap to beat): 3,676 real beats 1,838 real + 1,838
  synthetic by 2.82 BDD (p = 0.004; Cityscapes 2.42), and 1,838 real + 3,691 synthetic by 1.85
  (Cityscapes 2.53). Real images added +4.82 AP over the step-matched baseline.
* **Volume (second batch):** +0.97 BDD at 100% real (p = 0.011, mixed arm n = 2; person +0.93,
  car +0.65; Cityscapes -0.11, n.s., with person +1.5 and car +1.5 but truck -3.6) and +0.46 at 25%
  real (p = 0.14; person +0.72 p = 0.006, car +0.91 p = 0.002). The earlier -0.27 at 25% was the
  optimizer confound. More data helps a little, mostly person and car.
* **Value per synthetic image** (real-only AP curve read log-linearly; approximate): 510 images
  ≈ 210 real images (2.4 synthetic per real); 1,838 ≈ 450-550 (3.4-4.1 per real); 3,691 ≈ 500-930
  (4-7 per real). Diminishing at 25% real, steadier near 4:1 at 100% real.

**Truck/bus ablation** (25% real = 460 images + 510 synthetic; AdamW; n = 3 each): `notb25` uses the
510 synthetic training images that contain no truck or bus, `rand25` an equal number of random
ones. BDD100K AP: real-only 18.23, `notb25` 20.14, `rand25` 20.84. Both help (+1.9 p < 0.001 and
+2.6 p = 0.004). Removing trucks and buses costs only 0.70 AP (p = 0.088) overall but **-1.26 truck AP
(p < 0.001)** and -0.66 night; bus -1.43 (n.s.). Without any synthetic truck, truck AP still rises
+1.42 (p = 0.003) over real-only: the gain is mostly general, and **synthetic trucks help truck AP, so
the oversized truck share (5x BDD) is not what hurts it.** Caveat: truck-free scenes are not a random
subset (they may differ in other ways), so the -0.70 includes scene differences.

**Where the remaining gap to real data sits** (1,838 real + 3,691 synthetic minus 3,676 real, BDD100K):
* By object size: small -0.9, medium -2.1, **large -2.5** (mixed vs real3676: small -1.2, medium
  -2.9, large -4.1). The scale hypothesis (synthetic objects too large, no distant ones) is **not
  supported**; the gap is biggest on large objects.
* By class: **truck -3.0, bus -2.2**, car -1.2, person -1.1: the large vehicles lag most.
* By condition: night -1.9, daytime -1.85, clear -1.45, overcast -1.75, rain -2.1, snow -1.6,
  dawn/dusk -1.55, partly cloudy -2.2 -- **uniform. The earlier "night is worst" reading came from
  the MuSGD comparison and is not supported once the optimizer is controlled.**

**Verdict, revised:** synthetic data from this generator improves a real-data-limited detector at
every real-data size tested, by about +4.7 AP at 460 real images, +3.3 at 919 and about +2 at 1,838
(provisional), at roughly 3-7 synthetic images per real image; a second batch adds a little (mostly
person/car). It still loses to the same number of real images by 2-3 AP, uniformly across
conditions, and most on large vehicles (truck, bus). A uniform gap across weather and time of day
points at global image statistics or large-vehicle appearance, not at one missing condition.
Caveats: three seeds (two for one arm), borderline p-values, uncorrected subgroup tests; "equivalent
real images" are interpolated.

**Next:** (1) re-run `hpc_adamw_mixed_s1` and confirm the +2 at 100% real with n = 3; (2) test the
global-image-statistics hypothesis cheaply: apply the calibrated pixel-realism processing
(`bin/apply_image_realism.py`) to the existing synthetic images and re-run the 25%-real mixed arm
(no rendering); (3) large-vehicle content (semis, box trucks, more bus models) is the content
candidate that the data supports, but needs new assets; (4) do not cut the truck share.

### Correction: the numbered vehicle material instances are not livery variants

An asset audit said each bus/truck model's 23 numbered `MI_<model>_N` material instances were
unused livery variants. A read-only editor script (`unreal_plugin/tools/inspect_vehicle_instances.py`)
listed what each one overrides: they are the model's **per-part materials** (glass, windshield,
window, tire, rim, mirror, light, bulb, licence plate, interior, undercar, steel, plastic...), each
pointing at the same shared textures. The only livery content is one fixed side-graphic texture pair
(`GraphicsL`/`GraphicsR`) on the bus and two of the trucks. There is no unused livery variety to
switch on; more bus/truck variety needs more models. The idea of using "unused livery variants" is
withdrawn.

![BDD100K AP against the number of real images, with and without synthetic images](../images/results_benefit_vs_real_data.png)

![At 1,838 real images: adding 1,838 synthetic images adds about 2 AP, adding 1,838 real images adds about 5](../images/results_control_at_1838_real.png)

![The gap to equal-count real data by class: truck -3.0, bus -2.2, car -1.2, person -1.1](../images/results_gap_by_class.png)

*Figures from `bin/plot_results.py` (mean over three seeds, bar = sd).*

