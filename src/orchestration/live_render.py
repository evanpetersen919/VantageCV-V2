"""Render real frames from the running UE5 game with a known camera model.

The labels of a frame are projected through a ``Camera``; that only means
anything if the game renders through the same pinhole. This module builds that
camera from first principles and checks it against the engine.

UE5's default camera FOV is 90 degrees *horizontal at a 4:3 aspect*, and the
engine keeps the vertical FOV fixed when the window has another aspect (measured
at 3440x1440 and 1920x1080: 73.4 degrees vertical fitted, 73.74 analytic). So the
vertical FOV is ``2 atan(tan(45 deg) * 3/4)`` and the horizontal FOV follows the
image size. Python and UE5 world coordinates agree with no extra flip.
"""

import asyncio
import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import websockets
import websockets.exceptions
from numpy.typing import NDArray
from PIL import Image
from scipy import ndimage

from src.orchestration.scenario_serializer import _mesh_to_json
from src.procedural.mesh_factory import flat_quad_mesh
from src.sensors.camera_model import Camera, CameraExtrinsics, CameraIntrinsics
from src.ue5.backend import UE5Backend, UE5CommunicationTimeoutError, UE5RPCError

UE_DEFAULT_FOV_DEG = 90.0
UE_FOV_REFERENCE_ASPECT = 4.0 / 3.0
DEFAULT_SCREENSHOT = Path(r"F:\UE5Projects\VantageCV_UE5\Saved\rpc_debug_screenshot.png")
CAMERA_KEYS = ["cam_x", "cam_y", "cam_z", "target_x", "target_y", "target_z"]
METERS_TO_UE_UNITS = 100.0
FILE_POLL_SECONDS = 0.2
FILE_TIMEOUT_SECONDS = 30.0
FILE_STABLE_SECONDS = 0.4

CALIBRATION_SQUARE_CENTRES = [(10.0, 0.0), (10.0, 12.0), (24.0, -8.0), (24.0, 10.0)]
CALIBRATION_HALF_SIDE_M = 1.0
CALIBRATION_CAMERA = (np.array([-8.0, -20.0, 14.0]), np.array([14.0, 2.0, 0.0]))
CALIBRATION_MATCH_RADIUS_PX = 40.0
WHITE_LEVEL = 190
RECOVERABLE_ERRORS = (
    TimeoutError,
    UE5CommunicationTimeoutError,
    UE5RPCError,
    ConnectionError,
    OSError,
    websockets.exceptions.WebSocketException,
)


class GameUnavailableError(RuntimeError):
    """The game stopped answering and did not come back."""


def vertical_fov_deg() -> float:
    """UE5's fixed vertical FOV: its 90 degree default is defined at a 4:3 aspect."""
    half = np.radians(UE_DEFAULT_FOV_DEG) / 2.0
    return float(2.0 * np.degrees(np.arctan(np.tan(half) / UE_FOV_REFERENCE_ASPECT)))


def ue_camera(
    position: NDArray[np.float64], look_at: NDArray[np.float64], width: int, height: int
) -> Camera:
    """The pinhole camera the engine renders a ``width`` x ``height`` frame with."""
    half_vertical = np.radians(vertical_fov_deg()) / 2.0
    horizontal = 2.0 * np.degrees(np.arctan(np.tan(half_vertical) * width / height))
    intrinsics = CameraIntrinsics.from_fov(float(horizontal), width, height)
    return Camera(intrinsics, CameraExtrinsics.looking_at(position, look_at))


def _to_ue(point: NDArray[np.float64]) -> List[float]:
    """A python-world point as UE centimetres (Y mirrored)."""
    return [
        float(point[0]) * METERS_TO_UE_UNITS,
        -float(point[1]) * METERS_TO_UE_UNITS,
        float(point[2]) * METERS_TO_UE_UNITS,
    ]


class LiveRenderer:
    """Loads scenarios into the game and captures frames from a given camera pose."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        backend: UE5Backend,
        screenshot_path: Path = DEFAULT_SCREENSHOT,
        settle_seconds: float = 3.0,
        load_seconds: float = 10.0,
        payload_path: Path = Path(tempfile.gettempdir()) / "vantagecv_scenario.json",
    ) -> None:
        self._backend = backend
        self._payload_path = payload_path
        self._screenshot_path = screenshot_path
        self._settle_seconds = settle_seconds
        self._load_seconds = load_seconds

    async def load(self, payload: Dict[str, Any]) -> None:
        """Replace the scene with ``payload`` and wait for it to finish streaming in.

        The payload goes to the game as a file (see ``UE5Backend.load_scenario_file``).
        """
        self._payload_path.parent.mkdir(parents=True, exist_ok=True)
        self._payload_path.write_text(json.dumps(payload), encoding="utf-8")
        await self._backend.load_scenario_file(self._payload_path)
        await asyncio.sleep(self._load_seconds)

    async def recover(self, wait_seconds: float = 20.0, attempts: int = 12) -> None:
        """Wait for a hung or restarting game to answer again, reconnecting each try.

        Raises ``GameUnavailableError`` if it never does (about ``wait_seconds * attempts``).
        """
        for _ in range(attempts):
            await asyncio.sleep(wait_seconds)
            try:
                await self._backend.reconnect()
                await self._backend.ping()
                return
            except RECOVERABLE_ERRORS:
                continue
        raise GameUnavailableError(
            f"the game did not answer for {wait_seconds * attempts:.0f} s; restart it and rerun "
            "the same command to resume"
        )

    async def _wait_for_new_file(self, since: float) -> None:
        """Block until the screenshot file is newer than ``since`` and has stopped growing."""
        deadline = time.monotonic() + FILE_TIMEOUT_SECONDS
        last_size = -1
        stable_since = 0.0
        while time.monotonic() < deadline:
            if self._screenshot_path.exists() and self._screenshot_path.stat().st_mtime > since:
                size = self._screenshot_path.stat().st_size
                if size == last_size and time.monotonic() - stable_since >= FILE_STABLE_SECONDS:
                    return
                if size != last_size:
                    last_size, stable_since = size, time.monotonic()
            await asyncio.sleep(FILE_POLL_SECONDS)
        raise TimeoutError("the game did not write a screenshot")

    async def capture(
        self, position: NDArray[np.float64], look_at: NDArray[np.float64], out_path: Path
    ) -> Tuple[int, int]:
        """Render a frame from ``position`` to ``look_at``; save it; return (width, height)."""
        pose = dict(zip(CAMERA_KEYS, _to_ue(position) + _to_ue(look_at)))
        await self._backend.call("DebugMoveCameraTo", pose)
        await asyncio.sleep(self._settle_seconds)
        started = time.time()
        await self._backend.call("TakeScreenshot", {"filename": out_path.name})
        await self._wait_for_new_file(started)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(self._screenshot_path, out_path)
        with Image.open(out_path) as picture:
            return picture.size

    async def calibration_error_px(self, work_dir: Path) -> float:
        """Mean pixel error between four known ground squares as rendered and as projected.

        Loads a flat scene with four white squares, renders it, finds each square in the
        picture and compares it with where ``ue_camera`` says it should be. Returns inf if
        a square cannot be found near its predicted position.
        """
        meshes = [_mesh_to_json(flat_quad_mesh(-80.0, -80.0, 80.0, 80.0, 0.0, 4.0, "asphalt"))]
        for x, y in CALIBRATION_SQUARE_CENTRES:
            half = CALIBRATION_HALF_SIDE_M
            meshes.append(
                _mesh_to_json(
                    flat_quad_mesh(x - half, y - half, x + half, y + half, 0.02, 4.0, "paint_white")
                )
            )
        await self.load({"meshes": meshes, "assets": []})
        path = work_dir / "calibration.png"
        width, height = await self.capture(*CALIBRATION_CAMERA, path)
        return self._measure_error(path, ue_camera(*CALIBRATION_CAMERA, width, height))

    @staticmethod
    def _measure_error(path: Path, camera: Camera) -> float:
        """Mean distance from each square's projected centre to its nearest white blob."""
        with Image.open(path) as picture:
            bright = np.asarray(picture.convert("RGB")).min(axis=2) > WHITE_LEVEL
        labels, count = ndimage.label(bright)
        blobs = [
            np.array(ndimage.center_of_mass(labels == index)[::-1])
            for index in range(1, count + 1)
            if 100 < (labels == index).sum() < 8000
        ]
        errors = []
        for x, y in CALIBRATION_SQUARE_CENTRES:
            pixel, _ = camera.project(np.array([x, y, 0.02]))
            if pixel is None or not blobs:
                return float("inf")
            nearest = min(float(np.linalg.norm(blob - pixel)) for blob in blobs)
            if nearest > CALIBRATION_MATCH_RADIUS_PX:
                return float("inf")
            errors.append(nearest)
        return float(np.mean(errors))
