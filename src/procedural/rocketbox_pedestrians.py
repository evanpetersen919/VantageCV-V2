"""Microsoft Rocketbox pedestrians in place of City Sample's crowd characters.

``pedestrian_source: rocketbox`` in a scenario config swaps every placed pedestrian for a baked
Rocketbox avatar (MIT-licensed, Microsoft 2020; ``bin/bake_rocketbox.py`` makes and imports the
meshes) after the scenario is generated. Placement, headings, walking-or-standing and gender are
exactly those of the City Sample scenario with the same seed; only the avatar and its pose differ.
The choice of avatar and pose uses its own random stream, so no other draw of the generator moves.

Each baked mesh is a static posed mesh: feet on z = 0, centred on x and y, facing +Y at rotation 0.
The measured extents of every mesh (``configs/rocketbox_catalog.json``) give the pedestrian's width
(x), depth (y) and height (z), as the measured animation extents do for City Sample's characters.
At render time ``rotation_rad = heading + ROCKETBOX_FORWARD_OFFSET_RAD`` turns the avatar to face
its heading (checked in the game with the avatar facing toward, away from and across the camera).
"""

import json
import math
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

from src.procedural.actor_placement import Pedestrian
from src.procedural.city_sample_assets import PEDESTRIAN_STANDING_CLIP

CATALOG_PATH = Path(__file__).resolve().parents[2] / "configs" / "rocketbox_catalog.json"
ASSET_ROOT = "/Game/VantageCV/Pedestrians/Rocketbox"
ROCKETBOX_FORWARD_OFFSET_RAD = -math.pi / 2
STREAM_TAG = 0x40C8


@lru_cache(maxsize=1)
def catalog() -> Dict[str, Any]:
    """The baked avatars and the measured extents of each of their meshes."""
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def is_rocketbox(asset_path: str) -> bool:
    """Whether ``asset_path`` is one of the baked Rocketbox meshes."""
    return asset_path.startswith(ASSET_ROOT + "/")


def mesh_path(avatar: str, pose: str) -> str:
    """The project path of one baked mesh."""
    return f"{ASSET_ROOT}/{avatar}/{avatar}_{pose}"


def _gender(pedestrian: Pedestrian) -> str:
    """``"f"`` or ``"m"`` from the City Sample body mesh the pedestrian was drawn with."""
    name = pedestrian.asset_path.split("/")[-1]  # SM_<gender>_tal_<weight>_body
    return name.split("_")[1]


def _standing(pedestrian: Pedestrian) -> bool:
    low, high = PEDESTRIAN_STANDING_CLIP
    return low <= pedestrian.pose_frame <= high


def _options(gender: str, standing: bool) -> List[Tuple[str, Dict[str, Any]]]:
    kind = "standing" if standing else "walking"
    return [
        (avatar["avatar"], pose)
        for avatar in catalog()["avatars"]
        if avatar["gender"] == gender
        for pose in avatar["poses"]
        if pose["kind"] == kind
    ]


def swap_pedestrians(pedestrians: Sequence[Pedestrian], seed: int) -> List[Pedestrian]:
    """``pedestrians`` with each one's avatar and pose replaced by a Rocketbox mesh of the
    same gender and activity."""
    rng = np.random.Generator(np.random.PCG64([seed, STREAM_TAG]))
    swapped: List[Pedestrian] = []
    for pedestrian in pedestrians:
        options = _options(_gender(pedestrian), _standing(pedestrian))
        avatar, pose = options[int(rng.integers(len(options)))]
        swapped.append(
            replace(
                pedestrian,
                asset_path=mesh_path(avatar, pose["pose"]),
                part_paths=[],
                pose_frame=0.0,
                width=float(pose["x"]),
                depth=float(pose["y"]),
                height=float(pose["z"]),
                box_offset=(0.0, 0.0),
            )
        )
    return swapped
