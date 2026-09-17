// Compiles and loads cleanly against a real UE 5.4.4 editor (verified
// 2026-09-15 -- see KNOWN_GAPS_AND_ISSUES.md). Runtime rendering
// verified visually 2026-09-16 against a real 840-mesh scenario;
// empty normals/tangents (this file's original approach) produced
// visibly broken/noisy lighting on large flat surfaces (roads) --
// fixed below by computing real ones via
// UKismetProceduralMeshLibrary::CalculateTangentsForMesh.

#include "ProceduralMesh/ScenarioMeshBuilder.h"
#include "ProceduralMesh/MaterialResolver.h"
#include "ProceduralMeshComponent.h"
#include "KismetProceduralMeshLibrary.h"
#include "Materials/MaterialInterface.h"

UScenarioMeshBuilder::UScenarioMeshBuilder()
{
	PrimaryComponentTick.bCanEverTick = false;
}

bool UScenarioMeshBuilder::BuildMeshSection(
	UProceduralMeshComponent* TargetComponent,
	const FScenarioMeshData& MeshData) const
{
	if (TargetComponent == nullptr)
	{
		return false;
	}
	if (MeshData.Vertices.Num() == 0 || MeshData.Triangles.Num() == 0)
	{
		return false;
	}
	if (MeshData.Triangles.Num() % 3 != 0)
	{
		// Triangle index buffer must be a flat list of (a, b, c) triples;
		// see mesh_factory.py's Mesh.triangles docstring.
		return false;
	}

	// Vertex colors are left empty (UProceduralMeshComponent tolerates
	// this -- defaults to white, confirmed by the real visual test
	// referenced in this file's header comment). Normals/tangents are
	// NOT left empty: an earlier version did, and on a real generated
	// scenario that produced visibly broken/noisy lighting on large
	// flat surfaces (roads) -- computed here instead via the engine's
	// own tangent-calculation utility, the standard approach for
	// procedural meshes with well-formed vertex/triangle/UV data.
	TArray<FVector> Normals;
	TArray<FProcMeshTangent> Tangents;
	UKismetProceduralMeshLibrary::CalculateTangentsForMesh(
		MeshData.Vertices, MeshData.Triangles, MeshData.UVs, Normals, Tangents);

	const TArray<FColor> EmptyVertexColors;

	TargetComponent->CreateMeshSection(
		/*SectionIndex=*/0,
		MeshData.Vertices,
		MeshData.Triangles,
		Normals,
		MeshData.UVs,
		EmptyVertexColors,
		Tangents,
		/*bCreateCollision=*/true);

	// Resolves MeshData.Material (e.g. "brick", "asphalt" -- the same
	// tag strings mesh_factory.py/building_placement.py emit) to a real
	// migrated City Sample material via FMaterialResolver. An
	// unresolvable tag (unmapped, or its asset not yet migrated into
	// this project) is not fatal -- the section keeps
	// CreateMeshSection's own default material and a warning is logged
	// by FMaterialResolver itself, the same fail-soft convention every
	// other asset-loading path in this plugin already follows.
	if (UMaterialInterface* ResolvedMaterial = FMaterialResolver::Resolve(MeshData.Material))
	{
		TargetComponent->SetMaterial(0, ResolvedMaterial);
	}

	return true;
}
