"""A camera + depth rig on the ego car, with a YOLO detector turning frames into obstacles.

``CameraRig.vision`` has the signature the harness's agent expects. It returns vehicles built from
this tick's detections: a box in the image plus the depth under it gives a position (pinhole model),
the detected class gives a standard size, and the heading is assumed to be the ego's own (a single
box cannot tell more). Nothing is read from the simulator's vehicle list except in ``record_gt``
mode, which only *scores* the detector against the true vehicles and never feeds the agent.
"""

import math
import queue
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from numpy.typing import NDArray

from carla_loop.harness import carla  # the CARLA module, with its path set up

CLASS_NAMES = {0: "person", 1: "car", 2: "bus", 3: "truck"}
VEHICLE_CLASSES = (1, 2, 3)
# half extents (x forward, y right, z up) in metres of the stand-in vehicle for each class
HALF_EXTENTS = {1: (2.3, 0.95, 0.75), 2: (5.5, 1.3, 1.5), 3: (3.2, 1.1, 1.4)}
DISTANCE_BINS = ((0.0, 15.0), (15.0, 30.0), (30.0, 50.0))
MAX_DEPTH_M = 150.0


@dataclass
class Detection:
    """One detected box: class id, confidence and pixel corners."""

    cls: int
    score: float
    box: Tuple[float, float, float, float]  # x1, y1, x2, y2


class PerceivedVehicle:
    """What the agent is given in place of a simulator vehicle: id, pose and a box, nothing more."""

    def __init__(self, ident: int, transform: Any, half_extents: Tuple[float, float, float]) -> None:
        self.id = ident
        self._transform = transform
        self.bounding_box = carla.BoundingBox(
            carla.Location(0.0, 0.0, half_extents[2]), carla.Vector3D(*half_extents)
        )

    def get_transform(self) -> Any:
        """Pose in the world."""
        return self._transform

    def get_location(self) -> Any:
        """Position in the world."""
        return self._transform.location


def intrinsics(width: int, height: int, fov_deg: float) -> NDArray[np.float64]:
    """Pinhole camera matrix of a CARLA camera."""
    focal = width / (2.0 * math.tan(math.radians(fov_deg) / 2.0))
    return np.array([[focal, 0.0, width / 2.0], [0.0, focal, height / 2.0], [0.0, 0.0, 1.0]])


def decode_depth(image: Any) -> NDArray[np.float32]:
    """Metres per pixel from a CARLA depth image (BGRA, 24-bit depth over a 1000 m range)."""
    raw = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(image.height, image.width, 4)
    value = raw[:, :, 2].astype(np.float32) + raw[:, :, 1] * 256.0 + raw[:, :, 0] * 65536.0
    return value / (256.0**3 - 1.0) * 1000.0


def iou(first: Sequence[float], second: Sequence[float]) -> float:
    """Intersection over union of two x1, y1, x2, y2 boxes."""
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right, bottom = min(first[2], second[2]), min(first[3], second[3])
    inter = max(0.0, right - left) * max(0.0, bottom - top)
    union = (first[2] - first[0]) * (first[3] - first[1]) + (second[2] - second[0]) * (
        second[3] - second[1]
    ) - inter
    return inter / union if union > 0.0 else 0.0


def project_box(
    vertices: Sequence[Any], inverse: NDArray[np.float64], k: NDArray[np.float64], size: Tuple[int, int]
) -> Optional[Tuple[Tuple[float, float, float, float], float]]:
    """(pixel box, depth of the centre) of a world-space box, or None if it is behind the camera."""
    points = np.array([[v.x, v.y, v.z, 1.0] for v in vertices]).T
    cam = inverse @ points  # CARLA camera frame: x forward, y right, z up
    if np.all(cam[0] < 0.5):
        return None
    ahead = cam[:, cam[0] > 0.5]
    uvw = k @ np.vstack([ahead[1], -ahead[2], ahead[0]])
    u, v = uvw[0] / uvw[2], uvw[1] / uvw[2]
    width, height = size
    box = (
        float(np.clip(u.min(), 0, width - 1)),
        float(np.clip(v.min(), 0, height - 1)),
        float(np.clip(u.max(), 0, width - 1)),
        float(np.clip(v.max(), 0, height - 1)),
    )
    if box[2] - box[0] < 4 or box[3] - box[1] < 4:
        return None
    return box, float(cam[0].mean())


@dataclass
class Score:
    """Counts of true vehicles seen by the detector, by kind and distance, and false boxes."""

    gt: Dict[str, int] = field(default_factory=dict)
    found: Dict[str, int] = field(default_factory=dict)
    called: Dict[str, Dict[str, int]] = field(default_factory=dict)  # kind|distance -> class -> boxes
    unmatched_boxes: int = 0  # vehicle boxes with no true vehicle (includes static parked props)
    frames: int = 0


class CameraRig:  # pylint: disable=too-many-instance-attributes
    """RGB and depth cameras at the ego's front, a detector, and (optionally) a scorer."""

    def __init__(
        self,
        weights: Optional[Path] = None,
        record_gt: bool = False,
        size: Tuple[int, int] = (1280, 720),
        fov_deg: float = 90.0,
        imgsz: int = 960,
        conf: float = 0.25,
    ) -> None:
        self.size, self.fov, self.conf, self.imgsz = size, fov_deg, conf, imgsz
        self.record_gt = record_gt
        self.k = intrinsics(size[0], size[1], fov_deg)
        self._model = None
        if weights is not None:
            from ultralytics import YOLO  # pylint: disable=import-outside-toplevel

            self._model = YOLO(str(weights))
        self._queues: Dict[str, "queue.Queue[Any]"] = {}
        self._rgb: Any = None
        self.detections: List[Detection] = []
        self._depth: Optional[NDArray[np.float32]] = None
        self._camera_transform: Any = None
        self._ego_yaw = 0.0
        self.score = Score()

    def attach(self, world: Any, ego: Any) -> List[Any]:
        """Spawn the two cameras on ``ego``; they are returned for cleanup."""
        library = world.get_blueprint_library()
        pose = carla.Transform(carla.Location(x=1.6, z=1.7))
        sensors = []
        for name, blueprint in (("rgb", "sensor.camera.rgb"), ("depth", "sensor.camera.depth")):
            bp = library.find(blueprint)
            bp.set_attribute("image_size_x", str(self.size[0]))
            bp.set_attribute("image_size_y", str(self.size[1]))
            bp.set_attribute("fov", str(self.fov))
            sensor = world.spawn_actor(bp, pose, attach_to=ego)
            self._queues[name] = queue.Queue()
            sensor.listen(self._queues[name].put)
            sensors.append(sensor)
        self._rgb = sensors[0]
        return sensors

    def _frame(self, name: str, frame: int) -> Any:
        while True:
            image = self._queues[name].get(timeout=30.0)
            if image.frame >= frame:
                return image

    def step(self, world: Any, ego: Any, frame: int) -> None:
        """Read this tick's images, detect, and (if asked) score against the true vehicles."""
        rgb = self._frame("rgb", frame)
        depth = self._frame("depth", frame)
        self._depth = decode_depth(depth)
        self._camera_transform = self._rgb.get_transform()
        self._ego_yaw = ego.get_transform().rotation.yaw
        self.detections = []
        if self._model is not None:
            array = np.frombuffer(rgb.raw_data, dtype=np.uint8).reshape(rgb.height, rgb.width, 4)
            result = self._model.predict(
                array[:, :, :3], imgsz=self.imgsz, conf=self.conf, iou=0.6, verbose=False
            )[0]
            for box, score, cls in zip(
                result.boxes.xyxy.cpu().numpy(), result.boxes.conf.cpu().numpy(), result.boxes.cls.cpu().numpy()
            ):
                self.detections.append(Detection(int(cls), float(score), tuple(float(b) for b in box)))
        if self.record_gt:
            self._score(world, ego)

    def vision(self, _world: Any, _ego: Any) -> List[PerceivedVehicle]:
        """The detected vehicles as obstacles (the function the agent calls)."""
        found: List[PerceivedVehicle] = []
        assert self._depth is not None
        for index, det in enumerate(self.detections):
            if det.cls not in VEHICLE_CLASSES:
                continue
            x1, y1, x2, y2 = (int(round(v)) for v in det.box)
            patch = self._depth[y1 + (y2 - y1) // 2 : y2, x1 + (x2 - x1) // 5 : max(x2 - (x2 - x1) // 5, x1 + 1)]
            if patch.size == 0:
                continue
            depth = float(np.median(patch))
            if not 0.5 < depth < MAX_DEPTH_M:
                continue
            half = HALF_EXTENTS[det.cls]
            centre_u = (det.box[0] + det.box[2]) / 2.0
            lateral = (centre_u - self.k[0, 2]) / self.k[0, 0] * depth
            local = carla.Location(x=depth + half[0], y=lateral, z=-1.7 + half[2])
            world_location = self._camera_transform.transform(local)
            transform = carla.Transform(world_location, carla.Rotation(yaw=self._ego_yaw))
            found.append(PerceivedVehicle(-(index + 1), transform, half))
        return found

    def _score(self, world: Any, ego: Any) -> None:
        inverse = np.array(self._camera_transform.get_inverse_matrix())
        truth: List[Tuple[Tuple[float, float, float, float], str, float]] = []
        every_box: List[Tuple[float, float, float, float]] = []  # all true vehicles, any distance
        for vehicle in world.get_actors().filter("*vehicle*"):
            if vehicle.id == ego.id:
                continue
            reach = vehicle.get_location().distance(ego.get_location())
            projected = project_box(
                vehicle.bounding_box.get_world_vertices(vehicle.get_transform()), inverse, self.k, self.size
            )
            if projected is None:
                continue
            box, centre_depth = projected
            every_box.append(box)
            if reach > DISTANCE_BINS[-1][1]:
                continue
            u, v = int((box[0] + box[2]) / 2), int((box[1] + box[3]) / 2)
            assert self._depth is not None
            seen = float(np.median(self._depth[max(v - 2, 0) : v + 3, max(u - 2, 0) : u + 3]))
            if abs(seen - centre_depth) > vehicle.bounding_box.extent.x + 1.5:
                continue  # hidden behind something nearer
            kind = str(vehicle.attributes.get("base_type", "car"))
            truth.append((box, kind, reach))
        s = self.score
        s.frames += 1
        matched = set()
        for box, kind, reach in truth:
            bin_name = next(f"{lo:.0f}-{hi:.0f}m" for lo, hi in DISTANCE_BINS if reach < hi)
            key = f"{kind}|{bin_name}"
            s.gt[key] = s.gt.get(key, 0) + 1
            best, best_iou = None, 0.0
            for index, det in enumerate(self.detections):
                if det.cls in VEHICLE_CLASSES and iou(box, det.box) > best_iou:
                    best, best_iou = index, iou(box, det.box)
            if best is not None and best_iou >= 0.5:
                matched.add(best)
                s.found[key] = s.found.get(key, 0) + 1
                name = CLASS_NAMES[self.detections[best].cls]
                s.called.setdefault(key, {})[name] = s.called.setdefault(key, {}).get(name, 0) + 1
        for index, det in enumerate(self.detections):
            if det.cls in VEHICLE_CLASSES and index not in matched:
                if all(iou(box, det.box) < 0.3 for box in every_box):
                    s.unmatched_boxes += 1

    def report(self) -> Dict[str, Any]:
        """The scorer's counts as plain data."""
        s = self.score
        return {
            "frames": s.frames,
            "gt": s.gt,
            "found": s.found,
            "called": s.called,
            "unmatched_boxes": s.unmatched_boxes,
        }
