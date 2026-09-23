#include "ActorSpawn/PedestrianPoseFreezeComponent.h"
#include "Materials/MaterialInstanceDynamic.h"

UPedestrianPoseFreezeComponent::UPedestrianPoseFreezeComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
}

void UPedestrianPoseFreezeComponent::Initialize(
	const TArray<UMaterialInstanceDynamic*>& InMIDsToFreeze, float InFrozenFrame)
{
	MIDsToFreeze.Reset(InMIDsToFreeze.Num());
	for (UMaterialInstanceDynamic* MID : InMIDsToFreeze)
	{
		MIDsToFreeze.Add(MID);
	}
	FrozenFrame = InFrozenFrame;
}

void UPedestrianPoseFreezeComponent::TickComponent(
	float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	for (UMaterialInstanceDynamic* MID : MIDsToFreeze)
	{
		if (MID != nullptr)
		{
			MID->SetScalarParameterValue(TEXT("Frame"), FrozenFrame);
		}
	}
}
