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
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "EngineUtils.h"

DEFINE_LOG_CATEGORY_STATIC(LogSyntheticDataGenRpc, Log, All);

namespace
{
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
