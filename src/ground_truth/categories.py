"""Shared object category IDs.

Used consistently across ground-truth extraction
(``BoundingBox3D.category_id``) and COCO export (category definitions)
so the two can never independently drift out of sync -- a single source
of truth for "what is category 3," rather than each module inventing its
own numbering.
"""

from dataclasses import dataclass
from typing import Dict, Tuple

BUILDING = 1
SEDAN = 2
SUV = 3
TRUCK = 4
BUS = 5
PEDESTRIAN = 6
RIDER = 7
BICYCLE = 8

CATEGORY_NAMES: Dict[int, str] = {
    BUILDING: "building",
    SEDAN: "sedan",
    SUV: "suv",
    TRUCK: "truck",
    BUS: "bus",
    PEDESTRIAN: "pedestrian",
}

# The two classes cyclists add (see ``cyclists.py``). Kept out of ``CATEGORY_NAMES``, this project's
# fixed original schema, so every earlier export is unchanged; they are written by the ``riders``
# profile only.
CYCLIST_CATEGORY_NAMES: Dict[int, str] = {RIDER: "rider", BICYCLE: "bicycle"}

# Maps ScenarioTypeConfig.vehicle_mix's string keys (see
# src/procedural/scenario.py) onto the category IDs above.
VEHICLE_TYPE_TO_CATEGORY: Dict[str, int] = {
    "sedan": SEDAN,
    "suv": SUV,
    "truck": TRUCK,
    "bus": BUS,
}


@dataclass(frozen=True)
class CategoryProfile:
    """How this project's fine categories are written to a dataset.

    ``categories`` lists the (id, name) pairs of the output; ``mapping`` sends a fine
    category id to an output id. A fine category with no mapping is left out of the export.
    """

    name: str
    categories: Tuple[Tuple[int, str], ...]
    mapping: Dict[int, int]


FINE_PROFILE = CategoryProfile(
    name="fine",
    categories=tuple(sorted(CATEGORY_NAMES.items())),
    mapping={category_id: category_id for category_id in CATEGORY_NAMES},
)

# COCO's own ids for the classes real street datasets share (person, car, bus, truck), so a
# detector trained on the synthetic data can be tested on real images without a remap.
# Buildings are not a COCO class and are left out.
COCO_PROFILE = CategoryProfile(
    name="coco",
    categories=((1, "person"), (3, "car"), (6, "bus"), (8, "truck")),
    mapping={PEDESTRIAN: 1, SEDAN: 3, SUV: 3, BUS: 6, TRUCK: 8},
)

# The rider-study classes with the ids of ``src.evaluation.class_maps.RIDER_PROFILE``: person,
# bike (COCO's bicycle id), car, motor (COCO's motorcycle id), bus, truck and rider (BDD100K's own
# class). This pipeline places bicycles only, so motor has no instances.
RIDERS_PROFILE = CategoryProfile(
    name="riders",
    categories=(
        (1, "person"),
        (2, "bike"),
        (3, "car"),
        (4, "motor"),
        (6, "bus"),
        (8, "truck"),
        (10, "rider"),
    ),
    mapping={PEDESTRIAN: 1, BICYCLE: 2, SEDAN: 3, SUV: 3, BUS: 6, TRUCK: 8, RIDER: 10},
)

PROFILES: Dict[str, CategoryProfile] = {
    FINE_PROFILE.name: FINE_PROFILE,
    COCO_PROFILE.name: COCO_PROFILE,
    RIDERS_PROFILE.name: RIDERS_PROFILE,
}
