### [RESOLVED] Building types/materials were not assigned
Was: MASTER_PROMPT Section 3.3 lists "assign building types, heights,
materials" -- heights were implemented (sampled from
`config.building_heights`); building *type* and *materials* were not,
deferred until the mesh factory existed to consume them.

Resolved by `building_placement.py`'s `BuildingType` enum (RESIDENTIAL /
MIXED_USE / COMMERCIAL -- a taxonomy of this module's own invention,
since the spec gives none) and `_classify_building_type`: each
building's type is derived from where its own sampled height falls
*relative to* `config.building_heights`'s `(min, max)` range (bottom
third RESIDENTIAL, middle third MIXED_USE, top third COMMERCIAL), not a
fixed absolute threshold -- necessary because that range varies
enormously across scenario templates (a parking lot's tallest building
is shorter than urban_dense's shortest), so only a relative split means
the same thing across every scenario type. A degenerate range (`min ==
max`) defaults to MIXED_USE rather than dividing by zero. Material is
then sampled per building from `BUILDING_MATERIALS_BY_TYPE`, a small
hand-picked plausible set per type (not an exhaustive real-world
taxonomy). `mesh_factory.py`'s `build_building_mesh` now uses
`building.material` instead of a hardcoded `"concrete"` string.
`Building.building_type`/`material` both default (`MIXED_USE`/
`"concrete"`, matching the old hardcoded behavior exactly) so every
pre-existing `Building(...)` call site across the test suite kept
working unchanged.

