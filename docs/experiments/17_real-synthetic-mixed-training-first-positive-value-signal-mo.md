## Real + synthetic (mixed training) — first positive value signal, modest

**Change:** instead of asking whether synthetic can replace real data, ask whether it *adds* to
it. `F:/datasets/mixed_real_v5/data.yaml` trains on the real-control images (1,838 BDD100K
training images) **plus** the v5 synthetic images (1,838), 3,676 total, validated on the same
199 real images the real control used to pick its best checkpoint (BDD100K's own validation
set stays untouched for scoring). Everything else matches the real-control recipe: scratch,
200 epochs, imgsz 960, mosaic on, `close_mosaic` 10, seed 0.

| Arm | BDD100K AP / AP50 | Cityscapes AP / AP50 |
|---|---|---|
| Real only (1,838 real) | 28.1 / 48.4 | 26.1 / 42.5 |
| **Real + v5 synthetic (3,676)** | **29.3 / 49.8** | **27.1 / 44.4** |

Per class on BDD100K, all four rose (person 21.6 → 23.3, car 43.7 → 44.2, bus 23.5 → 25.2,
truck 23.6 → 24.3). Every BDD100K condition improved (+0.7 to +2.7 AP), most in rain (+2.1)
and snow (+2.7); those are 738- and 769-image subsets, so noisy. On Cityscapes three classes
rose (person 17.3 → 20.1, car 42.1 → 44.0, truck 16.7 → 20.3) and bus fell (28.2 → 24.0, 98
boxes).

**Verdict: the first positive sign that the synthetic data is worth something, but modest
(+1.2 and +1.0 AP, about 4%) and not yet established.** Consistent in direction across both
benchmarks, all four BDD100K classes and every condition, which is encouraging; but both arms
are single runs, the real-trained noise level is unmeasured (synthetic-only runs swing 0.6 to
2.5 AP, real-trained runs probably less), and the mixed run also takes twice as many training
steps per epoch (460 vs 230 batches). **Next, to turn this into a claim:** (1) a second seed
for both real-only and mixed, to measure the noise; (2) a real-only run at 3,676 real images,
to see how the synthetic images compare with real ones image for image; (3) a data-efficiency
sweep (e.g. 25% / 50% real + synthetic) -- the version a customer would care about.

