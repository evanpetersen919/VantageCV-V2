## Correction: the optimizer differs between arms (found in review, verified)

An independent review of the results found a confound that affects several comparisons above.
Ultralytics' default `optimizer=auto` picks **MuSGD (lr 0.01) when `ceil(N/64) x epochs > 10,000`,
otherwise AdamW (lr 0.00125)** (`ultralytics/engine/trainer.py`, `build_optimizer`). Checked in the
installed 8.4.163 source and in the local training logs (the 1,838-image real control logged AdamW,
the 3,676-image real + synthetic run logged MuSGD). Applying the rule to every arm:

* AdamW: real25, real50, real-only (1,838), mixed25 (2,298), mixed50 (2,757), the synthetic
  pre-train runs and all fine-tunes (50 epochs).
* MuSGD: mixed (3,676), real3676, mixed25big (4,151), mixedbig (5,529).

What this does and does not affect:

* **Not affected (same optimizer both sides):** the 25% and 50% gains from synthetic data
  (+4.7, +3.3); mixed vs real3676 (both MuSGD, same steps: real is +3.04 better); mixedbig vs
  mixed (both MuSGD; but with 1.5x the steps); pre-train + fine-tune vs mixed at 25% and 50%.
* **Confounded (optimizer differs):** mixed vs real-only at 100% real (+0.66) and the "+3.70" for
  3,676 real vs 1,838 real; mixed25big vs mixed25 (-0.27); mixedbig vs real-only (+1.59); fine-tune
  vs mixed at 100%. These numbers mix the effect of the data with the effect of the optimizer.

Other corrections: (1) bus/truck "302 and 746" boxes are the **night** subset of BDD100K; the full
val set has 1,597 bus and 4,231 truck boxes (Cityscapes: 98 and 93); (2) the "smallest possible
exact permutation p" of 0.05 for 3 vs 3 is one-sided (two-sided it is 0.10); (3) the "real-image
equivalents" interpolate linearly on a concave curve and are therefore upper-biased; log-linear
interpolation gives roughly +450 / +490 / +240 real images at 25% / 50% / 100% real instead of
+450 / +570 / +330; (4) with 17 mixed-vs-real-only tests at 100% real, a Holm correction
leaves only BDD car significant, so the 100% claims are weak even before the optimizer issue.

**Follow-up runs (prepared, same recipe with the optimizer fixed to AdamW lr 0.00125):** mixed,
real3676, mixed25big and mixedbig, plus a step-matched real-only run (400 epochs, so the same
number of optimizer steps as mixed), 3 seeds each.

