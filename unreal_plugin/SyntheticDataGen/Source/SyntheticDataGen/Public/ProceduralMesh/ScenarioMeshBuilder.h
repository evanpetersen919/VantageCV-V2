// Compiles cleanly against a real UE 5.4.4 editor and confirmed
// rendering real geometry in a live standalone session (verified
// 2026-09-16 -- see KNOWN_GAPS_AND_ISSUES.md's "[RESOLVED]
// LoadProceduralScenario now dispatches real mesh sections" entry).
//
// Consumes the vertex/triangle/UV/material data produced by the Python-side
// src/procedural/mesh_factory.py (road and building meshes), delivered
// over the real WebSocket JSON-RPC bridge, and builds it as runtime
// ProceduralMeshComponent sections, resolving Material via
// FMaterialResolver.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ScenarioMeshBuilder.generated.h"

class UProceduralMeshComponent;

// Mirrors mesh_factory.py's Mesh dataclass field-for-field so a JSON
// payload from the Python side maps onto it directly.
USTRUCT(BlueprintType)
struct FScenarioMeshData
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadWrite, Category = "SyntheticDataGen")
	TArray<FVector> Vertices;

	UPROPERTY(BlueprintReadWrite, Category = "SyntheticDataGen")
	TArray<int32> Triangles;

	UPROPERTY(BlueprintReadWrite, Category = "SyntheticDataGen")
	TArray<FVector2D> UVs;

	UPROPERTY(BlueprintReadWrite, Category = "SyntheticDataGen")
	FString Material;
};

/**
 * Builds a UProceduralMeshComponent section from FScenarioMeshData.
 *
 * One instance builds one mesh section (one road lane strip, or one
 * building box); the caller (Phase 4's scenario loader) is expected to
 * create one of these per Mesh object received from the Python side.
 */
UCLASS(ClassGroup = (SyntheticDataGen), meta = (BlueprintSpawnableComponent))
class SYNTHETICDATAGEN_API UScenarioMeshBuilder final : public UActorComponent
{
	GENERATED_BODY()

public:
	UScenarioMeshBuilder();

	/**
	 * Builds mesh section 0 of TargetComponent from MeshData.
	 *
	 * @param TargetComponent  Must already be attached to an actor in the
	 *        world; this function does not create or attach components.
	 * @param MeshData         Vertex/triangle/UV/material buffers, as
	 *        produced by src/procedural/mesh_factory.py.
	 * @return true if the mesh section was created successfully.
	 */
	UFUNCTION(BlueprintCallable, Category = "SyntheticDataGen")
	bool BuildMeshSection(
		UProceduralMeshComponent* TargetComponent,
		const FScenarioMeshData& MeshData) const;
};
