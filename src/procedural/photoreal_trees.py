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
class PlantModel:
    """One scanned plant: its mesh variants and how its leaf material is swapped."""

    name: str
    variants: Tuple[Tuple[str, float], ...]  # (mesh asset name, real height in metres)
    leaf_slots: Tuple[str, ...]  # material slot names that take the seasonal leaf instance
    instance: str  # leaf instance asset name with a ``{season}`` placeholder
    height_m: Tuple[float, float]  # target height range once placed


TREES: Dict[str, PlantModel] = {
    "jacaranda_tree": PlantModel(
        "jacaranda_tree",
        (("jacaranda_tree_2k", 19.322),),
        ("jacaranda_tree_leaves",),
        "MI_jacaranda_tree_leaves_{season}",
        (9.0, 12.5),
    ),
    "tree_small_02": PlantModel(
        "tree_small_02",
        (("tree_small_02_2k", 4.533),),
        ("tree_small_02_leaves",),
        "MI_tree_small_02_leaves_{season}",
        (6.5, 9.0),
    ),
}
# Probability weight of each tree model along a street.
TREE_WEIGHTS = {"jacaranda_tree": 0.6, "tree_small_02": 0.4}

_SEARSIA = "searsia_lucida_2k_searsia_lucida_{v}_LOD0"
_OTHONNA = "othonna_cerarioides_2k_othonna_cerarioides_{v}_LOD0"
# Evergreen shrubs: they keep their summer leaves in winter.
SHRUBS: Dict[str, PlantModel] = {
    "searsia_lucida": PlantModel(
        "searsia_lucida",
        tuple(
            (_SEARSIA.format(v=v), h)
            for v, h in zip("abcdefg", (2.315, 1.976, 1.659, 1.41, 1.011, 0.733, 0.781))
        ),
        ("searsia_lucida", "searsia_lucida_leaves", "searsia_lucida_twigs"),
        "MI_searsia_lucida_main_{season}",
        (0.7, 1.3),
    ),
    "othonna_cerarioides": PlantModel(
        "othonna_cerarioides",
        tuple(
            (_OTHONNA.format(v=v), h)
            for v, h in zip("abcdefg", (1.907, 1.72, 1.391, 1.117, 0.926, 0.65, 0.424))
        ),
        ("othonna_cerarioides", "othonna_cerarioides_leaves"),
        "MI_othonna_cerarioides_main_{season}",
        (0.8, 1.4),
    ),
    "fern_02": PlantModel(
        "fern_02",
        tuple((f"fern_02_2k_fern_02_{v}", h) for v, h in zip("abcd", (0.258, 0.397, 0.32, 0.2))),
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
) -> FacadePiece:
    """One plant of ``model`` at ``position``: a random mesh variant, scaled to ``height_m`` (or
    the model's own range), with the season's leaf material (summer's in winter, for shrubs)."""
    mesh, real_height = model.variants[int(rng.integers(len(model.variants)))]
    target = float(rng.uniform(*model.height_m)) if height_m is None else height_m
    scale = target / real_height
    yaw = float(rng.uniform(0.0, 2.0 * np.pi)) if rotation_rad is None else rotation_rad
    material = leaf_material(model, season if season in SEASON_SUFFIX else Season.SUMMER)
    return FacadePiece(
        asset_path=f"{TREE_DIR}/{mesh}",
        position=np.array([position[0], position[1], 0.0]),
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
