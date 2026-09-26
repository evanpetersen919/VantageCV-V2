"""Generate a dataset of real UE5 frames with labels from the same camera.

For each scenario the conditions (time of day, weather) are drawn from the seed,
the scenario is generated and loaded into the game, and each requested view is
rendered. The labels of a frame come from ``render_frame`` with the camera the
game rendered through (``ue_camera``), so image and annotations share one model.
Every frame gets a QA overlay of its labels; the images carry their scenario
conditions and camera pose in the COCO ``images`` entries.
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw

from src.export.coco_exporter import CocoFrame, export_coco
from src.ground_truth.overlay import draw_box_3d
from src.orchestration.camera_sampling import CameraPose, overview_pose, sample_ego_pose
from src.orchestration.dataset_generator import Bounds, generate_scenario, render_frame, write_json
from src.orchestration.live_render import LiveRenderer, ue_camera, vertical_fov_deg
from src.orchestration.scenario_serializer import serialize_scenario
from src.procedural.environment import TimeOfDay, Weather, draw_weather, scenario_environment
from src.procedural.scenario import ScenarioTypeConfig

NIGHT_SHARE = 0.2
NIGHT_RAIN_SHARE = 0.2
PARTLY_HIDDEN_BELOW = 0.5
MAX_CALIBRATION_ERROR_PX = 3.0
DEFAULT_VIEWS: Tuple[str, ...] = ("ego", "ego", "overview")


def draw_conditions(seed: int) -> Tuple[TimeOfDay, Weather]:
    """Time of day and weather for ``seed``, each from its own RNG stream.

    ``NIGHT_SHARE`` of scenarios are at night (a design choice). Night takes clear or
    rain only (its moonlit sky is kept); day draws from ``WEATHER_SHARES``.
    """
    rng = np.random.Generator(np.random.PCG64([seed, 0x7D1A]))
    if rng.random() < NIGHT_SHARE:
        return TimeOfDay.NIGHT, Weather.RAIN if rng.random() < NIGHT_RAIN_SHARE else Weather.CLEAR
    return TimeOfDay.DAY, draw_weather(seed)


@dataclass
class LiveDatasetResult:
    """What a run produced."""

    frames: List[CocoFrame] = field(default_factory=list)
    skipped_scenarios: int = 0
    skipped_views: int = 0
    calibration_error_px: float = 0.0
    elapsed_seconds: float = 0.0


def _views_for(
    scenario: Any, views: Tuple[str, ...], bounds: Bounds, seed: int
) -> List[CameraPose]:
    """The camera poses for one scenario; ego views that find no valid pose are dropped."""
    rng = np.random.Generator(np.random.PCG64([seed, 0x51C3]))
    poses: List[CameraPose] = []
    for kind in views:
        pose = overview_pose(bounds) if kind == "overview" else sample_ego_pose(scenario, rng)
        if pose is not None:
            poses.append(pose)
    return poses


def _save_qa(frame: CocoFrame, image_path: Path, qa_path: Path) -> None:
    """Draw the exported 3D boxes of ``frame`` on its image."""
    qa_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as source:
        picture = source.convert("RGB")
    draw = ImageDraw.Draw(picture)
    visible = {box.object_id: box.visible_fraction for box in frame.bboxes_2d}
    for object_id, fraction in visible.items():
        draw_box_3d(
            draw, frame.camera, frame.bboxes_3d_by_id[object_id], 2, fraction < PARTLY_HIDDEN_BELOW
        )
    picture.save(qa_path)


def _frame_metadata(
    scenario: Any, conditions: Tuple[TimeOfDay, Weather], seed: int, pose: CameraPose
) -> Dict[str, Any]:
    """Per-image fields: scenario conditions and the camera pose."""
    time_of_day, weather = conditions
    return {
        "scenario_id": scenario.scenario_id,
        "seed": seed,
        "season": scenario.season.value,
        "time_of_day": time_of_day.value,
        "weather": weather.value,
        "view": pose.kind,
        "camera_position": [round(float(value), 3) for value in pose.position],
        "camera_look_at": [round(float(value), 3) for value in pose.look_at],
        "vertical_fov_deg": round(vertical_fov_deg(), 4),
        "num_parking_lots": len(scenario.parking_lots),
    }


async def generate_live_dataset(  # pylint: disable=too-many-locals,too-many-arguments
    renderer: LiveRenderer,
    config: ScenarioTypeConfig,
    bounds: Bounds,
    output_dir: Path,
    num_scenarios: int,
    base_seed: int,
    views: Tuple[str, ...] = DEFAULT_VIEWS,
) -> LiveDatasetResult:
    """Render ``num_scenarios`` scenarios x ``views`` and write images, QA overlays and COCO."""
    started = time.perf_counter()
    result = LiveDatasetResult()
    result.calibration_error_px = await renderer.calibration_error_px(output_dir / "calibration")
    if result.calibration_error_px > MAX_CALIBRATION_ERROR_PX:
        raise RuntimeError(
            f"camera model does not match the game (calibration error "
            f"{result.calibration_error_px:.2f} px > {MAX_CALIBRATION_ERROR_PX} px)"
        )
    for index in range(num_scenarios):
        seed = base_seed + index
        conditions = draw_conditions(seed)
        try:
            scenario = generate_scenario(
                seed, config, bounds, f"live_{index:04d}", time_of_day=conditions[0]
            )
        except ValueError:
            result.skipped_scenarios += 1
            continue
        environment = scenario_environment(scenario.season, conditions[0], conditions[1], seed)
        await renderer.load(serialize_scenario(scenario, environment))
        for view_index, pose in enumerate(_views_for(scenario, views, bounds, seed)):
            name = f"{scenario.scenario_id}_{view_index}_{pose.kind}"
            image_path = output_dir / "images" / f"{name}.png"
            width, height = await renderer.capture(pose.position, pose.look_at, image_path)
            camera = ue_camera(pose.position, pose.look_at, width, height)
            frame = render_frame(scenario, camera, len(result.frames), f"images/{name}.png")
            frame.metadata = _frame_metadata(scenario, conditions, seed, pose)
            _save_qa(frame, image_path, output_dir / "qa" / f"{name}.png")
            result.frames.append(frame)
        print(
            f"scenario {index + 1}/{num_scenarios} seed {seed} {conditions[0].value}/"
            f"{conditions[1].value}: {len(result.frames)} frames so far",
            flush=True,
        )
    write_json(output_dir / "annotations.json", export_coco(result.frames))
    result.elapsed_seconds = time.perf_counter() - started
    return result


def default_output_dir(base: Optional[Path] = None) -> Path:
    """A fresh output directory name under ``base`` (default ``live_dataset``)."""
    return (base or Path("live_dataset")) / time.strftime("%Y%m%d_%H%M%S")
