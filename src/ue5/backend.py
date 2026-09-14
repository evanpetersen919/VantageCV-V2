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
from typing import Any, Dict, Optional

import websockets


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
            async with websockets.connect(self.uri) as connection:
                await asyncio.wait_for(
                    connection.send(json.dumps(request)), timeout=self.timeout_seconds
                )
                raw_response = await asyncio.wait_for(
                    connection.recv(), timeout=self.timeout_seconds
                )
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

    async def ping(self) -> float:
        """Round-trip a no-op RPC call and return elapsed time in seconds."""
        start = time.perf_counter()
        await self.call("Ping", {})
        return time.perf_counter() - start
