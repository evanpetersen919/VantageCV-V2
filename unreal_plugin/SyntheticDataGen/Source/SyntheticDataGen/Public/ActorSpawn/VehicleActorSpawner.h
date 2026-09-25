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

	// Per-instance scale along the mesh's OWN local axes (UE space, no
	// coordinate flip -- it is not a world-space quantity). Defaults to
	// (1, 1, 1). A negative component mirrors the mesh; City Sample's
	// real curbs are placed at (1, -0.75, 0.75).
	UPROPERTY(BlueprintReadWrite, Category = "SyntheticDataGen")
	FVector Scale = FVector::OneVector;

	// Per-instance material scalar parameter overrides (e.g. {"Frame":
	// 205.0}), applied identically to this entry's body mesh AND every
	// one of its PartPaths components -- real pedestrian pose selection
	// is the motivating case (see VehicleActorSpawner.cpp's
	// ApplyMaterialScalarOverrides for the real evidence behind this:
	// City Sample's own crowd VAT materials, confirmed live via a real
	// per-mesh AnimToTextureDataAsset query, share one universal 430-
	// frame/two-clip layout across every body/top/bottom/shoe/face/hair
	// asset this project uses, so one "Frame" value applies coherently
	// across a whole pedestrian's outfit). Empty for asset categories
	// that don't use this (vehicles, facade pieces) -- a genuinely
	// empty map is a no-op in ApplyMaterialScalarOverrides, not a
	// special case, so this costs those categories nothing.
	//
	// A live test (2026-09-23) initially found this alone had ZERO
	// visible effect on pose -- root-caused (not guessed) to two static
	// switch parameters ("Animate", "UseFourInfluences") defaulting to
	// False on the shared ML_BoneAnimation material layer, which compile
	// the pose-driving shader branch out entirely regardless of any
	// runtime value here. Fixed at the content level (see
	// VehicleActorSpawner.cpp's ApplyMaterialScalarOverrides and
	// KNOWN_GAPS_AND_ISSUES.md for the full investigation) -- this
	// mechanism itself was always correct.
	UPROPERTY(BlueprintReadWrite, Category = "SyntheticDataGen")
	TMap<FString, float> MaterialScalarOverrides;

	// Original material object path OR material slot name (e.g. "Bldg_glass") ->
	// replacement material object path, applied to every matching slot of the body mesh. Needed because
	// static switches (e.g. a window's lights-on branch) are baked per material
	// instance and cannot be flipped by a runtime MID override, so a
	// project-owned instance with the switch set is swapped in instead.
	UPROPERTY(BlueprintReadWrite, Category = "SyntheticDataGen")
	TMap<FString, FString> MaterialReplacements;

	// Opt-in, per-asset flag (default false -- absent in every payload
	// the real dataset-generation pipeline emits) enabling REAL
	// continuous per-instance walk-cycle animation for interactive Play
	// mode QA/review only. When true AND MaterialScalarOverrides
	// contains "Frame" (the existing, already-reliable signal that this
	// asset is an animatable pedestrian), SpawnVehicle attaches a
	// UPedestrianWalkCycleComponent that ticks the real "Frame" MID
	// parameter over elapsed wall-clock time, confined to whichever real
	// baked clip (walking 0-319, or standing 320-429 -- see
	// city_sample_assets.py's PEDESTRIAN_WALKING_CLIP/
	// PEDESTRIAN_STANDING_CLIP) this pedestrian's own assigned Frame
	// value already belongs to, starting from a random per-instance
	// phase so pedestrians are never synchronized.
	//
	// Deliberately NOT the default (2026-09-23 investigation, see
	// KNOWN_GAPS_AND_ISSUES.md): the dataset-generation pipeline's
	// reproducibility depends on a scenario's captured pose being a
	// deterministic function of its seed, not of wall-clock elapsed time
	// since actor spawn -- real-time animation is correct for a human
	// watching interactively, but would make the ACTUAL captured
	// training frame depend on exactly when the screenshot happens to be
	// taken, which is not acceptable for a reproducible research
	// dataset. serialize_scenario's enable_live_pose_preview parameter
	// (default False) is the only thing that ever sets this field to
	// true, and the real dataset-generation pipeline never passes it.
	UPROPERTY(BlueprintReadWrite, Category = "SyntheticDataGen")
	bool bEnableLivePosePreview = false;
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
