"""Measure every City Sample vehicle's real headlight/tail-light mesh
positions and body bounds through the live UE5 RPC bridge
(``GetStaticMeshBounds``), and print them as JSON -- the source data for
``src/procedural/vehicle_lamp_geometry.py``.

Run with the UE5 game up (``-game``), from the repo root:
``PYTHONPATH=. python bin/measure_vehicle_lamps.py > lamps.json``.
"""

import asyncio
import json
from typing import Any, Dict

from src.procedural.city_sample_assets import VEHICLE_ASSET_PATHS, VEHICLE_PART_PATHS
from src.ue5.backend import UE5Backend

_LAMP_KEYS = ("Headlight_L", "Headlight_R", "Taillight_L", "Taillight_R")


async def _bounds(backend: UE5Backend, asset_path: str) -> Dict[str, Any]:
    """One static mesh's origin and box extent, in centimeters."""
    bounds: Dict[str, Any] = await backend.call("GetStaticMeshBounds", {"asset_path": asset_path})
    return bounds


async def main() -> None:
    """Measure every vehicle model and print the result as JSON."""
    backend = UE5Backend("ws://localhost:8765", timeout_seconds=60.0)
    result: Dict[str, Any] = {}
    for paths in VEHICLE_ASSET_PATHS.values():
        for body_path in paths:
            folder = body_path.split("/")[3]
            entry: Dict[str, Any] = {"body": await _bounds(backend, body_path), "lamps": {}}
            for part_path in VEHICLE_PART_PATHS.get(folder, []):
                for key in _LAMP_KEYS:
                    if f"SM_{key}_" in part_path:
                        entry["lamps"][key] = await _bounds(backend, part_path)
            result[folder] = entry
    print(json.dumps(result, indent=1, sort_keys=True))


asyncio.run(main())
