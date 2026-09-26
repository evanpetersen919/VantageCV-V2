"""Draw the exported 3D ground-truth boxes over live UE5 renders, for eyeballing.

Generates one scenario, loads it into a running UE5 game, and for each view
photographs a vehicle from an oblique street-level camera. The boxes come from
the same ``extract_bboxes_3d_*`` functions the dataset export uses and are
projected through this project's own ``Camera`` model, so what is drawn is
exactly what a dataset consumer would get. The front face of every box is
crossed so the heading can be checked as well as the size and position.

Python and UE5 world coordinates agree in this projection with no extra flip
(the scene loader's Y mirror and UE's left-handed camera cancel). The camera's
vertical FOV (73.74 degrees, UE's default 90 degrees defined at 4:3) matches four
squares of known position rendered at two window sizes (under 1 px mean error
each); the horizontal FOV follows the screenshot's aspect ratio.

    PYTHONPATH=. python bin/overlay_boxes_3d.py --seed 42 --out boxes_out

Writes ``<out>/<view>.png`` for the views ``parked``, ``street`` and ``large``.
"""

import argparse
import asyncio
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw

from src.ground_truth.bbox_3d import (
    BoundingBox3D,
    extract_bboxes_3d,
    extract_bboxes_3d_pedestrians,
    extract_bboxes_3d_vehicles,
)
from src.ground_truth.occlusion import MIN_VISIBLE_FRACTION, visible_fraction
from src.ground_truth.overlay import draw_box_3d
from src.orchestration.dataset_generator import ScenarioResult, generate_scenario
from src.orchestration.scenario_serializer import serialize_scenario
from src.procedural.actor_placement import Vehicle
from src.procedural.environment import season_environment
from src.procedural.vehicle_meshes import world_triangles
from src.sensors.camera_model import Camera, CameraExtrinsics, CameraIntrinsics
from src.ue5.backend import UE5Backend
from src.utils.config_loader import load_scenario_config

SCREENSHOT = Path(r"F:\UE5Projects\VantageCV_UE5\Saved\rpc_debug_screenshot.png")
CAMERA_KEYS = ["cam_x", "cam_y", "cam_z", "target_x", "target_y", "target_z"]
VERTICAL_FOV_DEG = 73.74
CAMERA_DISTANCE_M = 15.0
CAMERA_HEIGHT_M = 4.5
VIEW_ANGLE_RAD = np.radians(55.0)
NEIGHBOUR_RADIUS_M = 25.0
PARTLY_BELOW = 0.5


def _camera_pose(
    target: NDArray[np.float64], heading_rad: float
) -> Tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Camera position and look-at point: ahead-and-to-the-side of ``target``."""
    angle = heading_rad + VIEW_ANGLE_RAD
    position = np.array(
        [
            target[0] + CAMERA_DISTANCE_M * np.cos(angle),
            target[1] + CAMERA_DISTANCE_M * np.sin(angle),
            CAMERA_HEIGHT_M,
        ]
    )
    return position, np.array([target[0], target[1], 0.8])


def _camera_from(
    position: NDArray[np.float64], look_at: NDArray[np.float64], screenshot: Path
) -> Camera:
    """The pinhole camera that produced ``screenshot``.

    UE keeps the vertical FOV fixed, so the horizontal FOV follows the image aspect
    (UE's default 90 deg FOV is defined at 4:3, i.e. 73.74 deg vertical; checked against
    fitted values at 3440x1440 and 1920x1080).
    """
    with Image.open(screenshot) as picture:
        width, height = picture.size
    horizontal = 2.0 * np.degrees(
        np.arctan(np.tan(np.radians(VERTICAL_FOV_DEG) / 2.0) * width / height)
    )
    intrinsics = CameraIntrinsics.from_fov(float(horizontal), width, height)
    return Camera(intrinsics, CameraExtrinsics.looking_at(position, look_at))


def _neighbour_count(vehicle: Vehicle, others: List[Vehicle]) -> int:
    """How many other vehicles lie within the view radius."""
    return sum(
        1 for other in others if np.linalg.norm(other.center - vehicle.center) < NEIGHBOUR_RADIUS_M
    )


def _pick_views(scenario: ScenarioResult) -> Dict[str, Vehicle]:
    """The most crowded parked vehicle, the most crowded moving one, the biggest one."""
    vehicles = scenario.vehicles
    views: Dict[str, Vehicle] = {}
    for name, group in (
        ("parked", [car for car in vehicles if car.parked]),
        ("street", [car for car in vehicles if not car.parked]),
    ):
        if group:
            views[name] = max(group, key=lambda car: _neighbour_count(car, vehicles))
    if vehicles:
        views["large"] = max(vehicles, key=lambda car: car.length)
    return views


Scene = Tuple[List[BoundingBox3D], List[BoundingBox3D], Dict[int, NDArray[np.float64]]]


def _all_boxes(scenario: ScenarioResult) -> Scene:
    """(labelled boxes, every box that can block a view, vehicle meshes by box id)."""
    labelled = extract_bboxes_3d_vehicles(
        scenario.vehicles, id_offset=len(scenario.buildings)
    ) + extract_bboxes_3d_pedestrians(
        scenario.pedestrians, id_offset=len(scenario.buildings) + len(scenario.vehicles)
    )
    meshes = {
        vehicle.vehicle_id + len(scenario.buildings): soup
        for vehicle in scenario.vehicles
        if (soup := world_triangles(vehicle)) is not None
    }
    return labelled, labelled + extract_bboxes_3d(scenario.buildings), meshes


def _in_frame(camera: Camera, box: BoundingBox3D) -> bool:
    """Whether any corner projects into the image."""
    for corner in box.corners():
        pixel, _ = camera.project(corner)
        if pixel is not None and camera.is_pixel_in_bounds(pixel):
            return True
    return False


async def _photograph(
    backend: UE5Backend, position: NDArray[np.float64], look_at: NDArray[np.float64], path: Path
) -> None:
    """Move the game camera (python metres to UE centimetres, Y mirrored) and screenshot."""

    def to_ue(point: NDArray[np.float64]) -> List[float]:
        return [float(point[0] * 100.0), float(-point[1] * 100.0), float(point[2] * 100.0)]

    pose = dict(zip(CAMERA_KEYS, to_ue(position) + to_ue(look_at)))
    await backend.call("DebugMoveCameraTo", pose)
    await asyncio.sleep(3.0)
    await backend.call("TakeScreenshot", {"filename": "boxes.png"})
    await asyncio.sleep(2.0)
    shutil.copy(SCREENSHOT, path)


async def _run(args: argparse.Namespace) -> None:
    """Generate, load, then photograph and annotate each view."""
    config = load_scenario_config(args.config).model_copy(update={"parking_lot_fraction": 0.5})
    bounds = tuple(args.bounds)
    scenario = generate_scenario(args.seed, config, bounds, "boxes")
    backend = UE5Backend(args.ue5_uri, timeout_seconds=300.0)
    await backend.load_scenario(serialize_scenario(scenario, season_environment(scenario.season)))
    await asyncio.sleep(10.0)
    args.out.mkdir(parents=True, exist_ok=True)
    scene = _all_boxes(scenario)
    for name, target in _pick_views(scenario).items():
        position, look_at = _camera_pose(
            np.array([target.box_center[0], target.box_center[1]]), target.heading_rad
        )
        path = args.out / f"{name}.png"
        await _photograph(backend, position, look_at, path)
        camera = _camera_from(position, look_at, path)
        target_box_id = target.vehicle_id + len(scenario.buildings)
        _annotate(path, camera, scene, target_box_id)


def _annotate(
    path: Path,
    camera: Camera,
    boxes: Scene,
    target_box_id: int,
) -> None:
    """Draw every in-frame labelled box on the screenshot, dimming occluded ones."""
    labelled, occluders, meshes = boxes
    picture = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(picture)
    counts = {"clear": 0, "partly hidden": 0, "hidden (skipped)": 0}
    for box in labelled:
        if not _in_frame(camera, box):
            continue
        fraction = visible_fraction(camera, box, occluders, meshes)
        if fraction < MIN_VISIBLE_FRACTION:
            counts["hidden (skipped)"] += 1
            continue
        partly = fraction < PARTLY_BELOW
        counts["partly hidden" if partly else "clear"] += 1
        draw_box_3d(draw, camera, box, 6 if box.object_id == target_box_id else 3, partly)
    picture.save(path)
    print(f"{path.name}: {counts}")


def main() -> None:
    """Parse arguments and run."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument(
        "--config", type=Path, default=Path("configs/scenario_templates/urban_dense.yaml")
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bounds", type=float, nargs=4, default=[-150.0, -150.0, 150.0, 150.0])
    parser.add_argument("--out", type=Path, default=Path("boxes_out"))
    parser.add_argument("--ue5-uri", default="ws://localhost:8765")
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
