### [RESOLVED] Three real UE5 rendering bugs found by actually looking at a rendered scenario (scale, handedness, missing normals)
Found immediately after the first successful end-to-end mesh-dispatch
test (see the "[RESOLVED] LoadProceduralScenario now dispatches real
mesh sections" entry) -- the geometry built, but looked wrong in three
distinct, real ways, each found by actually looking at the viewport,
not by reading code:

1. **1/100th scale.** `src/procedural/mesh_factory.py` generates
   geometry in meters, but Unreal's native unit is centimeters (1
   Unreal unit = 1cm) -- nothing anywhere in the pipeline converted
   between them before this session, so a "20-meter" building rendered
   20 Unreal units tall. Fixed in
   `ProceduralScenarioLoader.cpp::ParseVector3Array` with a
   `MetersToUnrealUnits = 100.0` multiplier at the JSON-ingestion
   boundary.
2. **Buildings missing one or more walls.** `mesh_factory.py`'s own
   module docstring already documented this exact, anticipated gap:
   its geometry is right-handed (CCW front-face winding) but UE5 is
   left-handed (CW front-face winding as seen from outside) --
   "reconciling the two is Phase 4's job (the coordinate transform
   happens at the JSON-RPC boundary when loading into UE5, not here)."
   That boundary just didn't exist until this session. Fixed by
   negating the Y axis for every vertex (`ApplyCoordinateConvention` in
   `ProceduralScenarioLoader.cpp`) -- a mirror transform flips
   handedness and reverses every triangle's perceived winding in one
   step, so no separate triangle-index swap was needed.
3. **Noisy/broken lighting on large flat surfaces (roads).**
   `ScenarioMeshBuilder::BuildMeshSection` called
   `UProceduralMeshComponent::CreateMeshSection` with empty
   normals/tangents arrays (documented at the time as "not yet visually
   verified"). Real visual result: staticky, broken-looking lighting,
   especially visible on roads. Fixed by computing real normals/
   tangents via `UKismetProceduralMeshLibrary::CalculateTangentsForMesh`
   before building the section, the engine's own standard utility for
   this exact situation.

All three verified visually against the same real 840-mesh scenario
used throughout this session's UE5 dogfooding.

