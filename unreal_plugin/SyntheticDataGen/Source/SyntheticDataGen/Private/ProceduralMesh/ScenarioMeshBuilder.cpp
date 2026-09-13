// UNVERIFIED: never compiled against UE5.4 (no local install). See
// ScenarioMeshBuilder.h and KNOWN_GAPS_AND_ISSUES.md.

#include "ProceduralMesh/ScenarioMeshBuilder.h"
#include "ProceduralMeshComponent.h"

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

	// Normals/tangents are left empty here; UE5's CreateMeshSection can
	// auto-generate them (bCreateCollision=false, bCalculateNormals via
	// the normals/tangents params being empty triggers a fallback in some
	// UE5 versions -- this has not been verified against an actual build,
	// see file header).
	const TArray<FVector> EmptyNormals;
	const TArray<FProcMeshTangent> EmptyTangents;
	TArray<FLinearColor> EmptyVertexColors;

	TargetComponent->CreateMeshSection(
		/*SectionIndex=*/0,
		MeshData.Vertices,
		MeshData.Triangles,
		EmptyNormals,
		MeshData.UVs,
		EmptyVertexColors,
		EmptyTangents,
		/*bCreateCollision=*/true);

	return true;
}
