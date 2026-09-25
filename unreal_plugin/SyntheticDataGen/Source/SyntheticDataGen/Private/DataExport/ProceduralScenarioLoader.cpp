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
#include "Engine/PointLight.h"
#include "Engine/SpotLight.h"
#include "Components/PointLightComponent.h"
#include "Components/SpotLightComponent.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/PostProcessVolume.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Components/VolumetricCloudComponent.h"
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

		// "material_scalar_overrides" is optional (missing/absent treated
		// as an empty map, not a parse failure), same forward/backward-
		// compatibility pattern as "part_paths" above -- see
		// FScenarioAssetData::MaterialScalarOverrides' own comment for
		// what this drives (real pedestrian pose selection).
		OutAssetData.MaterialScalarOverrides.Reset();
		const TSharedPtr<FJsonObject>* MaterialScalarOverridesJson = nullptr;
		if (AssetObject.TryGetObjectField(TEXT("material_scalar_overrides"), MaterialScalarOverridesJson))
		{
			for (const auto& Pair : (*MaterialScalarOverridesJson)->Values)
			{
				double Value = 0.0;
				if (Pair.Value.IsValid() && Pair.Value->TryGetNumber(Value))
				{
					OutAssetData.MaterialScalarOverrides.Add(Pair.Key, static_cast<float>(Value));
				}
			}
		}

		OutAssetData.MaterialSlotVectors.Reset();
		const TSharedPtr<FJsonObject>* SlotVectorsJson = nullptr;
		if (AssetObject.TryGetObjectField(TEXT("material_slot_vectors"), SlotVectorsJson))
		{
			for (const auto& SlotPair : (*SlotVectorsJson)->Values)
			{
				const TSharedPtr<FJsonObject>* ParamsJson = nullptr;
				if (!SlotPair.Value.IsValid() || !SlotPair.Value->TryGetObject(ParamsJson))
				{
					continue;
				}
				for (const auto& ParamPair : (*ParamsJson)->Values)
				{
					const TArray<TSharedPtr<FJsonValue>>* Components = nullptr;
					if (ParamPair.Value.IsValid() && ParamPair.Value->TryGetArray(Components) && Components->Num() >= 3)
					{
						const float R = static_cast<float>((*Components)[0]->AsNumber());
						const float G = static_cast<float>((*Components)[1]->AsNumber());
						const float BValue = static_cast<float>((*Components)[2]->AsNumber());
						const float A = Components->Num() >= 4 ? static_cast<float>((*Components)[3]->AsNumber()) : 1.0f;
						OutAssetData.MaterialSlotVectors.Add(SlotPair.Key + TEXT("|") + ParamPair.Key, FLinearColor(R, G, BValue, A));
					}
				}
			}
		}

		OutAssetData.MaterialReplacements.Reset();
		const TSharedPtr<FJsonObject>* MaterialReplacementsJson = nullptr;
		if (AssetObject.TryGetObjectField(TEXT("material_replacements"), MaterialReplacementsJson))
		{
			for (const auto& Pair : (*MaterialReplacementsJson)->Values)
			{
				FString Replacement;
				if (Pair.Value.IsValid() && Pair.Value->TryGetString(Replacement))
				{
					OutAssetData.MaterialReplacements.Add(Pair.Key, Replacement);
				}
			}
		}

		// "enable_live_pose_preview" is optional (missing/absent means
		// false -- the real dataset-generation pipeline never emits it,
		// see FScenarioAssetData::bEnableLivePosePreview's own comment).
		bool bEnableLivePosePreview = false;
		AssetObject.TryGetBoolField(TEXT("enable_live_pose_preview"), bEnableLivePosePreview);
		OutAssetData.bEnableLivePosePreview = bEnableLivePosePreview;

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
			double SunIntensity = 0.0;
			if ((*SunJson)->TryGetNumberField(TEXT("intensity_lux"), SunIntensity))
			{
				if (UDirectionalLightComponent* SunLight = Cast<UDirectionalLightComponent>(It->GetLightComponent()))
				{
					SunLight->SetIntensity(static_cast<float>(SunIntensity));
				}
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
				const TArray<TSharedPtr<FJsonValue>>* FogColor = nullptr;
				if ((*FogJson)->TryGetArrayField(TEXT("color"), FogColor) && FogColor->Num() == 3)
				{
					Fog->SetFogInscatteringColor(FLinearColor(
						static_cast<float>((*FogColor)[0]->AsNumber()),
						static_cast<float>((*FogColor)[1]->AsNumber()),
						static_cast<float>((*FogColor)[2]->AsNumber())));
				}
			}
			break;
		}
	}

	const TSharedPtr<FJsonObject>* RainJson = nullptr;
	if (Env->TryGetObjectField(TEXT("rain"), RainJson))
	{
		UMaterialInterface* RainBase = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/VantageCV/M_RainStreaks.M_RainStreaks"));
		if (RainBase == nullptr)
		{
			UE_LOG(LogProceduralScenarioLoader, Warning, TEXT("ApplyEnvironment: rain requested but /Game/VantageCV/M_RainStreaks is missing; run unreal_plugin/tools/create_rain_material.py"));
		}
		else
		{
			UMaterialInstanceDynamic* RainMaterial = UMaterialInstanceDynamic::Create(RainBase, this);
			double Value = 0.0;
			if ((*RainJson)->TryGetNumberField(TEXT("intensity"), Value))
			{
				RainMaterial->SetScalarParameterValue(TEXT("Intensity"), static_cast<float>(Value));
			}
			if ((*RainJson)->TryGetNumberField(TEXT("slant"), Value))
			{
				RainMaterial->SetScalarParameterValue(TEXT("Slant"), static_cast<float>(Value));
			}
			if ((*RainJson)->TryGetNumberField(TEXT("seed"), Value))
			{
				RainMaterial->SetScalarParameterValue(TEXT("Seed"), static_cast<float>(Value));
			}
			FActorSpawnParameters RainSpawnParams;
			RainSpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			if (APostProcessVolume* RainVolume = World->SpawnActor<APostProcessVolume>(FVector::ZeroVector, FRotator::ZeroRotator, RainSpawnParams))
			{
				RainVolume->bUnbound = true;
				RainVolume->BlendWeight = 1.0f;
				RainVolume->Priority = 101.0f;
				RainVolume->Settings.AddBlendable(RainMaterial, 1.0f);
				SpawnedAssetActors.Add(RainVolume);
			}
		}
	}

	const TSharedPtr<FJsonObject>* SkyLightJson = nullptr;
	if (Env->TryGetObjectField(TEXT("sky_light"), SkyLightJson))
	{
		double Value = 0.0;
		if ((*SkyLightJson)->TryGetNumberField(TEXT("intensity"), Value))
		{
			for (TObjectIterator<USkyLightComponent> It; It; ++It)
			{
				if (It->GetWorld() == World)
				{
					It->SetIntensity(static_cast<float>(Value));
				}
			}
		}
	}

	SurfaceScalars.Reset();
	const TSharedPtr<FJsonObject>* SurfaceJson = nullptr;
	if (Env->TryGetObjectField(TEXT("surface_scalars"), SurfaceJson))
	{
		for (const auto& TagPair : (*SurfaceJson)->Values)
		{
			const TSharedPtr<FJsonObject>* ParamsJson = nullptr;
			if (!TagPair.Value.IsValid() || !TagPair.Value->TryGetObject(ParamsJson))
			{
				continue;
			}
			TMap<FName, float>& Params = SurfaceScalars.FindOrAdd(TagPair.Key);
			for (const auto& ParamPair : (*ParamsJson)->Values)
			{
				double Number = 0.0;
				if (ParamPair.Value.IsValid() && ParamPair.Value->TryGetNumber(Number))
				{
					Params.Add(FName(*ParamPair.Key), static_cast<float>(Number));
				}
			}
		}
	}

	const TSharedPtr<FJsonObject>* AtmosphereJson = nullptr;
	if (Env->TryGetObjectField(TEXT("sky_atmosphere"), AtmosphereJson))
	{
		for (TObjectIterator<USkyAtmosphereComponent> It; It; ++It)
		{
			if (It->GetWorld() != World)
			{
				continue;
			}
			double Value = 0.0;
			if ((*AtmosphereJson)->TryGetNumberField(TEXT("rayleigh_scale"), Value))
			{
				It->SetRayleighScatteringScale(static_cast<float>(Value));
			}
			if ((*AtmosphereJson)->TryGetNumberField(TEXT("mie_scale"), Value))
			{
				It->SetMieScatteringScale(static_cast<float>(Value));
			}
			if ((*AtmosphereJson)->TryGetNumberField(TEXT("mie_absorption_scale"), Value))
			{
				It->SetMieAbsorptionScale(static_cast<float>(Value));
			}
			if ((*AtmosphereJson)->TryGetNumberField(TEXT("mie_anisotropy"), Value))
			{
				It->SetMieAnisotropy(static_cast<float>(Value));
			}
			if ((*AtmosphereJson)->TryGetNumberField(TEXT("multi_scattering"), Value))
			{
				It->SetMultiScatteringFactor(static_cast<float>(Value));
			}
		}
	}

	const TSharedPtr<FJsonObject>* CloudsJson = nullptr;
	if (Env->TryGetObjectField(TEXT("clouds"), CloudsJson))
	{
		double Extinction = 0.0;
		const bool bHasExtinction = (*CloudsJson)->TryGetNumberField(TEXT("extinction_scale"), Extinction);
		const TSharedPtr<FJsonObject>* ScalarsJson = nullptr;
		const bool bHasScalars = (*CloudsJson)->TryGetObjectField(TEXT("scalars"), ScalarsJson);
		double BottomKm = 0.0;
		const bool bHasBottom = (*CloudsJson)->TryGetNumberField(TEXT("layer_bottom_km"), BottomKm);
		double HeightKm = 0.0;
		const bool bHasHeight = (*CloudsJson)->TryGetNumberField(TEXT("layer_height_km"), HeightKm);
		for (TObjectIterator<UVolumetricCloudComponent> It; It; ++It)
		{
			if (It->GetWorld() != World)
			{
				continue;
			}
			if (bHasBottom)
			{
				It->SetLayerBottomAltitude(static_cast<float>(BottomKm));
			}
			if (bHasHeight)
			{
				It->SetLayerHeight(static_cast<float>(HeightKm));
			}
			if ((bHasExtinction || bHasScalars) && It->GetMaterial() != nullptr)
			{
				UMaterialInstanceDynamic* CloudMaterial = Cast<UMaterialInstanceDynamic>(It->GetMaterial());
				if (CloudMaterial == nullptr)
				{
					CloudMaterial = UMaterialInstanceDynamic::Create(It->GetMaterial(), this);
					It->SetMaterial(CloudMaterial);
				}
				if (bHasExtinction)
				{
					CloudMaterial->SetScalarParameterValue(TEXT("ExtinctionScale"), static_cast<float>(Extinction));
				}
				if (bHasScalars)
				{
					for (const auto& Scalar : (*ScalarsJson)->Values)
					{
						double Number = 0.0;
						if (Scalar.Value.IsValid() && Scalar.Value->TryGetNumber(Number))
						{
							CloudMaterial->SetScalarParameterValue(FName(*Scalar.Key), static_cast<float>(Number));
						}
					}
				}
			}
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

	// Every load starts from the map's own lighting, so no scenario inherits the
	// previous one's sun, sky, cloud or fog settings.
	RestoreMapEnvironmentDefaults();

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
			if (const TMap<FName, float>* Overrides = SurfaceScalars.Find(MeshData.Material))
			{
				if (UMaterialInstanceDynamic* SurfaceMaterial = Component->CreateDynamicMaterialInstance(0))
				{
					for (const TPair<FName, float>& Scalar : *Overrides)
					{
						SurfaceMaterial->SetScalarParameterValue(Scalar.Key, Scalar.Value);
					}
				}
			}
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

	// "lights" is optional (absent = a daytime scenario, nothing to spawn).
	const TArray<TSharedPtr<FJsonValue>>* LightsJson = nullptr;
	if (Root->TryGetArrayField(TEXT("lights"), LightsJson))
	{
		int32 LightsSpawned = 0;
		int32 LightsSkipped = 0;
		SpawnLights(*LightsJson, LightsSpawned, LightsSkipped);
		UE_LOG(
			LogProceduralScenarioLoader,
			Display,
			TEXT("LoadProceduralScenario: spawned %d light(s), skipped %d"),
			LightsSpawned,
			LightsSkipped);
	}

	const TArray<TSharedPtr<FJsonValue>>* GlowsJson = nullptr;
	if (Root->TryGetArrayField(TEXT("glows"), GlowsJson))
	{
		int32 GlowsSpawned = 0;
		int32 GlowsSkipped = 0;
		SpawnGlows(*GlowsJson, GlowsSpawned, GlowsSkipped);
		UE_LOG(
			LogProceduralScenarioLoader,
			Display,
			TEXT("LoadProceduralScenario: spawned %d glow(s), skipped %d"),
			GlowsSpawned,
			GlowsSkipped);
	}

	if (bHasAnyVertex)
	{
		RepositionOverviewCamera(GetWorld(), BoundsMin, BoundsMax);
	}

	return true;
}

void AProceduralScenarioLoader::SpawnLights(
	const TArray<TSharedPtr<FJsonValue>>& LightsJson, int32& OutSpawned, int32& OutSkipped)
{
	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		OutSkipped += LightsJson.Num();
		return;
	}

	auto ReadTriple = [](const FJsonObject& Object, const TCHAR* Field, double& X, double& Y, double& Z) -> bool
	{
		const TArray<TSharedPtr<FJsonValue>>* Triple = nullptr;
		if (!Object.TryGetArrayField(Field, Triple) || Triple->Num() != 3)
		{
			return false;
		}
		X = (*Triple)[0]->AsNumber();
		Y = (*Triple)[1]->AsNumber();
		Z = (*Triple)[2]->AsNumber();
		return true;
	};

	for (const TSharedPtr<FJsonValue>& LightValue : LightsJson)
	{
		const TSharedPtr<FJsonObject>* LightObject = nullptr;
		FString Type;
		double PX = 0.0, PY = 0.0, PZ = 0.0;
		double R = 1.0, G = 1.0, B = 1.0;
		double Intensity = 0.0;
		double AttenuationMeters = 0.0;
		if (!LightValue->TryGetObject(LightObject)
			|| !(*LightObject)->TryGetStringField(TEXT("type"), Type)
			|| !ReadTriple(**LightObject, TEXT("position"), PX, PY, PZ)
			|| !ReadTriple(**LightObject, TEXT("color"), R, G, B)
			|| !(*LightObject)->TryGetNumberField(TEXT("intensity"), Intensity)
			|| !(*LightObject)->TryGetNumberField(TEXT("attenuation_m"), AttenuationMeters))
		{
			++OutSkipped;
			continue;
		}

		const FVector Location = ApplyCoordinateConvention(PX, PY, PZ);
		const FLinearColor Color(static_cast<float>(R), static_cast<float>(G), static_cast<float>(B));
		FActorSpawnParameters SpawnParameters;
		SpawnParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

		ULightComponent* LightComponent = nullptr;
		AActor* LightActor = nullptr;
		if (Type == TEXT("spot"))
		{
			double DX = 0.0, DY = 0.0, DZ = 0.0;
			double InnerCone = 0.0, OuterCone = 0.0;
			if (!ReadTriple(**LightObject, TEXT("direction"), DX, DY, DZ)
				|| !(*LightObject)->TryGetNumberField(TEXT("inner_cone_deg"), InnerCone)
				|| !(*LightObject)->TryGetNumberField(TEXT("outer_cone_deg"), OuterCone))
			{
				++OutSkipped;
				continue;
			}
			// Direction is a unit vector, not a position: mirror Y for the
			// handedness change but do not scale meters to centimeters.
			const FVector Direction = FVector(DX, -DY, DZ).GetSafeNormal();
			ASpotLight* Spot = World->SpawnActor<ASpotLight>(
				Location, FRotationMatrix::MakeFromX(Direction).Rotator(), SpawnParameters);
			if (Spot != nullptr)
			{
				USpotLightComponent* SpotComponent = Cast<USpotLightComponent>(Spot->GetLightComponent());
				if (SpotComponent != nullptr)
				{
					// Movable FIRST: Unreal ignores dynamic property changes
					// (cone angles included) on a non-movable light, which
					// silently left every beam at the default 44 degree cone.
					SpotComponent->SetMobility(EComponentMobility::Movable);
					SpotComponent->SetInnerConeAngle(static_cast<float>(InnerCone));
					SpotComponent->SetOuterConeAngle(static_cast<float>(OuterCone));
				}
				LightComponent = SpotComponent;
				LightActor = Spot;
			}
		}
		else if (Type == TEXT("point"))
		{
			APointLight* Point = World->SpawnActor<APointLight>(Location, FRotator::ZeroRotator, SpawnParameters);
			if (Point != nullptr)
			{
				LightComponent = Point->GetLightComponent();
				LightActor = Point;
			}
		}

		if (LightActor == nullptr || LightComponent == nullptr)
		{
			if (LightActor != nullptr)
			{
				LightActor->Destroy();
			}
			++OutSkipped;
			continue;
		}

		// Runtime-spawned lights default to Stationary, which needs a
		// lighting build that -game never has: Movable is what actually
		// renders. Unshadowed keeps hundreds of small lights cheap.
		LightComponent->SetMobility(EComponentMobility::Movable);
		LightComponent->SetLightColor(Color);
		LightComponent->SetCastShadows(false);
		if (ULocalLightComponent* LocalLight = Cast<ULocalLightComponent>(LightComponent))
		{
			LocalLight->SetIntensityUnits(ELightUnits::Candelas);
			LocalLight->SetAttenuationRadius(static_cast<float>(AttenuationMeters) * MetersToUnrealUnits);
		}
		LightComponent->SetIntensity(static_cast<float>(Intensity));
		// Optional: an inverse-square light is far brighter close in than far
		// away, so a headlight 0.7 m off the road blows out the pavement just
		// ahead of the bumper. "inverse_squared": false gives an even wash out
		// to the attenuation radius instead (intensity is then unitless).
		bool bInverseSquared = true;
		if ((*LightObject)->TryGetBoolField(TEXT("inverse_squared"), bInverseSquared) && !bInverseSquared)
		{
			if (UPointLightComponent* LocalFalloff = Cast<UPointLightComponent>(LightComponent))
			{
				LocalFalloff->bUseInverseSquaredFalloff = false;
				double FalloffExponent = 0.0;
				if ((*LightObject)->TryGetNumberField(TEXT("falloff_exponent"), FalloffExponent))
				{
					LocalFalloff->SetLightFalloffExponent(static_cast<float>(FalloffExponent));
				}
				LocalFalloff->SetIntensity(static_cast<float>(Intensity));
				LocalFalloff->MarkRenderStateDirty();
			}
		}
		SpawnedAssetActors.Add(LightActor);
		++OutSpawned;
	}
}

void AProceduralScenarioLoader::SpawnGlows(
	const TArray<TSharedPtr<FJsonValue>>& GlowsJson, int32& OutSpawned, int32& OutSkipped)
{
	UWorld* World = GetWorld();
	UStaticMesh* SphereMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	UMaterialInterface* GlowMaterial = LoadObject<UMaterialInterface>(
		nullptr, TEXT("/Game/VantageCV/M_EmissiveGlow.M_EmissiveGlow"));
	if (World == nullptr || SphereMesh == nullptr || GlowMaterial == nullptr)
	{
		OutSkipped += GlowsJson.Num();
		return;
	}

	for (const TSharedPtr<FJsonValue>& GlowValue : GlowsJson)
	{
		const TSharedPtr<FJsonObject>* GlowObject = nullptr;
		const TArray<TSharedPtr<FJsonValue>>* Position = nullptr;
		const TArray<TSharedPtr<FJsonValue>>* Color = nullptr;
		double Intensity = 0.0;
		if (!GlowValue->TryGetObject(GlowObject)
			|| !(*GlowObject)->TryGetArrayField(TEXT("position"), Position) || Position->Num() != 3
			|| !(*GlowObject)->TryGetArrayField(TEXT("color"), Color) || Color->Num() != 3
			|| !(*GlowObject)->TryGetNumberField(TEXT("intensity"), Intensity))
		{
			++OutSkipped;
			continue;
		}

		// Optional shape: "semi_axes_m" [forward, lateral, vertical] of an
		// ellipsoid in the mesh's own local axes (a real lens's half-extents),
		// else a sphere of "radius_m" (default 5 cm); "rotation_rad" is a
		// heading, with its sign negated for the Y mirror exactly like an
		// asset's.
		FVector SemiAxesMeters(0.05);
		double RadiusMeters = 0.0;
		const TArray<TSharedPtr<FJsonValue>>* SemiAxes = nullptr;
		if ((*GlowObject)->TryGetArrayField(TEXT("semi_axes_m"), SemiAxes) && SemiAxes->Num() == 3)
		{
			SemiAxesMeters = FVector((*SemiAxes)[0]->AsNumber(), (*SemiAxes)[1]->AsNumber(), (*SemiAxes)[2]->AsNumber());
		}
		else if ((*GlowObject)->TryGetNumberField(TEXT("radius_m"), RadiusMeters))
		{
			SemiAxesMeters = FVector(RadiusMeters);
		}
		double RotationRad = 0.0;
		(*GlowObject)->TryGetNumberField(TEXT("rotation_rad"), RotationRad);

		FActorSpawnParameters SpawnParameters;
		SpawnParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		AStaticMeshActor* GlowActor = World->SpawnActor<AStaticMeshActor>(
			ApplyCoordinateConvention(
				(*Position)[0]->AsNumber(), (*Position)[1]->AsNumber(), (*Position)[2]->AsNumber()),
			FRotator(0.0, -FMath::RadiansToDegrees(RotationRad), 0.0),
			SpawnParameters);
		if (GlowActor == nullptr)
		{
			++OutSkipped;
			continue;
		}

		UStaticMeshComponent* Component = GlowActor->GetStaticMeshComponent();
		Component->SetMobility(EComponentMobility::Movable);
		Component->SetStaticMesh(SphereMesh);
		// The engine sphere is 100 cm across: scale = diameter in cm / 100.
		GlowActor->SetActorScale3D(SemiAxesMeters * 2.0);
		Component->SetCastShadow(false);
		Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);

		UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(GlowMaterial, GlowActor);
		const FLinearColor GlowColor(
			static_cast<float>((*Color)[0]->AsNumber() * Intensity),
			static_cast<float>((*Color)[1]->AsNumber() * Intensity),
			static_cast<float>((*Color)[2]->AsNumber() * Intensity));
		MID->SetVectorParameterValue(TEXT("GlowColor"), GlowColor);
		Component->SetMaterial(0, MID);

		SpawnedAssetActors.Add(GlowActor);
		++OutSpawned;
	}
}

void AProceduralScenarioLoader::CaptureMapEnvironmentDefaults()
{
	UWorld* World = GetWorld();
	if (World == nullptr || MapDefaults.bCaptured)
	{
		return;
	}
	for (TActorIterator<ADirectionalLight> It(World); It; ++It)
	{
		if (UDirectionalLightComponent* Light = Cast<UDirectionalLightComponent>(It->GetLightComponent()))
		{
			MapDefaults.SunIntensity = Light->Intensity;
			MapDefaults.SunTemperature = Light->Temperature;
			MapDefaults.bSunUseTemperature = Light->bUseTemperature;
		}
		MapDefaults.SunRotation = It->GetActorRotation();
		break;
	}
	for (TObjectIterator<USkyLightComponent> It; It; ++It)
	{
		if (It->GetWorld() == World)
		{
			MapDefaults.SkyLightIntensity = It->Intensity;
			break;
		}
	}
	for (TObjectIterator<USkyAtmosphereComponent> It; It; ++It)
	{
		if (It->GetWorld() == World)
		{
			MapDefaults.RayleighScale = It->RayleighScatteringScale;
			MapDefaults.MieScale = It->MieScatteringScale;
			MapDefaults.MieAbsorptionScale = It->MieAbsorptionScale;
			MapDefaults.MieAnisotropy = It->MieAnisotropy;
			MapDefaults.MultiScattering = It->MultiScatteringFactor;
			break;
		}
	}
	for (TObjectIterator<UVolumetricCloudComponent> It; It; ++It)
	{
		if (It->GetWorld() != World)
		{
			continue;
		}
		MapDefaults.CloudLayerBottom = It->LayerBottomAltitude;
		MapDefaults.CloudLayerHeight = It->LayerHeight;
		if (UMaterialInterface* CloudBase = It->GetMaterial())
		{
			TArray<FMaterialParameterInfo> Infos;
			TArray<FGuid> Ids;
			CloudBase->GetAllScalarParameterInfo(Infos, Ids);
			for (const FMaterialParameterInfo& Info : Infos)
			{
				float Value = 0.0f;
				if (CloudBase->GetScalarParameterValue(FHashedMaterialParameterInfo(Info.Name), Value))
				{
					MapDefaults.CloudScalars.Add(Info.Name, Value);
				}
			}
		}
		break;
	}
	for (TActorIterator<AExponentialHeightFog> It(World); It; ++It)
	{
		if (UExponentialHeightFogComponent* Fog = It->GetComponent())
		{
			MapDefaults.FogDensity = Fog->FogDensity;
			MapDefaults.FogHeightFalloff = Fog->FogHeightFalloff;
			MapDefaults.FogStartDistance = Fog->StartDistance;
			MapDefaults.FogColor = Fog->FogInscatteringLuminance;
		}
		break;
	}
	MapDefaults.bCaptured = true;
}

void AProceduralScenarioLoader::RestoreMapEnvironmentDefaults()
{
	UWorld* World = GetWorld();
	if (World == nullptr)
	{
		return;
	}
	CaptureMapEnvironmentDefaults();
	for (TActorIterator<ADirectionalLight> It(World); It; ++It)
	{
		if (UDirectionalLightComponent* Light = Cast<UDirectionalLightComponent>(It->GetLightComponent()))
		{
			Light->SetIntensity(MapDefaults.SunIntensity);
			Light->SetTemperature(MapDefaults.SunTemperature);
			Light->SetUseTemperature(MapDefaults.bSunUseTemperature);
		}
		It->SetActorRotation(MapDefaults.SunRotation);
		break;
	}
	for (TObjectIterator<USkyLightComponent> It; It; ++It)
	{
		if (It->GetWorld() == World)
		{
			It->SetIntensity(MapDefaults.SkyLightIntensity);
		}
	}
	for (TObjectIterator<USkyAtmosphereComponent> It; It; ++It)
	{
		if (It->GetWorld() == World)
		{
			It->SetRayleighScatteringScale(MapDefaults.RayleighScale);
			It->SetMieScatteringScale(MapDefaults.MieScale);
			It->SetMieAbsorptionScale(MapDefaults.MieAbsorptionScale);
			It->SetMieAnisotropy(MapDefaults.MieAnisotropy);
			It->SetMultiScatteringFactor(MapDefaults.MultiScattering);
		}
	}
	for (TObjectIterator<UVolumetricCloudComponent> It; It; ++It)
	{
		if (It->GetWorld() != World)
		{
			continue;
		}
		It->SetLayerBottomAltitude(MapDefaults.CloudLayerBottom);
		It->SetLayerHeight(MapDefaults.CloudLayerHeight);
		if (UMaterialInstanceDynamic* CloudMaterial = Cast<UMaterialInstanceDynamic>(It->GetMaterial()))
		{
			for (const TPair<FName, float>& Scalar : MapDefaults.CloudScalars)
			{
				CloudMaterial->SetScalarParameterValue(Scalar.Key, Scalar.Value);
			}
		}
	}
	for (TActorIterator<AExponentialHeightFog> It(World); It; ++It)
	{
		if (UExponentialHeightFogComponent* Fog = It->GetComponent())
		{
			Fog->SetFogDensity(MapDefaults.FogDensity);
			Fog->SetFogHeightFalloff(MapDefaults.FogHeightFalloff);
			Fog->SetStartDistance(MapDefaults.FogStartDistance);
			Fog->SetFogInscatteringColor(MapDefaults.FogColor);
		}
		break;
	}
}
