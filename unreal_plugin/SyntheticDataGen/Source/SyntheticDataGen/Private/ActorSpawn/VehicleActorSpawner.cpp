// Compiles cleanly against a real UE 5.4.4 editor (verified
// 2026-09-16 -- see KNOWN_GAPS_AND_ISSUES.md). Runtime spawn behavior
// (LoadClass + SpawnActor for a real City Sample vehicle Blueprint,
// SetSimulatePhysics(false) on every primitive component) not yet
// verified in a live PIE session -- pending manual asset migration and
// a PIE check, same as the rest of Phase 1.

#include "ActorSpawn/VehicleActorSpawner.h"
#include "Components/PrimitiveComponent.h"
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

	// AssetData.AssetPath points at a real City Sample vehicle
	// Blueprint (e.g.
	// "/Game/Vehicle/vehCar_vehicle02/BP_vehCar_vehicle02_Sandbox") --
	// a Blueprint-generated AActor subclass, not a plain UStaticMesh,
	// so LoadClass is the correct loader here, not a static mesh load.
	UClass* VehicleClass = LoadClass<AActor>(nullptr, *AssetData.AssetPath);
	if (VehicleClass == nullptr)
	{
		UE_LOG(
			LogVehicleActorSpawner,
			Warning,
			TEXT("SpawnVehicle: failed to load class %s"),
			*AssetData.AssetPath);
		return nullptr;
	}

	FActorSpawnParameters SpawnParams;
	SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

	const FTransform SpawnTransform(AssetData.Rotation, AssetData.Position);
	AActor* SpawnedActor = World->SpawnActor<AActor>(VehicleClass, SpawnTransform, SpawnParams);
	if (SpawnedActor == nullptr)
	{
		UE_LOG(
			LogVehicleActorSpawner,
			Warning,
			TEXT("SpawnVehicle: SpawnActor failed for %s"),
			*AssetData.AssetPath);
		return nullptr;
	}

	// Scenarios are deterministic frozen-frame captures, not live
	// simulations. These are real Chaos-physics vehicle Blueprints
	// (confirmed via direct inspection of City Sample's installed
	// content -- see KNOWN_GAPS_AND_ISSUES.md's Phase 0 entry), so
	// without this an unfrozen vehicle would not stay at its
	// procedurally-computed pose. Every primitive component is frozen,
	// not just a root/single body, since a Chaos vehicle's wheels are
	// typically simulated as their own physics bodies.
	TArray<UPrimitiveComponent*> PrimitiveComponents;
	SpawnedActor->GetComponents<UPrimitiveComponent>(PrimitiveComponents);
	for (UPrimitiveComponent* Primitive : PrimitiveComponents)
	{
		if (Primitive != nullptr)
		{
			Primitive->SetSimulatePhysics(false);
		}
	}

	return SpawnedActor;
}
