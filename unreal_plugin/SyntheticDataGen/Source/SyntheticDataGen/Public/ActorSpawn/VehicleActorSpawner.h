// City Sample asset integration Phase 1: spawns a plain actor holding a
// real City Sample vehicle skeletal mesh at a fixed pose.
//
// This is NOT City Sample's own driveable-vehicle Blueprint
// (BP_veh*_Sandbox). A real live PIE check (2026-09-16) found every
// such Blueprint's parent chain ultimately depends on
// ACitySampleVehicleBase -- a native C++ class defined in CitySample's
// own game-project *source*, not portable content, and itself deeply
// wired into CitySample's gameplay framework (Mass AI traffic control,
// Enhanced Input, a custom UI/menu system, photo mode,
// ACitySampleCharacter). None of that is needed here: scenarios are
// frozen-frame captures, not driveable, so this spawns a minimal actor
// with just the real skeletal mesh -- genuinely portable content with
// no such dependency -- instead. See KNOWN_GAPS_AND_ISSUES.md.

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
 * Spawns a plain AActor with a USkeletalMeshComponent set to a real
 * City Sample vehicle skeletal mesh, from one FScenarioAssetData entry.
 * No vehicle movement component, no physics simulation -- scenarios are
 * deterministic frozen-frame captures, so the mesh only needs to sit at
 * its procedurally-computed pose, not drive.
 */
UCLASS(ClassGroup = (SyntheticDataGen), meta = (BlueprintSpawnableComponent))
class SYNTHETICDATAGEN_API UVehicleActorSpawner final : public UActorComponent
{
	GENERATED_BODY()

public:
	UVehicleActorSpawner();

	/**
	 * Loads AssetData.AssetPath as a USkeletalMesh and spawns a plain
	 * actor holding it (via a USkeletalMeshComponent) into World at
	 * AssetData.Position/Rotation.
	 *
	 * @param World      World to spawn into; must be non-null.
	 * @param AssetData  One vehicle entry, with Position/Rotation
	 *        already converted to UE5 space by the caller.
	 * @return The spawned actor, or nullptr if AssetPath didn't resolve
	 *         to a loadable skeletal mesh or spawning otherwise failed.
	 */
	UFUNCTION(BlueprintCallable, Category = "SyntheticDataGen")
	AActor* SpawnVehicle(UWorld* World, const FScenarioAssetData& AssetData) const;
};
