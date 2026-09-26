"""The real ground-truth box of a placed pedestrian, from measured animation extents.

Pedestrians are animated by vertex-animation textures, so their meshes do not give
the posed shape. ``bin/measure_pedestrian_extents.py`` renders every body at every
10th frame of its animation and records, relative to the pivot (the feet), the
forward/backward and left/right extents (``pedestrian_bounds.py``). The head-top
height, hair included, is measured per character and does not depend on pose or
weight (spread under 1 cm across 144 renders).

The animation has two clips: a walk cycle (frames 0-319) and a second baked
activity (320-429); a pose is interpolated only within its own clip.
"""

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import numpy as np

from src.procedural.pedestrian_bounds import PEDESTRIAN_HEAD_HEIGHTS, PEDESTRIAN_POSE_EXTENTS

WALK_CLIP_END_FRAME = 320
Row = Tuple[float, float, float, float, float]  # frame, fwd_min, fwd_max, lat_min, lat_max


@dataclass(frozen=True)
class PedestrianBox:
    """A pedestrian's box in its own frame: extents and the box centre's offset from the
    pivot, forward (along heading) and lateral (to the pedestrian's left, +y at heading 0)."""

    length: float
    width: float
    height: float
    offset_forward: float
    offset_lateral: float


def interpolate_extents(rows: Sequence[Row], frame: float) -> Tuple[float, float, float, float]:
    """(forward_min, forward_max, lateral_min, lateral_max) at ``frame``, interpolated
    between the measured rows of the same clip (held at the clip's ends)."""
    clip = [row for row in rows if (row[0] < WALK_CLIP_END_FRAME) == (frame < WALK_CLIP_END_FRAME)]
    frames = [row[0] for row in clip]
    return (
        float(np.interp(frame, frames, [row[1] for row in clip])),
        float(np.interp(frame, frames, [row[2] for row in clip])),
        float(np.interp(frame, frames, [row[3] for row in clip])),
        float(np.interp(frame, frames, [row[4] for row in clip])),
    )


def character_id(face_asset_path: str) -> str:
    """The character number in a face asset path (``.../SM_f_003_nrw_FaceMesh`` -> ``003``)."""
    return face_asset_path.split("/")[-1].split("_")[2]


def pedestrian_box(
    gender: str, weight: str, face_asset_path: str, pose_frame: float
) -> Optional[PedestrianBox]:
    """The measured box of a pedestrian, or ``None`` if its body or face was not measured."""
    rows = PEDESTRIAN_POSE_EXTENTS.get(f"{gender}_{weight}")
    height = PEDESTRIAN_HEAD_HEIGHTS.get(f"{gender}_{character_id(face_asset_path)}")
    if rows is None or height is None:
        return None
    forward_min, forward_max, lateral_min, lateral_max = interpolate_extents(rows, pose_frame)
    return PedestrianBox(
        length=forward_max - forward_min,
        width=lateral_max - lateral_min,
        height=height,
        offset_forward=(forward_max + forward_min) / 2.0,
        offset_lateral=(lateral_max + lateral_min) / 2.0,
    )
