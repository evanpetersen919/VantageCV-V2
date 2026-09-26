"""JSON-RPC-over-WebSocket client for communicating with a running UE5
instance.

Implements MASTER_PROMPT Section 3.5's "JSON-RPC communication layer
(WebSocket)" bullet, and the two Phase 4 test bullets that are actually
about this communication layer: "UE5 communication latency < 100ms" and
"Mesh loading completes in < 2s".

This module has never been exercised against a real UE5 instance -- no
UE5 install exists in this environment (see KNOWN_GAPS_AND_ISSUES.md,
same limitation as ``unreal_plugin/``). It is instead tested against a
local mock WebSocket server speaking the same JSON-RPC 2.0 protocol (see
``tests/unit/test_backend.py``), which genuinely exercises the request
construction, response parsing, error handling, and timeout logic --
everything on this side of the wire. The 100ms/2s latency budgets are
therefore verified against a local loopback server, not real UE5-side
scenario-loading cost, which cannot be measured without the engine.

Connection model: each call opens, uses, and closes its own WebSocket
connection (stateless per-call), rather than holding a persistent session.
Simpler and sufficient for the request volume this generator produces
(one call per scenario load, not a high-frequency stream); a persistent
connection would be a reasonable optimization once real UE5-side latency
numbers show it's needed.
"""

import asyncio
import itertools
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import websockets
import websockets.exceptions


class UE5RPCError(Exception):
    """Raised when UE5 returns a JSON-RPC error response."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"UE5 RPC error {code}: {message}")


class UE5CommunicationTimeoutError(Exception):
    """Raised when a UE5 RPC call doesn't respond within the configured
    timeout."""


def build_request(method: str, params: Dict[str, Any], request_id: int) -> Dict[str, Any]:
    """Build a JSON-RPC 2.0 request object."""
    return {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": request_id,
    }


def parse_response(raw: Dict[str, Any]) -> Any:
    """Parse a JSON-RPC 2.0 response object, returning its result.

    Raises
    ------
    UE5RPCError
        If the response contains an ``error`` field.
    ValueError
        If the response has neither ``result`` nor ``error`` (malformed).
    """
    if "error" in raw:
        error = raw["error"]
        raise UE5RPCError(code=error.get("code", -1), message=error.get("message", "unknown"))
    if "result" not in raw:
        raise ValueError(f"Malformed JSON-RPC response (no result or error): {raw}")
    return raw["result"]


def _as_text(message: Any) -> str:
    """A received websocket message (text or bytes) as text."""
    return message if isinstance(message, str) else bytes(message).decode("utf-8")


class UE5Backend:
    """JSON-RPC-over-WebSocket client for a running UE5 instance."""

    def __init__(self, uri: str, timeout_seconds: float = 5.0) -> None:
        """
        Parameters
        ----------
        uri : str
            WebSocket URI of the UE5-side JSON-RPC listener, e.g.
            ``"ws://localhost:8765"``.
        timeout_seconds : float
            Maximum time to wait for a response before raising
            ``UE5CommunicationTimeoutError``.
        """
        self.uri = uri
        self.timeout_seconds = timeout_seconds
        self._request_id_counter = itertools.count(1)
        self._connection: Optional[Any] = None

    async def __aenter__(self) -> "UE5Backend":
        """Keep one connection open for every call inside ``async with`` -- the
        connect handshake alone costs a couple of game frames per call otherwise."""
        self._connection = await websockets.connect(self.uri, max_size=None, ping_interval=None)
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        """Close the shared connection."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def reconnect(self) -> None:
        """Replace the shared connection (after the game hung or restarted). Does nothing
        outside ``async with``, where every call already connects afresh."""
        if self._connection is None:
            return
        try:
            await self._connection.close()
        except (OSError, websockets.exceptions.WebSocketException):
            pass
        self._connection = await websockets.connect(self.uri, max_size=None, ping_interval=None)

    async def _exchange(self, request: Dict[str, Any]) -> str:
        """Send one request and return the raw response text."""
        if self._connection is not None:
            await asyncio.wait_for(
                self._connection.send(json.dumps(request)), timeout=self.timeout_seconds
            )
            return _as_text(
                await asyncio.wait_for(self._connection.recv(), timeout=self.timeout_seconds)
            )
        async with websockets.connect(self.uri, max_size=None, ping_interval=None) as connection:
            await asyncio.wait_for(
                connection.send(json.dumps(request)), timeout=self.timeout_seconds
            )
            return _as_text(await asyncio.wait_for(connection.recv(), timeout=self.timeout_seconds))

    async def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Make one JSON-RPC call and return its result.

        Raises
        ------
        UE5RPCError
            If UE5 returns a JSON-RPC error response.
        UE5CommunicationTimeoutError
            If no response arrives within ``timeout_seconds``.
        """
        request_id = next(self._request_id_counter)
        request = build_request(method, params or {}, request_id)

        try:
            # max_size=None: the websockets library defaults to a 1 MiB
            # per-message cap, sized for arbitrary untrusted servers --
            # this is a local, trusted connection to our own UE5 plugin,
            # and a real generated scenario's "assets" array (one entry
            # per building facade piece, tens of pieces per building) can
            # legitimately exceed 1 MiB. Confirmed necessary via a real
            # test failure (websockets.exceptions.PayloadTooBig) once
            # building facade pieces started populating "assets".
            #
            # ping_interval=None: the websockets library's default
            # keepalive ping/pong (20s interval, 20s timeout) is a client
            # behavior independent of our own asyncio.wait_for timeout
            # below. UE5's game thread can't service WebSocket ping
            # frames while it's synchronously spawning a large scenario's
            # actors on the game thread -- confirmed via a real failure
            # where UE5's own log showed "LoadProceduralScenario: spawned
            # 30395 asset(s)" completing successfully immediately after
            # the client had already torn down the connection with
            # "sent 1011 (internal error) keepalive ping timeout". The
            # explicit recv() timeout below already provides real
            # dead-connection detection; the keepalive ping only adds a
            # false-positive failure mode for exactly the slow, blocking
            # calls (like this one) that need long timeouts most.
            raw_response = await self._exchange(request)
        except asyncio.TimeoutError as exc:
            raise UE5CommunicationTimeoutError(
                f"No response from {self.uri} within {self.timeout_seconds}s"
            ) from exc

        response = json.loads(raw_response)
        return parse_response(response)

    async def load_scenario(self, payload: Dict[str, Any]) -> Any:
        """Send a generated scenario (nodes/edges/lanes/buildings/meshes,
        JSON-serialized) to UE5's ``LoadProceduralScenario`` RPC method."""
        return await self.call("LoadProceduralScenario", {"scenario": payload})

    async def load_scenario_file(self, path: Path) -> Any:
        """Have UE5 read a serialized scenario from ``path`` (same machine) instead of
        receiving it through the socket, which moves only ~0.2 MB/s on a full scene."""
        return await self.call("LoadProceduralScenario", {"scenario_path": str(path.resolve())})

    async def ping(self) -> float:
        """Round-trip a no-op RPC call and return elapsed time in seconds."""
        start = time.perf_counter()
        await self.call("Ping", {})
        return time.perf_counter() - start
