"""Lit windows for a night scenario, using City Sample's own window glass.

Every building wall's glass slot is an interior-mapped window material
(``M_Window``): real room interiors with curtains, furniture and ceiling
lights. Its lights-on branch sits behind the ``UseLightOverride`` static
switch, off in every shipped kit instance and unreachable by a runtime
override, so the project owns copies with it on
(``unreal_plugin/tools/create_night_glass.py``) and a night payload swaps
them into each wall's ``Bldg_glass`` slot.

The material has no per-window on/off control a payload can reach: its
``LightsOff`` scalar dims every window of a mesh together, and ``AmountOff``
and the ``Luma*`` variation scalars have no effect (all measured live). So
the on/off choice is made per wall module -- one bay of 1 to 3 windows --
by setting that instance's ``LightsOff`` to 0 (lit) or 1 (dark). The choice
is random from the scenario seed (a dedicated RNG stream, so nothing else
in a scenario changes), lighting ``LIT_FRACTION`` of the modules.

Every piece would otherwise show the same room (the material seeds its room
choice with ``PerInstanceRandom``, constant for separately spawned actors), so
the night glass copies also switch on the material's manual room selection
(``ManualRoom`` + ``UseManualID``) and each module gets a random
``ManualRoomID``: real, distinct office/bedroom/lobby interiors. (A random
``InteriorOffset`` was tried and rejected: it shifts the view into the room
capture, so floor and wall lines land mid-window. The ``UseCustomTemp`` light
temperature switch washed rooms out white.) The copies also raise the ``Tint``
emission multiplier a little so lit rooms glow more.
"""

from typing import Dict, List, Optional

import numpy as np

# The share of wall modules lit at night; the rest are dark.
LIT_FRACTION = 0.2

NIGHT_GLASS_FOLDER = "/Game/VantageCV/NightGlass"
GLASS_SLOT_NAME = "Bldg_glass"
KIT_FOLDER_PREFIX = "Kit_Bldg_"
# /Game/Building/<style>/<variant>/<kit folder>/Mesh/<mesh>
KIT_FOLDER_INDEX = 5
# Room IDs are drawn from [0, ROOM_ID_COUNT): the smallest of Epic's four room
# arrays (by window size) holds 5 rooms, so every ID is valid for every window.
ROOM_ID_COUNT = 5


def building_pieces_lit(piece_count: int, seed: int) -> List[bool]:
    """Whether each of ``piece_count`` building facade pieces is lit, drawn
    independently with probability ``LIT_FRACTION``."""
    rng = np.random.Generator(np.random.PCG64([seed, 0x11D0]))
    return [bool(draw < LIT_FRACTION) for draw in rng.random(piece_count)]


def building_piece_room_ids(piece_count: int, seed: int) -> List[int]:
    """A random ``ManualRoomID`` for each of ``piece_count`` pieces, from its
    own RNG stream."""
    rng = np.random.Generator(np.random.PCG64([seed, 0x2007]))
    return [int(room) for room in rng.integers(0, ROOM_ID_COUNT, size=piece_count)]


def night_glass_replacements(asset_path: str) -> Optional[Dict[str, str]]:
    """The ``material_replacements`` entry swapping a wall mesh's glass slot
    for its kit's project-owned lit copy, or ``None`` for an asset that is
    not a building-kit mesh."""
    parts = asset_path.split("/")
    if len(parts) <= KIT_FOLDER_INDEX or not parts[KIT_FOLDER_INDEX].startswith(KIT_FOLDER_PREFIX):
        return None
    name = f"{parts[KIT_FOLDER_INDEX]}_M_Bldg_glass"
    return {GLASS_SLOT_NAME: f"{NIGHT_GLASS_FOLDER}/{name}.{name}"}


def glass_scalar_overrides(lit: bool, room_id: int) -> Dict[str, float]:
    """Material scalars for a module: lit (``LightsOff`` 0) or dark (1), and
    which room it shows (``ManualRoomID``)."""
    return {"LightsOff": 0.0 if lit else 1.0, "ManualRoomID": float(room_id)}
