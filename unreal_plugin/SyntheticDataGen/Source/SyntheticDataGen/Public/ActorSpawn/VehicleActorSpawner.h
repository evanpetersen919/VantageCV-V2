// City Sample asset integration Phase 1: spawns a plain actor holding a
// real City Sample vehicle's body mesh plus its wheels/doors/glass/
// interior/steering-wheel, all as sibling components at a fixed pose.
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
// instead. A first attempt used each vehicle's real skeletal mesh, but
// a real live screenshot (2026-09-16, see KNOWN_GAPS_AND_ISSUES.md)
// showed it rendering as only a tiny sliver of its true geometry --
// City Sample's skeletal rigs drive a runtime damage-state system, and
// without an AnimBlueprint actively posing them, the reference pose
// doesn't show the intact body. Switched to each vehicle's static
// "SM_Frame_<name>" body-shell mesh instead, which has no such
// dependency and renders unconditionally. The body alone is wheel/door/
// glass-less; a real live test (2026-09-16) confirmed each of those
// parts' own static meshes are pre-modeled in their final assembled
// position already (a common modular-kit convention), so spawning them
// as sibling components at the exact same actor transform as the body
// -- no offset math needed at all -- produces a correctly assembled
// vehicle. See city_sample_assets.py's VEHICLE_PART_PATHS.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "VehicleActorSpawner.generated.h"

// Mirrors one entry of the JSON "assets" array (scenario_serializer.py's
// _vehicle_to_asset_json / the City Sample integration plan's schema:
// {"category", "asset_path", "part_paths", "position", "rotation_rad",
// "id"}). Position/Rotation are already in UE5 space here -- the caller
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

	// Additional static meshes (wheels/doors/glass/interior/steering
	// wheel) spawned as sibling components at this same entry's
	// Position/Rotation -- see this file's own header comment for why
	// no per-part offset is needed. Empty for asset categories that
	// don't have parts (or a vehicle folder city_sample_assets.py's
	// VEHICLE_PART_PATHS has no entry for).
	UPROPERTY(BlueprintReadWrite, Category = "SyntheticDataGen")
	TArray<FString> PartPaths;

	UPROPERTY(BlueprintReadWrite, Category = "SyntheticDataGen")
	FVector Position = FVector::ZeroVector;

	UPROPERTY(BlueprintReadWrite, Category = "SyntheticDataGen")
	FRotator Rotation = FRotator::ZeroRotator;
};

/**
 * Spawns a plain AActor with a UStaticMeshComponent set to a real City
 * Sample vehicle body mesh, from one FScenarioAssetData entry. No
 * vehicle movement component, no physics simulation -- scenarios are
 * deterministic frozen-frame captures, so the mesh only needs to sit at
 * its procedurally-computed pose, not drive.
 *
 * Uses each vehicle's static "SM_Frame_<name>" body-shell mesh, not the
 * combined "SKM_<name>" skeletal rig City Sample itself uses. Real live
 * screenshots (2026-09-16, see KNOWN_GAPS_AND_ISSUES.md) showed the
 * combined skeletal mesh renders as only a tiny sliver of its true
 * geometry without an AnimBlueprint actively driving it -- City
 * Sample's vehicles are rigged for a runtime damage-state system
 * (Sandbox/Destruction/Deformable), and the reference pose alone
 * doesn't show the intact body. A plain static mesh has no such
 * dependency and renders its authored geometry unconditionally;
 * "SM_Frame_<name>" (confirmed present for all 14 vehicles, unlike the
 * skeletal "SKM_Exterior_<name>" variant some but not all vehicles
 * have) is the body shell without wheels/doors/interior detail -- a
 * real known limitation (see this class's .cpp), not the full vehicle,
 * but correctly visible and recognizably vehicle-shaped, unlike the
 * skeletal mesh it replaced.
 */
UCLASS(ClassGroup = (SyntheticDataGen), meta = (BlueprintSpawnableComponent))
class SYNTHETICDATAGEN_API UVehicleActorSpawner final : public UActorComponent
{
	GENERATED_BODY()

public:
	UVehicleActorSpawner();

	/**
	 * Loads AssetData.AssetPath as a UStaticMesh and spawns a plain
	 * actor holding it (via a UStaticMeshComponent) into World at
	 * AssetData.Position/Rotation.
	 *
	 * @param World      World to spawn into; must be non-null.
	 * @param AssetData  One vehicle entry, with Position/Rotation
	 *        already converted to UE5 space by the caller.
	 * @return The spawned actor, or nullptr if AssetPath didn't resolve
	 *         to a loadable static mesh or spawning otherwise failed.
	 */
	UFUNCTION(BlueprintCallable, Category = "SyntheticDataGen")
	AActor* SpawnVehicle(UWorld* World, const FScenarioAssetData& AssetData) const;
};
