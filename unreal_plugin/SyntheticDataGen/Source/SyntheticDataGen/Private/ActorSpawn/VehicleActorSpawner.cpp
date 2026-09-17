// Compiles cleanly against a real UE 5.4.4 editor and confirmed
// spawning real vehicle meshes in a live standalone session (verified
// 2026-09-16 -- see KNOWN_GAPS_AND_ISSUES.md). An earlier version of
// this file tried to LoadClass + SpawnActor City Sample's own
// BP_veh*_Sandbox driveable-vehicle Blueprints; that failed for all 14
// real migrated vehicles because their parent chain ultimately depends
// on ACitySampleVehicleBase, a native C++ class in CitySample's own
// game-project source (not portable content) that is itself wired into
// CitySample's gameplay framework (Mass AI traffic control, Enhanced
// Input, a custom UI/menu system). This version instead loads just the
// real skeletal mesh (genuinely portable content) and spawns a plain
// actor holding it -- everything this project actually needs for a
// frozen-frame synthetic scene. See this file's header for the real
// failure this replaced.

#include "ActorSpawn/VehicleActorSpawner.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"

DEFINE_LOG_CATEGORY_STATIC(LogVehicleActorSpawner, Log, All);

UVehicleActorSpawner::UVehicleActorSpawner()
{
	PrimaryComponentTick.bCanEverTick = false;
}

AActor* UVehicleActorSpawner::SpawnVehicle(UWorld* World, const FScenarioAssetData& AssetData) const
{
	if (World == nullptr)
	{
		return nullptr;
	}

	// AssetData.AssetPath points at a real City Sample vehicle's
	// combined skeletal mesh (e.g.
	// "/Game/Vehicle/vehCar_vehicle02/Mesh/SKM_vehCar_vehicle02") --
	// genuinely portable content, confirmed via direct inspection of
	// every migrated vehicle's Mesh/ subfolder (see
	// city_sample_assets.py's module docstring).
	USkeletalMesh* Mesh = LoadObject<USkeletalMesh>(nullptr, *AssetData.AssetPath);
	if (Mesh == nullptr)
	{
		UE_LOG(
			LogVehicleActorSpawner,
			Warning,
			TEXT("SpawnVehicle: failed to load skeletal mesh %s"),
			*AssetData.AssetPath);
		return nullptr;
	}

	FActorSpawnParameters SpawnParams;
	SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

	const FTransform SpawnTransform(AssetData.Rotation, AssetData.Position);
	AActor* SpawnedActor = World->SpawnActor<AActor>(AActor::StaticClass(), SpawnTransform, SpawnParams);
	if (SpawnedActor == nullptr)
	{
		UE_LOG(
			LogVehicleActorSpawner,
			Warning,
			TEXT("SpawnVehicle: SpawnActor failed for %s"),
			*AssetData.AssetPath);
		return nullptr;
	}

	// A plain AActor has no default root component -- create one here
	// holding the real vehicle mesh. No vehicle movement component and
	// no physics simulation: scenarios are deterministic frozen-frame
	// captures, so the mesh only needs to sit at its
	// procedurally-computed pose, not drive (SetSimulatePhysics(false)
	// is a defensive no-op here since simulation is already off by
	// default, kept in case that default ever changes).
	USkeletalMeshComponent* MeshComponent = NewObject<USkeletalMeshComponent>(SpawnedActor);
	MeshComponent->SetSkeletalMesh(Mesh);
	MeshComponent->RegisterComponent();
	SpawnedActor->SetRootComponent(MeshComponent);
	MeshComponent->SetSimulatePhysics(false);

	return SpawnedActor;
}
