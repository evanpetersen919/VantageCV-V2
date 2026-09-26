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

CATEGORY_NAMES: Dict[int, str] = {
    BUILDING: "building",
    SEDAN: "sedan",
    SUV: "suv",
    TRUCK: "truck",
    BUS: "bus",
    PEDESTRIAN: "pedestrian",
}

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

PROFILES: Dict[str, CategoryProfile] = {
    FINE_PROFILE.name: FINE_PROFILE,
    COCO_PROFILE.name: COCO_PROFILE,
}
