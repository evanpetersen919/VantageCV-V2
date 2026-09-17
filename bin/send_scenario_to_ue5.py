#!/usr/bin/env python
"""Command-line entry point for sending one generated scenario to a live
UE5 editor over the WebSocket JSON-RPC bridge.

Wraps a real, existing capability this codebase already has --
:func:`src.orchestration.dataset_generator.generate_scenario`,
:func:`src.orchestration.scenario_serializer.serialize_scenario`, and
:meth:`src.ue5.backend.UE5Backend.load_scenario` -- matching this
project's established ``bin/*.py`` philosophy (see
``generate_dataset.py``'s own docstring): only wrap capabilities that
genuinely exist, don't invent new ones for the sake of a CLI.

Replaces the ad hoc, uncommitted scratchpad script used to verify the
real UE5 round trip earlier in this session (a real generated scenario
rendering correctly in a live PIE session) with a permanent, tested tool
-- see KNOWN_GAPS_AND_ISSUES.md.

Requires a live UE5 editor with the SyntheticDataGen plugin's
``USyntheticDataGenRpcSubsystem`` running (Play-In-Editor started, not
just the editor open -- the RPC server only starts once a GameInstance
exists) and listening on the given ``--ue5-uri``.

Example
-------
.. code-block:: bash

   python bin/send_scenario_to_ue5.py \\
       --config configs/scenario_templates/urban_dense.yaml \\
       --seed 42 \\
       --bounds -250 -250 250 250
"""

# pylint: disable=duplicate-code
# The --config/--bounds argparse setup and config-loading error handling
# below inevitably resemble generate_dataset.py's own -- both are thin
# argparse wrappers around a real capability, per this file's own
# docstring; a shared helper for ~10 lines of argparse boilerplate would
# be more indirection than it saves.

import asyncio
import sys
from pathlib import Path
from typing import List, Optional

# Running this file directly (`python bin/send_scenario_to_ue5.py`) puts
# bin/ itself on sys.path, not the repo root -- `import src...` would
# otherwise fail. Must happen before the src imports below.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# pylint: disable=wrong-import-position
import argparse  # noqa: E402

from src.orchestration.dataset_generator import generate_scenario  # noqa: E402
from src.orchestration.scenario_serializer import serialize_scenario  # noqa: E402
from src.ue5.backend import UE5Backend, UE5CommunicationTimeoutError, UE5RPCError  # noqa: E402
from src.utils.config_loader import load_scenario_config  # noqa: E402

# pylint: enable=wrong-import-position

DEFAULT_UE5_URI = "ws://localhost:8765"


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one procedural scenario and send it to a live UE5 editor."
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to a configs/scenario_templates/-shaped YAML file "
        "(only urban_dense/urban_sparse-typed templates are currently "
        "generatable -- see KNOWN_GAPS_AND_ISSUES.md).",
    )
    parser.add_argument("--seed", default=42, type=int, help="Scenario seed. Default: 42.")
    parser.add_argument(
        "--bounds",
        required=True,
        nargs=4,
        type=float,
        metavar=("X_MIN", "Y_MIN", "X_MAX", "Y_MAX"),
        help="Scenario generation bounds in meters.",
    )
    parser.add_argument(
        "--ue5-uri",
        default=DEFAULT_UE5_URI,
        help=f"WebSocket URI of the UE5-side RPC listener. Default: {DEFAULT_UE5_URI}.",
    )
    parser.add_argument(
        "--timeout-seconds",
        default=15.0,
        type=float,
        help="Max time to wait for UE5's response. Default: 15.0.",
    )
    return parser.parse_args(argv)


async def _send(args: argparse.Namespace) -> int:
    try:
        config = load_scenario_config(args.config)
    except (FileNotFoundError, NotImplementedError, ValueError) as exc:
        print(f"Error loading --config {args.config}: {exc}", file=sys.stderr)
        return 1

    x_min, y_min, x_max, y_max = args.bounds
    bounds = (x_min, y_min, x_max, y_max)

    try:
        scenario = generate_scenario(args.seed, config, bounds, "sent_to_ue5")
    except ValueError as exc:
        print(f"Error during generation: {exc}", file=sys.stderr)
        return 1

    print(f"Generated scenario: {len(scenario.meshes)} meshes")
    payload = serialize_scenario(scenario)

    backend = UE5Backend(args.ue5_uri, timeout_seconds=args.timeout_seconds)
    try:
        result = await backend.load_scenario(payload)
    except UE5CommunicationTimeoutError as exc:
        print(f"Timed out waiting for UE5: {exc}", file=sys.stderr)
        print(
            "Is a UE5 editor running with Play-In-Editor started (not just the editor open)?",
            file=sys.stderr,
        )
        return 1
    except UE5RPCError as exc:
        print(f"UE5 returned an RPC error: {exc}", file=sys.stderr)
        return 1

    print(f"LoadProceduralScenario result: {result}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Parse arguments, run the async send, print a summary. Returns the
    process exit code (0 on success, 1 on an expected failure mode)."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    return asyncio.run(_send(args))


if __name__ == "__main__":
    sys.exit(main())
