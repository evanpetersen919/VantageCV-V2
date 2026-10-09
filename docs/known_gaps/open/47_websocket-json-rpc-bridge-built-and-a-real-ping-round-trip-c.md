### [RESOLVED] WebSocket JSON-RPC bridge built and a real Ping round trip confirmed against a live UE5 editor
The piece that made `src/ue5/backend.py` untestable against anything
real: nothing on the UE5 side ever hosted a WebSocket JSON-RPC server
to receive `UE5Backend`'s `Ping`/`LoadProceduralScenario` calls, so
every test of that module was against a local Python mock, never a
real engine. Built `USyntheticDataGenRpcSubsystem`
(`unreal_plugin/.../Networking/SyntheticDataGenRpcSubsystem.{h,cpp}`),
a `UGameInstanceSubsystem` that hosts a server via the engine's own
`WebSocketNetworking` plugin (`Engine/Plugins/Experimental/
WebSocketNetworking`) and answers `Ping` and `LoadProceduralScenario`
(dispatching to `AProceduralScenarioLoader`, spawning one into the
current world if none exists). Starts listening automatically once a
GameInstance exists (i.e. on Play-In-Editor start, not merely from the
editor being open) on port 8765, matching `backend.py`'s own docstring
example URI.

Real, non-mocked verification: `UE5Backend("ws://localhost:8765").ping()`
run from this repo's own Python against the live PIE session returned
successfully, repeatedly (~2.1s each across 4 calls -- see the
`[RISK]` latency entry above for what that number means and doesn't).

Getting a clean compile took three real, wrong-then-fixed attempts
worth recording since they're non-obvious and would trip up anyone
else adding a `TUniquePtr<ForwardDeclaredType>` member to a `UCLASS`:
1. First attempt: `TUniquePtr<IWebSocketServer> Server` member, no
   custom constructor/destructor. Real error: `C4150: deletion of
   pointer to incomplete type`, because the class's implicit
   destructor (generated inline in the header, where
   `IWebSocketServer` is only forward-declared) needs the complete
   type.
2. Second attempt: declared the constructor and destructor
   out-of-line (defined in the .cpp, where the full type is included)
   -- standard C++ Pimpl practice. Still failed with the *same* error,
   now traced (via the compiler's own template-instantiation-context
   notes) to a *different*, UHT-generated constructor:
   `DEFINE_VTABLE_PTR_HELPER_CTOR`, a hot-reload-support constructor
   UnrealHeaderTool auto-emits into every `UCLASS`'s `.gen.cpp`,
   independently of any constructor the class itself declares.
3. Third attempt: tried declaring `DECLARE_VTABLE_PTR_HELPER_CTOR`
   manually to suppress UHT's auto-generation and supply our own
   out-of-line definition -- turned out `GENERATED_BODY()` *already*
   declares this constructor unconditionally (confirmed by reading the
   actual generated `.generated.h`), so this was a duplicate
   declaration (`C2535`), not a fix.
4. **What actually worked**: switched `Server` from `TUniquePtr<IWebSocketServer>`
   to a plain `IWebSocketServer*`, with manual `delete` in
   `Deinitialize()`. A raw pointer has no destructor/constructor of
   its own to instantiate, so none of the above machinery (implicit
   destructors, UHT's `FVTableHelper` ctor) ever needs the complete
   type at all -- sidesteps the entire category of problem rather than
   fighting it. `TPimplPtr` (Epic's own purpose-built Pimpl smart
   pointer) was considered and rejected: it requires constructing the
   pointee via its own `MakePimpl` factory, but `IWebSocketServer`
   instances come from `IWebSocketNetworkingModule::CreateServer()`
   instead, which `TPimplPtr` can't take ownership of.

**Still open**: `LoadProceduralScenario`'s own dispatch through this
bridge (not just `Ping`) hasn't been tested against a real scenario
payload yet -- see the "[DEFERRED] LoadProceduralScenario" entry above,
which is itself still a stub past JSON validation.

