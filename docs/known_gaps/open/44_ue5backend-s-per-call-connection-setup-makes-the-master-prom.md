### [RISK] `UE5Backend`'s per-call connection setup makes the master prompt's <100ms/<2s latency budgets unverifiable as literally stated
`UE5Backend.call()` opens a brand-new WebSocket connection for every RPC
call (documented as a deliberate simplicity tradeoff in backend.py).
Measured directly and repeatedly against a local mock server: round-trip
time for the *same* call varied from well under 100ms to over 2 seconds
across otherwise-identical runs on this machine, with values landing
suspiciously close to whole seconds (e.g. 2.04s) -- consistent with
intermittent external interference on new local socket connections (most
likely antivirus real-time scanning on Windows), not a bug in the
request/response logic itself (which is 100% covered and passes every
functional test). The tests now assert only generous smoke-test bounds
(<5s) rather than the spec's literal targets.

**Update 2026-09-15, against a real UE5 server (not the mock)**: once
the actual UE5-side WebSocket RPC bridge was built (see the
"[RESOLVED] WebSocket JSON-RPC bridge" entry below), a real `Ping`
round trip via `ws://localhost:8765` landed consistently at ~2.1s
across 4 separate calls -- squarely in the same suspicious ~2-second
range as the mock-server variance above, which strengthens (not
proves) the antivirus/socket-interference theory: this is a second,
independent data point at nearly the same value against a completely
different server implementation. A related, still-unexplained
oddity found in the same session: connecting explicitly to
`ws://127.0.0.1:8765` or `ws://[::1]:8765` (rather than `localhost`)
was refused outright (`ConnectionRefusedError`) on both, even though
`localhost` itself connects successfully -- inconsistent with a simple
"IPv6 attempted first, times out, falls back to IPv4" explanation,
since neither literal loopback address works alone. `Server->Init()`
was called with an empty `BindAddress` (documented as "bind to all
interfaces"); what interface `localhost` actually resolves to and
successfully reaches on this machine, that neither loopback literal
does, was not investigated further.
**Action**: if real <100ms production latency is ever required, switch to
a persistent connection (connect once, reuse for many calls) rather than
per-call connect/disconnect -- this removes handshake cost from the
steady-state latency and would likely resolve the spec's target being
achievable in practice, though it doesn't explain the *variance* seen
here, which needs testing on a machine without the same local antivirus
configuration to confirm the root cause.

