"""Street trees and shrubs from scanned, photographic models (Poly Haven, CC0).

The card trees of ``foliage.py`` read as stylised however they are shaded, so this module stands
real photogrammetry plants at the street-tree spots and on the curb planting patches instead:
high-triangle meshes (tens of thousands to millions) imported into the project as Nanite meshes by
``unreal_plugin/tools/prepare_photoreal_trees.py`` and ``setup_photoreal_trees.py``. A scene's
payload for them is just an asset path and a transform.

A plant keeps its trunk and branches and swaps its leaf material per season (spring, summer, fall;
none in winter for trees, where the bare Epic trees stay; the evergreen shrubs keep their summer
leaves) through ``material_replacements``, the same mechanism the signal poles use. Meshes are
scaled to a street tree's or a shrub's height.

Sizes and which scan is used where are design choices, not measurements. The real mesh heights are
the ones ``setup_photoreal_trees.py`` wrote to ``ue_info.json``.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from src.procedural.building_facade import FacadePiece
from src.procedural.environment import Season

TREE_DIR = "/Game/VantageCV/Trees"
SEASON_SUFFIX = {Season.SPRING: "spring", Season.SUMMER: "summer", Season.FALL: "fall"}


@dataclass(frozen=True)
class Variant:
    """One mesh of a plant model: its real size and where its visible centre is."""

    mesh: str
    height_m: float
    width_m: float  # the larger horizontal extent
    # The bounds centre relative to the mesh pivot, in the engine's local x and y (metres). The
    # scans of a plant are authored side by side, so a variant's pivot can be 1.6 m from its
    # visible centre.
    centre_x_m: float = 0.0
    centre_y_m: float = 0.0


@dataclass(frozen=True)
class PlantModel:
    """One scanned plant: its mesh variants and how its leaf material is swapped."""

    name: str
    variants: Tuple[Variant, ...]
    leaf_slots: Tuple[str, ...]  # material slot names that take the seasonal leaf instance
    instance: str  # leaf instance asset name with a ``{season}`` placeholder
    height_m: Tuple[float, float]  # target height range once placed


TREES: Dict[str, PlantModel] = {
    "jacaranda_tree": PlantModel(
        "jacaranda_tree",
        (Variant("jacaranda_tree_2k", 19.322, 24.4),),
        ("jacaranda_tree_leaves",),
        "MI_jacaranda_tree_leaves_{season}",
        (9.0, 12.5),
    ),
    "tree_small_02": PlantModel(
        "tree_small_02",
        (Variant("tree_small_02_2k", 4.533, 4.3),),
        ("tree_small_02_leaves",),
        "MI_tree_small_02_leaves_{season}",
        (6.5, 9.0),
    ),
}
# Probability weight of each tree model along a street.
TREE_WEIGHTS = {"jacaranda_tree": 0.6, "tree_small_02": 0.4}

_SEARSIA = "searsia_lucida_2k_searsia_lucida_{v}_LOD0"
_OTHONNA = "othonna_cerarioides_2k_othonna_cerarioides_{v}_LOD0"
# Measured from the imported meshes (setup_photoreal_trees.py): height, width, bounds centre
# x and y.
_SEARSIA_ROWS = (
    (2.315, 1.966, 1.586, -0.586),
    (1.976, 1.524, 0.004, -0.823),
    (1.659, 1.509, -1.534, -0.743),
    (1.41, 1.095, 1.464, 0.776),
    (1.011, 1.034, 0.502, 0.727),
    (0.733, 0.658, -0.51, 0.693),
    (0.781, 0.382, -1.518, 0.733),
)
_OTHONNA_ROWS = (
    (1.907, 1.091, 1.57, -0.656),
    (1.72, 1.052, -0.092, -0.586),
    (1.391, 0.945, -1.492, -0.669),
    (1.117, 0.654, 1.531, 0.342),
    (0.926, 0.554, 0.53, 0.388),
    (0.65, 0.455, -0.497, 0.401),
    (0.424, 0.496, -1.471, 0.384),
)
_FERN_ROWS = (
    (0.258, 0.613, -0.022, 0.995),
    (0.397, 0.99, -0.033, 0.025),
    (0.32, 0.874, 1.007, -0.035),
    (0.2, 0.593, 0.996, 0.945),
)
# Evergreen shrubs: they keep their summer leaves in winter.
SHRUBS: Dict[str, PlantModel] = {
    "searsia_lucida": PlantModel(
        "searsia_lucida",
        tuple(Variant(_SEARSIA.format(v=v), *row) for v, row in zip("abcdefg", _SEARSIA_ROWS)),
        ("searsia_lucida", "searsia_lucida_leaves", "searsia_lucida_twigs"),
        "MI_searsia_lucida_main_{season}",
        (0.7, 1.3),
    ),
    "othonna_cerarioides": PlantModel(
        "othonna_cerarioides",
        tuple(Variant(_OTHONNA.format(v=v), *row) for v, row in zip("abcdefg", _OTHONNA_ROWS)),
        ("othonna_cerarioides", "othonna_cerarioides_leaves"),
        "MI_othonna_cerarioides_main_{season}",
        (0.8, 1.4),
    ),
    "fern_02": PlantModel(
        "fern_02",
        tuple(Variant(f"fern_02_2k_fern_02_{v}", *row) for v, row in zip("abcd", _FERN_ROWS)),
        ("fern_02",),
        "MI_fern_02_main_{season}",
        (0.35, 0.6),
    ),
}


def leaf_material(model: PlantModel, season: Season) -> str:
    """The leaf material instance of ``model`` for ``season``."""
    name = model.instance.format(season=SEASON_SUFFIX[season])
    return f"{TREE_DIR}/{name}.{name}"


def plant_piece(  # pylint: disable=too-many-arguments
    model: PlantModel,
    position: Tuple[float, float],
    season: Season,
    rng: np.random.Generator,
    rotation_rad: Optional[float] = None,
    height_m: Optional[float] = None,
    max_width_m: Optional[float] = None,
    centred: bool = False,
) -> FacadePiece:
    """One plant of ``model`` at ``position``: a random mesh variant, scaled to ``height_m`` (or
    the model's own range), with the season's leaf material (summer's in winter, for shrubs).

    With ``max_width_m`` the scale is capped so the plant's footprint fits that width (a shrub on a
    grass strip must not overhang the pavement). With ``centred`` the mesh is shifted so its visible
    centre, not its pivot, lands on ``position``; that is exact only without a turn, so the yaw is
    forced to zero (the engine's y is mirrored against the scenario's, hence the sign of ``y``)."""
    variant = model.variants[int(rng.integers(len(model.variants)))]
    target = float(rng.uniform(*model.height_m)) if height_m is None else height_m
    scale = target / variant.height_m
    if max_width_m is not None:
        scale = min(scale, max_width_m / variant.width_m)
    yaw = float(rng.uniform(0.0, 2.0 * np.pi)) if rotation_rad is None else rotation_rad
    x, y = position
    if centred:
        yaw = 0.0
        x -= scale * variant.centre_x_m
        y += scale * variant.centre_y_m
    material = leaf_material(model, season if season in SEASON_SUFFIX else Season.SUMMER)
    return FacadePiece(
        asset_path=f"{TREE_DIR}/{variant.mesh}",
        position=np.array([x, y, 0.0]),
        rotation_rad=yaw,
        scale=(scale, scale, scale),
        material_replacements={slot: material for slot in model.leaf_slots},
    )


def photoreal_tree_pieces(
    spots: Sequence[Tuple[float, float]], season: Season, seed: int
) -> List[FacadePiece]:
    """One scanned tree per spot with the season's leaves; empty in winter or without spots.

    Deterministic from ``seed`` on its own random stream, so no other generator's draws change."""
    if season not in SEASON_SUFFIX or not spots:
        return []
    rng = np.random.Generator(np.random.PCG64([seed, 0x7A11]))
    names = sorted(TREE_WEIGHTS)
    weights = np.array([TREE_WEIGHTS[name] for name in names])
    weights = weights / weights.sum()
    pieces: List[FacadePiece] = []
    for spot in spots:
        model = TREES[str(rng.choice(names, p=weights))]
        pieces.append(plant_piece(model, spot, season, rng))
    return pieces
