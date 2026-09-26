"""Dump the render triangles of every City Sample vehicle model to a data file.

Needs a running UE5 game with the plugin (``GetStaticMeshGeometry`` RPC). For
each model folder the body shell, wheels, doors and glass are merged into one
triangle soup in the vehicle's own frame (+x forward, +y left, z up, metres --
the plugin's UE frame with Y mirrored and centimetres converted), and written to
``src/procedural/vehicle_meshes.npz`` as ``<folder>_vertices`` /
``<folder>_triangles``. The interior frame and steering wheel are skipped: they
sit inside the shell. Occlusion tests use these real shapes instead of boxes.

    PYTHONPATH=. python bin/dump_vehicle_meshes.py
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from numpy.typing import NDArray

from src.procedural.city_sample_assets import VEHICLE_ASSET_PATHS, VEHICLE_PART_PATHS
from src.ue5.backend import UE5Backend

OUTPUT = Path("src/procedural/vehicle_meshes.npz")
MAX_TRIANGLES_PER_PART = 500
SKIPPED_PART_MARKERS = ("Steering",)
CM = 100.0


async def _part_geometry(
    backend: UE5Backend, asset_path: str
) -> Tuple[NDArray[np.float64], NDArray[np.int64]]:
    """One static mesh's vertices (metres, vehicle frame) and triangle indices."""
    reply = await backend.call(
        "GetStaticMeshGeometry",
        {"asset_path": asset_path, "max_triangles": MAX_TRIANGLES_PER_PART},
    )
    if not reply.get("vertices"):
        raise RuntimeError(f"no CPU geometry for {asset_path}: {reply}")
    vertices = np.array(reply["vertices"], dtype=np.float64).reshape(-1, 3) / CM
    vertices[:, 1] *= -1.0
    triangles = np.array(reply["indices"], dtype=np.int64).reshape(-1, 3)
    return vertices, triangles


async def _dump() -> Dict[str, NDArray[np.generic]]:
    """Merge every model's parts into one triangle soup per model folder."""
    backend = UE5Backend("ws://localhost:8765", timeout_seconds=120.0)
    arrays: Dict[str, NDArray[np.generic]] = {}
    for bodies in VEHICLE_ASSET_PATHS.values():
        for body in bodies:
            folder = body.split("/")[3]
            paths = [body] + [
                part
                for part in VEHICLE_PART_PATHS.get(folder, [])
                if not any(marker in part for marker in SKIPPED_PART_MARKERS)
            ]
            vertex_blocks: List[NDArray[np.float64]] = []
            triangle_blocks: List[NDArray[np.int64]] = []
            offset = 0
            for path in paths:
                vertices, triangles = await _part_geometry(backend, path)
                vertex_blocks.append(vertices)
                triangle_blocks.append(triangles + offset)
                offset += len(vertices)
            arrays[f"{folder}_vertices"] = np.concatenate(vertex_blocks).astype(np.float32)
            arrays[f"{folder}_triangles"] = np.concatenate(triangle_blocks).astype(np.int32)
            print(f"{folder}: {len(paths)} parts, {len(arrays[f'{folder}_triangles'])} triangles")
    return arrays


def main() -> None:
    """Dump and save."""
    arrays = asyncio.run(_dump())
    np.savez_compressed(OUTPUT, **arrays)
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
