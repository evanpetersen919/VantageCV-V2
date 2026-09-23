// Guarantees a pedestrian's real dataset-capture pose never drifts,
// regardless of any internal auto-advance the VAT material itself may
// perform. Real bug this exists to work around: ML_BoneAnimation's
// GetFrame material function visibly keeps advancing a pedestrian's
// pose over real wall-clock time even after its "Playrate"/"Looping"
// per-instance custom primitive data inputs are forced to 0 -- direct
// engine node-graph inspection (obj dump) confirmed the wiring should
// stop it, but live testing (with the game window actually focused --
// Unreal throttles game time while unfocused, which produced a long
// run of false "it's frozen" readings earlier) proved the pose still
// visibly changes. Rather than keep reverse-engineering a closed,
// third-party content graph with real live-editing crash risk, this
// component wins by brute force: it re-asserts the pedestrian's own
// assigned "Frame" value on every tick, after whatever the material's
// own internal logic computes, so the render always shows the correct
// static pose regardless of what that internal logic is doing.
//
// This is NOT the live-preview component (PedestrianWalkCycleComponent,
// still opt-in/QA-only) -- this one exists on EVERY pedestrian in the
// real dataset-capture path, since without it that path is not actually
// reproducible (a captured frame must be a deterministic function of
// the scenario seed, not of wall-clock time since spawn).

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "PedestrianPoseFreezeComponent.generated.h"

class UMaterialInstanceDynamic;

UCLASS(ClassGroup = (SyntheticDataGen), meta = (BlueprintSpawnableComponent))
class SYNTHETICDATAGEN_API UPedestrianPoseFreezeComponent final : public UActorComponent
{
	GENERATED_BODY()

public:
	UPedestrianPoseFreezeComponent();

	// Call once, any time before or after RegisterComponent() -- unlike
	// UPedestrianWalkCycleComponent this class has no BeginPlay-time
	// state that depends on call order.
	void Initialize(const TArray<UMaterialInstanceDynamic*>& InMIDsToAnimate, float InFrozenFrame);

protected:
	virtual void TickComponent(
		float DeltaTime,
		ELevelTick TickType,
		FActorComponentTickFunction* ThisTickFunction) override;

private:
	UPROPERTY()
	TArray<TObjectPtr<UMaterialInstanceDynamic>> MIDsToFreeze;

	float FrozenFrame = 0.0f;
};
