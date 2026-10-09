# Rider headroom check: does more real rare-class data help at all?

Registered 2026-10-09, before any dataset of this study is built or any detector is trained for it. It comes before
the synthetic experiment in `preregistration.md` and is cheaper: it needs no new assets. Its job is to decide
whether building the rider pipeline further is worth it.

Tags as in `preregistration.md`: **measured**, **recipe** (the project's logged training recipe), **choice**
(decided now, without evidence, and fixed).

## Question

At the project's real-data size (1,838 images), does training on more real images of riders, bikes and motors raise
rider, bike and motor AP on real BDD100K validation images, beyond what the same number of extra *ordinary* real
images gives? If more real rare-class data does not help, synthetic rare-class data is unlikely to either, and the rider
pipeline should not be built further on that argument.

## Arms (built by `bin/prepare_rider_headroom.py`)

All arms train on the 7-class rider profile (person, bike, car, motor, bus, truck, rider) and share one validation
list used only to pick the best checkpoint.

| Arm | Training images |
|---|---|
| A | The base set: the first 1,838 images of the seeded shuffle (seed 0) of BDD100K's training images, **the project's existing real control**. The builder checks that its split equals `bdd100k_control/split.json`: it does (train and validation lists identical). |
| rare2 | A + r0 rare images from the rest of the shuffle, so the base's rare images are doubled |
| rare4 | A + 3 r0 rare images, so quadrupled (contains rare2's extras) |
| rand2 | A + r0 images drawn at random from the rest of the shuffle (the same number of extra images, at the natural rate of rare images) |
| rand4 | A + 3 r0 random images (contains rand2's extras) |

A *rare image* contains at least one rider, bike or motor `box2d`. **Measured** (from the full training labels, no
training involved): r0 = 172 of the 1,838 base images (9.4%), 9.13% of all 70,000 training images are rare, so
rare2 and rand2 each have 2,010 images and rare4 and rand4 2,354. `rare` against `rand` separates "more rare images"
from "more images".

## Training and evaluation

**Recipe** as in `preregistration.md` section 4: YOLOv10m from scratch, 200 epochs, image size 960, batch 8, mosaic 1.0
with close-mosaic 10, AdamW fixed explicitly (`--lr0 0.00125 --momentum 0.9 --warmup-bias-lr 0.0`). **Seeds 0, 1, 2** for
each of the 5 arms, 15 runs (**choice**: three seeds because this is a go / no-go check, not the final claim; the
decision rule below is chosen to be robust to that). Scored on the BDD100K validation set (10,000 images) with the
rider profile (`bin/evaluate_detector.py --profile riders`, `--conf 0.001 --iou 0.6 --max-det 100`, **recipe**).

**Primary outcome M:** the mean AP@[.5:.95] of the classes rider, bike and motor.

## Decision rule

Compare per seed (paired by seed s = 0, 1, 2):

- d_rare(s) = M(rare4, s) - M(rand4, s): the effect of more rare real images, over the same number of other images.

**Headroom exists** only if **both** hold (**choices**):

1. the mean of d_rare is at least **1.0 AP**;
2. d_rare(s) is positive for **all three** seeds.

Otherwise **the result is "no headroom shown"**: the rider build is stopped (or redirected to the cheaper
alternatives named in the project notes), and the result is logged with the same detail as a positive one. If the rule
says headroom exists, the next step is the synthetic experiment in `preregistration.md`.

Reported but not used for the decision: M(rand4) - M(A) (the effect of more images alone), the same differences for
the doubled arms, per-class AP, AP by box size and by time of day, and the guards (car and person AP of every arm
against A).

## Limits stated in advance

- Three seeds cannot show a small effect reliably; 1.0 AP with a positive sign in all three seeds is a deliberately
  modest bar, not a significance test, and the per-seed numbers are published.
- Rare images are chosen by label content, so they are not a random sample of riders; they may be easier or harder than
  the riders in the base set. This is the point of the check (the data a detector would be shown), and it is a caveat on
  reading it as a pure data-quantity effect.
- The regime is one real-data size (1,838). A flat curve here does not say what 70,000 real images would do.
- Real rare images carry the real label conventions and noise; synthetic ones would carry exact labels. A "no
  headroom" result is evidence against the synthetic route's usefulness but is not a proof.
- The cluster runs have not been executed when this is written.

## How to run (cluster)

Built and checked locally (`F:/datasets/rider_headroom`, 245 MB; every listed image and label file exists, and the YOLO
class histogram of each arm equals its instance counts). The job scripts were **not run on a cluster**: the shell syntax
and the data re-rooting step were tested locally, and a 1-epoch training run and the scoring of its weights with the
rider profile were run locally as a smoke test (the report lists all 7 classes), but the Slurm path itself has not run.

```bash
# on the PC (Git Bash): bundle the datasets; BDD100K validation and Cityscapes are already on the cluster
tar -cf rider_headroom.tar -C /f/datasets rider_headroom/images rider_headroom/labels rider_headroom/arms     rider_headroom/val.txt rider_headroom/split.json
scp rider_headroom.tar <you>@<cluster>:~/vantagecv/data/   # then untar there, so ~/vantagecv/data/rider_headroom exists

# on the cluster, after `git pull` of this repository
EPOCHS=2 bash hpc/submit_rider.sh smoke_rider A 0        # smoke test first
bash hpc/experiments/submit_rider_headroom.sh            # 15 jobs: hpc_rider_<arm>_s<seed>
```

Results land in `results/hpc_rider_<arm>_s<seed>_bdd100k_riders.json` (and `_cityscapes_riders.json`). Scoring is the
project's `bin/evaluate_detector.py --profile riders`; per-class AP is in `overall.per_class_ap`.

## Reference: the COCO-pretrained detector on the rider classes

`results/baseline_coco_bdd100k_riders.json`: the COCO-pretrained YOLOv10m scored with the rider profile (bicycle maps
to bike, motorcycle to motor; COCO has no rider class, so rider AP is 0 by construction). It is a reference for the
scale of bike and motor AP, not an arm of the study.

## Amendments

None yet.
