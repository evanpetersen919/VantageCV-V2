// Compiles cleanly against a real UE 5.4.4 editor (verified
// 2026-09-15). Mesh-section dispatch (this file's main body) verified
// end-to-end and visually 2026-09-16: a real 840-mesh scenario, sent
// over the real WebSocket bridge, produced real visible geometry in a
// live PIE viewport -- see KNOWN_GAPS_AND_ISSUES.md's "[RESOLVED]
// LoadProceduralScenario now dispatches real mesh sections" entry.

#include "DataExport/ProceduralScenarioLoader.h"
#include "ActorSpawn/VehicleActorSpawner.h"
#include "ProceduralMesh/ScenarioMeshBuilder.h"
#include "ProceduralMeshComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetMathLibrary.h"

DEFINE_LOG_CATEGORY_STATIC(LogProceduralScenarioLoader, Log, All);

namespace
{
	// src/procedural/mesh_factory.py generates all geometry in meters
	// (matching ScenarioTypeConfig's own bounds/road-width/building-height
	// units), but Unreal's native unit is centimeters (1 Unreal unit =
	// 1cm) -- this is the boundary where that conversion needs to happen,
	// since every mesh entering this function came from that Python-side
	// meter-scale pipeline. Confirmed necessary via a real visual check:
	// without this factor, a real scenario's buildings/roads rendered at
	// 1/100th their intended size.
	constexpr double MetersToUnrealUnits = 100.0;

	// src/procedural/mesh_factory.py's own module docstring documents
	// this exactly: its geometry is right-handed (CCW front-face
	// winding), but UE5 is left-handed (CW front-face winding as seen
	// from outside) -- "reconciling the two is Phase 4's job (the
	// coordinate transform happens at the JSON-RPC boundary when
	// loading into UE5, not here)". This is that boundary. Negating one
	// axis (Y) both flips handedness and reverses every triangle's
	// perceived winding in one step (a mirror transform reverses
	// orientation), so no separate triangle-index swap is needed.
	// Confirmed necessary via a real visual check: without this,
	// buildings rendered with one or more walls missing (their normals
	// pointed inward, so UE5's default backface culling hid them when
	// viewed from outside).
	FVector ApplyCoordinateConvention(double X, double Y, double Z)
	{
		return FVector(X, -Y, Z) * MetersToUnrealUnits;
	}

	// Parses a JSON array of [x, y, z] triples (in meters, right-handed)
	// into an FVector array (in Unreal units/centimeters, left-handed).
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
			OutVertices.Add(ApplyCoordinateConvention(
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

	// Parses one entry of the "assets" array into an FScenarioAssetData,
	// matching scenario_serializer.py's asset-entry schema
	// ({"category", "asset_path", "part_paths", "position",
	// "rotation_rad", "id"} -- "id" isn't needed here, it exists for the
	// Python side's own bookkeeping). Position is converted to UE5 space
	// via the same ApplyCoordinateConvention used for mesh vertices
	// above. rotation_rad's sign is negated for the same reason:
	// mirroring the Y axis reverses the sense of rotation, so the angle
	// measured in the transformed space is the negation of the one
	// Python computed -- converted from radians to the degrees
	// FRotator::Yaw expects. "part_paths" is optional (missing/absent
	// treated as empty, not a parse failure) for forward/backward
	// compatibility with any future asset category that doesn't have
	// per-vehicle parts.
	bool ParseAssetData(const FJsonObject& AssetObject, FScenarioAssetData& OutAssetData)
	{
		const TArray<TSharedPtr<FJsonValue>>* PositionJson = nullptr;
		FString Category;
		FString AssetPath;
		double RotationRad = 0.0;

		if (!AssetObject.TryGetStringField(TEXT("category"), Category)
			|| !AssetObject.TryGetStringField(TEXT("asset_path"), AssetPath)
			|| !AssetObject.TryGetArrayField(TEXT("position"), PositionJson)
			|| PositionJson->Num() != 3
			|| !AssetObject.TryGetNumberField(TEXT("rotation_rad"), RotationRad))
		{
			return false;
		}

		OutAssetData.Category = Category;
		OutAssetData.AssetPath = AssetPath;

		OutAssetData.PartPaths.Reset();
		const TArray<TSharedPtr<FJsonValue>>* PartPathsJson = nullptr;
		if (AssetObject.TryGetArrayField(TEXT("part_paths"), PartPathsJson))
		{
			for (const TSharedPtr<FJsonValue>& PartPathValue : *PartPathsJson)
			{
				FString PartPath;
				if (PartPathValue->TryGetString(PartPath))
				{
					OutAssetData.PartPaths.Add(PartPath);
				}
			}
		}

		OutAssetData.Position = ApplyCoordinateConvention(
			(*PositionJson)[0]->AsNumber(), (*PositionJson)[1]->AsNumber(), (*PositionJson)[2]->AsNumber());
		OutAssetData.Rotation = FRotator(0.0, -FMath::RadiansToDegrees(RotationRad), 0.0);
		return true;
	}

	// Real root cause found via a live screenshot (not guessed -- see
	// KNOWN_GAPS_AND_ISSUES.md): vehicles/roads/buildings were never
	// invisible or misplaced. The player's camera was sitting wherever
	// the current level's own default PlayerStart happens to be (in
	// this project, the empty /Engine/Maps/Templates/OpenWorld
	// template), which has no relationship at all to a generated
	// scenario's own coordinates -- a screenshot confirmed the camera
	// was looking at that template's own default checkered floor and
	// mountains, nowhere near the real generated content. Repositions
	// the local player's pawn to overlook the real bounds of whatever
	// was actually just built, mirroring
	// default_overview_camera()'s own positioning logic in
	// src/orchestration/dataset_generator.py (offset above and outside
	// one corner, looking at the center) for consistency with the
	// Python-side COCO-frame camera.
	// Real bug found via dogfooding (2026-09-17 -- see
	// KNOWN_GAPS_AND_ISSUES.md): SetActorHiddenInGame(true) alone does
	// NOT stop a character Pawn's mesh from casting a shadow --
	// third-person/first-person character meshes commonly have
	// bCastHiddenShadow = true set explicitly (so a first-person view
	// that hides its own body mesh still shows that body's shadow in
	// the world), which is exactly this project's default Pawn.
	// Confirmed via a real screenshot: hiding the pawn alone left its
	// shadow unchanged on a vehicle positioned underneath it. Forcing
	// SetCastShadow(false) on every primitive component is what
	// actually stops it.
	void HideActorAndItsShadow(AActor* Actor)
	{
		if (Actor == nullptr)
		{
			return;
		}
		Actor->SetActorHiddenInGame(true);

		TArray<UPrimitiveComponent*> PrimitiveComponents;
		Actor->GetComponents<UPrimitiveComponent>(PrimitiveComponents);
		for (UPrimitiveComponent* PrimitiveComponent : PrimitiveComponents)
		{
			if (PrimitiveComponent != nullptr)
			{
				PrimitiveComponent->SetCastShadow(false);
			}
		}
	}

	void RepositionOverviewCamera(UWorld* World, const FVector2D& BoundsMin, const FVector2D& BoundsMax)
	{
		if (World == nullptr)
		{
			return;
		}

		APlayerController* PlayerController = UGameplayStatics::GetPlayerController(World, 0);
		APawn* Pawn = PlayerController != nullptr ? PlayerController->GetPawn() : nullptr;
		if (Pawn == nullptr)
		{
			return;
		}

		const FVector2D Center = (BoundsMin + BoundsMax) * 0.5;
		const double Extent = FMath::Max(BoundsMax.X - BoundsMin.X, BoundsMax.Y - BoundsMin.Y);
		if (Extent <= 0.0)
		{
			return;
		}

		const FVector CameraPosition(
			BoundsMin.X - Extent * 0.05, BoundsMin.Y - Extent * 0.05, Extent * 0.35);
		const FVector LookTarget(Center.X, Center.Y, 0.0);
		const FRotator LookRotation = UKismetMathLibrary::FindLookAtRotation(CameraPosition, LookTarget);

		Pawn->SetActorLocationAndRotation(CameraPosition, LookRotation);
		if (PlayerController->PlayerCameraManager != nullptr)
		{
			// A SpectatorPawn/DefaultPawn's camera follows its own
			// control rotation, not just the actor's rotation -- set
			// both so the view actually turns to face the scenario
			// immediately rather than on the next input event.
			PlayerController->SetControlRotation(LookRotation);
		}

		// Real bug found via dogfooding (2026-09-17 -- see
		// KNOWN_GAPS_AND_ISSUES.md): this Pawn is the level's actual
		// gameplay character/spectator mesh, repurposed here as a
		// flying overview camera. Left visible, it still casts a
		// real-time dynamic shadow from the sun even though it's never
		// in its own captured frame -- at the close/overhead angles
		// this function's own positioning produces, that shadow lands
		// squarely on the generated vehicles, showing up as a jagged
		// dark patch that looks like a broken paint texture but is
		// really just the pawn's own silhouette. See
		// HideActorAndItsShadow's own comment for why hiding alone
		// isn't enough.
		HideActorAndItsShadow(Pawn);
	}
} // namespace

AProceduralScenarioLoader::AProceduralScenarioLoader()
{
	PrimaryActorTick.bCanEverTick = false;
}

void AProceduralScenarioLoader::ClearPreviousScenario()
{
	TArray<UProceduralMeshComponent*> MeshComponents;
	GetComponents<UProceduralMeshComponent>(MeshComponents);
	for (UProceduralMeshComponent* MeshComponent : MeshComponents)
	{
		if (MeshComponent != nullptr)
		{
			MeshComponent->DestroyComponent();
		}
	}
	SetRootComponent(nullptr);

	for (const TObjectPtr<AActor>& SpawnedActor : SpawnedAssetActors)
	{
		if (SpawnedActor != nullptr)
		{
			SpawnedActor->Destroy();
		}
	}
	SpawnedAssetActors.Reset();
}

bool AProceduralScenarioLoader::LoadProceduralScenario(const FString& ScenarioJson)
{
	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ScenarioJson);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		return false;
	}

	// Each call fully replaces the previously loaded scenario rather
	// than accumulating on top of it -- real requirement once this is
	// called repeatedly against one running session (e.g. cycling
	// through several procedurally generated city layouts live), not
	// just once per editor session.
	ClearPreviousScenario();

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

	FVector2D BoundsMin(TNumericLimits<double>::Max(), TNumericLimits<double>::Max());
	FVector2D BoundsMax(TNumericLimits<double>::Lowest(), TNumericLimits<double>::Lowest());
	bool bHasAnyVertex = false;

	for (const TSharedPtr<FJsonValue>& MeshValue : *MeshesJson)
	{
		const TSharedPtr<FJsonObject>* MeshObject = nullptr;
		FScenarioMeshData MeshData;
		if (!MeshValue->TryGetObject(MeshObject) || !ParseMeshData(**MeshObject, MeshData))
		{
			++SkippedCount;
			continue;
		}

		for (const FVector& Vertex : MeshData.Vertices)
		{
			BoundsMin.X = FMath::Min(BoundsMin.X, Vertex.X);
			BoundsMin.Y = FMath::Min(BoundsMin.Y, Vertex.Y);
			BoundsMax.X = FMath::Max(BoundsMax.X, Vertex.X);
			BoundsMax.Y = FMath::Max(BoundsMax.Y, Vertex.Y);
			bHasAnyVertex = true;
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

	// "assets" (asset-reference + transform entries for real City
	// Sample content this project spawns rather than builds as a
	// procedural box) is a City Sample asset integration Phase 1
	// addition -- see the "assets" schema documented in
	// scenario_serializer.py and docs/architecture.rst. Only the
	// "vehicle" category is implemented so far; "prop"/"hero_building"
	// entries are skipped (not a parse failure) until later phases of
	// that same integration work add them.
	const TArray<TSharedPtr<FJsonValue>>* AssetsJson = nullptr;
	int32 SpawnedCount = 0;
	int32 SpawnSkippedCount = 0;

	if (Root->TryGetArrayField(TEXT("assets"), AssetsJson))
	{
		for (const TSharedPtr<FJsonValue>& AssetValue : *AssetsJson)
		{
			const TSharedPtr<FJsonObject>* AssetObject = nullptr;
			FScenarioAssetData AssetData;
			if (!AssetValue->TryGetObject(AssetObject) || !ParseAssetData(**AssetObject, AssetData))
			{
				++SpawnSkippedCount;
				continue;
			}

			// Include every parsed asset's position in the overview
			// camera's bounds, not just mesh vertices -- vehicle
			// positions should already fall within the road meshes'
			// own extent in practice, but this removes the dependency
			// entirely rather than assuming it always holds.
			BoundsMin.X = FMath::Min(BoundsMin.X, AssetData.Position.X);
			BoundsMin.Y = FMath::Min(BoundsMin.Y, AssetData.Position.Y);
			BoundsMax.X = FMath::Max(BoundsMax.X, AssetData.Position.X);
			BoundsMax.Y = FMath::Max(BoundsMax.Y, AssetData.Position.Y);
			bHasAnyVertex = true;

			if (AssetData.Category != TEXT("vehicle"))
			{
				++SpawnSkippedCount;
				continue;
			}

			UVehicleActorSpawner* Spawner = NewObject<UVehicleActorSpawner>(this);
			AActor* SpawnedVehicle = Spawner->SpawnVehicle(GetWorld(), AssetData);
			if (SpawnedVehicle != nullptr)
			{
				SpawnedAssetActors.Add(SpawnedVehicle);
				++SpawnedCount;
			}
			else
			{
				++SpawnSkippedCount;
			}
		}
	}

	UE_LOG(
		LogProceduralScenarioLoader,
		Display,
		TEXT("LoadProceduralScenario: spawned %d asset(s), skipped %d"),
		SpawnedCount,
		SpawnSkippedCount);

	if (bHasAnyVertex)
	{
		RepositionOverviewCamera(GetWorld(), BoundsMin, BoundsMax);
	}

	return true;
}
