// Compiles cleanly against a real UE 5.4.4 editor (verified
// 2026-09-15). Mesh-section dispatch (this file's main body) verified
// end-to-end and visually 2026-09-16: a real 840-mesh scenario, sent
// over the real WebSocket bridge, produced real visible geometry in a
// live PIE viewport -- see KNOWN_GAPS_AND_ISSUES.md's "[RESOLVED]
// LoadProceduralScenario now dispatches real mesh sections" entry.

#include "DataExport/ProceduralScenarioLoader.h"
#include "ProceduralMesh/ScenarioMeshBuilder.h"
#include "ProceduralMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

DEFINE_LOG_CATEGORY_STATIC(LogProceduralScenarioLoader, Log, All);

namespace
{
	// Parses a JSON array of [x, y, z] triples into an FVector array.
	bool ParseVector3Array(const TArray<TSharedPtr<FJsonValue>>& Json, TArray<FVector>& OutVertices)
	{
		OutVertices.Reserve(Json.Num());
		for (const TSharedPtr<FJsonValue>& Entry : Json)
		{
			const TArray<TSharedPtr<FJsonValue>>* Triple = nullptr;
			if (!Entry->TryGetArray(Triple) || Triple->Num() != 3)
			{
				return false;
			}
			OutVertices.Add(FVector(
				(*Triple)[0]->AsNumber(), (*Triple)[1]->AsNumber(), (*Triple)[2]->AsNumber()));
		}
		return true;
	}

	// Parses a JSON array of [u, v] pairs into an FVector2D array.
	bool ParseVector2Array(const TArray<TSharedPtr<FJsonValue>>& Json, TArray<FVector2D>& OutUVs)
	{
		OutUVs.Reserve(Json.Num());
		for (const TSharedPtr<FJsonValue>& Entry : Json)
		{
			const TArray<TSharedPtr<FJsonValue>>* Pair = nullptr;
			if (!Entry->TryGetArray(Pair) || Pair->Num() != 2)
			{
				return false;
			}
			OutUVs.Add(FVector2D((*Pair)[0]->AsNumber(), (*Pair)[1]->AsNumber()));
		}
		return true;
	}

	// Parses a JSON array of ints into an int32 array.
	bool ParseIntArray(const TArray<TSharedPtr<FJsonValue>>& Json, TArray<int32>& OutTriangles)
	{
		OutTriangles.Reserve(Json.Num());
		for (const TSharedPtr<FJsonValue>& Entry : Json)
		{
			int32 Value = 0;
			if (!Entry->TryGetNumber(Value))
			{
				return false;
			}
			OutTriangles.Add(Value);
		}
		return true;
	}

	// Parses one entry of the "meshes" array into an FScenarioMeshData,
	// matching src/procedural/mesh_factory.py's Mesh dataclass field for
	// field (vertices: [N,3], triangles: flat [M*3], uvs: [N,2], material).
	bool ParseMeshData(const FJsonObject& MeshObject, FScenarioMeshData& OutMeshData)
	{
		const TArray<TSharedPtr<FJsonValue>>* VerticesJson = nullptr;
		const TArray<TSharedPtr<FJsonValue>>* TrianglesJson = nullptr;
		const TArray<TSharedPtr<FJsonValue>>* UVsJson = nullptr;
		FString Material;

		if (!MeshObject.TryGetArrayField(TEXT("vertices"), VerticesJson)
			|| !MeshObject.TryGetArrayField(TEXT("triangles"), TrianglesJson)
			|| !MeshObject.TryGetArrayField(TEXT("uvs"), UVsJson)
			|| !MeshObject.TryGetStringField(TEXT("material"), Material))
		{
			return false;
		}

		if (!ParseVector3Array(*VerticesJson, OutMeshData.Vertices)
			|| !ParseIntArray(*TrianglesJson, OutMeshData.Triangles)
			|| !ParseVector2Array(*UVsJson, OutMeshData.UVs))
		{
			return false;
		}

		OutMeshData.Material = Material;
		return true;
	}
} // namespace

AProceduralScenarioLoader::AProceduralScenarioLoader()
{
	PrimaryActorTick.bCanEverTick = false;
}

bool AProceduralScenarioLoader::LoadProceduralScenario(const FString& ScenarioJson)
{
	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ScenarioJson);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		return false;
	}

	// Traffic controller initialization and streaming/culling setup
	// (MASTER_PROMPT Section 3.5's other "Procedural Meshes"/"Traffic
	// Network" bullets for this phase) still belong here once their own
	// upstream pieces exist -- see KNOWN_GAPS_AND_ISSUES.md. This
	// function currently only dispatches mesh sections from "meshes".
	const TArray<TSharedPtr<FJsonValue>>* MeshesJson = nullptr;
	if (!Root->TryGetArrayField(TEXT("meshes"), MeshesJson))
	{
		// No "meshes" field at all is a valid (if empty) scenario --
		// nothing to build, not a parse failure.
		return true;
	}

	int32 BuiltCount = 0;
	int32 SkippedCount = 0;

	for (const TSharedPtr<FJsonValue>& MeshValue : *MeshesJson)
	{
		const TSharedPtr<FJsonObject>* MeshObject = nullptr;
		FScenarioMeshData MeshData;
		if (!MeshValue->TryGetObject(MeshObject) || !ParseMeshData(**MeshObject, MeshData))
		{
			++SkippedCount;
			continue;
		}

		UProceduralMeshComponent* Component = NewObject<UProceduralMeshComponent>(this);
		Component->RegisterComponent();
		if (RootComponent == nullptr)
		{
			SetRootComponent(Component);
		}
		else
		{
			Component->AttachToComponent(RootComponent, FAttachmentTransformRules::KeepRelativeTransform);
		}

		UScenarioMeshBuilder* Builder = NewObject<UScenarioMeshBuilder>(this);
		if (Builder->BuildMeshSection(Component, MeshData))
		{
			++BuiltCount;
		}
		else
		{
			++SkippedCount;
		}
	}

	UE_LOG(
		LogProceduralScenarioLoader,
		Display,
		TEXT("LoadProceduralScenario: built %d mesh section(s), skipped %d"),
		BuiltCount,
		SkippedCount);

	return true;
}
