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

from dataclasses import dataclass
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


@dataclass(frozen=True)
class ClassProfile:  # pylint: disable=too-many-instance-attributes
    """A set of classes, and how real benchmark labels and a COCO detector map onto it."""

    name: str
    classes: Dict[int, str]
    bdd_positive: Dict[str, int]
    bdd_ignore: Dict[str, Tuple[int, ...]]
    cityscapes_positive: Dict[str, int]
    cityscapes_ignore: Dict[str, Tuple[int, ...]]
    coco80_to_ours: Dict[int, int]

    @property
    def class_order(self) -> Tuple[int, ...]:
        """Class ids in YOLO index order (sorted by id)."""
        return tuple(sorted(self.classes))


DEFAULT_PROFILE = ClassProfile(
    "default",
    OUR_CLASSES,
    BDD100K_POSITIVE,
    BDD100K_IGNORE,
    CITYSCAPES_POSITIVE,
    CITYSCAPES_IGNORE,
    COCO80_INDEX_TO_OURS,
)

# The rider profile scores the vulnerable-road-user classes as classes instead of ignoring or
# dropping them: BDD100K ``rider`` (the person on the vehicle), ``bike`` and ``motor``; Cityscapes
# ``rider``, ``bicycle`` and ``motorcycle``. ``bike`` and ``motor`` take the COCO ids of bicycle (2)
# and motorcycle (4); ``rider`` has no COCO counterpart and gets id 10. A COCO-pretrained detector's
# bicycle and motorcycle outputs map to bike and motor; it has no rider output.
BIKE, MOTOR, RIDER = 2, 4, 10
RIDER_CLASSES: Dict[int, str] = {
    PERSON: "person",
    BIKE: "bike",
    CAR: "car",
    MOTOR: "motor",
    BUS: "bus",
    TRUCK: "truck",
    RIDER: "rider",
}
_RIDER_POSITIVE = {"person": PERSON, "car": CAR, "bus": BUS, "truck": TRUCK, "rider": RIDER}
RIDER_PROFILE = ClassProfile(
    "riders",
    RIDER_CLASSES,
    {**_RIDER_POSITIVE, "bike": BIKE, "motor": MOTOR},
    {"train": (BUS, TRUCK)},
    {**_RIDER_POSITIVE, "bicycle": BIKE, "motorcycle": MOTOR},
    {"train": (BUS, TRUCK), "caravan": (TRUCK, CAR), "trailer": (TRUCK,)},
    {0: PERSON, 1: BIKE, 2: CAR, 3: MOTOR, 5: BUS, 7: TRUCK},
)
PROFILES: Dict[str, ClassProfile] = {
    DEFAULT_PROFILE.name: DEFAULT_PROFILE,
    RIDER_PROFILE.name: RIDER_PROFILE,
}
