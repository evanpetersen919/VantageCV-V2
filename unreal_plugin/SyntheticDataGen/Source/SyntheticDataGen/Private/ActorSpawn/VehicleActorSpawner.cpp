// Compiles cleanly against a real UE 5.4.4 editor and confirmed
// rendering real, correctly-shaped, correctly-positioned vehicle
// bodies in a live standalone session via real screenshots (verified
// 2026-09-16 -- see KNOWN_GAPS_AND_ISSUES.md). Two earlier versions of
// this file were tried and real-screenshot-confirmed broken before
// this one:
//   1. LoadClass + SpawnActor on City Sample's own BP_veh*_Sandbox
//      driveable-vehicle Blueprints -- failed for all 14 real migrated
//      vehicles because their parent chain ultimately depends on
//      ACitySampleVehicleBase, native C++ in CitySample's own
//      game-project source (not portable content).
//   2. LoadObject<USkeletalMesh> on each vehicle's combined "SKM_<name>"
//      rig -- loaded and spawned successfully (no errors, valid
//      non-degenerate mesh bounds, visible=1) but a real screenshot
//      showed it rendering as only a tiny sliver of its true geometry:
//      City Sample's skeletal rigs drive a runtime damage-state system
//      (Sandbox/Destruction/Deformable), and without an AnimBlueprint
//      actively posing them, the reference pose alone doesn't show the
//      intact body.
// This version loads each vehicle's static "SM_Frame_<name>" body-shell
// mesh instead -- confirmed present for all 14 vehicles (unlike the
// skeletal "SKM_Exterior_<name>" variant only some have), and, being a
// plain static mesh with no skeleton at all, has no pose dependency:
// renders its authored geometry unconditionally.
//
// The body alone is wheel/door/glass/interior-less (those are separate
// SM_Wheel_*/SM_Door_*/SM_All_Trans_*/SM_Frame_Interior_* meshes). A
// real live test (2026-09-16) confirmed each of those parts' own mesh
// data is pre-modeled in its final assembled position already -- a
// common modular-vehicle-kit convention -- so spawning them as sibling
// UStaticMeshComponents at the exact same actor transform as the body,
// with no offset at all, produces a correctly assembled vehicle
// (confirmed via a real screenshot: wheels at all four corners, a
// correctly placed door with handle, glass, and a visible interior).
// See city_sample_assets.py's VEHICLE_PART_PATHS for the real,
// per-vehicle part lists (genuinely not uniform -- e.g. dual-rear-axle
// trucks have 6 wheels, the trailer has no doors/glass/interior).

#include "ActorSpawn/VehicleActorSpawner.h"
#include "ActorSpawn/PedestrianWalkCycleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Materials/MaterialInstanceDynamic.h"

DEFINE_LOG_CATEGORY_STATIC(LogVehicleActorSpawner, Log, All);

namespace
{
	// Real, evidence-backed mechanism for pedestrian pose variety (see
	// FScenarioAssetData::MaterialScalarOverrides' own comment): City
	// Sample's crowd VAT materials bake pose into a "Frame" scalar
	// parameter of a shared material layer (confirmed live by reading
	// the real parameter source via UE Python's
	// MaterialEditingLibrary.get_scalar_parameter_source -- it resolves
	// to /Game/Crowd/VAT/Materials/ML_BoneAnimation, not a per-mesh
	// material), so freezing a specific pose is exactly the same
	// well-known "per-instance MaterialInstanceDynamic scalar override"
	// pattern already used throughout the engine for cheap runtime
	// material variation. A no-op (does nothing, allocates nothing) when
	// Overrides is empty -- every existing caller (vehicles, facade
	// pieces) passes an empty map and is completely unaffected.
	//
	// Iterates every material slot, not just slot 0: a real live query
	// of one crowd FaceMesh found a SEPARATE eye-refractive material
	// instance on its own slot (MI_VAT_EyeRefractive_Inst_L_...) --
	// setting Frame on slot 0 alone would leave the eyes rendering a
	// different, unsynchronized pose than the rest of the face.
	//
	// A live test (2026-09-23) initially found this alone had ZERO
	// visible effect: two pedestrians with different "Frame" overrides
	// rendered pixel-identical. Root-caused via engine C++ headers +
	// live "obj dump" queries (not guessed) to three STATIC SWITCH
	// parameters on the shared /Game/Crowd/VAT/Materials/ML_BoneAnimation
	// material layer -- "Animate" and "UseFourInfluences" -- both
	// defaulting to False in the migrated content, which compiles the
	// whole pose-driving shader branch out entirely regardless of any
	// runtime MID scalar value. Static switches can't be overridden by a
	// MaterialInstanceDynamic at all (they're baked into the shader
	// permutation at the Material Instance Constant level); fixed
	// instead by editing those two expression nodes' own DefaultValue
	// directly on ML_BoneAnimation (a real, project-owned asset, not
	// shared engine content) via UE Python, confirmed live afterward:
	// three pedestrians with different Frame values now render three
	// genuinely distinct walking poses. See KNOWN_GAPS_AND_ISSUES.md for
	// the full investigation.
	//
	// Returns every MID it creates (previously discarded, returned void)
	// so the opt-in live-preview path (FScenarioAssetData::
	// bEnableLivePosePreview, UPedestrianWalkCycleComponent) can keep
	// ticking them after this call returns; every other caller ignores
	// the return value, completely unaffected.
	TArray<UMaterialInstanceDynamic*> ApplyMaterialScalarOverrides(
		UStaticMeshComponent* Component, const TMap<FString, float>& Overrides)
	{
		TArray<UMaterialInstanceDynamic*> CreatedMIDs;
		if (Overrides.Num() == 0 || Component == nullptr)
		{
			return CreatedMIDs;
		}

		const int32 NumMaterials = Component->GetNumMaterials();
		for (int32 ElementIndex = 0; ElementIndex < NumMaterials; ++ElementIndex)
		{
			UMaterialInstanceDynamic* MID = Component->CreateDynamicMaterialInstance(ElementIndex);
			if (MID == nullptr)
			{
				continue;
			}
			for (const TPair<FString, float>& Override : Overrides)
			{
				MID->SetScalarParameterValue(FName(*Override.Key), Override.Value);
			}
			CreatedMIDs.Add(MID);
		}
		return CreatedMIDs;
	}
}

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

	// AssetData.AssetPath points at a real City Sample vehicle's static
	// body-shell mesh (e.g.
	// "/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Frame_vehCar_vehicle02")
	// -- see this file's header comment for why a static mesh, not the
	// skeletal rig City Sample itself uses.
	UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *AssetData.AssetPath);
	if (Mesh == nullptr)
	{
		UE_LOG(
			LogVehicleActorSpawner,
			Warning,
			TEXT("SpawnVehicle: failed to load static mesh %s"),
			*AssetData.AssetPath);
		return nullptr;
	}

#if WITH_EDITOR
	// This project runs under D3D11, where Nanite is unsupported and Nanite
	// meshes fall back to a heavily simplified copy. City Sample's tree
	// meshes lose their thin leaf cards in that copy (every species rendered
	// bare). Turning Nanite off rebuilds the mesh from its full source
	// geometry once per mesh (the change persists for the session).
	if (AssetData.AssetPath.Contains(TEXT("/Kit_Tree_")) && Mesh->NaniteSettings.bEnabled)
	{
		Mesh->NaniteSettings.bEnabled = false;
		Mesh->PostEditChange();
		UE_LOG(LogVehicleActorSpawner, Display, TEXT("SpawnVehicle: disabled Nanite on %s"), *AssetData.AssetPath);
	}
#endif

	FActorSpawnParameters SpawnParams;
	SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

	AActor* SpawnedActor = World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, SpawnParams);
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
	UStaticMeshComponent* MeshComponent = NewObject<UStaticMeshComponent>(SpawnedActor);
	MeshComponent->SetStaticMesh(Mesh);
	MeshComponent->RegisterComponent();
	SpawnedActor->SetRootComponent(MeshComponent);
	MeshComponent->SetSimulatePhysics(false);

	for (int32 SlotIndex = 0; SlotIndex < MeshComponent->GetNumMaterials(); ++SlotIndex)
	{
		UMaterialInterface* Current = MeshComponent->GetMaterial(SlotIndex);
		const FString* Replacement = Current ? AssetData.MaterialReplacements.Find(Current->GetPathName()) : nullptr;
		if (Replacement == nullptr)
		{
			Replacement = AssetData.MaterialReplacements.Find(MeshComponent->GetMaterialSlotNames()[SlotIndex].ToString());
		}
		if (Replacement != nullptr)
		{
			if (UMaterialInterface* Loaded = LoadObject<UMaterialInterface>(nullptr, **Replacement))
			{
				MeshComponent->SetMaterial(SlotIndex, Loaded);
			}
		}
	}

	// Collected across the body AND every part below so the opt-in
	// live-preview component (if this asset requests one) can tick every
	// MID for this pedestrian's whole outfit, not just the body.
	TArray<UMaterialInstanceDynamic*> AllMIDs =
		ApplyMaterialScalarOverrides(MeshComponent, AssetData.MaterialScalarOverrides);

	// SpawnActor's own SpawnTransform argument only takes effect by
	// being applied to a RootComponent, and a bare AActor::StaticClass()
	// has none at spawn time -- spawning at FTransform::Identity above
	// and setting the real position/rotation here (now that a real root
	// component exists) avoids relying on that timing at all. Real bug
	// found via dogfooding when this used to pass AssetData's transform
	// straight to SpawnActor instead: every vehicle spawned stacked at
	// world origin, not its procedurally-computed position.
	SpawnedActor->SetActorLocationAndRotation(AssetData.Position, AssetData.Rotation);
	SpawnedActor->SetActorScale3D(AssetData.Scale);

	// Wheels/doors/glass/interior/steering-wheel -- see this file's
	// header comment. Each one is its own sibling component at the
	// actor's own (already correct) root transform, i.e. zero relative
	// offset -- confirmed correct via a real screenshot, not assumed.
	// An individual part failing to load is logged and skipped, not
	// fatal to the whole vehicle (mirrors the body's own
	// fail-soft behavior above).
	for (const FString& PartPath : AssetData.PartPaths)
	{
		UStaticMesh* PartMesh = LoadObject<UStaticMesh>(nullptr, *PartPath);
		if (PartMesh == nullptr)
		{
			UE_LOG(
				LogVehicleActorSpawner,
				Warning,
				TEXT("SpawnVehicle: failed to load part static mesh %s"),
				*PartPath);
			continue;
		}

		// KeepRelativeTransform, not KeepWorldTransform: a freshly
		// created component's relative transform defaults to identity,
		// and identity-relative-to-the-body is exactly the (confirmed
		// correct) placement every part needs -- KeepWorldTransform
		// would instead preserve the component's current *world*
		// transform (world origin, since it was just created), which
		// would leave every part sitting at (0,0,0) instead of on the
		// vehicle.
		UStaticMeshComponent* PartComponent = NewObject<UStaticMeshComponent>(SpawnedActor);
		PartComponent->SetStaticMesh(PartMesh);
		PartComponent->RegisterComponent();
		PartComponent->AttachToComponent(MeshComponent, FAttachmentTransformRules::KeepRelativeTransform);
		PartComponent->SetSimulatePhysics(false);
		AllMIDs.Append(ApplyMaterialScalarOverrides(PartComponent, AssetData.MaterialScalarOverrides));
	}

	// Opt-in ONLY -- see FScenarioAssetData::bEnableLivePosePreview's own
	// comment for why this is never set by the real dataset-generation
	// pipeline. "Frame" presence is the existing, already-reliable signal
	// that this asset is an animatable pedestrian (vehicles/facade pieces
	// never carry it), used here instead of a second new per-asset flag.
	if (AssetData.bEnableLivePosePreview && AssetData.MaterialScalarOverrides.Contains(TEXT("Frame")))
	{
		// Real, evidence-backed clip boundary (see city_sample_assets.py's
		// PEDESTRIAN_WALKING_CLIP/PEDESTRIAN_STANDING_CLIP): whichever
		// clip this pedestrian's OWN assigned Frame value already belongs
		// to is the clip its live-preview motion must stay confined to,
		// recovered from data already present rather than a new field.
		const float AssignedFrame = AssetData.MaterialScalarOverrides[TEXT("Frame")];
		const float ClipStartFrame = AssignedFrame < 320.0f ? 0.0f : 320.0f;
		const float ClipEndFrame = AssignedFrame < 320.0f ? 319.0f : 429.0f;

		// Initialize() BEFORE RegisterComponent(): RegisterComponent()
		// synchronously calls this component's own BeginPlay() when (as
		// here) the owning actor has already begun play (confirmed via
		// AActor::HandleRegisterComponentWithWorld in engine source) --
		// calling Initialize() first ensures BeginPlay's own random
		// phase-offset roll uses the real clip bounds, not this class's
		// default (0,0) construction-time values.
		UPedestrianWalkCycleComponent* WalkCycleComponent =
			NewObject<UPedestrianWalkCycleComponent>(SpawnedActor);
		WalkCycleComponent->Initialize(AllMIDs, ClipStartFrame, ClipEndFrame);
		WalkCycleComponent->RegisterComponent();
	}

	return SpawnedActor;
}
