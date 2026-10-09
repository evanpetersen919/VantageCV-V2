### [RESOLVED] COCO export only carried building/"structure" annotations
Was: `coco_exporter.py` declared exactly one category ("building"), since
no vehicle/pedestrian placement existed anywhere in the pipeline.
Resolved by `actor_placement.py` (see the ground-truth entry below):
`coco_exporter.py` now declares every category in
`src.ground_truth.categories` (building, sedan, suv, truck, bus,
pedestrian) and reads each annotation's real `category_id` from its
source `BoundingBox3D` rather than hard-coding `BUILDING_CATEGORY_ID`.
Cyclists are still not a category -- `ScenarioTypeConfig.vehicle_mix` has
no cyclist entry, and nothing in MASTER_PROMPT's roadmap asks for one.

