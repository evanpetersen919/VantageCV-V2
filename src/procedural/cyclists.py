"""Cyclists: a Rocketbox rider on the project's parametric bicycle, riding along the road.

``cyclists: true`` in a scenario config places riders near the curb of the driving lanes, in the
direction of travel, clear of every vehicle and of the intersections' crosswalks and queues. A
cyclist is two objects with two labels, as BDD100K labels them: the rider (class ``rider``, the
person) and the bicycle (class ``bike``), each with its own exact mask and box.

The meshes were baked once by ``bin/bake_riders.py`` (Blender, then the ImportAssets commandlet):
per avatar, four right-crank angles of the rider seated on the bicycle with hands on the grips and
feet on the pedals (contact errors under 0.001 mm, see ``docs/riders/step2_bicycle_spike.md``),
and the bicycle as 13 part meshes per crank angle. Rider and bicycle share one frame, so placing
both at the same transform puts the rider on the bike. Both face +Y at rotation 0, like the
Rocketbox pedestrians, and are turned to their heading the same way.

Measured sizes (Blender bounds of the baked FBX files, metres, in the mesh frame, ``MESH_BOUNDS``):
the bicycle is 0.66 wide, 1.762 long (y from -0.791 to +0.971) and 0.954 high; a seated rider is
about 0.6 wide, 0.83 deep and reaches 1.75 m. What is a choice, not a measurement, is where
cyclists ride (a lateral offset from the curb), how many there are and which avatar and crank
angle each takes; the report on the generated data says so.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np
import numpy.typing as npt

from src.procedural.actor_placement import Vehicle
from src.procedural.lane_topology import Lane
from src.procedural.road_edge_kit import edge_runs
from src.procedural.road_network import RoadEdge

ASSET_ROOT = "/Game/VantageCV/Riders/Spike"
AVATARS: Tuple[str, ...] = ("Female_Adult_01", "Male_Adult_01", "Male_Adult_05")
CRANK_ANGLES: Tuple[int, ...] = (0, 90, 180, 270)
BIKE_FRAME_PART = "frame"
BIKE_OTHER_PARTS: Tuple[str, ...] = (
    "cranks_pedals",
    "fork_bars",
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
# Measured: (min x, min y, min z, max x, max y, max z) in the mesh frame, metres.
BIKE_BOUNDS = (-0.330, -0.7913, 0.0, 0.330, 0.9707, 0.9542)
RIDER_BOUNDS: Dict[str, Tuple[float, float, float, float, float, float]] = {
    "Female_Adult_01": (-0.2874, -0.2531, 0.1097, 0.2874, 0.5723, 1.6841),
    "Male_Adult_01": (-0.3244, -0.2412, 0.1114, 0.3245, 0.5715, 1.7544),
    "Male_Adult_05": (-0.3242, -0.2640, 0.1103, 0.3232, 0.5715, 1.7507),
}

# Choices (not measurements), fixed here so a dataset is reproducible from its seed.
CURB_OFFSET_M = 0.75  # the bicycle's centre line from the curb: its far side is 0.42 m from it
END_MARGIN_M = 18.0  # clear of crosswalks, stop lines and the queues behind them
MIN_SPACING_M = 9.0  # between two cyclists on one run
VEHICLE_CLEARANCE_M = 0.45
STREAM_TAG = 0xC1C1


@dataclass(eq=False)
class Cyclist:
    """One rider on a bicycle."""

    cyclist_id: int
    center: npt.NDArray[np.float64]  # ground point of the mesh frame's origin (x, y)
    heading_rad: float  # the direction of travel, math convention
    avatar: str
    crank_deg: int
    surface_z: float = 0.0

    @property
    def rider_asset(self) -> str:
        """The baked rider mesh (rider seated on the bicycle, in the shared frame)."""
        return f"{ASSET_ROOT}/rider_{self.avatar}_c{self.crank_deg}"

    @property
    def bike_asset(self) -> str:
        """The bicycle's frame mesh; the other parts ride along as ``part_paths``."""
        return f"{ASSET_ROOT}/bike_real_c{self.crank_deg}_{BIKE_FRAME_PART}"

    @property
    def bike_part_paths(self) -> List[str]:
        """The bicycle's other 12 part meshes, placed at the frame's transform."""
        return [f"{ASSET_ROOT}/bike_real_c{self.crank_deg}_{part}" for part in BIKE_OTHER_PARTS]

    @property
    def bike_bounds(self) -> Tuple[float, float, float, float, float, float]:
        """The bicycle's mesh-frame bounds."""
        return BIKE_BOUNDS

    @property
    def rider_bounds(self) -> Tuple[float, float, float, float, float, float]:
        """This avatar's mesh-frame bounds on the bicycle."""
        return RIDER_BOUNDS[self.avatar]

    def world_box(
        self, bounds: Tuple[float, float, float, float, float, float]
    ) -> Tuple[npt.NDArray[np.float64], float, float, float, float]:
        """``(centre xy, length, width, z_min, z_max)`` of a mesh-frame box placed at this cyclist.

        The mesh faces +Y at rotation 0, so its length is along the heading."""
        x0, y0, z0, x1, y1, z1 = bounds
        local = np.array([(x0 + x1) / 2.0, (y0 + y1) / 2.0])
        forward = np.array([math.cos(self.heading_rad), math.sin(self.heading_rad)])
        left = np.array([-forward[1], forward[0]])
        # mesh +Y is the heading, mesh +X is to the heading's right
        centre = self.center + forward * local[1] - left * local[0]
        return centre, y1 - y0, x1 - x0, z0 + self.surface_z, z1 + self.surface_z

    def footprint_aabb(self) -> Tuple[float, float, float, float]:
        """Axis-aligned footprint of bicycle and rider together (conservative when turned)."""
        boxes = [self.world_box(self.bike_bounds), self.world_box(self.rider_bounds)]
        cos_h, sin_h = abs(math.cos(self.heading_rad)), abs(math.sin(self.heading_rad))
        lo = np.array([np.inf, np.inf])
        hi = np.array([-np.inf, -np.inf])
        for centre, length, width, _, _ in boxes:
            half = np.array(
                [(length * cos_h + width * sin_h) / 2.0, (length * sin_h + width * cos_h) / 2.0]
            )
            lo = np.minimum(lo, centre - half)
            hi = np.maximum(hi, centre + half)
        return float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])


def _overlaps(
    a: Tuple[float, float, float, float], b: Tuple[float, float, float, float], margin: float
) -> bool:
    return not (
        a[2] + margin <= b[0]
        or b[2] + margin <= a[0]
        or a[3] + margin <= b[1]
        or b[3] + margin <= a[1]
    )


def generate_cyclists(  # pylint: disable=too-many-arguments,too-many-locals
    lanes: Dict[int, Lane],
    edges: Dict[int, RoadEdge],
    vehicles: Sequence[Vehicle],
    seed: int,
    run_probability: float = 0.6,
    max_per_run: int = 2,
) -> List[Cyclist]:
    """Cyclists along the curb of every driving run, on their own random stream.

    A run (a directed edge's right-hand curb line) gets at least one cyclist with probability
    ``run_probability`` and another with the same probability, up to ``max_per_run``, each
    at least ``MIN_SPACING_M`` from the others and ``END_MARGIN_M`` from the run's ends, and clear
    of every vehicle's box. Heading is the edge's direction of travel (right-hand traffic)."""
    rng = np.random.Generator(np.random.PCG64([seed, STREAM_TAG]))
    vehicle_boxes = [vehicle.aabb for vehicle in vehicles]
    placed: List[Cyclist] = []
    for run in edge_runs(lanes, edges):
        usable = run.length - 2.0 * END_MARGIN_M
        if usable <= 0.0:
            continue
        along: List[float] = []
        for _ in range(max_per_run):
            if rng.random() >= run_probability:
                break
            for _attempt in range(6):
                spot = END_MARGIN_M + float(rng.random()) * usable
                if any(abs(spot - other) < MIN_SPACING_M for other in along):
                    continue
                position = run.start + run.run_direction * spot - run.outward * CURB_OFFSET_M
                cyclist = Cyclist(
                    cyclist_id=len(placed),
                    center=np.array([float(position[0]), float(position[1])]),
                    heading_rad=run.rotation_rad,
                    avatar=AVATARS[int(rng.integers(len(AVATARS)))],
                    crank_deg=CRANK_ANGLES[int(rng.integers(len(CRANK_ANGLES)))],
                )
                box = cyclist.footprint_aabb()
                others = [c.footprint_aabb() for c in placed]
                if any(_overlaps(box, v, VEHICLE_CLEARANCE_M) for v in vehicle_boxes + others):
                    continue
                placed.append(cyclist)
                along.append(spot)
                break
    return placed
