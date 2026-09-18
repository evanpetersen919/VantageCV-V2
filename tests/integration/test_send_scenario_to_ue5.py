"""Integration tests for bin/send_scenario_to_ue5.py.

Runs the actual CLI as a subprocess (not by importing its main()
directly) against a real local mock WebSocket server -- see
test_backend.py's own module docstring for why a local mock server is
the right level of verification here (it exercises every line of the
real generate -> serialize -> send round trip; it cannot verify UE5-side
scenario-loading behavior, which needs the actual engine and was
verified manually earlier in this session).
"""

# pylint: disable=duplicate-code
# The mock-server handlers below inevitably resemble test_backend.py's own
# (same JSON-RPC 2.0 shape by construction); the --bounds argument lists
# inevitably resemble test_cli.py's own -- a shared helper for either would
# be more indirection than the ~5 lines it would save. Same rationale as
# test_actor_placement.py's own module-level disable.

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import websockets

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CLI_PATH = _REPO_ROOT / "bin" / "send_scenario_to_ue5.py"
_URBAN_DENSE_CONFIG = _REPO_ROOT / "configs" / "scenario_templates" / "urban_dense.yaml"

_BASE_ARGS = [
    "--config",
    str(_URBAN_DENSE_CONFIG),
    "--seed",
    "42",
    "--bounds",
    "-250",
    "-250",
    "250",
    "250",
    "--timeout-seconds",
    "5",
]


async def _run_cli_against_mock_server(handler, args: list) -> subprocess.CompletedProcess:
    """Start `handler` as a local WebSocket server on an OS-assigned
    port, run the real CLI as a subprocess pointed at it, and return the
    completed process."""
    # max_size=None: matches UE5Backend's own real client-side setting --
    # see backend.py's comment on why the websockets library's 1 MiB
    # default is too small for a real scenario's "assets" array once
    # building facade pieces populate it.
    async with websockets.serve(handler, "localhost", 0, max_size=None) as server:
        port = server.sockets[0].getsockname()[1]
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                [sys.executable, str(_CLI_PATH), *args, "--ue5-uri", f"ws://localhost:{port}"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            ),
        )


def _run(coro):
    return asyncio.run(coro)


async def _load_scenario_handler(connection):
    raw = await connection.recv()
    request = json.loads(raw)
    mesh_count = len(request["params"]["scenario"].get("meshes", []))
    await connection.send(
        json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": {"loaded_meshes": mesh_count}})
    )


def test_cli_sends_real_scenario_and_prints_result() -> None:
    """A successful round trip exits 0, prints the real generated mesh
    count and UE5's real response, matching what was manually verified
    against a live editor earlier in this session."""
    result = _run(_run_cli_against_mock_server(_load_scenario_handler, _BASE_ARGS))

    assert result.returncode == 0, result.stderr
    assert "Generated scenario:" in result.stdout
    assert "meshes" in result.stdout
    assert "LoadProceduralScenario result:" in result.stdout
    assert "loaded_meshes" in result.stdout


async def _silent_handler(connection):
    # Receive the request but never respond, to trigger a client timeout.
    await connection.recv()
    await asyncio.sleep(10)


def test_cli_timeout_exits_nonzero_with_clean_message() -> None:
    """A UE5 server that never responds exits 1 with a clean,
    actionable message (not a raw traceback), matching the real failure
    mode hit tonight whenever the editor wasn't in Play-In-Editor yet."""
    args = [*_BASE_ARGS[:-2], "--timeout-seconds", "0.5"]  # override the base 5s for speed
    result = _run(_run_cli_against_mock_server(_silent_handler, args))

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "Play-In-Editor" in result.stderr


async def _error_handler(connection):
    raw = await connection.recv()
    request = json.loads(raw)
    await connection.send(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request["id"],
                "error": {"code": -32000, "message": "rejected"},
            }
        )
    )


def test_cli_rpc_error_exits_nonzero_with_clean_message() -> None:
    """A JSON-RPC error response from UE5 exits 1 with a clean message,
    not a raw traceback."""
    result = _run(_run_cli_against_mock_server(_error_handler, _BASE_ARGS))

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "rejected" in result.stderr


def test_cli_missing_config_exits_nonzero_with_clean_message(tmp_path) -> None:
    """A nonexistent --config path exits 1 with a clean message, before
    ever trying to contact UE5."""
    args = [
        "--config",
        str(tmp_path / "does_not_exist.yaml"),
        "--bounds",
        "-100",
        "-100",
        "100",
        "100",
    ]
    result = subprocess.run(
        [sys.executable, str(_CLI_PATH), *args],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 1
    assert "Traceback" not in result.stderr


def test_cli_missing_required_argument_exits_nonzero() -> None:
    """argparse itself rejects a missing required argument (--bounds)
    with the standard argparse exit code (2)."""
    result = subprocess.run(
        [sys.executable, str(_CLI_PATH), "--config", str(_URBAN_DENSE_CONFIG)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 2
    assert "--bounds" in result.stderr


def test_cli_default_seed_is_42() -> None:
    """Omitting --seed defaults to 42, matching this script's own
    documented default."""
    args = [
        "--config",
        str(_URBAN_DENSE_CONFIG),
        "--bounds",
        "-250",
        "-250",
        "250",
        "250",
        "--timeout-seconds",
        "5",
    ]
    result = _run(_run_cli_against_mock_server(_load_scenario_handler, args))

    assert result.returncode == 0, result.stderr
    assert "Generated scenario:" in result.stdout
