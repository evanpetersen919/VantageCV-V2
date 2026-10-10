"""Street trees from scanned, photographic tree models (Poly Haven, CC0).

The card trees of ``foliage.py`` read as stylised however they are shaded, so this module stands
real photogrammetry trees at the street-tree spots instead: high-triangle meshes (hundreds of
thousands to millions) imported into the project as Nanite meshes by
``unreal_plugin/tools/prepare_photoreal_trees.py`` and ``setup_photoreal_trees.py``. A scene's
payload for them is just an asset path and a transform.

A tree keeps its trunk and branches and swaps its leaf material per season (spring, summer, fall;
none in winter, where the bare Epic trees stay) through ``material_replacements``, the same
mechanism the signal poles use. The model's real size is about 19.5 m; each tree is scaled to a
street tree's height.

The scale range and the choice of which scan to use are design choices, not measurements.
"""

from typing import Dict, List, Sequence, Tuple

import numpy as np

from src.procedural.building_facade import FacadePiece
from src.procedural.environment import Season

_TREE_DIR = "/Game/VantageCV/Trees"
# name -> (mesh path, the leaf material slot's name, its real height in metres)
TREES: Dict[str, Tuple[str, str, float]] = {
    "jacaranda_tree": (f"{_TREE_DIR}/jacaranda_tree_2k", "jacaranda_tree_leaves", 19.5),
}
SEASON_SUFFIX = {Season.SPRING: "spring", Season.SUMMER: "summer", Season.FALL: "fall"}
TREE_HEIGHT_M = (9.0, 12.5)
# Spots closer than this to a parking-lot driveway etc. are already removed by street_furniture.


def leaf_material(name: str, season: Season) -> str:
    """The leaf material instance of tree ``name`` for ``season``."""
    suffix = SEASON_SUFFIX[season]
    return f"{_TREE_DIR}/MI_{name}_leaves_{suffix}.MI_{name}_leaves_{suffix}"


def photoreal_tree_pieces(
    spots: Sequence[Tuple[float, float]], season: Season, seed: int
) -> List[FacadePiece]:
    """One scanned tree per spot with the season's leaves; empty in winter or without spots.

    Deterministic from ``seed`` on its own random stream, so no other generator's draws change."""
    if season not in SEASON_SUFFIX or not spots:
        return []
    rng = np.random.Generator(np.random.PCG64([seed, 0x7A11]))
    names = sorted(TREES)
    pieces: List[FacadePiece] = []
    for x, y in spots:
        name = names[int(rng.integers(len(names)))]
        path, leaf_slot, real_height = TREES[name]
        scale = float(rng.uniform(*TREE_HEIGHT_M)) / real_height
        pieces.append(
            FacadePiece(
                asset_path=path,
                position=np.array([x, y, 0.0]),
                rotation_rad=float(rng.uniform(0.0, 2.0 * np.pi)),
                scale=(scale, scale, scale),
                material_replacements={leaf_slot: leaf_material(name, season)},
            )
        )
    return pieces
