## Priority list: most critical to least critical (post-v4b/v5a synthesis)

Four research passes fed this ranking: a statistical-rigor audit, a Grad-CAM comparison
across v3/v4a/v4b(scratch+finetune) on 11 real images, a "what would a startup-grade
pipeline need" gap analysis, and the v5a mosaic ablation above. Ranked by expected impact on
real-world transfer, not by ease of implementation.

1. **The model isn't learning real object shape at all — it's keyed on spurious texture.**
   Grad-CAM overlays (`runs/gradcam_v2/`, `runs/gradcam_v3/`) show the *same* attention
   pattern — foliage edges, curb lines, lane paint, glare — across every arm tested (v3, v4a
   pixel-realism, v4b modal boxes), on the same 11 real images. **Update (Grad-CAM v3, see the
   entry above): v5's changes measurably reduced this in daytime conditions, but did not fix
   it, and night is untouched.** A specific, now-confirmed reason: this project's live-render
   pipeline has a real, generic material-override system (scalar/vector/whole-material-swap)
   reaching buildings, ground/pavement and vehicles, but **trees/foliage have zero appearance-
   override mechanism at all** — no fix so far could have touched Grad-CAM's foliage cue
   directly, regardless of intent. This is the single most important open finding: until
   synthetic training teaches shape/silhouette cues that generalize, every other fix is
   polishing a symptom. Grounded in the literature, not a guess: Geirhos et al. 2019 (ImageNet
   CNNs are texture-biased by default; training on style-randomized-texture data restores
   shape bias) and Tobin et al. 2017 / Tremblay et al. 2018 (sim-to-real domain randomization:
   randomize textures/lighting/camera in non-realistic ways specifically to force shape
   learning) all independently prescribe the same fix this project has never tried: texture/
   style randomization decorrelating class identity from background texture, not more
   realism. A full plan for this (staged: rebuild Grad-CAM tooling → segmentation-guided
   background stylization, no re-render needed → push existing render-side randomization
   harder → new C++ texture/post-process work if still needed) is written up separately.
2. **Zero domain randomization of camera intrinsics/extrinsics, materials, or textures.**
   Every render uses the same camera model and a fixed small set of building/vehicle
   materials. Real datasets are shot on dozens of different camera rigs; a detector trained
   on one fixed synthetic camera setup has an easy shortcut (exact pixel-to-metric scale) that
   doesn't exist in real data and won't transfer. This is upstream of and likely a bigger lever
   than any single asset fix (trees, lamps, etc.).
3. **Dataset scale is 1-2 orders of magnitude below the academic synthetic baselines this
   project is implicitly competing with** (~2,000 images here vs. 100k+ in published
   sim-to-real work). Every arm in this log is trained on a dataset small enough that label
   convention and augmentation flags can visibly move the needle by whole percentage
   points — a sign the model is data-starved, not just imperfectly labeled.
4. **No run in this entire experiment (v1 through v5a) has ever been repeated with a
   different seed.** Every "gain" or "regression" logged above, including v4b's flagship
   +0.9 AP and v5a's +0.3 AP, is a single sample with completely unmeasured run-to-run
   variance. Before trusting any ranking in this list numerically, the top 2-3 candidate
   fixes should be validated with at least 2 seeds each.
5. **Mosaic augmentation** (this ablation): real, consistent, but modest (+0.3 AP quick
   signal) — worth keeping `mosaic=0` as the default going forward given it's free (a training
   flag, no re-render) and never lost on any class, but it will not close the sim-to-real gap
   by itself and should not be over-weighted relative to items 1-3.
6. **Modal (visible-region) occlusion boxes** (v4b, already shipped) — confirmed real,
   modest gain on the scratch arm (+0.9 AP), flat on fine-tune. Correct box convention is a
   prerequisite others might build on, but the Grad-CAM evidence (item 1) shows it doesn't
   touch the actual attention problem.
7. **Small-object/rare-class volatility** (per the statistical-rigor agent): bus/truck
   numbers swing by 2-4x across arms on ground truth as small as 93-98 boxes (Cityscapes).
   These deltas are consistent with sampling noise alone and shouldn't be read as signal
   without more data or seeds.
8. **Architecture/tooling gaps that block scaling up**, not blockers to any single number
   today but blockers to acting on items 2-3 cheaply: single-instance sequential live-render
   architecture (Ray parallelism exists for the offline path but was never extended to
   live-render), no automated synthetic-vs-real drift detection, 3D boxes/lane-graph data
   computed then discarded at export (no LiDAR pairing yet).
9. **Unused already-installed assets** (Alder/Maple Red/Maple Sugar trees, extra building
   facades, second lamp style, bench/sign kits — v5b above) — real diversity gaps, but the
   least critical item here: cheap to add, but nothing in the Grad-CAM evidence suggests
   scene-object diversity is the bottleneck compared to items 1-4.

