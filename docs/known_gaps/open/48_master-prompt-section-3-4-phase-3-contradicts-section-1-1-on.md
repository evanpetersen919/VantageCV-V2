### [DEFERRED] Master prompt Section 3.4 (Phase 3) contradicts Section 1.1 on which language owns mesh generation
MASTER_PROMPT_PROCEDURAL_AV_DATASET_GENERATOR.md Section 3.4 labels
"Procedural Meshes" as "(C++ in UE5)". Section 1.1's own architecture
diagram, by contrast, lists a "Procedural Mesh Factory (Geometry)" as
part of the Python-side "PROCEDURAL GENERATION ENGINE" box, distinct from
UE5's "Procedural Mesh Component (Real-time Generation)" in the C++
simulation backend. These directly conflict. Resolved in favor of the
testable interpretation: `src/procedural/mesh_factory.py` computes
vertex/triangle/UV buffers in Python; a C++ `UScenarioMeshBuilder` class
exists under `unreal_plugin/.../ProceduralMesh/` as the UE5-side
consumer of that data -- now confirmed to actually compile and load
(see the resolved entry above), though `BuildMeshSection`'s own
rendering output hasn't been visually verified yet.

