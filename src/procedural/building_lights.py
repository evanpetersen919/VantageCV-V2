"""Lit windows for a night scenario, using City Sample's own window glass.

Every building wall's glass slot is an interior-mapped window material
(``M_Window``): real room interiors with curtains, furniture and ceiling
lights, chosen per window, with a per-instance ``AmountOff`` scalar for the
fraction of rooms left dark. Its lights-on branch sits behind the
``UseLightOverride`` static switch, off in every shipped kit instance and
unreachable by a runtime override, so the project owns copies with it on
(``unreal_plugin/tools/create_night_glass.py``) and a night payload swaps
them into each wall's ``Bldg_glass`` slot.

Randomization is deterministic from the scenario seed (a dedicated RNG
stream, so nothing else in a scenario changes): each BUILDING draws its own
lit fraction, and the material then picks which of its windows are lit.
The fraction range is tuned by eye -- real city occupancy varies far too
much to cite one number.
"""

from typing import Dict, List, Optional, Sequence

import numpy as np

from src.procedural.building_facade import FacadePiece

# Each building's lit fraction is drawn uniformly from this range: some
# buildings are nearly dark, some mostly lit.
LIT_FRACTION_RANGE = (0.05, 0.9)

NIGHT_GLASS_FOLDER = "/Game/VantageCV/NightGlass"
GLASS_SLOT_NAME = "Bldg_glass"
KIT_FOLDER_PREFIX = "Kit_Bldg_"
# /Game/Building/<style>/<variant>/<kit folder>/Mesh/<mesh>
KIT_FOLDER_INDEX = 5


def building_piece_lit_fractions(
    pieces_by_building: Sequence[Sequence[FacadePiece]], seed: int
) -> List[float]:
    """One lit fraction per facade piece (flattened in building order): the
    same value for every piece of a building, drawn once per building."""
    rng = np.random.Generator(np.random.PCG64([seed, 0x11D0]))
    fractions: List[float] = []
    for pieces in pieces_by_building:
        fraction = float(rng.uniform(*LIT_FRACTION_RANGE))
        fractions += [fraction] * len(pieces)
    return fractions


def night_glass_replacements(asset_path: str) -> Optional[Dict[str, str]]:
    """The ``material_replacements`` entry swapping a wall mesh's glass slot
    for its kit's project-owned lit copy, or ``None`` for an asset that is
    not a building-kit mesh."""
    parts = asset_path.split("/")
    if len(parts) <= KIT_FOLDER_INDEX or not parts[KIT_FOLDER_INDEX].startswith(KIT_FOLDER_PREFIX):
        return None
    name = f"{parts[KIT_FOLDER_INDEX]}_M_Bldg_glass"
    return {GLASS_SLOT_NAME: f"{NIGHT_GLASS_FOLDER}/{name}.{name}"}


def glass_scalar_overrides(lit_fraction: float) -> Dict[str, float]:
    """Material scalars for a building's glass: every room's light allowed
    on (``LightsOff`` 0) and ``AmountOff`` the fraction left dark."""
    return {"LightsOff": 0.0, "AmountOff": 1.0 - lit_fraction}
