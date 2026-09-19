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

**Street trees** (birch in a tree base, one pair per spot): Epic places
them in plazas and courtyards, not along the curb, so where they go here
is partly inferred. MEASURED from the real placements: consecutive tree
pits are about 20m apart (median 2021cm), every tree pairs 1:1 with a base
at the same position, the base is scaled 1.2, the tree uniformly 0.8-1.1
with a random yaw, the commonest birch variants are f, g and h, and the
base sits at sidewalk-top height (z=74 against the road crown's 63, so
0.108m here). INFERRED (not measured for curb streets): the tree pit sits
1.5m out from the curb line (the middle of our 3m sidewalk). Tree scale,
yaw and variant are random per tree (from ``seed``); the base style is one
per scenario.

Pieces keep clear of intersections (``END_MARGIN_METERS``) and of each
other (lamps first, then trees, hydrants, signs, trash cans, meters). One
lamp style and one tree-base style are used for a whole scenario (chosen
by the caller from the seed); item positions are deterministic.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import numpy.typing as npt

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


@dataclass(frozen=True)
class TreeRule:  # pylint: disable=too-many-instance-attributes
    """How street trees are placed: a base and a tree at the same spot."""

    name: str
    tree_asset_paths: Tuple[str, ...]
    offset_m: float
    spacing_m: float
    phase_fraction: float
    clearance_m: float
    z_m: float
    base_scale: float
    tree_scale_range: Tuple[float, float]


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


# Tree base styles, one per scenario (SM_TreeBase_A: round or square, with or
# without a grill).
TREE_BASE_STYLES: Tuple[str, ...] = (
    "/Game/Prop/Kit_TreeBase_A/Mesh/SM_TreeBase_Circle_A",
    "/Game/Prop/Kit_TreeBase_A/Mesh/SM_TreeBase_CircleGrill_A",
    "/Game/Prop/Kit_TreeBase_A/Mesh/SM_TreeBase_Square_A",
    "/Game/Prop/Kit_TreeBase_A/Mesh/SM_TreeBase_SquareGrill_A",
)

# Birch variants f, g and h are 154 of the 188 real birches.
_BIRCH_VARIANTS: Tuple[str, ...] = tuple(
    f"/Game/Prop/Kit_Tree_Birch/Mesh/SM_Tree_Birch_{v}" for v in "fgh"
)

_Rule = Union[FurnitureRule, TreeRule]


def furniture_rules(lamp_style: int = 0) -> List[_Rule]:
    """The placement rules, highest priority first (a lower-priority item
    is skipped where it would come closer than its clearance to one that
    is already placed)."""
    lamp_path, lamp_rotation = LAMP_STYLES[lamp_style % len(LAMP_STYLES)]
    return [
        FurnitureRule("lamp", lamp_path, 0.40, 14.35, 0.0, lamp_rotation, 1.0),
        TreeRule("tree", _BIRCH_VARIANTS, 1.5, 20.21, 0.25, 2.5, 0.108, 1.2, (0.8, 1.1)),
        FurnitureRule("hydrant", _HYDRANT, 0.30, 27.87, 0.31, 0.0, 1.2),
        FurnitureRule("sign", _SIGN, 0.55, 33.35, 0.63, 0.0, 1.2),
        FurnitureRule("trash", _TRASH, 0.40, 12.35, 0.47, 0.0, 1.2),
        FurnitureRule("meter", _METER, 0.25, 7.00, 0.5, 0.0, 1.0),
    ]


# A tree that would land on a lamp is nudged along the curb instead of being
# dropped (a missing tree leaves a 40m gap; a slightly shifted one does not).
_TREE_NUDGES_METERS: Tuple[float, ...] = (0.0, 2.0, -2.0, 3.5, -3.5)


def _free_spot(
    rule: _Rule, s: float, placed_along: List[float], run_length: float
) -> Optional[float]:
    """``s`` if it is clear of every placed item, else (trees only) the
    nearest nudged spot that is; ``None`` if there is none."""
    nudges = _TREE_NUDGES_METERS if isinstance(rule, TreeRule) else (0.0,)
    for nudge in nudges:
        spot = s + nudge
        if not END_MARGIN_METERS <= spot <= run_length - END_MARGIN_METERS:
            continue
        if all(abs(spot - other) >= rule.clearance_m for other in placed_along):
            return spot
    return None


def _tree_pieces(  # pylint: disable=too-many-arguments
    rule: TreeRule,
    position: npt.NDArray[np.float64],
    base_asset: str,
    rng: np.random.Generator,
) -> List[FacadePiece]:
    """A tree base and a tree at the same spot: base scaled 1.2, tree scaled
    uniformly within the measured range, random yaw, random birch variant."""
    at = np.array([position[0], position[1], rule.z_m])
    tree_scale = float(rng.uniform(*rule.tree_scale_range))
    tree_asset = rule.tree_asset_paths[int(rng.integers(len(rule.tree_asset_paths)))]
    yaw = float(rng.uniform(0.0, 2.0 * math.pi))
    return [
        FacadePiece(base_asset, at, 0.0, (rule.base_scale,) * 3),
        FacadePiece(tree_asset, at.copy(), yaw, (tree_scale,) * 3),
    ]


def generate_street_furniture_pieces(  # pylint: disable=too-many-locals,too-many-arguments
    lanes: Dict[int, Lane],
    edges: Dict[int, RoadEdge],
    lamp_style: int = 0,
    tree_base_style: int = 0,
    seed: int = 0,
    include_trees: bool = True,
) -> List[FacadePiece]:
    """Street furniture and street trees along the curb line of every
    directed road edge.

    Item positions are deterministic (``lamp_style`` and ``tree_base_style``
    select the scenario's lamp model and tree-base model); only each tree's
    scale, yaw and birch variant are random, from ``seed``. Each rule
    places an item every ``spacing_m`` starting at ``END_MARGIN_METERS +
    phase * spacing``, skipping any spot too close to an item that was
    already placed on the same run.
    """
    rules: Sequence[_Rule] = [
        rule
        for rule in furniture_rules(lamp_style)
        if include_trees or not isinstance(rule, TreeRule)
    ]
    base_asset = TREE_BASE_STYLES[tree_base_style % len(TREE_BASE_STYLES)]
    tree_rng = np.random.Generator(np.random.PCG64([seed, 0x7EE5]))
    pieces: List[FacadePiece] = []
    for run in edge_runs(lanes, edges):
        usable = run.length - 2.0 * END_MARGIN_METERS
        if usable <= 0.0:
            continue
        placed_along: List[float] = []
        for rule in rules:
            s = END_MARGIN_METERS + rule.phase_fraction * rule.spacing_m
            while s <= run.length - END_MARGIN_METERS:
                spot = _free_spot(rule, s, placed_along, run.length)
                if spot is not None:
                    placed_along.append(spot)
                    position = run.start + run.run_direction * spot + run.outward * rule.offset_m
                    if isinstance(rule, TreeRule):
                        pieces += _tree_pieces(rule, position, base_asset, tree_rng)
                    else:
                        pieces.append(
                            FacadePiece(
                                asset_path=rule.asset_path,
                                position=np.array([position[0], position[1], 0.0]),
                                rotation_rad=run.rotation_rad + rule.rotation_offset_rad,
                            )
                        )
                s += rule.spacing_m
    return pieces
