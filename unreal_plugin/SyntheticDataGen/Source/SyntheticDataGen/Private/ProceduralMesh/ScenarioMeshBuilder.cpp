// Compiles and loads cleanly against a real UE 5.4.4 editor (verified
// 2026-09-15 -- see KNOWN_GAPS_AND_ISSUES.md). Runtime behavior of
// BuildMeshSection itself (does a section actually render as expected
// once fed real MeshData from the Python side) has not yet been
// exercised -- only that the module compiles, links, and the plugin
// loads without error.

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

	// Normals/tangents/vertex colors are left empty here -- compiles and
	// links against UProceduralMeshComponent::CreateMeshSection (real
	// signature: Vertices/Triangles/Normals/UV0/VertexColors as
	// TArray<FColor>/Tangents/bCreateCollision), but whether the
	// resulting section renders/lights correctly with all three left
	// empty hasn't been visually verified in the editor yet.
	const TArray<FVector> EmptyNormals;
	const TArray<FProcMeshTangent> EmptyTangents;
	const TArray<FColor> EmptyVertexColors;

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
