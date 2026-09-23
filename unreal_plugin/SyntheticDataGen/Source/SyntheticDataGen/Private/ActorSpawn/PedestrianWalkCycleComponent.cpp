#include "ActorSpawn/PedestrianWalkCycleComponent.h"
#include "Materials/MaterialInstanceDynamic.h"

UPedestrianWalkCycleComponent::UPedestrianWalkCycleComponent()
{
	// The one component in this whole plugin that ticks at all -- every
	// other spawned actor/component is a frozen frame by design (see
	// VehicleActorSpawner.h's own header comment). This is deliberately
	// scoped to the explicitly opt-in live-preview path only; see this
	// class's own header comment for why.
	PrimaryComponentTick.bCanEverTick = true;
}

void UPedestrianWalkCycleComponent::Initialize(
	const TArray<UMaterialInstanceDynamic*>& InMIDsToAnimate, float InClipStartFrame, float InClipEndFrame)
{
	MIDsToAnimate.Reset(InMIDsToAnimate.Num());
	for (UMaterialInstanceDynamic* MID : InMIDsToAnimate)
	{
		MIDsToAnimate.Add(MID);
	}
	ClipStartFrame = InClipStartFrame;
	ClipEndFrame = InClipEndFrame;
}

void UPedestrianWalkCycleComponent::BeginPlay()
{
	Super::BeginPlay();

	// Real per-instance phase desync -- see this class's own header
	// comment for why FMath::RandRange (not the deterministic scenario
	// RNG) is the right choice here.
	const float ClipLength = ClipEndFrame - ClipStartFrame + 1.0f;
	ElapsedFrames = ClipLength > 0.0f ? FMath::RandRange(0.0f, ClipLength) : 0.0f;
}

void UPedestrianWalkCycleComponent::TickComponent(
	float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	const float ClipLength = ClipEndFrame - ClipStartFrame + 1.0f;
	if (ClipLength <= 0.0f || MIDsToAnimate.Num() == 0)
	{
		return;
	}

	ElapsedFrames = FMath::Fmod(ElapsedFrames + DeltaTime * SampleRateFps, ClipLength);
	const float CurrentFrame = ClipStartFrame + ElapsedFrames;

	for (UMaterialInstanceDynamic* MID : MIDsToAnimate)
	{
		if (MID != nullptr)
		{
			MID->SetScalarParameterValue(TEXT("Frame"), CurrentFrame);
		}
	}
}
