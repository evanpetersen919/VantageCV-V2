### [RESOLVED] Building mesh had no roof geometry beyond a flat cap
Was: `MeshFactory.build_building_mesh` extruded every building's
rectangular footprint straight up with a flat roof quad regardless of
type -- no pitched/hipped roof or other architectural detail.

Resolved (partially -- see below) by `_gable_roof_mesh_parts`:
RESIDENTIAL buildings (see the `BuildingType` entry above) now get a
real gable (pitched) roof -- ridge along the footprint's longer
horizontal axis (matching how real gable roofs are always oriented),
peak `RESIDENTIAL_ROOF_HEIGHT_METERS` (2.5m, a fixed rise rather than one
proportional to footprint size, matching how a real gable roof's rise
doesn't scale with floor area) above the flat-roof-equivalent eave
height. MIXED_USE/COMMERCIAL buildings keep the original flat cap --
real low/mid-rise commercial buildings are overwhelmingly flat-roofed,
so this is a deliberate type-driven choice, not an oversight. 10
vertices (8 box corners + 2 ridge peaks), 16 true triangles (not
fan-triangulated quads, since the 2 gable-end faces are triangular by
construction). Every triangle's outward-normal orientation was verified
directly (for both the ridge-along-x and ridge-along-y footprint cases,
plus the square tie-breaking case) in `test_mesh_factory.py`.

Still deferred: hipped roofs, parapets, roof overhang, and any other
architectural detail beyond a single gable shape -- MASTER_PROMPT gives
no building-detail spec to implement against, and a single reasonable
shape per type is enough to close the "flat cap regardless of type" gap
without inventing an open-ended architectural taxonomy nobody asked for.

