"""Measure every City Sample pedestrian body's real extents per animation frame.

Pedestrians are animated by vertex-animation textures, so their meshes cannot give
the posed shape. Instead each (gender, weight) body is rendered in the running game
at every 10th frame of its 430-frame animation, eight to a picture, against a white
wall under overcast light (no hard shadows), from the side and from the front. The
silhouette against the empty scene gives, relative to the pedestrian's pivot, the
forward and backward extent, the left and right extent, and the head-top height. The
result is written as ``src/procedural/pedestrian_bounds.py``:

    PYTHONPATH=. python bin/measure_pedestrian_extents.py

Needs a running UE5 game with the plugin.
"""

import asyncio
import tempfile
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from scipy import ndimage

from src.orchestration.live_render import LiveRenderer, vertical_fov_deg
from src.orchestration.scenario_serializer import _mesh_to_json, _pedestrian_to_asset_json
from src.procedural.actor_placement import Pedestrian
from src.procedural.city_sample_assets import (
    PEDESTRIAN_BODY_ASSET_PATHS,
    PEDESTRIAN_BOTTOM_ASSET_PATHS,
    PEDESTRIAN_FACE_ASSET_PATHS,
    PEDESTRIAN_SHOE_ASSET_PATHS,
    PEDESTRIAN_TOP_ASSET_PATHS,
    pedestrian_face_and_hair,
)
from src.procedural.environment import Season, TimeOfDay, Weather, scenario_environment
from src.procedural.mesh_factory import Mesh, flat_quad_mesh
from src.ue5.backend import UE5Backend

WORK_DIR = Path(tempfile.gettempdir()) / "ped_extents"
OUTPUT = Path("src/procedural/pedestrian_bounds.py")
FRAME_COUNT = 430
FRAME_STEP = 10
DISTANCE_M = 8.0
CAMERA_HEIGHT_M = 0.9
PER_PICTURE = 8
HEAD_FRAME = 20
SPACING_M = 2.4
WALL_DISTANCE_M = 5.0
DIFFERENCE_THRESHOLD = 30.0
FOOT_MARGIN_M = 0.1
WINDOW_HALF_PX = 100
REFERENCE_PATCH = (slice(900, 1060), slice(100, 400))
Record = Tuple[str, str, int, int]  # gender, weight, animation frame, face index


def _wall(vertical_axis: str) -> Mesh:
    """A big white wall behind the pedestrians: along x at +y (side view) or along y at -x."""
    if vertical_axis == "side":
        corners = [[-40, WALL_DISTANCE_M, 0], [40, WALL_DISTANCE_M, 0]]
        corners += [[40, WALL_DISTANCE_M, 20], [-40, WALL_DISTANCE_M, 20]]
    else:
        corners = [[-WALL_DISTANCE_M, -40, 0], [-WALL_DISTANCE_M, 40, 0]]
        corners += [[-WALL_DISTANCE_M, 40, 20], [-WALL_DISTANCE_M, -40, 20]]
    vertices = np.array(corners, dtype=float)
    return Mesh(
        vertices=vertices,
        triangles=np.array([0, 1, 2, 0, 2, 3]),  # faces the camera; a second winding z-fights
        uvs=vertices[:, [0, 2]] / 4.0,
        material="paint_white",
    )


def _scene_meshes(view: str) -> List[Dict[str, object]]:
    """Ground plus the wall for ``view``."""
    ground = flat_quad_mesh(-40.0, -40.0, 40.0, 40.0, 0.0, 4.0, "asphalt")
    return [_mesh_to_json(ground), _mesh_to_json(_wall(view))]


def _pedestrian(index: int, job: Record, position: Sequence[float]) -> Pedestrian:
    """The pedestrian of ``job`` (body, frame, face and its hair) at ``position``, facing +x,
    in the first listed outfit."""
    gender, weight, frame, face_index = job
    face = PEDESTRIAN_FACE_ASSET_PATHS[gender][face_index]
    parts = [
        PEDESTRIAN_TOP_ASSET_PATHS[(gender, weight)][0],
        PEDESTRIAN_BOTTOM_ASSET_PATHS[(gender, weight)][0],
        PEDESTRIAN_SHOE_ASSET_PATHS[(gender, weight)][0],
        face,
    ]
    hair = pedestrian_face_and_hair(gender, face)
    if hair is not None:
        parts.append(hair)
    return Pedestrian(
        pedestrian_id=index,
        center=np.array(position, dtype=float),
        heading_rad=0.0,
        asset_path=PEDESTRIAN_BODY_ASSET_PATHS[(gender, weight)],
        part_paths=parts,
        pose_frame=float(frame),
        surface_z=0.0,
    )


def _normalised(path: Path, reference: NDArray[np.float64]) -> NDArray[np.float64]:
    """The picture's luminance, scaled so its ground patch matches the reference's."""
    picture = np.asarray(Image.open(path).convert("RGB"), dtype=float).mean(axis=2)
    ratio = np.median(reference[REFERENCE_PATCH]) / np.median(picture[REFERENCE_PATCH])
    return np.asarray(picture * ratio)


def _column_extents(
    mask: NDArray[np.bool_], centre_px: int, focal_px: float
) -> Tuple[float, float, float]:
    """(left, right, top-row offset) of the silhouette in a window around ``centre_px``:
    horizontal extents in metres from the window centre, head top as pixel row."""
    window = mask[:, centre_px - WINDOW_HALF_PX : centre_px + WINDOW_HALF_PX]
    rows, columns = np.nonzero(window)
    if rows.size < 50:
        return 0.0, 0.0, -1.0
    scale = DISTANCE_M / focal_px
    return (
        (columns.min() - WINDOW_HALF_PX) * scale,
        (columns.max() + 1 - WINDOW_HALF_PX) * scale,
        float(rows.min()),
    )


def _camera_pose(view: str) -> Tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Camera position and look-at for the side (from -y) or front (from +x) view."""
    look_at = np.array([0.0, 0.0, CAMERA_HEIGHT_M])
    if view == "side":
        return np.array([0.0, -DISTANCE_M, CAMERA_HEIGHT_M]), look_at
    return np.array([DISTANCE_M, 0.0, CAMERA_HEIGHT_M]), look_at


def _silhouette(path: Path, empty: NDArray[np.float64], focal_px: float) -> NDArray[np.bool_]:
    """Pixels of ``path`` that differ from the empty scene, above the feet line."""
    mask = ndimage.binary_opening(
        np.abs(_normalised(path, empty) - empty) > DIFFERENCE_THRESHOLD, iterations=2
    )
    mask[int(540 + (CAMERA_HEIGHT_M - FOOT_MARGIN_M) * focal_px / DISTANCE_M) :, :] = False
    return np.asarray(mask)


async def _measure_view(  # pylint: disable=too-many-locals
    renderer: LiveRenderer, view: str, jobs: List[Record], focal_px: float
) -> Dict[Record, Tuple[float, float, float]]:
    """Render every job in ``view``, eight to a picture; return extents per job."""
    meshes = _scene_meshes(view)
    positions = [-SPACING_M * (PER_PICTURE - 1) / 2.0 + SPACING_M * k for k in range(PER_PICTURE)]
    camera, look_at = _camera_pose(view)
    environment = scenario_environment(Season.SUMMER, TimeOfDay.DAY, Weather.OVERCAST, 1).to_json()
    await renderer.load({"meshes": meshes, "assets": [], "environment": environment})
    await renderer.capture(camera, look_at, WORK_DIR / f"empty_{view}.png")
    picture = Image.open(WORK_DIR / f"empty_{view}.png").convert("RGB")
    empty = np.asarray(picture, dtype=float).mean(axis=2)
    results: Dict[Record, Tuple[float, float, float]] = {}
    for start in range(0, len(jobs), PER_PICTURE):
        chunk = jobs[start : start + PER_PICTURE]
        placed = [
            _pedestrian(i, job, (positions[i], 0.0) if view == "side" else (0.0, positions[i]))
            for i, job in enumerate(chunk)
        ]
        assets = [_pedestrian_to_asset_json(p, i) for i, p in enumerate(placed)]
        await renderer.load({"meshes": meshes, "assets": assets, "environment": environment})
        path = WORK_DIR / f"{view}_{start}.png"
        await renderer.capture(camera, look_at, path)
        mask = _silhouette(path, empty, focal_px)
        for i, job in enumerate(chunk):
            centre = int(960 + positions[i] / DISTANCE_M * focal_px)
            results[job] = _column_extents(mask, centre, focal_px)
        print(f"{view}: {min(start + PER_PICTURE, len(jobs))}/{len(jobs)}", flush=True)
    return results


def _head_heights(
    heads: Dict[Record, Tuple[float, float, float]], focal_px: float
) -> Dict[str, float]:
    """Head-top height per ``<gender>_<character id>`` from the head-pass silhouettes."""
    heights = {}
    for (gender, _, _, face_index), (_, _, top_row) in heads.items():
        face = PEDESTRIAN_FACE_ASSET_PATHS[gender][face_index]
        heights[f"{gender}_{face.split('/')[-1].split('_')[2]}"] = round(
            CAMERA_HEIGHT_M + (540 - top_row) * DISTANCE_M / focal_px, 3
        )
    return heights


def _pose_rows(
    side: Dict[Record, Tuple[float, float, float]], front: Dict[Record, Tuple[float, float, float]]
) -> Dict[str, List[List[float]]]:
    """(frame, forward min/max, lateral min/max) rows per ``<gender>_<weight>``."""
    rows: Dict[str, List[List[float]]] = {}
    for job, (forward_min, forward_max, _) in side.items():
        lateral_min, lateral_max, _ = front[job]
        rows.setdefault(f"{job[0]}_{job[1]}", []).append(
            [job[2], forward_min, forward_max, lateral_min, lateral_max]
        )
    return rows


async def _run() -> Tuple[Dict[str, List[List[float]]], Dict[str, float]]:
    """Measure all bodies and frames from both views, and every character's head top."""
    WORK_DIR.mkdir(exist_ok=True)
    focal_px = 1080 / 2 / np.tan(np.radians(vertical_fov_deg()) / 2.0)
    frames = list(range(0, FRAME_COUNT, FRAME_STEP))
    jobs = [(g, w, f, 0) for (g, w) in PEDESTRIAN_BODY_ASSET_PATHS for f in frames]
    head_jobs = [
        (g, "nrw", HEAD_FRAME, index)
        for g, faces in PEDESTRIAN_FACE_ASSET_PATHS.items()
        for index in range(len(faces))
    ]
    async with UE5Backend("ws://localhost:8765", timeout_seconds=300.0) as backend:
        renderer = LiveRenderer(backend, load_seconds=6.0)
        heads = await _measure_view(renderer, "side", head_jobs, focal_px)
        side = await _measure_view(renderer, "side", jobs, focal_px)
        front = await _measure_view(renderer, "front", jobs, focal_px)
    return _pose_rows(side, front), _head_heights(heads, focal_px)


def render_module(rows: Dict[str, List[List[float]]], head_heights: Dict[str, float]) -> str:
    """The source of ``src/procedural/pedestrian_bounds.py`` for the measured data."""
    lines = [
        '"""Measured pedestrian extents: GENERATED by ``bin/measure_pedestrian_extents.py``.',
        "",
        "``PEDESTRIAN_POSE_EXTENTS[<gender>_<weight>]`` rows are (animation frame, forward min,",
        "forward max, lateral min, lateral max) in metres relative to the pivot at the feet,",
        "forward along the pedestrian's heading and lateral to its left.",
        "``PEDESTRIAN_HEAD_HEIGHTS`` gives the head-top height, hair included, per",
        '``<gender>_<character id>``."""',
        "",
        "from typing import Dict, Tuple",
        "",
        "Row = Tuple[float, float, float, float, float]",
        "",
        "PEDESTRIAN_POSE_EXTENTS: Dict[str, Tuple[Row, ...]] = {",
    ]
    for key, entries in sorted(rows.items()):
        lines.append(f'    "{key}": (')
        lines += [f"        {tuple(round(value, 3) for value in row)}," for row in entries]
        lines.append("    ),")
    lines += ["}", "", "PEDESTRIAN_HEAD_HEIGHTS: Dict[str, float] = {"]
    lines += [f'    "{key}": {value},' for key, value in sorted(head_heights.items())]
    lines += ["}", ""]
    return "\n".join(lines)


def main() -> None:
    """Measure and write the data module."""
    rows, head_heights = asyncio.run(_run())
    OUTPUT.write_text(render_module(rows, head_heights), encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
