// UNVERIFIED: never compiled against UE5.4 (no local install). See
// KNOWN_GAPS_AND_ISSUES.md.
//
// UE5-side counterpart to src/ue5/backend.py: receives the JSON payload
// that backend.py's UE5Backend.load_scenario() sends over the
// LoadProceduralScenario JSON-RPC method, and is where per-mesh
// UScenarioMeshBuilder::BuildMeshSection calls (see
// ProceduralMesh/ScenarioMeshBuilder.h) would be dispatched from.
// Traffic controller initialization and streaming/culling (MASTER_PROMPT
// Section 3.5's remaining "Procedural Meshes"/"Traffic Network" bullets
// for this phase) are not implemented even at the skeleton level --
// there's no traffic-controller actor class yet to initialize, and
// streaming/culling requires an actual UE5 project/level to profile
// against, neither of which exist in this environment.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ProceduralScenarioLoader.generated.h"

/**
 * Parses and loads one generated scenario (as JSON from the Python-side
 * orchestration layer) into the current UE5 level.
 */
UCLASS()
class SYNTHETICDATAGEN_API AProceduralScenarioLoader final : public AActor
{
	GENERATED_BODY()

public:
	AProceduralScenarioLoader();

	/**
	 * Parses ScenarioJson (the payload UE5Backend.load_scenario() sends)
	 * and spawns/builds every mesh section and traffic control point it
	 * describes.
	 *
	 * @param ScenarioJson  UTF-8 JSON matching the {nodes, edges, lanes,
	 *        buildings, meshes, traffic} shape produced by the Python
	 *        orchestration layer (Phase 6, not yet implemented -- see
	 *        KNOWN_GAPS_AND_ISSUES.md; this function's JSON schema is
	 *        therefore provisional).
	 * @return true if the scenario was parsed and loaded without error.
	 */
	UFUNCTION(BlueprintCallable, Category = "SyntheticDataGen")
	bool LoadProceduralScenario(const FString& ScenarioJson);
};
