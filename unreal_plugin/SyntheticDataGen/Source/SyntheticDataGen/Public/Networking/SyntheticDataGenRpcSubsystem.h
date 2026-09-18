// WebSocket JSON-RPC 2.0 server bridge for src/ue5/backend.py's
// UE5Backend client -- the piece that previously didn't exist at all
// (see KNOWN_GAPS_AND_ISSUES.md: backend.py has only ever been tested
// against a local Python mock server, never a real UE5 listener).
// Compiles against a real UE 5.4.4 editor (verified 2026-09-15), but
// the actual Ping/LoadProceduralScenario round trip against backend.py
// has not yet been exercised -- this is the first attempt, needs a
// real test before being trusted.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Containers/Ticker.h"
#include "WebSocketNetworkingDelegates.h"
#include "SyntheticDataGenRpcSubsystem.generated.h"

class IWebSocketServer;
class INetworkingWebSocket;
class AProceduralScenarioLoader;

/**
 * Hosts a WebSocket JSON-RPC 2.0 server (via the engine's
 * WebSocketNetworking plugin) that src/ue5/backend.py's UE5Backend
 * client talks to. One instance runs per GameInstance (i.e. one per
 * Play-In-Editor session, or one per running packaged instance);
 * starts listening in Initialize(), stops in Deinitialize().
 *
 * Answers "Ping" (no-op, proves the wire protocol works),
 * "LoadProceduralScenario" (dispatches to
 * AProceduralScenarioLoader::LoadProceduralScenario, spawning a loader
 * actor in the current world if none exists yet), "TakeScreenshot"
 * (real visual debugging aid -- see its own comment in the .cpp for why
 * this exists), "DebugMoveCameraTo" (moves the local player's pawn
 * for close-up visual verification, alongside TakeScreenshot), and
 * "GetStaticMeshBounds" (returns a static mesh asset's real
 * world-space origin/extent in centimeters -- needed to compute exact
 * tiling offsets for modular kit assets like building wall segments or
 * sidewalk pieces, since asset dimensions aren't knowable from the
 * Python side any other way).
 */
UCLASS()
class SYNTHETICDATAGEN_API USyntheticDataGenRpcSubsystem final : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	/** Port the RPC server listens on. Matches src/ue5/backend.py's own
	 * docstring example ("ws://localhost:8765"). */
	static constexpr uint32 RpcListenPort = 8765;

	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

private:
	void HandleClientConnected(INetworkingWebSocket* Socket);
	void HandleReceive(INetworkingWebSocket* Socket, void* Data, int32 Size);
	void HandleSocketClosed(INetworkingWebSocket* Socket);
	bool TickServer(float DeltaTime);

	/** Parses one JSON-RPC 2.0 request and returns the JSON-RPC 2.0
	 * response to send back -- always valid JSON, even on error
	 * (malformed requests get a JSON-RPC error response, not a dropped
	 * connection), matching backend.py's parse_response()'s expectation
	 * of a well-formed {"result": ...} or {"error": {...}} object. */
	FString HandleRpcRequest(const FString& RequestJson);

	/** Finds the first AProceduralScenarioLoader in the current world, or
	 * spawns one if none exists yet. Returns nullptr if there is no
	 * world to spawn into (e.g. called before any world is loaded). */
	AProceduralScenarioLoader* FindOrSpawnLoader();

	// Deliberately a raw pointer, not TUniquePtr<IWebSocketServer>: a
	// UCLASS's own implicit constructor/destructor (including UHT's
	// separately auto-generated FVTableHelper hot-reload constructor)
	// all need TUniquePtr's destructor available wherever they're
	// instantiated, which fails for a type this header only forward-
	// declares. A raw pointer has no such requirement -- ownership is
	// managed manually via `delete Server;` in Deinitialize() (the
	// .cpp, where IWebSocketServer.h is actually included).
	IWebSocketServer* Server = nullptr;
	TArray<INetworkingWebSocket*> Connections;
	FTSTicker::FDelegateHandle TickerHandle;
};
