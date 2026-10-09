### [RESOLVED] LoadProceduralScenario now dispatches real mesh sections -- verified end-to-end, visually, against a real scenario
Was: `AProceduralScenarioLoader::LoadProceduralScenario` only validated
that its input was well-formed JSON; it never dispatched per-mesh
`UScenarioMeshBuilder::BuildMeshSection` calls, so no geometry was ever
actually built from a real payload.

Resolved 2026-09-15/16: implemented real parsing of the `"meshes"`
array (`vertices`/`triangles`/`uvs`/`material`, matching
`src/procedural/mesh_factory.py`'s `Mesh` dataclass field-for-field --
vertices/uvs as `[[x,y,z], ...]`/`[[u,v], ...]` JSON arrays, triangles
as a flat int list), and for each entry: spawn a real
`UProceduralMeshComponent` on the loader actor and call
`UScenarioMeshBuilder::BuildMeshSection` on it. Verified with a real,
full end-to-end test, not a synthetic small payload: generated one
real `urban_dense` scenario via this repo's own
`generate_scenario` (840 meshes), sent it over the real WebSocket
bridge (see the entry above) to a live UE 5.4.4 editor with PIE
running, and confirmed via the editor's own log
(`LogProceduralScenarioLoader: Display: LoadProceduralScenario: built
840 mesh section(s), skipped 0`) that every single mesh built
successfully -- then confirmed **visually**, in the PIE viewport, that
real geometry (roads, buildings) was actually there. This is the first
time any geometry this pipeline generated has ever been seen rendered
by an actual engine, rather than only plotted via matplotlib or
asserted correct by a unit test.

**Still open**: traffic controller initialization (no such actor class
exists yet) and streaming/culling (needs profiling against a real,
populated level) -- MASTER_PROMPT Section 3.5's other two "Procedural
Meshes"/"Traffic Network" bullets for this phase. Also: the JSON
schema used here (`{"meshes": [{"vertices", "triangles", "uvs",
"material"}, ...]}`) only covers meshes -- `nodes`/`edges`/`lanes`/
`buildings`/`traffic` from `ProceduralScenarioLoader.h`'s own original
docstring shape are not sent or parsed; revisit if UE5-side traffic
light/stop-sign visualization or road-lane-level detail ever becomes
a real requirement, rather than just visualizing raw mesh geometry.

