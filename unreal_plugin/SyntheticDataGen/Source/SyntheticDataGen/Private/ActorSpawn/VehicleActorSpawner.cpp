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
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
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
	}

	return SpawnedActor;
}
