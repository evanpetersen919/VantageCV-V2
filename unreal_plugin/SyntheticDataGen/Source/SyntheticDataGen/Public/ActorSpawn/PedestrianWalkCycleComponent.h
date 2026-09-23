// Real, live-preview-ONLY continuous per-instance walk-cycle animation
// -- see FScenarioAssetData::bEnableLivePosePreview's own comment
// (VehicleActorSpawner.h) for why this is deliberately opt-in and never
// used by the real dataset-generation pipeline (reproducibility: a
// scenario's captured pose must be a deterministic function of its
// seed, not of wall-clock elapsed time since actor spawn).
//
// Advances a per-instance "Frame" material scalar parameter over real
// elapsed wall-clock time, confined to whichever real baked clip range
// this pedestrian was assigned at spawn (0-319 walking, or 320-429
// standing -- see city_sample_assets.py's PEDESTRIAN_WALKING_CLIP/
// PEDESTRIAN_STANDING_CLIP for the live evidence these are two real,
// distinct, non-overlapping baked poses, not phase variants of the
// same one), so a pedestrian's live-preview motion never crosses into
// the other activity's frame range. Starts at a random per-instance
// phase (FMath::RandRange, not the deterministic scenario RNG -- this
// component only ever exists on the explicitly opt-in live-preview
// path, where per-instance non-determinism is correct and expected,
// exactly like any other live game) so multiple pedestrians are never
// synchronized.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "PedestrianWalkCycleComponent.generated.h"

class UMaterialInstanceDynamic;

UCLASS(ClassGroup = (SyntheticDataGen), meta = (BlueprintSpawnableComponent))
class SYNTHETICDATAGEN_API UPedestrianWalkCycleComponent final : public UActorComponent
{
	GENERATED_BODY()

public:
	UPedestrianWalkCycleComponent();

	// Real, evidence-backed baked frame rate -- see city_sample_assets.
	// py's PEDESTRIAN_ANIM_SAMPLE_RATE_FPS (queried directly from every
	// real pedestrian asset's own AnimToTextureDataAsset, 123/123
	// checked, zero exceptions). Mirrored here, not re-derived.
	static constexpr float SampleRateFps = 30.0f;

	/**
	 * Configures which MIDs to animate and which real baked clip range
	 * to loop within. Must be called once, immediately after this
	 * component is registered and before it starts ticking --
	 * VehicleActorSpawner::SpawnVehicle does this right after creating
	 * the component.
	 *
	 * @param InMIDsToAnimate  Every material instance dynamic created for
	 *        this pedestrian's body + parts (ApplyMaterialScalarOverrides'
	 *        return value) -- all of them get the same Frame value each
	 *        tick, keeping the whole outfit visually synchronized.
	 * @param InClipStartFrame  Inclusive first frame of the real baked
	 *        clip this pedestrian was assigned (0 for walking, 320 for
	 *        standing).
	 * @param InClipEndFrame  Inclusive last frame of that same clip (319
	 *        or 429).
	 */
	void Initialize(
		const TArray<UMaterialInstanceDynamic*>& InMIDsToAnimate, float InClipStartFrame, float InClipEndFrame);

protected:
	virtual void BeginPlay() override;
	virtual void TickComponent(
		float DeltaTime,
		ELevelTick TickType,
		FActorComponentTickFunction* ThisTickFunction) override;

private:
	UPROPERTY()
	TArray<TObjectPtr<UMaterialInstanceDynamic>> MIDsToAnimate;

	float ClipStartFrame = 0.0f;
	float ClipEndFrame = 0.0f;

	// Real elapsed position WITHIN the clip (0 = ClipStartFrame), so the
	// wrap-around math in TickComponent never depends on ClipStartFrame
	// itself -- keeps the modulo correct regardless of which real clip
	// (walking or standing) this instance was assigned.
	float ElapsedFrames = 0.0f;
};
