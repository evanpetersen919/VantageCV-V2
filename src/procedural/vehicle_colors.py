"""Body colours for cars, so a scene is not all one white.

City Sample's car paint colours itself from a gradient sampled with a
per-instance random value that is always 0 for individually spawned actors, so
every car would render the same cream white. The project therefore owns a copy
of each model's paint material with that gradient switched off
(``unreal_plugin/tools/create_vehicle_paint.py``); a payload swaps it in for the
``veh_carPaint`` slot and sets ``BaseColor`` (and the metallic flake tints) to
the drawn colour. Models with a livery of their own (the yellow taxi, the police
car, the box van, the trucks and the bus) keep their look.

Colour shares are the US model-year-2025 figures from iSeeCars' study of about
22 million vehicles: white 25.7%, black 23.4%, gray 22.9%, silver 8.4%, red
7.0%, blue 6.0%. That study names nothing else, so the remaining 6.6% is split
among beige, brown, green, orange, yellow and gold by this project's own
choice. Display colours are typical sRGB values for each colour name.
``PAINT_SCALE`` maps the display colour to the paint parameter: it was set by
rendering a palette in the engine and comparing with the sunlit result, not
derived.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

from src.procedural.actor_placement import Vehicle

PAINT_SLOT_NAME = "veh_carPaint"
PAINT_MATERIAL_FOLDER = "/Game/VantageCV/VehiclePaint"
# Model folders with a project-owned paint copy; matches MODEL_FOLDERS in
# create_vehicle_paint.py.
RECOLORABLE_MODELS = (
    "vehCar_vehicle02",
    "vehCar_vehicle03",
    "vehCar_vehicle05",
    "vehCar_vehicle06",
    "vehCar_vehicle07",
    "vehVan_vehicle01",
    "vehTruck_vehicle04",
)
PAINT_SCALE = 1.2
VEHICLE_FOLDER_INDEX = 3


@dataclass(frozen=True)
class PaintColor:
    """A named body colour: its share of cars and its sRGB display value."""

    name: str
    share: float
    srgb: Tuple[int, int, int]


PAINT_COLORS: Tuple[PaintColor, ...] = (
    PaintColor("white", 0.257, (238, 238, 236)),
    PaintColor("black", 0.234, (24, 24, 26)),
    PaintColor("gray", 0.229, (110, 112, 116)),
    PaintColor("silver", 0.084, (178, 180, 184)),
    PaintColor("red", 0.070, (170, 20, 28)),
    PaintColor("blue", 0.060, (24, 52, 130)),
    PaintColor("beige", 0.015, (196, 170, 130)),
    PaintColor("brown", 0.010, (90, 60, 40)),
    PaintColor("green", 0.015, (30, 84, 52)),
    PaintColor("orange", 0.010, (200, 90, 20)),
    PaintColor("yellow", 0.008, (230, 190, 30)),
    PaintColor("gold", 0.008, (176, 144, 80)),
)


PAINT_COLORS_BY_NAME: Dict[str, PaintColor] = {color.name: color for color in PAINT_COLORS}


def model_folder(asset_path: str) -> str:
    """The City Sample vehicle folder of a body-shell path (for example
    ``vehCar_vehicle02``)."""
    parts = asset_path.split("/")
    return parts[VEHICLE_FOLDER_INDEX] if len(parts) > VEHICLE_FOLDER_INDEX else ""


def is_recolorable(asset_path: str) -> bool:
    """Whether the model has a project-owned paint copy to recolour."""
    return model_folder(asset_path) in RECOLORABLE_MODELS


def _srgb_to_linear(channel: float) -> float:
    if channel <= 0.04045:
        return channel / 12.92
    return float(((channel + 0.055) / 1.055) ** 2.4)


def paint_parameter(color: PaintColor) -> Tuple[float, float, float]:
    """The linear RGB the paint's ``BaseColor`` is set to for ``color``."""
    return tuple(  # type: ignore[return-value]
        min(1.0, _srgb_to_linear(channel / 255.0) * PAINT_SCALE) for channel in color.srgb
    )


def draw_paint_color(seed: int, vehicle_id: int) -> PaintColor:
    """A colour for one vehicle, drawn by share from its own RNG stream (so
    the same seed and vehicle always get the same colour, and no other draw
    in a scenario is disturbed)."""
    rng = np.random.Generator(np.random.PCG64([seed, 0xC010, vehicle_id]))
    shares = np.array([color.share for color in PAINT_COLORS])
    return PAINT_COLORS[int(rng.choice(len(PAINT_COLORS), p=shares / shares.sum()))]


def paint_material_replacement(asset_path: str) -> Optional[Dict[str, str]]:
    """The ``material_replacements`` entry giving this model its paint copy,
    or ``None`` for a model that is not recolourable."""
    folder = model_folder(asset_path)
    if folder not in RECOLORABLE_MODELS:
        return None
    return {PAINT_SLOT_NAME: f"{PAINT_MATERIAL_FOLDER}/{folder}.{folder}"}


def assign_vehicle_paint(vehicles: Sequence[Vehicle], seed: int) -> None:
    """Give every recolourable vehicle a body colour (in place)."""
    for vehicle in vehicles:
        if is_recolorable(vehicle.asset_path):
            vehicle.paint = draw_paint_color(seed, vehicle.vehicle_id).name
