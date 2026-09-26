"""Generate a dataset of real UE5 frames with labels from the same camera.

For each scenario the conditions (time of day, weather) are drawn from the seed,
the scenario is generated and loaded into the game, and each requested view is
rendered. The labels of a frame come from ``render_frame`` with the camera the
game rendered through (``ue_camera``), so image and annotations share one model.
Every frame gets a QA overlay of its labels; the images carry their scenario
conditions and camera pose in the COCO ``images`` entries.

A run is crash-safe and resumable: each finished scenario is stored on its own (see
``dataset_store.py``), a failed scenario is retried after waiting for the game to answer
again, and rerunning the same command skips everything already finished.
"""

import hashlib
import time
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, TypeVar

import numpy as np
from PIL import Image, ImageDraw

from src.export.annotation_policy import AnnotationPolicy, apply_policy
from src.export.coco_exporter import CocoFrame, export_coco
from src.ground_truth.overlay import draw_box_3d
from src.orchestration.camera_sampling import (
    CameraPose,
    overview_pose,
    sample_ego_pose,
    sample_lot_pose,
)
from src.orchestration.dataset_generator import Bounds, generate_scenario, render_frame
from src.orchestration.dataset_store import DatasetStore
from src.orchestration.live_render import (
    RECOVERABLE_ERRORS,
    GameUnavailableError,
    LiveRenderer,
    ue_camera,
    vertical_fov_deg,
)
from src.orchestration.scenario_serializer import serialize_scenario
from src.procedural.environment import TimeOfDay, Weather, draw_weather, scenario_environment
from src.procedural.scenario import ScenarioTypeConfig

NIGHT_SHARE = 0.2
NIGHT_RAIN_SHARE = 0.2
PARTLY_HIDDEN_BELOW = 0.5
MAX_CALIBRATION_ERROR_PX = 3.0
MAX_VIEWS_PER_SCENARIO = 100
MAX_SCENARIO_ATTEMPTS = 3
T = TypeVar("T")
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

    rendered_scenarios: int = 0
    resumed_scenarios: int = 0
    skipped_scenarios: int = 0
    frames: int = 0
    calibration_error_px: float = 0.0
    elapsed_seconds: float = 0.0


def _views_for(
    scenario: Any, views: Tuple[str, ...], bounds: Bounds, seed: int
) -> List[CameraPose]:
    """The camera poses for one scenario; ego and lot views that find no valid pose are dropped."""
    rng = np.random.Generator(np.random.PCG64([seed, 0x51C3]))
    poses: List[CameraPose] = []
    for kind in views:
        if kind == "overview":
            pose: Optional[CameraPose] = overview_pose(bounds)
        elif kind == "lot":
            pose = sample_lot_pose(scenario, rng)
        else:
            pose = sample_ego_pose(scenario, rng, bounds)
        if pose is not None:
            poses.append(pose)
    return poses


def _save_qa(frame: CocoFrame, image_path: Path, qa_path: Path) -> None:
    """Draw the exported labels of ``frame`` on its image: 3D boxes (dimmed when mostly
    hidden), the exported 2D boxes in white and mesh silhouettes in cyan."""
    qa_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as source:
        picture = source.convert("RGB")
    draw = ImageDraw.Draw(picture)
    for box in frame.bboxes_2d:
        dimmed = box.visible_fraction < PARTLY_HIDDEN_BELOW
        draw_box_3d(draw, frame.camera, frame.bboxes_3d_by_id[box.object_id], 2, dimmed)
        draw.rectangle(
            [box.x_min, box.y_min, box.x_max, box.y_max], outline=(255, 255, 255), width=1
        )
        polygon = frame.silhouettes_by_id.get(box.object_id)
        if polygon is not None:
            draw.polygon([tuple(point) for point in polygon], outline=(0, 255, 255))
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


def _settings(
    config: ScenarioTypeConfig,
    bounds: Bounds,
    views: Tuple[str, ...],
    base_seed: int,
    policy: AnnotationPolicy,
) -> Dict[str, Any]:
    """The settings a run is identified by; a resume must match them."""
    return {
        "config_hash": hashlib.sha1(config.model_dump_json().encode("utf-8")).hexdigest(),
        "bounds": list(bounds),
        "views": list(views),
        "base_seed": base_seed,
        "night_share": NIGHT_SHARE,
        "night_rain_share": NIGHT_RAIN_SHARE,
        "vertical_fov_deg": round(vertical_fov_deg(), 4),
        "annotation_policy": policy.settings(),
    }


async def _render_scenario(  # pylint: disable=too-many-arguments,too-many-locals
    renderer: LiveRenderer,
    config: ScenarioTypeConfig,
    bounds: Bounds,
    output_dir: Path,
    index: int,
    views: Tuple[str, ...],
    seed: int,
    policy: AnnotationPolicy,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Generate, load and photograph one scenario; return its COCO images and annotations.

    A scenario the validator rejects has no frames (empty lists), the same every time.
    """
    conditions = draw_conditions(seed)
    try:
        scenario = generate_scenario(
            seed, config, bounds, f"live_{index:04d}", time_of_day=conditions[0]
        )
    except ValueError:
        return [], []
    environment = scenario_environment(scenario.season, conditions[0], conditions[1], seed)
    await renderer.load(serialize_scenario(scenario, environment))
    frames: List[CocoFrame] = []
    for view_index, pose in enumerate(_views_for(scenario, views, bounds, seed)):
        name = f"{scenario.scenario_id}_{view_index}_{pose.kind}"
        image_path = output_dir / "images" / f"{name}.png"
        width, height = await renderer.capture(pose.position, pose.look_at, image_path)
        camera = ue_camera(pose.position, pose.look_at, width, height)
        image_id = index * MAX_VIEWS_PER_SCENARIO + view_index
        frame = render_frame(scenario, camera, image_id, f"images/{name}.png")
        frame, dropped = apply_policy(frame, policy)
        frame.metadata = _frame_metadata(scenario, conditions, seed, pose)
        frame.metadata["dropped_annotations"] = dropped
        _save_qa(frame, image_path, output_dir / "qa" / f"{name}.png")
        frames.append(frame)
    coco = export_coco(frames, policy.profile)
    return coco["images"], coco["annotations"]


async def _with_recovery(
    renderer: LiveRenderer, label: str, operation: Callable[[], Awaitable[T]]
) -> T:
    """Run ``operation``; if the game fails, wait for it to answer again and retry.

    Raises ``GameUnavailableError`` after ``MAX_SCENARIO_ATTEMPTS`` failures.
    """
    for attempt in range(1, MAX_SCENARIO_ATTEMPTS + 1):
        try:
            return await operation()
        except RECOVERABLE_ERRORS as error:
            print(
                f"{label} attempt {attempt}/{MAX_SCENARIO_ATTEMPTS} failed: "
                f"{type(error).__name__}: {error}",
                flush=True,
            )
            if attempt == MAX_SCENARIO_ATTEMPTS:
                raise GameUnavailableError(
                    f"{label} failed {MAX_SCENARIO_ATTEMPTS} times; "
                    "rerun the same command to resume"
                ) from error
            await renderer.recover()
    raise AssertionError("unreachable")


async def generate_live_dataset(  # pylint: disable=too-many-locals,too-many-arguments
    renderer: LiveRenderer,
    config: ScenarioTypeConfig,
    bounds: Bounds,
    output_dir: Path,
    num_scenarios: int,
    base_seed: int,
    views: Tuple[str, ...] = DEFAULT_VIEWS,
    policy: Optional[AnnotationPolicy] = None,
) -> LiveDatasetResult:
    """Render ``num_scenarios`` scenarios x ``views``, resuming any earlier run in ``output_dir``.

    Raises ``ManifestMismatchError`` if ``output_dir`` holds a run with other settings and
    ``GameUnavailableError`` if the game stops answering (everything finished so far is
    kept; rerun the same command to continue).
    """
    started = time.perf_counter()
    policy = policy or AnnotationPolicy()
    store = DatasetStore(output_dir, export_coco([], policy.profile)["categories"])
    store.check_manifest(_settings(config, bounds, views, base_seed, policy))
    result = LiveDatasetResult()
    if any(store.load_part(index) is None for index in range(num_scenarios)):
        result.calibration_error_px = await _with_recovery(
            renderer,
            "camera check",
            lambda: renderer.calibration_error_px(output_dir / "calibration"),
        )
        if result.calibration_error_px > MAX_CALIBRATION_ERROR_PX:
            raise RuntimeError(
                f"camera model does not match the game (calibration error "
                f"{result.calibration_error_px:.2f} px > {MAX_CALIBRATION_ERROR_PX} px)"
            )
    try:
        for index in range(num_scenarios):
            existing = store.load_part(index)
            if existing is not None:
                result.resumed_scenarios += 1
                result.frames += len(existing["images"])
                continue
            images, annotations = await _with_recovery(
                renderer,
                f"scenario {index}",
                partial(
                    _render_scenario,
                    renderer,
                    config,
                    bounds,
                    output_dir,
                    index,
                    views,
                    base_seed + index,
                    policy,
                ),
            )
            store.save_part(index, images, annotations)
            result.frames += len(images)
            if images:
                result.rendered_scenarios += 1
            else:
                result.skipped_scenarios += 1
            print(
                f"scenario {index + 1}/{num_scenarios} seed {base_seed + index}: "
                f"{len(images)} frames, {result.frames} total, "
                f"{time.perf_counter() - started:.0f} s elapsed",
                flush=True,
            )
    finally:
        store.merge()
    result.elapsed_seconds = time.perf_counter() - started
    return result


def default_output_dir(base: Optional[Path] = None) -> Path:
    """A fresh output directory name under ``base`` (default ``live_dataset``)."""
    return (base or Path("live_dataset")) / time.strftime("%Y%m%d_%H%M%S")
