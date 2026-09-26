"""Check every vehicle ground-truth box against what the engine renders.

Needs a running UE5 game with the plugin. For each of seven models it loads one
vehicle on flat ground, photographs it from directly above (so perspective
leaves the footprint undistorted), subtracts an empty render to get the
silhouette, calibrates scale from a 10 m white marker, and prints the
silhouette size next to the ground-truth box. It also writes an overlay image
with each predicted footprint box drawn on its render (nad_overlay.png in the
temp directory):

    PYTHONPATH=. python bin/verify_vehicle_boxes.py

A roof h metres up looks (1 + h / 80) times larger from 80 m, so lengths a few
percent over 1.0 are expected; widths can read a little under 1.0 where wheels
or glass are wider than the visible top.
"""

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Any, List, Tuple

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw
from scipy import ndimage

from src.ground_truth.bbox_3d import extract_bbox_3d_vehicle
from src.orchestration.scenario_serializer import _mesh_to_json, _vehicle_to_asset_json
from src.procedural.actor_placement import Vehicle, vehicle_box
from src.procedural.mesh_factory import flat_quad_mesh
from src.ue5.backend import UE5Backend

OUT = Path(tempfile.gettempdir())
SCREENSHOT = Path(r"F:\UE5Projects\VantageCV_UE5\Saved\rpc_debug_screenshot.png")
CAMERA_KEYS = ["cam_x", "cam_y", "cam_z", "target_x", "target_y", "target_z"]
CAMERA_HEIGHT_CM = 8000.0
CAMERA_HEIGHT_M = CAMERA_HEIGHT_CM / 100.0
MARKER_SIDE_M = 10.0
BRIGHTER_THAN_GROUND = 22.0
SEARCH_MARGIN_PX = 40
MODELS: List[Tuple[str, str]] = [
    ("/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Frame_vehCar_vehicle02", "sedan"),
    ("/Game/Vehicle/vehCar_vehicle03/Mesh/SM_Frame_vehCar_vehicle03", "sedan"),
    ("/Game/Vehicle/vehCar_vehicle06/Mesh/SM_Frame_vehCar_vehicle06", "sedan"),
    ("/Game/Vehicle/vehVan_vehicle01/Mesh/SM_Frame_vehVan_vehicle01", "suv"),
    ("/Game/Vehicle/vehTruck_vehicle04/Mesh/SM_Frame_vehTruck_vehicle04", "truck"),
    ("/Game/Vehicle/vehTruck_vehicle11/Mesh/SM_Frame_vehTruck_vehicle11", "truck"),
    ("/Game/Vehicle/vehBus_vehicle10/Mesh/SM_Frame_vehBus_vehicle10", "bus"),
]
GROUND = _mesh_to_json(flat_quad_mesh(-60.0, -60.0, 60.0, 60.0, 0.0, 4.0, "asphalt"))
MARKER = _mesh_to_json(flat_quad_mesh(14.0, -5.0, 24.0, 5.0, 0.02, 4.0, "paint_white"))


def _vehicle(asset_path: str, vehicle_type: str) -> Vehicle:
    """The vehicle at the origin with its model's measured box."""
    length, width, height, offset_x, offset_y, z_min = vehicle_box(asset_path, vehicle_type)
    return Vehicle(
        vehicle_id=0,
        vehicle_type=vehicle_type,
        asset_path=asset_path,
        center=np.array([0.0, 0.0]),
        heading_rad=0.0,
        length=length,
        width=width,
        height=height,
        box_offset=(offset_x, offset_y),
        box_z_min=z_min,
    )


async def _shoot(backend: UE5Backend, assets: List[Any], name: str) -> None:
    """Load the scene and save a screenshot from directly above the origin."""
    await backend.load_scenario({"meshes": [GROUND, MARKER], "assets": assets})
    await asyncio.sleep(5.0)
    camera = (0.0, -1.0, CAMERA_HEIGHT_CM, 0.0, 0.0, 0.0)
    await backend.call("DebugMoveCameraTo", dict(zip(CAMERA_KEYS, camera)))
    await asyncio.sleep(3.0)
    await backend.call("TakeScreenshot", {"filename": "l.png"})
    shutil.copy(SCREENSHOT, OUT / f"{name}.png")


async def _capture() -> None:
    """Render the empty scene and each model alone."""
    backend = UE5Backend("ws://localhost:8765", timeout_seconds=300.0)
    await _shoot(backend, [], "nad_empty")
    for index, (path, kind) in enumerate(MODELS):
        await _shoot(backend, [_vehicle_to_asset_json(_vehicle(path, kind))], f"nad_{index}")


def _luminance(image: NDArray[Any]) -> NDArray[Any]:
    """Per-pixel mean of the colour channels."""
    return np.asarray(image.mean(axis=2))


def _pixels_per_metre(empty: NDArray[Any]) -> float:
    """Ground-level scale from the largest bright blob (the white marker)."""
    bright = empty.min(axis=2) > 190
    labels, count = ndimage.label(bright)
    if count == 0:
        raise SystemExit("marker not found in the empty render")
    sizes = ndimage.sum(bright, labels, range(1, count + 1))
    box = ndimage.find_objects(labels)[int(np.argmax(sizes))]
    side_px = ((box[1].stop - box[1].start) + (box[0].stop - box[0].start)) / 2.0
    return float(side_px / MARKER_SIDE_M)


def _measure(
    mask: NDArray[Any], car: Vehicle, centre: Tuple[float, float], scale: float
) -> Tuple[float, float]:
    """Silhouette (length, width) in metres around the vehicle's box centre."""
    half_y = int(0.5 * car.length * scale + SEARCH_MARGIN_PX)
    half_x = int(0.5 * car.width * scale + SEARCH_MARGIN_PX)
    top, left = int(centre[1] - half_y), int(centre[0] - half_x)
    rows, cols = np.nonzero(mask[top : top + 2 * half_y, left : left + 2 * half_x])
    return (rows.max() - rows.min() + 1) / scale, (cols.max() - cols.min() + 1) / scale


def _annotate(
    picture: Image.Image, dimensions: Tuple[float, float], centre: Tuple[float, float], scale: float
) -> Image.Image:
    """Draw the ground-truth footprint on the render and crop around it."""
    half_length, half_width = dimensions[0] * scale / 2.0, dimensions[1] * scale / 2.0
    centre_x, centre_y = centre
    ImageDraw.Draw(picture).rectangle(
        [
            centre_x - half_width,
            centre_y - half_length,
            centre_x + half_width,
            centre_y + half_length,
        ],
        outline=(255, 0, 0),
        width=2,
    )
    return picture.crop(
        (
            int(centre_x - 150),
            int(centre_y - half_length - 25),
            int(centre_x + 150),
            int(centre_y + half_length + 25),
        )
    )


def _check_model(
    index: int, model: Tuple[str, str], empty: NDArray[Any], scale: float
) -> Image.Image:
    """Print one model's silhouette vs box comparison and return its overlay crop."""
    path, kind = model
    picture = Image.open(OUT / f"nad_{index}.png").convert("RGB")
    difference = _luminance(np.asarray(picture, dtype=float)) - _luminance(empty)
    mask = ndimage.binary_closing(difference > BRIGHTER_THAN_GROUND, iterations=2)
    car = _vehicle(path, kind)
    box = extract_bbox_3d_vehicle(car)
    centre = (
        empty.shape[1] / 2.0 + car.box_center[1] * scale,
        empty.shape[0] / 2.0 - car.box_center[0] * scale,
    )
    length_m, width_m = _measure(mask, car, centre, scale)
    print(
        f"{path.split('/')[3]:<20} | {box.dimensions[0]:5.2f} x {box.dimensions[1]:4.2f} | "
        f"{length_m:5.2f} x {width_m:4.2f} | "
        f"{length_m / box.dimensions[0]:.3f}, {width_m / box.dimensions[1]:.3f} | "
        f"{1.0 + car.height / CAMERA_HEIGHT_M:.3f}"
    )
    return _annotate(picture, (box.dimensions[0], box.dimensions[1]), centre, scale)


def _save_sheet(crops: List[Image.Image]) -> None:
    """Lay the per-model overlay crops side by side and save the sheet."""
    sheet = Image.new(
        "RGB",
        (sum(crop.size[0] for crop in crops), max(crop.size[1] for crop in crops)),
        (255, 255, 255),
    )
    left = 0
    for crop in crops:
        sheet.paste(crop, (left, 0))
        left += crop.size[0]
    sheet.save(OUT / "nad_overlay.png")


def _report() -> None:
    """Compare every model's silhouette with its box and save the overlay sheet."""
    empty = np.asarray(Image.open(OUT / "nad_empty.png").convert("RGB"), dtype=float)
    scale = _pixels_per_metre(empty)
    print(f"image {empty.shape[1]}x{empty.shape[0]}, {scale:.2f} px/m at ground level")
    print("model | GT L x W | silhouette L x W | ratio L, W | perspective bound (1 + h/80 m)")
    _save_sheet([_check_model(index, model, empty, scale) for index, model in enumerate(MODELS)])


def main() -> None:
    """Capture the renders, then compare them with the labels."""
    asyncio.run(_capture())
    _report()


if __name__ == "__main__":
    main()
