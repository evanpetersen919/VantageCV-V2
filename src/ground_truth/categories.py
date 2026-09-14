"""Shared object category IDs.

Used consistently across ground-truth extraction
(``BoundingBox3D.category_id``) and COCO export (category definitions)
so the two can never independently drift out of sync -- a single source
of truth for "what is category 3," rather than each module inventing its
own numbering.
"""

from typing import Dict

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
