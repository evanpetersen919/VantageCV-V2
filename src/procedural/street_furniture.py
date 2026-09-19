"""Real City Sample street furniture along every sidewalk.

Placement rules are measured from Epic's own generated city (the real
``CITY_street_furniture_sidewalk`` point cloud, about 15,000 placements),
relative to the curb line (this project's outer pavement edge, see
``road_edge_kit.edge_runs``), measured outward onto the sidewalk:

============  =========  ===========  ==================================
item          offset cm  spacing cm   note
============  =========  ===========  ==================================
parking meter 25         700 (exact)  Megascans ``Parking_Meter_00``
street lamp   40         ~1435        arm over the road
fire hydrant  30         ~2787        Megascans ``Fire_Hydrant_02``
trash can     40         ~1235        ``Kit_Trashcan_A``
no-parking    55         ~3335        Megascans ``No_Parking_Road_Sign_00``
============  =========  ===========  ==================================

Every real placement is unscaled and sits with its pivot at road-crown
height (the base sinks into the raised sidewalk), so ``z = 0`` here.

Orientation was verified live on a real sidewalk (each item at four
rotations, seen from the side and straight down): every item here looks
right at the run's own rotation except the cobra-head lamp, whose arm
points over the road at run rotation + pi. Items whose front could not be
told apart from above (mailboxes, fire call boxes) are deliberately left
out rather than guessed.

Pieces keep clear of intersections (``END_MARGIN_METERS``) and of each
other (lamps first, then hydrants, signs, trash cans, meters). One lamp
style is used for a whole scenario (chosen by the caller from the seed);
placement itself is deterministic.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

from src.procedural.building_facade import FacadePiece
from src.procedural.lane_topology import Lane
from src.procedural.road_edge_kit import edge_runs
from src.procedural.road_network import RoadEdge

# Keep furniture this far from either end of a run (crosswalks and the
# intersection corner live there).
END_MARGIN_METERS = 5.0


@dataclass(frozen=True)
class FurnitureRule:  # pylint: disable=too-many-instance-attributes
    """How one kind of street furniture is placed along a curb line."""

    name: str
    asset_path: str
    offset_m: float
    spacing_m: float
    phase_fraction: float
    rotation_offset_rad: float
    clearance_m: float


_METER = "/Game/Megascans/3D_Assets/Parking_Meter_00/ujpkaadfa_LOD0"
_HYDRANT = "/Game/Megascans/3D_Assets/Fire_Hydrant_02/uh4ocfafa_LOD0"
_SIGN = "/Game/Megascans/3D_Assets/No_Parking_Road_Sign_00/ui1lbhlbb_LOD0"
_TRASH = "/Game/Prop/Kit_Trashcan_A/Mesh/SM_Trashcan_A_01"

# Street lamp styles, one per scenario: (asset path, rotation offset). The
# cobra-head pole's arm points over the road at run rotation + pi; the
# ornate double-globe lamps are symmetric across the road.
LAMP_STYLES: Tuple[Tuple[str, float], ...] = (
    ("/Game/Prop/Kit_StreetLamp_A/Mesh/SM_StreetLamp_A_Pole_Large", math.pi),
    ("/Game/Prop/Kit_StreetLamp_C/Mesh/streetLampC", 0.0),
    ("/Game/Prop/Kit_StreetLamp_E/Mesh/streetLamp_E", 0.0),
)


def furniture_rules(lamp_style: int = 0) -> List[FurnitureRule]:
    """The placement rules, highest priority first (a lower-priority item
    is skipped where it would come closer than its clearance to one that
    is already placed)."""
    lamp_path, lamp_rotation = LAMP_STYLES[lamp_style % len(LAMP_STYLES)]
    return [
        FurnitureRule("lamp", lamp_path, 0.40, 14.35, 0.0, lamp_rotation, 1.0),
        FurnitureRule("hydrant", _HYDRANT, 0.30, 27.87, 0.31, 0.0, 1.2),
        FurnitureRule("sign", _SIGN, 0.55, 33.35, 0.63, 0.0, 1.2),
        FurnitureRule("trash", _TRASH, 0.40, 12.35, 0.47, 0.0, 1.2),
        FurnitureRule("meter", _METER, 0.25, 7.00, 0.5, 0.0, 1.0),
    ]


def generate_street_furniture_pieces(
    lanes: Dict[int, Lane],
    edges: Dict[int, RoadEdge],
    lamp_style: int = 0,
) -> List[FacadePiece]:
    """Street furniture along the curb line of every directed road edge.

    Deterministic and RNG-free (``lamp_style`` selects the scenario's lamp
    model). Each rule places an item every ``spacing_m`` starting at
    ``END_MARGIN_METERS + phase * spacing``, skipping any spot too close to
    an item that was already placed on the same run.
    """
    rules = furniture_rules(lamp_style)
    pieces: List[FacadePiece] = []
    for run in edge_runs(lanes, edges):
        usable = run.length - 2.0 * END_MARGIN_METERS
        if usable <= 0.0:
            continue
        placed_along: List[float] = []
        for rule in rules:
            s = END_MARGIN_METERS + rule.phase_fraction * rule.spacing_m
            while s <= run.length - END_MARGIN_METERS:
                if all(abs(s - other) >= rule.clearance_m for other in placed_along):
                    placed_along.append(s)
                    position = run.start + run.run_direction * s + run.outward * rule.offset_m
                    pieces.append(
                        FacadePiece(
                            asset_path=rule.asset_path,
                            position=np.array([position[0], position[1], 0.0]),
                            rotation_rad=run.rotation_rad + rule.rotation_offset_rad,
                        )
                    )
                s += rule.spacing_m
    return pieces
