## v17 street realism: does it change detector AP? (pre-registered 2026-10-10)

Written before the render finishes and before any detector is trained on it. Result: **pending**.

**Question.** Entries 30 to 34 made the streets look more like real ones (lane markings and stop lines, signal heads that
follow the phase, wet-road-capable scenes unchanged, scanned trees, shrubs and grass). None of that has been tested against a
detector. Does a detector trained with real BDD100K images plus the v17 synthetic supplement score differently on real
BDD100K validation images than the same detector with the v13r supplement?

**Arms (same scenes, same seeds).**

| Arm | Synthetic supplement | Config |
|---|---|---|
| `v13r25` (existing) | `train_v13r`: seeds 70000 to 70255, 512 frames, exact labels | `urban_dense_v13r.yaml` |
| `v17_25` (new) | `train_v17`: the same seeds 70000 to 70255, 512 frames, exact labels | `urban_dense_v17.yaml` |

Both use the 25% real regime of the project's logged recipe (YOLOv10m from scratch, 200 epochs, 960 px, AdamW fixed, seeds
0, 1, 2) and are scored with the same settings on BDD100K val and Cityscapes val. Because the layout, traffic and
pedestrians for a seed are unchanged by the v14 to v17 flags (a tested property), the differences between the arms are the
street-level features only: markings and stop lines (and the queue position with them), signal heads, trees, shrubs, grass.
The v17 vegetation also changes in spring and summer (none before), which is part of what is being tested.

**What is not controlled.** These changes are bundled, so a difference cannot be attributed to one of them. This is a
"does the bundle matter" test, not an ablation.

**Primary outcome.** Overall BDD100K AP@[.5:.95] (person, car, bus, truck), mean over three seeds, v17_25 minus v13r25.

**Decision rule (fixed now).**
- **Helps**: mean difference at least +0.5 AP and a paired comparison over seeds that is positive in all three.
- **Hurts**: mean difference at most -0.5 AP and negative in all three.
- **No resolvable effect**: otherwise (the project does not interpret differences under about 0.5 AP at three seeds).

Reported, not decisive: per-class AP, Cityscapes AP, AP by time of day, and the person, car and truck guards.

**Limits stated in advance.**
- Three seeds, one real-data size, one batch size: a null result is "not resolvable", not "no effect".
- v13r and v17 differ in vegetation for spring and summer scenes, in winter and fall the trees are different models.
- The synthetic supplement is 512 images; effects of road paint on small boxes may need more.

**Run.** Render `live_dataset/train_v17` (`bin/generate_live_dataset.py --profile v7 --config ...v17.yaml
--num-scenarios 256 --seed 70000 --exact-labels`), split by scenario, upload with the cluster scripts, three seeds.
