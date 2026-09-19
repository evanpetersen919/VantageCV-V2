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
#include "EngineUtils.h"
#include "Engine/Engine.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/PostProcessVolume.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Engine/Level.h"
#include "Engine/World.h"

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

		// "scale" is optional ([sx, sy, sz] along the mesh's own local
		// axes; absent means unscaled). Not run through
		// ApplyCoordinateConvention: it is a local-axis quantity, not a
		// world-space position, so the Y mirror does not apply to it.
		OutAssetData.Scale = FVector::OneVector;
		const TArray<TSharedPtr<FJsonValue>>* ScaleJson = nullptr;
		if (AssetObject.TryGetArrayField(TEXT("scale"), ScaleJson))
		{
			if (ScaleJson->Num() != 3)
			{
				return false;
			}
			OutAssetData.Scale = FVector(
				(*ScaleJson)[0]->AsNumber(), (*ScaleJson)[1]->AsNumber(), (*ScaleJson)[2]->AsNumber());
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

bool AProceduralScenarioLoader::HideIfTemplateTerrain(AActor* Actor)
{
	if (Actor == nullptr)
	{
		return false;
	}
	// Landscape/LandscapeStreamingProxy (the checkerboard/hills) and the
	// template's plain StaticMeshActor were the first two found (a live
	// screenshot still showed distant terrain after hiding both). A third
	// class, WorldPartitionHLOD, turned out to be the real cause of a
	// separate pale "ribbon" artifact at the horizon that survived both:
	// HLOD (Hierarchical LOD) actors are Epic's own auto-generated merged
	// proxy meshes standing in for distant/unloaded terrain tiles, a
	// completely different class from Landscape or StaticMeshActor, so
	// neither earlier check matched them. Confirmed via a live query (new
	// DebugListActorsWithMesh RPC): 24 WorldPartitionHLOD actors existed,
	// all is_spatially_loaded=false (always resident, not streamed in
	// late) -- ruling out the streaming-timing theory this fix started
	// from disproving is what actually mattered here.
	const FString ClassName = Actor->GetClass()->GetName();
	if (ClassName.Contains(TEXT("Landscape")) || ClassName == TEXT("StaticMeshActor")
		|| ClassName.Contains(TEXT("HLOD")))
	{
		Actor->SetActorHiddenInGame(true);
		return true;
	}
	return false;
}

void AProceduralScenarioLoader::OnLevelAddedToWorld(ULevel* Level, UWorld* World)
{
	if (Level == nullptr || World != GetWorld())
	{
		// FWorldDelegates::LevelAddedToWorld is global across every world in
		// the process; only act on levels streaming into THIS actor's own
		// world.
		return;
	}
	for (AActor* Actor : Level->Actors)
	{
		HideIfTemplateTerrain(Actor);
	}
}

void AProceduralScenarioLoader::ApplyEnvironment(const TSharedPtr<FJsonObject>& Env)
{
	UWorld* World = GetWorld();
	if (World == nullptr || !Env.IsValid())
	{
		return;
	}

	// The engine template map's checkerboard floor and desert hills are
	// its Landscape. Turning the Landscape show flag off hides all of it,
	// including World Partition proxies that stream in later, which
	// hiding individual actors would not survive.
	bool bHideTerrain = false;
	if (Env->TryGetBoolField(TEXT("hide_template_terrain"), bHideTerrain) && bHideTerrain)
	{
		if (GEngine != nullptr)
		{
			GEngine->Exec(World, TEXT("ShowFlag.Landscape 0"));
		}
		// The show flag alone left distant terrain visible at the horizon
		// (confirmed in a screenshot), so also hide every loaded template
		// terrain actor directly (see HideIfTemplateTerrain's own comment
		// for the three classes this covers and why). This runs before
		// this loader spawns any asset actors of its own, so it cannot
		// hide our own content.
		int32 HiddenCount = 0;
		for (TActorIterator<AActor> It(World); It; ++It)
		{
			if (HideIfTemplateTerrain(*It))
			{
				++HiddenCount;
			}
		}
		UE_LOG(LogProceduralScenarioLoader, Display, TEXT("ApplyEnvironment: hid %d already-loaded template terrain actor(s)"), HiddenCount);

		// World Partition streams the rest of the template map's actors in
		// via level-add (see OnLevelAddedToWorld's own comment for why
		// FOnActorSpawned does not fire for these) -- catch those too,
		// registered once per world.
		if (!bRegisteredLevelAddedDelegate)
		{
			FWorldDelegates::LevelAddedToWorld.AddUObject(this, &AProceduralScenarioLoader::OnLevelAddedToWorld);
			bRegisteredLevelAddedDelegate = true;
		}
	}

	const TSharedPtr<FJsonObject>* SunJson = nullptr;
	if (Env->TryGetObjectField(TEXT("sun"), SunJson))
	{
		for (TActorIterator<ADirectionalLight> It(World); It; ++It)
		{
			double Pitch = 0.0;
			double Yaw = 0.0;
			const bool bHasPitch = (*SunJson)->TryGetNumberField(TEXT("pitch_deg"), Pitch);
			const bool bHasYaw = (*SunJson)->TryGetNumberField(TEXT("yaw_deg"), Yaw);
			if (bHasPitch || bHasYaw)
			{
				const FRotator Current = It->GetActorRotation();
				It->SetActorRotation(FRotator(
					bHasPitch ? Pitch : Current.Pitch, bHasYaw ? Yaw : Current.Yaw, 0.0));
			}
			double Temperature = 0.0;
			if ((*SunJson)->TryGetNumberField(TEXT("temperature_k"), Temperature))
			{
				if (UDirectionalLightComponent* Light = Cast<UDirectionalLightComponent>(It->GetLightComponent()))
				{
					Light->SetTemperature(static_cast<float>(Temperature));
					Light->SetUseTemperature(true);
				}
			}
			break;
		}
	}

	const TSharedPtr<FJsonObject>* FogJson = nullptr;
	if (Env->TryGetObjectField(TEXT("fog"), FogJson))
	{
		for (TActorIterator<AExponentialHeightFog> It(World); It; ++It)
		{
			if (UExponentialHeightFogComponent* Fog = It->GetComponent())
			{
				double Value = 0.0;
				if ((*FogJson)->TryGetNumberField(TEXT("density"), Value))
				{
					Fog->SetFogDensity(static_cast<float>(Value));
				}
				if ((*FogJson)->TryGetNumberField(TEXT("height_falloff"), Value))
				{
					Fog->SetFogHeightFalloff(static_cast<float>(Value));
				}
				if ((*FogJson)->TryGetNumberField(TEXT("start_distance_m"), Value))
				{
					Fog->SetStartDistance(static_cast<float>(Value * MetersToUnrealUnits));
				}
			}
			break;
		}
	}

	const TSharedPtr<FJsonObject>* PostJson = nullptr;
	if (Env->TryGetObjectField(TEXT("post_process"), PostJson))
	{
		FActorSpawnParameters SpawnParams;
		SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		APostProcessVolume* Volume = World->SpawnActor<APostProcessVolume>(
			FVector::ZeroVector, FRotator::ZeroRotator, SpawnParams);
		if (Volume != nullptr)
		{
			Volume->bUnbound = true;
			Volume->BlendWeight = 1.0f;
			Volume->Priority = 100.0f;
			FPostProcessSettings& Settings = Volume->Settings;

			double Value = 0.0;
			if ((*PostJson)->TryGetNumberField(TEXT("exposure_bias"), Value))
			{
				Settings.bOverride_AutoExposureBias = true;
				Settings.AutoExposureBias = static_cast<float>(Value);
			}
			if ((*PostJson)->TryGetNumberField(TEXT("saturation"), Value))
			{
				Settings.bOverride_ColorSaturation = true;
				Settings.ColorSaturation = FVector4(Value, Value, Value, 1.0);
			}
			const TArray<TSharedPtr<FJsonValue>>* Gain = nullptr;
			if ((*PostJson)->TryGetArrayField(TEXT("gain"), Gain) && Gain->Num() == 3)
			{
				Settings.bOverride_ColorGain = true;
				Settings.ColorGain = FVector4(
					(*Gain)[0]->AsNumber(), (*Gain)[1]->AsNumber(), (*Gain)[2]->AsNumber(), 1.0);
			}
			SpawnedAssetActors.Add(Volume);
		}
	}
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

	// Environment first: it applies even to a scenario with no meshes.
	const TSharedPtr<FJsonObject>* EnvironmentJson = nullptr;
	if (Root->TryGetObjectField(TEXT("environment"), EnvironmentJson))
	{
		ApplyEnvironment(*EnvironmentJson);
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
	// scenario_serializer.py and docs/architecture.rst. "vehicle" and
	// "static_asset" (real building wall/corner/entrance pieces) are
	// implemented; "prop" entries are skipped (not a parse failure)
	// until a later phase of that same integration work adds them.
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

			// "vehicle" (Phase 1) and "static_asset" (real building
			// wall/corner/entrance pieces -- see
			// scenario_serializer.py's _facade_piece_to_asset_json) both
			// route through the same UVehicleActorSpawner::SpawnVehicle:
			// it already handles an empty PartPaths list gracefully (a
			// standalone facade piece has no sub-parts), so no separate
			// spawn path is needed for the new category. "prop" is not
			// implemented yet (deliberate fast-follow, not this phase).
			if (AssetData.Category != TEXT("vehicle") && AssetData.Category != TEXT("static_asset"))
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
