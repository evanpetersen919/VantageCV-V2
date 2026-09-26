"""Draw the exported 3D ground-truth boxes over live UE5 renders, for eyeballing.

Generates one scenario, loads it into a running UE5 game, and for each view
photographs a vehicle from an oblique street-level camera. The boxes come from
the same ``extract_bboxes_3d_*`` functions the dataset export uses and are
projected through this project's own ``Camera`` model, so what is drawn is
exactly what a dataset consumer would get. The front face of every box is
crossed so the heading can be checked as well as the size and position.

Python and UE5 world coordinates agree in this projection with no extra flip
(the scene loader's Y mirror and UE's left-handed camera cancel). The default
horizontal FOV is the one fitted to four squares of known position rendered in
the 3440x1440 game window: 121.6 degrees, under 1 px mean error. If the window
size changes, refit it (a different aspect ratio changes the horizontal FOV).

    PYTHONPATH=. python bin/overlay_boxes_3d.py --seed 42 --out boxes_out

Writes ``<out>/<view>.png`` for the views ``parked``, ``street`` and ``large``.
"""

import argparse
import asyncio
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw

from src.ground_truth.bbox_3d import (
    BoundingBox3D,
    extract_bboxes_3d_pedestrians,
    extract_bboxes_3d_vehicles,
)
from src.ground_truth.categories import BUS, PEDESTRIAN, SEDAN, SUV, TRUCK
from src.orchestration.dataset_generator import ScenarioResult, generate_scenario
from src.orchestration.scenario_serializer import serialize_scenario
from src.procedural.actor_placement import Vehicle
from src.procedural.environment import season_environment
from src.sensors.camera_model import Camera, CameraExtrinsics, CameraIntrinsics
from src.ue5.backend import UE5Backend
from src.utils.config_loader import load_scenario_config

SCREENSHOT = Path(r"F:\UE5Projects\VantageCV_UE5\Saved\rpc_debug_screenshot.png")
CAMERA_KEYS = ["cam_x", "cam_y", "cam_z", "target_x", "target_y", "target_z"]
WIDTH_PX, HEIGHT_PX = 3440, 1440
FITTED_HFOV_DEG = 121.6
NEAR_PLANE_M = 0.2
CAMERA_DISTANCE_M = 15.0
CAMERA_HEIGHT_M = 4.5
VIEW_ANGLE_RAD = np.radians(55.0)
NEIGHBOUR_RADIUS_M = 25.0
DRAW_RADIUS_M = 14.0
COLOURS: Dict[int, Tuple[int, int, int]] = {
    SEDAN: (255, 40, 40),
    SUV: (255, 150, 0),
    TRUCK: (255, 0, 220),
    BUS: (0, 200, 255),
    PEDESTRIAN: (60, 255, 60),
}
EDGES = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4)] + [
    (i, i + 4) for i in range(4)
]
FRONT_FACE = (1, 2, 6, 5)


def _clip_to_near(
    start: NDArray[np.float64], end: NDArray[np.float64]
) -> Optional[Tuple[NDArray[np.float64], NDArray[np.float64]]]:
    """Clip a camera-space segment to z >= the near plane, or drop it."""
    if start[2] < NEAR_PLANE_M and end[2] < NEAR_PLANE_M:
        return None
    if start[2] < NEAR_PLANE_M or end[2] < NEAR_PLANE_M:
        fraction = (NEAR_PLANE_M - start[2]) / (end[2] - start[2])
        cut = start + fraction * (end - start)
        return (cut, end) if start[2] < NEAR_PLANE_M else (start, cut)
    return start, end


def _pixel(camera: Camera, point_camera: NDArray[np.float64]) -> Tuple[float, float]:
    """Pinhole projection of a camera-space point."""
    matrix = camera.intrinsics.get_intrinsic_matrix()
    homogeneous = matrix @ (point_camera / point_camera[2])
    return float(homogeneous[0]), float(homogeneous[1])


def _draw_segment(
    draw: ImageDraw.ImageDraw,
    camera: Camera,
    ends: Tuple[NDArray[np.float64], NDArray[np.float64]],
    colour: Tuple[int, int, int],
    width: int,
) -> None:
    """Draw one world-space segment, clipped at the near plane."""
    to_camera = camera.extrinsics.world_to_camera
    clipped = _clip_to_near(to_camera(ends[0]), to_camera(ends[1]))
    if clipped is not None:
        draw.line(
            [_pixel(camera, clipped[0]), _pixel(camera, clipped[1])], fill=colour, width=width
        )


def _draw_box(draw: ImageDraw.ImageDraw, camera: Camera, box: BoundingBox3D, width: int) -> None:
    """The 12 edges of the box, plus a cross on its front (+x) face."""
    corners = box.corners()
    colour = COLOURS.get(box.category_id, (255, 255, 255))
    for first, second in EDGES:
        _draw_segment(draw, camera, (corners[first], corners[second]), colour, width)
    _draw_segment(draw, camera, (corners[FRONT_FACE[0]], corners[FRONT_FACE[2]]), colour, width)
    _draw_segment(draw, camera, (corners[FRONT_FACE[1]], corners[FRONT_FACE[3]]), colour, width)


def _camera_for(
    target: NDArray[np.float64], heading_rad: float
) -> Tuple[Camera, NDArray[np.float64]]:
    """An oblique camera looking at ``target`` from ahead-and-to-the-side."""
    angle = heading_rad + VIEW_ANGLE_RAD
    position = np.array(
        [
            target[0] + CAMERA_DISTANCE_M * np.cos(angle),
            target[1] + CAMERA_DISTANCE_M * np.sin(angle),
            CAMERA_HEIGHT_M,
        ]
    )
    look_at = np.array([target[0], target[1], 0.8])
    intrinsics = CameraIntrinsics.from_fov(FITTED_HFOV_DEG, WIDTH_PX, HEIGHT_PX)
    return Camera(intrinsics, CameraExtrinsics.looking_at(position, look_at)), position


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


def _boxes_in_view(scenario: ScenarioResult, target: Vehicle) -> List[BoundingBox3D]:
    """Every exported vehicle and pedestrian box near the target."""
    every = extract_bboxes_3d_vehicles(
        scenario.vehicles, id_offset=len(scenario.buildings)
    ) + extract_bboxes_3d_pedestrians(
        scenario.pedestrians, id_offset=len(scenario.buildings) + len(scenario.vehicles)
    )
    return [box for box in every if np.linalg.norm(box.center[:2] - target.center) < DRAW_RADIUS_M]


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
    for name, target in _pick_views(scenario).items():
        camera, position = _camera_for(
            np.array([target.box_center[0], target.box_center[1]]), target.heading_rad
        )
        path = args.out / f"{name}.png"
        await _photograph(backend, position, np.array([*target.box_center, 0.8]), path)
        picture = Image.open(path).convert("RGB")
        draw = ImageDraw.Draw(picture)
        for box in _boxes_in_view(scenario, target):
            is_target = box.object_id == target.vehicle_id + len(scenario.buildings)
            _draw_box(draw, camera, box, 6 if is_target else 3)
        picture.save(path)
        print(f"{name}: vehicle {target.vehicle_id} ({target.asset_path.split('/')[3]}) -> {path}")


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
