// City Sample asset integration Phase 1: spawns real City Sample
// vehicle Blueprint actors (not static meshes -- see
// KNOWN_GAPS_AND_ISSUES.md's Phase 0 investigation entry: vehicles are
// real Blueprint actors with Chaos vehicle physics and skeletal wheel
// animation, confirmed via direct inspection of City Sample's
// installed content).

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "VehicleActorSpawner.generated.h"

// Mirrors one entry of the JSON "assets" array (scenario_serializer.py's
// _vehicle_to_asset_json / the City Sample integration plan's schema:
// {"category", "asset_path", "position", "rotation_rad", "id"}).
// Position/Rotation are already in UE5 space here -- the caller
// (AProceduralScenarioLoader) owns that conversion via
// ApplyCoordinateConvention, the same split FScenarioMeshData's
// Vertices already use for mesh geometry.
USTRUCT(BlueprintType)
struct FScenarioAssetData
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadWrite, Category = "SyntheticDataGen")
	FString Category;

	UPROPERTY(BlueprintReadWrite, Category = "SyntheticDataGen")
	FString AssetPath;

	UPROPERTY(BlueprintReadWrite, Category = "SyntheticDataGen")
	FVector Position = FVector::ZeroVector;

	UPROPERTY(BlueprintReadWrite, Category = "SyntheticDataGen")
	FRotator Rotation = FRotator::ZeroRotator;
};

/**
 * Spawns a real City Sample vehicle Blueprint actor from one
 * FScenarioAssetData entry, and freezes its physics immediately so it
 * stays at its procedurally-computed pose -- scenarios are
 * deterministic frozen-frame captures, not live simulations (see the
 * City Sample integration plan's "Vehicle physics" architectural
 * decision).
 */
UCLASS(ClassGroup = (SyntheticDataGen), meta = (BlueprintSpawnableComponent))
class SYNTHETICDATAGEN_API UVehicleActorSpawner final : public UActorComponent
{
	GENERATED_BODY()

public:
	UVehicleActorSpawner();

	/**
	 * Loads AssetData.AssetPath as an actor Blueprint class and spawns
	 * it into World at AssetData.Position/Rotation, then freezes
	 * physics simulation on every primitive component (a Chaos
	 * vehicle's wheels are typically simulated as their own physics
	 * bodies, not just the root).
	 *
	 * @param World      World to spawn into; must be non-null.
	 * @param AssetData  One vehicle entry, with Position/Rotation
	 *        already converted to UE5 space by the caller.
	 * @return The spawned actor, or nullptr if AssetPath didn't resolve
	 *         to a loadable actor class or spawning otherwise failed.
	 */
	UFUNCTION(BlueprintCallable, Category = "SyntheticDataGen")
	AActor* SpawnVehicle(UWorld* World, const FScenarioAssetData& AssetData) const;
};
