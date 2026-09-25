"""Per-building wall colours, so a city is not one stone colour throughout.

Every wall module's stone, brick and painted-stone materials expose a colour
tint the plugin can set per instance (the ``material_slot_vectors`` payload
field, whose slot keys may be wildcards). Each building draws one palette
entry and every piece of it gets the same colours; an entry of ``None`` leaves
City Sample's own finish alone.

The tint values were chosen by rendering the palette on a wall of each of the
three building families (CHA limestone, CHH granite, SFA painted stone) and
keeping colours that read as plausible building stone or paint on all three.
Tints are multipliers of the material's own albedo texture, so the same tint
looks different on a different family; the shares are this project's own
choice (no source for building colour statistics was found), with a large
share left as Epic's stock finish.

Window frames (painted metal) are deliberately not recoloured.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# Slot patterns (matched against each mesh's material slot names) and the
# colour parameter each material family reads.
STONE_SLOT_PATTERNS = ("Bldg_block*", "Bldg_brick*")
STONE_TINT_PARAMETER = "Color Tint M1"
PAINT_SLOT_PATTERN = "Bldg_paintedStone*"
PAINT_TINT_PARAMETER = "Color Tint/Mult(A) M1"

Tint = Tuple[float, float, float, float]


@dataclass(frozen=True)
class WallPalette:
    """One building colour: its share, and the stone and painted-stone tints
    (``None`` for both keeps the stock finish)."""

    name: str
    share: float
    stone: Optional[Tint]
    paint: Optional[Tint]


WALL_PALETTES: Tuple[WallPalette, ...] = (
    WallPalette("stock", 0.30, None, None),
    WallPalette("cream", 0.12, (2.3, 2.15, 1.8, 1.0), (2.4, 2.3, 2.0, 1.0)),
    WallPalette("warm-grey", 0.14, (1.3, 1.25, 1.2, 1.0), (1.3, 1.25, 1.2, 1.0)),
    WallPalette("charcoal", 0.06, (0.55, 0.55, 0.58, 1.0), (0.55, 0.55, 0.58, 1.0)),
    WallPalette("terracotta", 0.10, (1.9, 1.0, 0.7, 1.0), (2.0, 1.1, 0.8, 1.0)),
    WallPalette("sage", 0.06, (1.0, 1.35, 1.0, 1.0), (1.1, 1.5, 1.1, 1.0)),
    WallPalette("blue-grey", 0.08, (0.95, 1.1, 1.4, 1.0), (1.0, 1.2, 1.6, 1.0)),
    WallPalette("tan", 0.14, (1.9, 1.5, 1.05, 1.0), (2.0, 1.6, 1.1, 1.0)),
)


def draw_building_palettes(building_count: int, seed: int) -> List[int]:
    """A palette index for each of ``building_count`` buildings, by share,
    from a dedicated RNG stream (no other draw in a scenario changes)."""
    rng = np.random.Generator(np.random.PCG64([seed, 0xB01D]))
    shares = np.array([palette.share for palette in WALL_PALETTES])
    return [
        int(i) for i in rng.choice(len(WALL_PALETTES), size=building_count, p=shares / shares.sum())
    ]


def wall_slot_vectors(palette_index: int) -> Optional[Dict[str, Dict[str, List[float]]]]:
    """The ``material_slot_vectors`` entry for a palette, or ``None`` for the
    stock finish."""
    palette = WALL_PALETTES[palette_index]
    if palette.stone is None or palette.paint is None:
        return None
    vectors: Dict[str, Dict[str, List[float]]] = {
        pattern: {STONE_TINT_PARAMETER: list(palette.stone)} for pattern in STONE_SLOT_PATTERNS
    }
    vectors[PAINT_SLOT_PATTERN] = {PAINT_TINT_PARAMETER: list(palette.paint)}
    return vectors


def piece_palettes(building_of_piece: Sequence[int], palettes: Sequence[int]) -> List[int]:
    """The palette index of each facade piece, given the building each piece
    belongs to."""
    return [palettes[building] for building in building_of_piece]
