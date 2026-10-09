"""Render the imported riders and bicycles at several distances and measure their engine masks (game running).

    PYTHONPATH=. python scripts/rider_spike_probe.py --out demo/rider_spike

A flat road, the camera at 1.6 m looking along +X, and rows of bicycles seen from the side at 6 to 65 m, one row
with the real 2 mm spokes and one with 6 mm spokes. For every bicycle the engine returns exact masks (the rider, the
bicycle without its spokes, the spokes), and the script writes the pixel counts, the boxes, a render and a mask
overlay. This is the check for the main risk of thin wheel spokes: do they drop out of the depth-based masks, and
does it change the bicycle's instance mask or box?
"""

import argparse
import asyncio
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw

from src.orchestration.live_render import LiveRenderer, vertical_fov_deg
from src.orchestration.scenario_serializer import _mesh_to_json
from src.procedural.environment import (
    Season,
    TimeOfDay,
    Weather,
    build_ground_mesh,
    scenario_environment,
)
from src.procedural.mesh_factory import flat_quad_mesh
from src.ue5.backend import UE5Backend

ROOT = "/Game/VantageCV/Riders/Spike"
PARTS = (
    "cranks_pedals",
    "fork_bars",
    "frame",
    "grips",
    "saddle",
    "wheel_front_hub",
    "wheel_front_rim",
    "wheel_front_spokes",
    "wheel_front_tyre",
    "wheel_rear_hub",
    "wheel_rear_rim",
    "wheel_rear_spokes",
    "wheel_rear_tyre",
)
AVATARS = ("Male_Adult_01", "Female_Adult_01", "Male_Adult_05")
DISTANCES_M = (6.0, 10.0, 16.0, 25.0, 40.0, 65.0)
CAMERA_HEIGHT_M = 1.6
SIZE = (1920, 1080)
FORWARD_OFFSET_RAD = -math.pi / 2  # the baked meshes face +Y; the loader turns them to the heading


def placements(variants: Tuple[str, ...] = ("real", "thick")) -> List[Dict[str, Any]]:
    """Where every bicycle goes: one row per spoke variant at each distance, seen from the side. With a single
    variant the same riders, positions and crank angles are used, so two runs differ only in the spokes.
    """
    out = []
    for k, distance in enumerate(DISTANCES_M):
        for row, variant in enumerate(variants):
            lateral = (-1.3, 1.3)[row]
            out.append(
                {
                    "variant": variant,
                    "distance": distance,
                    "x": distance,
                    "y": lateral,
                    "crank": (0, 90, 180, 270)[k % 4],
                    "avatar": AVATARS[k % len(AVATARS)],
                    "heading": math.pi / 2,
                }
            )
    return out


def build_payload(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The scene (road, sky) with every bicycle's parts and rider as assets; remember each one's asset indices."""
    environment = scenario_environment(Season.SUMMER, TimeOfDay.DAY, Weather.CLEAR, 1, "v7")
    meshes = [
        _mesh_to_json(build_ground_mesh(environment)),
        _mesh_to_json(flat_quad_mesh(-20.0, -40.0, 120.0, 40.0, 0.0, 4.0, "asphalt")),
    ]
    assets: List[Dict[str, Any]] = []
    for item in items:
        indices: Dict[str, int] = {}
        for part in PARTS:
            indices[part] = len(assets)
            assets.append(
                _asset(f"{ROOT}/bike_{item['variant']}_c{item['crank']}_{part}", item, len(assets))
            )
        indices["rider"] = len(assets)
        assets.append(_asset(f"{ROOT}/rider_{item['avatar']}_c{item['crank']}", item, len(assets)))
        item["indices"] = indices
    return {"meshes": meshes, "assets": assets, "environment": environment.to_json()}


def _asset(path: str, item: Dict[str, Any], identifier: int) -> Dict[str, Any]:
    return {
        "category": "static_asset",
        "asset_path": path,
        "part_paths": [],
        "position": [item["x"], item["y"], 0.0],
        "rotation_rad": item["heading"] + FORWARD_OFFSET_RAD,
        "id": identifier,
    }


async def run(out: Path, variants: Tuple[str, ...]) -> None:
    """Load the scene, photograph it, and ask the engine for each bicycle's masks."""
    out.mkdir(parents=True, exist_ok=True)
    items = placements(variants)
    payload = build_payload(items)
    position = np.array([0.0, 0.0, CAMERA_HEIGHT_M])
    look_at = np.array([30.0, 0.0, CAMERA_HEIGHT_M - 0.4])
    async with UE5Backend("ws://localhost:8765", timeout_seconds=300.0) as backend:
        renderer = LiveRenderer(backend, settle_seconds=1.0, load_seconds=15.0)
        await renderer.load(payload)
        await renderer.capture(position, look_at, out / "scene.png")
        results = []
        for item in items:
            groups = {
                "rider": [item["indices"]["rider"]],
                "bike": [
                    i
                    for part, i in item["indices"].items()
                    if part not in ("rider",) and "spokes" not in part
                ],
                "spokes": [
                    item["indices"]["wheel_front_spokes"],
                    item["indices"]["wheel_rear_spokes"],
                ],
            }
            names = list(groups)
            reply = await backend.call(
                "CaptureObjectMasks",
                {
                    "out_path": str((out / "mask.u16").resolve()),
                    "objects": [groups[n] for n in names],
                    "width": SIZE[0],
                    "height": SIZE[1],
                    "vertical_fov_deg": vertical_fov_deg(),
                },
            )
            visible = np.fromfile(out / "mask.u16", dtype="<u2").reshape(
                reply["height"], reply["width"]
            )
            row = {k: item[k] for k in ("variant", "distance", "crank", "avatar")}
            for index, name in enumerate(names):
                report = reply["objects"][index]
                row[name] = {
                    "amodal_px": report.get("amodal_px"),
                    "visible_px": report.get("visible_px"),
                    "visible_bbox": report.get("visible_bbox"),
                }
            focal_px = (SIZE[1] / 2.0) / math.tan(math.radians(vertical_fov_deg()) / 2.0)
            row["wheel_radius_px"] = 0.311 * focal_px / item["distance"]
            row["mask_pixels"] = {n: int((visible == i + 1).sum()) for i, n in enumerate(names)}
            results.append(row)
            np.save(
                out / f"visible_{item['variant']}_{int(item['distance'])}_{item['y']}.npy", visible
            )
    (out / "probe.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    overlay(out, items)
    print(f"{len(results)} bicycles -> {out}")


def overlay(out: Path, items: List[Dict[str, Any]]) -> None:
    """The render with every probed mask tinted (rider red, bike blue, spokes yellow)."""
    picture = Image.open(out / "scene.png").convert("RGB")
    pixels = np.asarray(picture).astype(np.float64)
    colours = {1: (255, 60, 60), 2: (60, 160, 255), 3: (255, 220, 0)}
    for item in items:
        mask = np.load(out / f"visible_{item['variant']}_{int(item['distance'])}_{item['y']}.npy")
        for code, colour in colours.items():
            region = mask == code
            pixels[region] = 0.4 * pixels[region] + 0.6 * np.array(colour)
    Image.fromarray(pixels.astype(np.uint8)).save(out / "overlay.png")
    ImageDraw.Draw(picture)


def main() -> None:
    """Parse arguments and run."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--out", type=Path, default=Path("demo/rider_spike"))
    parser.add_argument(
        "--variants", nargs="+", default=["real", "thick"], choices=["real", "thick"]
    )
    args = parser.parse_args()
    asyncio.run(run(args.out, tuple(args.variants)))


if __name__ == "__main__":
    main()
