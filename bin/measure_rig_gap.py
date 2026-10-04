"""Measure the gap between a tractor cab and its trailer in the engine, for several hitch offsets.

Needs the running UE5 game (``bin/launch_ue5.ps1``). For each candidate offset (the trailer's origin
that many metres behind the cab's origin) the rig stands alone on flat ground and is photographed
from the side at a fixed height, level with the cab body; an empty render of the same view is
subtracted to get the silhouette. Along that row band the script reports, in metres from the cab's
origin, where the cab's rear wall is, where the trailer's front face is, and the gap between them,
plus the same at the height of the trailer's underside (the chassis and the coupling).

    PYTHONPATH=. python bin/measure_rig_gap.py --hitches -1.58 -0.5 -0.1056 0.0

The scale comes from the known length of the whole rig (its silhouette's two ends), so a few
percent of perspective error remains across the vehicle's width; use several camera distances to
see how much (``--distance``).
"""

import argparse
import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Any, List, Tuple

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from src.orchestration.scenario_serializer import (
    _mesh_to_json,
    _vehicle_to_asset_json,
    trailer_asset_json,
)
from src.procedural.actor_placement import Vehicle, vehicle_box
from src.procedural.city_sample_assets import TRACTOR_FOLDER
from src.procedural.mesh_factory import flat_quad_mesh
from src.ue5.backend import UE5Backend

SCREENSHOT = Path(r"F:\UE5Projects\VantageCV_UE5\Saved\rpc_debug_screenshot.png")
CAMERA_KEYS = ["cam_x", "cam_y", "cam_z", "target_x", "target_y", "target_z"]
CAB = f"/Game/Vehicle/{TRACTOR_FOLDER}/Mesh/SM_Frame_{TRACTOR_FOLDER}"
GROUND = _mesh_to_json(flat_quad_mesh(-80.0, -80.0, 80.0, 80.0, 0.0, 4.0, "asphalt"))
CHANGED = 28.0  # a pixel differs from the empty render by more than this (mean of channels)
FOCAL_PX = 1080.0 / (2.0 * np.tan(np.radians(73.7398) / 2.0))  # vertical focal length in pixels


def _cab() -> Vehicle:
    length, width, height, offset_x, offset_y, z_min = vehicle_box(CAB, "truck")
    base = Vehicle(0, "truck", CAB, np.array([0.0, 0.0]), 0.0, length, width, height)
    base.box_offset, base.box_z_min = (offset_x, offset_y), z_min
    return base


async def _shoot(  # pylint: disable=too-many-arguments
    backend: UE5Backend, assets: List[Any], name: str, distance: float, height: float, out: Path
) -> Path:
    """Load the scene and save a side view (camera on the -y side, looking +y at the origin)."""
    await backend.load_scenario({"meshes": [GROUND], "assets": assets})
    await asyncio.sleep(6.0)
    camera = (0.0, -distance * 100.0, height * 100.0, 0.0, 0.0, height * 100.0)
    await backend.call("DebugMoveCameraTo", dict(zip(CAMERA_KEYS, camera)))
    await asyncio.sleep(3.0)
    await backend.call("TakeScreenshot", {"filename": "g.png"})
    await asyncio.sleep(1.5)
    path = out / f"{name}.png"
    shutil.copy(SCREENSHOT, path)
    return path


def _runs(mask_row: NDArray[Any]) -> List[Tuple[int, int]]:
    """Start and end columns (inclusive) of each run of True in a row."""
    padded = np.concatenate([[False], mask_row, [False]])
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return [(int(a), int(b) - 1) for a, b in zip(edges[::2], edges[1::2])]


def _measure(
    empty: Path, shot: Path, distance: float, height: float, band_m: Tuple[float, float]
) -> List[Tuple[float, float]]:
    """Silhouette runs along the rows between ``band_m`` (heights in metres) as (from, to) world x
    in metres of the cab's frame. The camera looks along +y, so image x grows toward world -x. The
    scale is the focal length at the nearest vehicle face (y = -1.3 m), where the silhouette edges
    are; runs more than 16 m from the cab are the changing sky and ground texture, not the rig."""
    base = np.asarray(Image.open(empty).convert("RGB"), dtype=np.float32)
    now = np.asarray(Image.open(shot).convert("RGB"), dtype=np.float32)
    mask = np.abs(now - base).mean(axis=2) > CHANGED
    scale = FOCAL_PX / (distance - 1.3)
    top = int(540 - (band_m[1] - height) * scale)
    bottom = int(540 - (band_m[0] - height) * scale)
    columns = mask[max(top, 0) : min(bottom, 1080)].any(axis=0)
    runs = [r for r in _runs(columns) if r[1] - r[0] > 6]
    metres = [(-(b + 1 - 960) / scale, -(a - 960) / scale) for a, b in runs]
    return [(lo, hi) for lo, hi in sorted(metres) if abs(lo) < 16.0 and abs(hi) < 16.0]


def _gap(runs: List[Tuple[float, float]]) -> str:
    """The cab's rear wall (the first silhouette run that starts ahead of the cab's origin
    region, x > 0.3 m) and the trailer's front wall (the last run that ends behind that wall):
    the gap between them."""
    cab = [r for r in runs if r[0] > 0.3]
    if not cab:
        return "no cab run found"
    wall = min(r[0] for r in cab)
    trailer = [r for r in runs if r[1] < wall - 0.01]
    if not trailer:
        return f"cab wall at {wall:.2f} m, no trailer run behind it"
    front = max(r[1] for r in trailer)
    return f"gap {wall - front:.2f} m (trailer front {front:.2f}, cab rear wall {wall:.2f})"


async def _run(args: argparse.Namespace) -> None:
    out = Path(tempfile.gettempdir())
    cab = _vehicle_to_asset_json(_cab())
    async with UE5Backend("ws://localhost:8765", timeout_seconds=300.0) as backend:
        empty = await _shoot(backend, [], "gap_empty", args.distance, args.height, out)
        for hitch in args.hitches:
            trailer = trailer_asset_json(_cab_rig(), hitch)
            shot = await _shoot(
                backend, [cab, trailer], f"gap_{hitch}", args.distance, args.height, out
            )
            runs = _measure(empty, shot, args.distance, args.height, (2.2, 3.0))
            print(f"hitch {hitch:7.4f} at {args.distance:.0f} m: {_gap(runs)}", flush=True)


def _cab_rig() -> Vehicle:
    rig = _cab()
    rig.trailer = True
    return rig


def main() -> None:
    """Parse arguments and run."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--hitches", type=float, nargs="+", required=True)
    parser.add_argument("--distance", type=float, default=40.0, help="camera distance in metres")
    parser.add_argument("--height", type=float, default=2.6, help="camera height in metres")
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
