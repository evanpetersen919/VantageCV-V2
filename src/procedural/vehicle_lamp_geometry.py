"""Real headlight / tail-light positions and lens sizes for the City Sample
vehicle models that ship separate lamp meshes, measured live through the
UE5 RPC bridge (``bin/measure_vehicle_lamps.py`` -> ``GetStaticMeshBounds``
on each model's ``SM_Headlight_L/R`` and ``SM_Taillight_L/R`` part).

Every number is in meters in the vehicle mesh's own local frame, whose
origin is exactly where ``Vehicle.center`` places the mesh: ``forward``
along the heading, ``lateral`` the absolute distance from the centreline
(each lamp pair is symmetric, so sign is irrelevant), ``height`` above the
road. ``half_*`` are the lens mesh's own half-extents. Models not listed
here have no separate lamp meshes (the bus, trucks, trailer and a few
cars) and fall back to generic placement -- see ``night_lights.py``.
"""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class LampGeometry:
    """One lamp pair's real position and lens half-extents (meters)."""

    forward_m: float
    lateral_m: float
    height_m: float
    half_extents_m: Tuple[float, float, float]  # (forward, lateral, vertical)


@dataclass(frozen=True)
class VehicleLampGeometry:
    """A model's real headlight pair and tail-light pair."""

    headlight: LampGeometry
    taillight: LampGeometry


VEHICLE_LAMP_GEOMETRY: Dict[str, VehicleLampGeometry] = {
    "vehCar_vehicle02": VehicleLampGeometry(
        headlight=LampGeometry(2.013, 0.645, 0.854, (0.209, 0.201, 0.1)),
        taillight=LampGeometry(-2.25, 0.688, 0.94, (0.079, 0.131, 0.162)),
    ),
    "vehCar_vehicle05": VehicleLampGeometry(
        headlight=LampGeometry(1.948, 0.553, 0.922, (0.23, 0.207, 0.076)),
        taillight=LampGeometry(-2.01, 0.741, 0.862, (0.116, 0.073, 0.123)),
    ),
    "vehCar_vehicle06": VehicleLampGeometry(
        headlight=LampGeometry(1.79, 0.533, 0.704, (0.267, 0.168, 0.103)),
        taillight=LampGeometry(-1.897, 0.638, 0.722, (0.143, 0.149, 0.05)),
    ),
    "vehCar_vehicle07": VehicleLampGeometry(
        headlight=LampGeometry(1.786, 0.621, 0.65, (0.156, 0.146, 0.078)),
        taillight=LampGeometry(-2.075, 0.595, 0.828, (0.135, 0.13, 0.137)),
    ),
    "vehCar_vehicle13": VehicleLampGeometry(
        headlight=LampGeometry(2.325, 0.575, 0.659, (0.098, 0.148, 0.07)),
        taillight=LampGeometry(-2.571, 0.732, 0.878, (0.103, 0.135, 0.126)),
    ),
    "vehTruck_vehicle04": VehicleLampGeometry(
        headlight=LampGeometry(2.199, 0.666, 0.957, (0.183, 0.203, 0.109)),
        taillight=LampGeometry(-2.804, 0.779, 1.034, (0.099, 0.086, 0.144)),
    ),
    "vehVan_vehicle01": VehicleLampGeometry(
        headlight=LampGeometry(2.086, 0.672, 0.737, (0.195, 0.223, 0.093)),
        taillight=LampGeometry(-2.004, 0.791, 1.234, (0.224, 0.062, 0.082)),
    ),
}
