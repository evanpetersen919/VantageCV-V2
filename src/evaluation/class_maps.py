"""How real-dataset labels map onto this project's four detection classes.

The synthetic export (``COCO_PROFILE``) has person 1, car 3, bus 6, truck 8. A real
benchmark has more classes than that, and some of them look like ours: a rider on a
bike looks like a person, a train looks like a bus or truck. Scoring a detector on the
real labels needs three outcomes for every real label:

* **positive** -- maps to one of our classes and is scored normally;
* **ignore** -- a region where a detection of some of our classes is neither rewarded
  nor penalised (COCO's ``iscrowd`` mechanism), because the object is real but is not
  something the synthetic data ever contained (riders, trains, trailers, crowds);
* **dropped** -- irrelevant (traffic signs, road, sky) and not represented at all.

Every choice below is a design decision, not a measured fact; they are collected here so
they can be reviewed and changed in one place, and the loaders record the mapping used.
"""

from typing import Dict, Tuple

PERSON, CAR, BUS, TRUCK = 1, 3, 6, 8

OUR_CLASSES: Dict[int, str] = {PERSON: "person", CAR: "car", BUS: "bus", TRUCK: "truck"}

# COCO-80 class indices (0-based, as ultralytics and torchvision-COCO detectors emit them)
# onto our ids. Anything else a COCO-pretrained detector predicts is discarded.
COCO80_INDEX_TO_OURS: Dict[int, int] = {0: PERSON, 2: CAR, 5: BUS, 7: TRUCK}

# BDD100K detection categories.
BDD100K_POSITIVE: Dict[str, int] = {"person": PERSON, "car": CAR, "bus": BUS, "truck": TRUCK}
BDD100K_IGNORE: Dict[str, Tuple[int, ...]] = {
    "rider": (PERSON,),
    "train": (BUS, TRUCK),
}
# "bike", "motor", "traffic light" and "traffic sign" are dropped.

# Cityscapes instance labels.
CITYSCAPES_POSITIVE: Dict[str, int] = {"person": PERSON, "car": CAR, "bus": BUS, "truck": TRUCK}
CITYSCAPES_IGNORE: Dict[str, Tuple[int, ...]] = {
    "rider": (PERSON,),
    "train": (BUS, TRUCK),
    "caravan": (TRUCK, CAR),
    "trailer": (TRUCK,),
}
# A Cityscapes "<x>group" label (persongroup, cargroup, ...) marks a crowd of x that is
# not split into instances: an ignore region for x's own class.
CITYSCAPES_GROUP_SUFFIX = "group"

# Objects smaller than the export policy's floor were never in the training labels, so
# they are not scored on the real side either (they become ignore regions).
MIN_BOX_HEIGHT_PX = 8.0
MIN_BOX_WIDTH_PX = 4.0
