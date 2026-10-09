## v5a — mosaic ablation (quick signal)

**Change:** two YOLOv10m scratch runs on the same v4b training set, differing only in
`mosaic`: default (`1.0`) vs. `mosaic=0`, all other augmentation/hyperparameters identical.
Evaluated both on the same fast 1,000-image slice of BDD100K val (not the full 10,000-image
benchmark used elsewhere in this log — a quick signal, not a final number) at the standard
`imgsz=960 conf=0.001 iou=0.6`.

| Arm | AP / AP50 | person | car | bus | truck |
|---|---|---|---|---|---|
| mosaic=1.0 (default) | 2.9 / 6.2 | 4.4 | 6.3 | 0.5 | 0.5 |
| mosaic=0 | **3.2 / 7.2** | 4.8 | 6.4 | 0.9 | 0.8 |

**Verdict: mosaic off wins on every class, on this quick slice** — small in absolute terms
(+0.3 AP, ~10% relative) but directionally consistent, unlike the mixed/class-splitting
pattern v4a showed. This is consistent with the standing hypothesis: this project's images
are single coherent scenes with real geometric consistency (fixed camera height, consistent
distance-to-scale relationships) that 4-way mosaic stitching destroys, and a model trained
without it retains those real cues better. Not yet confirmed at full-benchmark scale or
across a second seed — see the priority list below for what would raise confidence.

