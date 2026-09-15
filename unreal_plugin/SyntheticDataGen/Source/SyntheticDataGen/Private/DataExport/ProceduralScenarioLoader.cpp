// Compiles cleanly against a real UE 5.4.4 editor (verified
// 2026-09-15 -- see KNOWN_GAPS_AND_ISSUES.md). See
// ProceduralScenarioLoader.h for what's still a stub.

#include "DataExport/ProceduralScenarioLoader.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

AProceduralScenarioLoader::AProceduralScenarioLoader()
{
	PrimaryActorTick.bCanEverTick = false;
}

bool AProceduralScenarioLoader::LoadProceduralScenario(const FString& ScenarioJson)
{
	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ScenarioJson);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		return false;
	}

	// Mesh section instantiation (dispatching to
	// UScenarioMeshBuilder::BuildMeshSection per entry in Root->"meshes"),
	// traffic controller initialization, and streaming/culling setup all
	// belong here once there's an actual UE5 project to build and test
	// them against -- see file header and KNOWN_GAPS_AND_ISSUES.md. This
	// stub only validates that the payload is well-formed JSON.

	return true;
}
