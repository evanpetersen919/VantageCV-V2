// See SyntheticDataGenRpcSubsystem.h for verification status.

#include "Networking/SyntheticDataGenRpcSubsystem.h"
#include "DataExport/ProceduralScenarioLoader.h"

#include "IWebSocketNetworkingModule.h"
#include "IWebSocketServer.h"
#include "INetworkingWebSocket.h"
#include "Modules/ModuleManager.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Components/PrimitiveComponent.h"
#include "Engine/GameInstance.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshSocket.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetMathLibrary.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"

DEFINE_LOG_CATEGORY_STATIC(LogSyntheticDataGenRpc, Log, All);

namespace
{
	// Real bug found via dogfooding (2026-09-17 -- see
	// KNOWN_GAPS_AND_ISSUES.md): SetActorHiddenInGame(true) alone does
	// NOT stop a character Pawn's mesh from casting a shadow --
	// third-person/first-person character meshes commonly have
	// bCastHiddenShadow = true set explicitly (so a first-person view
	// that hides its own body mesh still shows that body's shadow in
	// the world), which is exactly this project's default Pawn. Confirmed
	// via a real screenshot: hiding the pawn alone left its shadow
	// unchanged on a vehicle positioned underneath it. Forcing
	// SetCastShadow(false) on every primitive component is what
	// actually stops it.
	void HideActorAndItsShadow(AActor* Actor)
	{
		if (Actor == nullptr)
		{
			return;
		}
		Actor->SetActorHiddenInGame(true);

		TArray<UPrimitiveComponent*> PrimitiveComponents;
		Actor->GetComponents<UPrimitiveComponent>(PrimitiveComponents);
		for (UPrimitiveComponent* PrimitiveComponent : PrimitiveComponents)
		{
			if (PrimitiveComponent != nullptr)
			{
				PrimitiveComponent->SetCastShadow(false);
			}
		}
	}

	FString SerializeResponse(const TSharedRef<FJsonObject>& Response)
	{
		FString Out;
		const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Out);
		FJsonSerializer::Serialize(Response, Writer);
		return Out;
	}

	TSharedRef<FJsonValue> IdOrNull(const TSharedPtr<FJsonValue>& RequestId)
	{
		return RequestId.IsValid() ? RequestId.ToSharedRef() : MakeShared<FJsonValueNull>();
	}

	FString BuildErrorResponse(const TSharedPtr<FJsonValue>& RequestId, int32 Code, const FString& Message)
	{
		const TSharedRef<FJsonObject> Response = MakeShared<FJsonObject>();
		Response->SetStringField(TEXT("jsonrpc"), TEXT("2.0"));

		const TSharedRef<FJsonObject> Error = MakeShared<FJsonObject>();
		Error->SetNumberField(TEXT("code"), Code);
		Error->SetStringField(TEXT("message"), Message);
		Response->SetObjectField(TEXT("error"), Error);
		Response->SetField(TEXT("id"), IdOrNull(RequestId));

		return SerializeResponse(Response);
	}

	FString BuildResultResponse(const TSharedPtr<FJsonValue>& RequestId, const TSharedRef<FJsonValue>& Result)
	{
		const TSharedRef<FJsonObject> Response = MakeShared<FJsonObject>();
		Response->SetStringField(TEXT("jsonrpc"), TEXT("2.0"));
		Response->SetField(TEXT("result"), Result);
		Response->SetField(TEXT("id"), IdOrNull(RequestId));

		return SerializeResponse(Response);
	}
} // namespace

void USyntheticDataGenRpcSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	IWebSocketNetworkingModule& Module =
		FModuleManager::LoadModuleChecked<IWebSocketNetworkingModule>("WebSocketNetworking");
	// .Release(): CreateServer() returns a TUniquePtr, but Server is a raw
	// pointer here (see the header's comment on why) -- ownership
	// transfers to this raw pointer, freed manually in Deinitialize().
	Server = Module.CreateServer().Release();
	if (Server == nullptr)
	{
		UE_LOG(LogSyntheticDataGenRpc, Error, TEXT("Failed to create WebSocket RPC server"));
		return;
	}

	FWebSocketClientConnectedCallBack ConnectedCallback;
	ConnectedCallback.BindUObject(this, &USyntheticDataGenRpcSubsystem::HandleClientConnected);

	if (!Server->Init(RpcListenPort, ConnectedCallback))
	{
		UE_LOG(LogSyntheticDataGenRpc, Error, TEXT("WebSocket RPC server failed to bind port %d"), RpcListenPort);
		delete Server;
		Server = nullptr;
		return;
	}

	UE_LOG(LogSyntheticDataGenRpc, Display, TEXT("WebSocket RPC server listening on port %d"), RpcListenPort);

	TickerHandle = FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateUObject(this, &USyntheticDataGenRpcSubsystem::TickServer), 0.0f);
}

void USyntheticDataGenRpcSubsystem::Deinitialize()
{
	if (TickerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(TickerHandle);
		TickerHandle.Reset();
	}
	Connections.Reset();

	delete Server;
	Server = nullptr;

	Super::Deinitialize();
}

bool USyntheticDataGenRpcSubsystem::TickServer(float /*DeltaTime*/)
{
	if (Server != nullptr)
	{
		Server->Tick();
	}
	return true; // keep ticking every frame until Deinitialize removes this ticker
}

void USyntheticDataGenRpcSubsystem::HandleClientConnected(INetworkingWebSocket* Socket)
{
	if (Socket == nullptr)
	{
		return;
	}

	Connections.Add(Socket);

	FWebSocketPacketReceivedCallBack ReceiveCallback;
	ReceiveCallback.BindLambda(
		[this, Socket](void* Data, int32 Size)
		{
			HandleReceive(Socket, Data, Size);
		});
	Socket->SetReceiveCallBack(ReceiveCallback);

	FWebSocketInfoCallBack ClosedCallback;
	ClosedCallback.BindLambda(
		[this, Socket]()
		{
			HandleSocketClosed(Socket);
		});
	Socket->SetSocketClosedCallBack(ClosedCallback);
}

void USyntheticDataGenRpcSubsystem::HandleSocketClosed(INetworkingWebSocket* Socket)
{
	// The WebSocketNetworking module owns Socket's lifetime; this only
	// drops our own tracking reference, never deletes it.
	Connections.RemoveSingleSwap(Socket);
}

void USyntheticDataGenRpcSubsystem::HandleReceive(INetworkingWebSocket* Socket, void* Data, int32 Size)
{
	if (Socket == nullptr || Data == nullptr || Size <= 0)
	{
		return;
	}

	// Python's `websockets` library sends JSON-RPC requests as UTF-8 text
	// frames. The engine's own LWS_CALLBACK_RECEIVE handling (see
	// WebSocketServer.cpp) routes non-binary frames to this callback with
	// the raw frame bytes unmodified -- no length-prefix framing to
	// strip here (that only applies to the binary/OnRawRecieve path,
	// which this bridge never sends over -- see the Send() call below).
	const FUTF8ToTCHAR Converter(static_cast<const ANSICHAR*>(Data), Size);
	const FString RequestJson = FString::ConstructFromPtrSize(Converter.Get(), Converter.Length());

	const FString ResponseJson = HandleRpcRequest(RequestJson);

	const FTCHARToUTF8 Utf8Response(*ResponseJson);
	// bPrependSize=false: this bridge is a plain JSON-RPC-over-WebSocket
	// transport (one complete JSON message per frame), not this module's
	// own length-prefixed game-networking protocol. The default
	// bPrependSize=true bakes a 4-byte size header into the frame
	// content, which a plain WebSocket client (Python's `websockets`)
	// would receive as 4 garbage bytes before the JSON and fail to parse.
	Socket->Send(
		reinterpret_cast<const uint8*>(Utf8Response.Get()), Utf8Response.Length(), /*bPrependSize=*/false);
}

FString USyntheticDataGenRpcSubsystem::HandleRpcRequest(const FString& RequestJson)
{
	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(RequestJson);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		return BuildErrorResponse(nullptr, -32700, TEXT("Parse error"));
	}

	const TSharedPtr<FJsonValue> RequestId = Root->TryGetField(TEXT("id"));

	FString Method;
	if (!Root->TryGetStringField(TEXT("method"), Method))
	{
		return BuildErrorResponse(RequestId, -32600, TEXT("Invalid request: missing 'method'"));
	}

	if (Method == TEXT("Ping"))
	{
		return BuildResultResponse(RequestId, MakeShared<FJsonValueNull>());
	}

	if (Method == TEXT("LoadProceduralScenario"))
	{
		const TSharedPtr<FJsonObject>* Params = nullptr;
		if (!Root->TryGetObjectField(TEXT("params"), Params))
		{
			return BuildErrorResponse(RequestId, -32602, TEXT("Invalid params: expected an object"));
		}

		const TSharedPtr<FJsonObject>* ScenarioObject = nullptr;
		if (!(*Params)->TryGetObjectField(TEXT("scenario"), ScenarioObject))
		{
			return BuildErrorResponse(RequestId, -32602, TEXT("Invalid params: missing 'scenario' object"));
		}

		// AProceduralScenarioLoader::LoadProceduralScenario's own
		// interface takes ScenarioJson as a string (it does its own
		// parsing), so re-serialize the already-parsed "scenario"
		// sub-object back into JSON text for it.
		FString ScenarioJson;
		const TSharedRef<TJsonWriter<>> ScenarioWriter = TJsonWriterFactory<>::Create(&ScenarioJson);
		FJsonSerializer::Serialize(ScenarioObject->ToSharedRef(), ScenarioWriter);

		AProceduralScenarioLoader* Loader = FindOrSpawnLoader();
		if (Loader == nullptr)
		{
			return BuildErrorResponse(RequestId, -32000, TEXT("No world available to load the scenario into"));
		}

		if (!Loader->LoadProceduralScenario(ScenarioJson))
		{
			return BuildErrorResponse(RequestId, -32000, TEXT("LoadProceduralScenario rejected the payload"));
		}

		return BuildResultResponse(RequestId, MakeShared<FJsonValueBoolean>(true));
	}

	if (Method == TEXT("TakeScreenshot"))
	{
		// Real debugging capability, kept permanently (not removed
		// after the investigation that motivated it -- see
		// KNOWN_GAPS_AND_ISSUES.md): diagnostic logs alone proved
		// insufficient to root-cause vehicles being reported invisible
		// despite correct positions/valid mesh bounds -- only an actual
		// screenshot revealed the real problem (the camera looking at
		// the wrong place, then a skeletal-mesh rendering issue).
		// Useful for the same kind of visual verification in later
		// phases. FScreenshotRequest is the direct engine API the
		// "Shot"/"HighResShot" console commands themselves call --
		// calling it directly here (an earlier attempt routed through
		// GEngine->Exec("HighResShot ..."), which produced no file and
		// no log trace at all, so it never reached the actual capture
		// code) guarantees the exact same capture path without
		// depending on console-command dispatch. The request is
		// fulfilled by the next real frame the running game renders
		// (this is a live, still-rendering session, not headless), so
		// no explicit "wait a frame" is needed here.
		UGameInstance* Instance = GetGameInstance();
		UWorld* World = Instance != nullptr ? Instance->GetWorld() : nullptr;
		if (World == nullptr)
		{
			return BuildErrorResponse(RequestId, -32000, TEXT("No world available to take a screenshot"));
		}

		const FString Filename = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("rpc_debug_screenshot.png"));
		FScreenshotRequest::RequestScreenshot(Filename, /*bInShowUI=*/false, /*bAddFilenameSuffix=*/false);
		return BuildResultResponse(RequestId, MakeShared<FJsonValueString>(Filename));
	}

	if (Method == TEXT("DebugMoveCameraTo"))
	{
		// Real debugging capability, kept permanently alongside
		// TakeScreenshot (see that method's own comment above): the
		// overview camera frames the whole scenario, which can leave
		// individual small objects (a single vehicle) too small in
		// frame to conclusively confirm visually. Takes an explicit
		// camera position and look-at target (both full x/y/z in
		// Unreal units) so both can be iterated from the Python side
		// without rebuilding the plugin each time.
		const TSharedPtr<FJsonObject>* Params = nullptr;
		double CamX = 0.0;
		double CamY = 0.0;
		double CamZ = 0.0;
		double TargetX = 0.0;
		double TargetY = 0.0;
		double TargetZ = 0.0;
		if (!Root->TryGetObjectField(TEXT("params"), Params)
			|| !(*Params)->TryGetNumberField(TEXT("cam_x"), CamX)
			|| !(*Params)->TryGetNumberField(TEXT("cam_y"), CamY)
			|| !(*Params)->TryGetNumberField(TEXT("cam_z"), CamZ)
			|| !(*Params)->TryGetNumberField(TEXT("target_x"), TargetX)
			|| !(*Params)->TryGetNumberField(TEXT("target_y"), TargetY)
			|| !(*Params)->TryGetNumberField(TEXT("target_z"), TargetZ))
		{
			return BuildErrorResponse(
				RequestId, -32602, TEXT("Invalid params: expected numeric cam_x/y/z and target_x/y/z"));
		}

		UGameInstance* Instance = GetGameInstance();
		UWorld* World = Instance != nullptr ? Instance->GetWorld() : nullptr;
		APlayerController* PlayerController = World != nullptr ? UGameplayStatics::GetPlayerController(World, 0) : nullptr;
		APawn* Pawn = PlayerController != nullptr ? PlayerController->GetPawn() : nullptr;
		if (Pawn == nullptr)
		{
			return BuildErrorResponse(RequestId, -32000, TEXT("No pawn available to move"));
		}

		const FVector CameraPosition(CamX, CamY, CamZ);
		const FVector Target(TargetX, TargetY, TargetZ);
		const FRotator LookRotation = UKismetMathLibrary::FindLookAtRotation(CameraPosition, Target);
		Pawn->SetActorLocationAndRotation(CameraPosition, LookRotation);
		PlayerController->SetControlRotation(LookRotation);

		// Real bug found via dogfooding (2026-09-17): this repurposes the
		// level's actual gameplay Pawn (a visible character/spectator
		// mesh) as a flying camera. That mesh still casts a real-time
		// dynamic shadow from the sun even though it's never in frame
		// (the screenshot is taken from its own first-person view) --
		// close/overhead debug positions routinely land that shadow
		// directly on the vehicle being inspected, producing a jagged
		// dark patch on its roof/body that looks exactly like a broken
		// paint texture but is actually just the pawn's own silhouette.
		// See HideActorAndItsShadow's own comment for why hiding alone
		// isn't enough.
		HideActorAndItsShadow(Pawn);

		return BuildResultResponse(RequestId, MakeShared<FJsonValueBoolean>(true));
	}

	if (Method == TEXT("GetStaticMeshBounds"))
	{
		// Real, reusable debugging capability (kept permanently alongside
		// TakeScreenshot/DebugMoveCameraTo -- same rationale): tiling
		// modular kit assets (building wall/corner segments, sidewalk/curb
		// pieces, props) against each other requires their real
		// world-space size and pivot offset, which is not knowable from
		// the Python side at all (no editor access, asset dimensions
		// aren't exported anywhere) -- guessing at spacing produces
		// gapped or overlapping tiling. Returns the same
		// origin/box-extent/sphere-radius a UE5 editor's own "Bounds"
		// display shows, in centimeters (Unreal's native unit), so the
		// Python side can compute exact tiling offsets.
		const TSharedPtr<FJsonObject>* Params = nullptr;
		FString AssetPath;
		if (!Root->TryGetObjectField(TEXT("params"), Params) || !(*Params)->TryGetStringField(TEXT("asset_path"), AssetPath))
		{
			return BuildErrorResponse(RequestId, -32602, TEXT("Invalid params: expected a string 'asset_path'"));
		}

		UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *AssetPath);
		if (Mesh == nullptr)
		{
			return BuildErrorResponse(
				RequestId, -32000, FString::Printf(TEXT("Failed to load static mesh %s"), *AssetPath));
		}

		const FBoxSphereBounds Bounds = Mesh->GetBounds();
		const TSharedRef<FJsonObject> ResultObject = MakeShared<FJsonObject>();
		ResultObject->SetNumberField(TEXT("origin_x"), Bounds.Origin.X);
		ResultObject->SetNumberField(TEXT("origin_y"), Bounds.Origin.Y);
		ResultObject->SetNumberField(TEXT("origin_z"), Bounds.Origin.Z);
		ResultObject->SetNumberField(TEXT("extent_x"), Bounds.BoxExtent.X);
		ResultObject->SetNumberField(TEXT("extent_y"), Bounds.BoxExtent.Y);
		ResultObject->SetNumberField(TEXT("extent_z"), Bounds.BoxExtent.Z);
		return BuildResultResponse(RequestId, MakeShared<FJsonValueObject>(ResultObject));
	}

	if (Method == TEXT("GetStaticMeshSockets"))
	{
		// Real modular kit assets (this one included) are normally authored
		// with explicit UStaticMeshSocket snap points (e.g. "corner_in"/
		// "corner_out"/"wall_end") marking the EXACT point/rotation another
		// piece's pivot should be placed at to tile flush -- the actual
		// ground truth the kit's own artists used, vs. inferring a tiling
		// offset from the mesh's overall axis-aligned bounding box (which
		// this session found is NOT reliable for an asymmetric L-shaped
		// corner piece: its bbox includes a large non-structural overhang
		// that doesn't represent the true snap point, confirmed via
		// repeated live-screenshot mismatches). If real sockets exist,
		// they are the authoritative source; if none exist, the returned
		// array is simply empty and bbox-based inference remains the
		// fallback.
		const TSharedPtr<FJsonObject>* Params = nullptr;
		FString AssetPath;
		if (!Root->TryGetObjectField(TEXT("params"), Params) || !(*Params)->TryGetStringField(TEXT("asset_path"), AssetPath))
		{
			return BuildErrorResponse(RequestId, -32602, TEXT("Invalid params: expected a string 'asset_path'"));
		}

		UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *AssetPath);
		if (Mesh == nullptr)
		{
			return BuildErrorResponse(
				RequestId, -32000, FString::Printf(TEXT("Failed to load static mesh %s"), *AssetPath));
		}

		TArray<TSharedPtr<FJsonValue>> SocketsArray;
		for (UStaticMeshSocket* Socket : Mesh->Sockets)
		{
			if (Socket == nullptr)
			{
				continue;
			}
			const TSharedRef<FJsonObject> SocketObject = MakeShared<FJsonObject>();
			SocketObject->SetStringField(TEXT("name"), Socket->SocketName.ToString());
			SocketObject->SetNumberField(TEXT("location_x"), Socket->RelativeLocation.X);
			SocketObject->SetNumberField(TEXT("location_y"), Socket->RelativeLocation.Y);
			SocketObject->SetNumberField(TEXT("location_z"), Socket->RelativeLocation.Z);
			SocketObject->SetNumberField(TEXT("rotation_pitch"), Socket->RelativeRotation.Pitch);
			SocketObject->SetNumberField(TEXT("rotation_yaw"), Socket->RelativeRotation.Yaw);
			SocketObject->SetNumberField(TEXT("rotation_roll"), Socket->RelativeRotation.Roll);
			SocketsArray.Add(MakeShared<FJsonValueObject>(SocketObject));
		}
		return BuildResultResponse(RequestId, MakeShared<FJsonValueArray>(SocketsArray));
	}

	if (Method == TEXT("GetStaticMeshFootprintAtHeight"))
	{
		// GetStaticMeshBounds' own overall AABB proved unreliable for
		// tiling this specific kit's wall/corner pieces (see
		// GetStaticMeshSockets' comment above) -- confirmed via repeated
		// live-screenshot mismatches this session that its bbox mixes
		// together whatever is at the TALLEST/WIDEST point of the WHOLE
		// mesh (a roof coping / balcony overhang near the top) with the
		// actual ground-level wall-plane footprint the tiling math
		// actually needs. This reads the REAL raw vertex buffer (LOD0,
		// not a coarse proxy) and returns the min/max X/Y among only the
		// vertices whose local Z falls within [z_min, z_max] -- i.e. the
		// mesh's true footprint at a specific height slice, letting the
		// Python side isolate "ground floor plan" from "roof overhang"
		// instead of guessing which part of an asymmetric AABB is which.
		const TSharedPtr<FJsonObject>* Params = nullptr;
		FString AssetPath;
		double ZMin = 0.0;
		double ZMax = 0.0;
		if (!Root->TryGetObjectField(TEXT("params"), Params) || !(*Params)->TryGetStringField(TEXT("asset_path"), AssetPath)
			|| !(*Params)->TryGetNumberField(TEXT("z_min"), ZMin) || !(*Params)->TryGetNumberField(TEXT("z_max"), ZMax))
		{
			return BuildErrorResponse(RequestId, -32602, TEXT("Invalid params: expected 'asset_path', 'z_min', 'z_max'"));
		}

		UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *AssetPath);
		if (Mesh == nullptr)
		{
			return BuildErrorResponse(
				RequestId, -32000, FString::Printf(TEXT("Failed to load static mesh %s"), *AssetPath));
		}

		const FStaticMeshRenderData* RenderData = Mesh->GetRenderData();
		if (RenderData == nullptr || RenderData->LODResources.Num() == 0)
		{
			return BuildErrorResponse(RequestId, -32000, TEXT("Mesh has no LOD0 render data"));
		}

		const FPositionVertexBuffer& PositionBuffer = RenderData->LODResources[0].VertexBuffers.PositionVertexBuffer;
		const uint32 NumVertices = PositionBuffer.GetNumVertices();

		double MinX = TNumericLimits<double>::Max();
		double MaxX = TNumericLimits<double>::Lowest();
		double MinY = TNumericLimits<double>::Max();
		double MaxY = TNumericLimits<double>::Lowest();
		int32 MatchedVertexCount = 0;
		for (uint32 Index = 0; Index < NumVertices; ++Index)
		{
			const FVector3f Position = PositionBuffer.VertexPosition(Index);
			if (Position.Z < ZMin || Position.Z > ZMax)
			{
				continue;
			}
			++MatchedVertexCount;
			MinX = FMath::Min(MinX, static_cast<double>(Position.X));
			MaxX = FMath::Max(MaxX, static_cast<double>(Position.X));
			MinY = FMath::Min(MinY, static_cast<double>(Position.Y));
			MaxY = FMath::Max(MaxY, static_cast<double>(Position.Y));
		}

		const TSharedRef<FJsonObject> ResultObject = MakeShared<FJsonObject>();
		ResultObject->SetNumberField(TEXT("matched_vertex_count"), MatchedVertexCount);
		ResultObject->SetNumberField(TEXT("total_vertex_count"), static_cast<double>(NumVertices));
		if (MatchedVertexCount > 0)
		{
			ResultObject->SetNumberField(TEXT("min_x"), MinX);
			ResultObject->SetNumberField(TEXT("max_x"), MaxX);
			ResultObject->SetNumberField(TEXT("min_y"), MinY);
			ResultObject->SetNumberField(TEXT("max_y"), MaxY);
		}
		return BuildResultResponse(RequestId, MakeShared<FJsonValueObject>(ResultObject));
	}

	return BuildErrorResponse(RequestId, -32601, FString::Printf(TEXT("Method not found: %s"), *Method));
}

AProceduralScenarioLoader* USyntheticDataGenRpcSubsystem::FindOrSpawnLoader()
{
	UGameInstance* Instance = GetGameInstance();
	UWorld* World = Instance != nullptr ? Instance->GetWorld() : nullptr;
	if (World == nullptr)
	{
		return nullptr;
	}

	for (TActorIterator<AProceduralScenarioLoader> It(World); It; ++It)
	{
		return *It;
	}

	return World->SpawnActor<AProceduralScenarioLoader>();
}
