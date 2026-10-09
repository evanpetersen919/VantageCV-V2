### [RESOLVED] `ScenarioTypeConfig`/`ScenarioType` were referenced but never defined in the master prompt
MASTER_PROMPT Section 3.2.2's test fixtures construct
`ScenarioTypeConfig(...)` and Section 3.1.3's file tree lists
`src/procedural/scenario.py`, but the document never actually defines
either the `ScenarioType` enum or the `ScenarioTypeConfig` schema/fields —
a genuine gap in the spec itself, not something I overlooked. Filled in
`src/procedural/scenario.py`: a `ScenarioType` str-enum matching Section
1.3's six categories, and a pydantic `ScenarioTypeConfig` model with the
fields implied by the fixtures (`avg_block_size`, `num_intersections`,
`building_density`, `vehicle_mix`, etc.), plus validators for range
ordering, density bounds, and vehicle-mix-sums-to-1. Covered by
`tests/unit/test_scenario.py` (14 tests, 100% coverage).

