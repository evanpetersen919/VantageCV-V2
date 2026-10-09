### [DEFERRED] Procedural material generation (asphalt, concrete, brick) and LOD system not implemented
MASTER_PROMPT Section 3.4 lists both under "Procedural Meshes." `Mesh.material`
is currently just a string name (`"asphalt"`, `"concrete"`) with no
backing material definition, parameter set (roughness/metallic per
QOL_RESEARCH_CHECKLIST.md Section D.2), or LOD levels -- there is no
rendering phase yet to consume any of that, and UE5 material assets can't
be authored/verified without the engine installed. Revisit in Phase 4+
once there's an actual UE5 project to define materials in.

