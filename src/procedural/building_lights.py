"""Randomized lit windows for a night scenario: warm emissive panes placed
just behind real window glass, so a building reads as occupied at night.

City Sample's glass material has no usable "lights on" switch (its
``LightsOff`` value changes nothing in a controlled with/without render --
the few bright windows seen at night are just street-lamp reflections), so
lit windows are drawn the same way vehicle lenses are: small emissive boxes
(``night_lights.SceneGlow`` with ``shape="box"``) sent in the payload's
``"glows"`` array. Positions come from each facade module's own measured
window panes (``building_window_geometry.py``), so every glow sits exactly
behind a real window.

Randomization is deterministic from the scenario seed (a dedicated RNG
stream, so nothing else in a scenario changes): each BUILDING draws its own
lit fraction, then each window cell is lit independently with that
probability, in a warm or (less often) cool white with varied brightness.
The fractions, colours and brightness range are tuned by eye -- real city
occupancy varies far too much to cite one number.
"""

from typing import List, Sequence, Tuple

import numpy as np

from src.procedural.building_facade import FacadePiece
from src.procedural.building_window_geometry import BUILDING_WINDOW_PANES, WindowPane
from src.procedural.environment import NIGHT_ENVIRONMENT
from src.procedural.night_lights import SceneGlow

# Each building's lit fraction is drawn uniformly from this range: some
# buildings are nearly dark, some mostly lit.
LIT_FRACTION_RANGE = (0.05, 0.6)

# A large pane (a curtain-wall storefront, a tall SFA window) is split into
# cells no bigger than this, so lit windows read as windows, not as one huge
# glowing wall. A small gap between cells stands in for a mullion.
MAX_CELL_WIDTH_M = 1.3
MAX_CELL_HEIGHT_M = 1.8
CELL_GAP_M = 0.08

# Which way a facade module's local +Y runs along the wall, in the
# scenario's python frame (its local +X is the outward normal). -1, not the
# +1 that road_edge_kit's curb/sidewalk pieces use, found live: with +1 every
# lit pane landed inside the wall masonry, invisible; with -1 they sit in
# the real window frames.
LATERAL_SIGN = -1.0

# The lit pane sits just behind the glass, and is a thin slab.
BEHIND_GLASS_M = 0.05
SLAB_HALF_DEPTH_M = 0.02

# Saturated amber/orange dominates (a pale warm white washes out to grey
# under the night grade's desaturation -- found live); a minority are cool
# (TV, fluorescent). Brightness is a multiplier around the base intensity.
WARM_COLORS = ((1.0, 0.44, 0.08), (1.0, 0.56, 0.16), (1.0, 0.38, 0.05))
COOL_COLORS = ((0.85, 0.92, 1.0), (0.95, 0.97, 1.0))
COOL_FRACTION = 0.12
BASE_INTENSITY = 0.5
INTENSITY_RANGE = (0.6, 1.4)


def _graded(color: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """``color`` pre-compensated for the night environment's own colour
    gain (cool blue, see ``environment.NIGHT_ENVIRONMENT``), so a warm
    window still reads warm after the grade instead of washing to cool
    white -- found live. Normalised so its brightest channel stays put."""
    gain = NIGHT_ENVIRONMENT.color_gain or (1.0, 1.0, 1.0)
    compensated = [channel / g for channel, g in zip(color, gain)]
    peak = max(compensated)
    return (compensated[0] / peak, compensated[1] / peak, compensated[2] / peak)


def _cells(pane: WindowPane) -> List[Tuple[float, float, float, float]]:
    """A pane split into (lateral, height, half_width, half_height) cells no
    bigger than the max cell size, separated by the mullion gap."""
    columns = max(1, int(np.ceil(2.0 * pane.half_width_m / MAX_CELL_WIDTH_M)))
    rows = max(1, int(np.ceil(2.0 * pane.half_height_m / MAX_CELL_HEIGHT_M)))
    cell_w = 2.0 * pane.half_width_m / columns
    cell_h = 2.0 * pane.half_height_m / rows
    gap_w = CELL_GAP_M if columns > 1 else 0.0
    gap_h = CELL_GAP_M if rows > 1 else 0.0
    cells = []
    for column in range(columns):
        for row in range(rows):
            lateral = pane.lateral_m - pane.half_width_m + cell_w * (column + 0.5)
            height = pane.height_m - pane.half_height_m + cell_h * (row + 0.5)
            cells.append((lateral, height, (cell_w - gap_w) / 2.0, (cell_h - gap_h) / 2.0))
    return cells


def _piece_glows(  # pylint: disable=too-many-locals
    piece: FacadePiece, lit_fraction: float, rng: np.random.Generator
) -> List[SceneGlow]:
    panes = BUILDING_WINDOW_PANES.get(piece.asset_path)
    if not panes:
        return []
    forward = np.array([np.cos(piece.rotation_rad), np.sin(piece.rotation_rad)])
    lateral_axis = LATERAL_SIGN * np.array(
        [np.sin(piece.rotation_rad), -np.cos(piece.rotation_rad)]
    )
    scale = piece.scale or (1.0, 1.0, 1.0)
    base = np.asarray(piece.position, dtype=np.float64)

    glows: List[SceneGlow] = []
    for pane in panes:
        for lateral, height, half_width, half_height in _cells(pane):
            if rng.random() >= lit_fraction:
                continue
            palette = COOL_COLORS if rng.random() < COOL_FRACTION else WARM_COLORS
            color = _graded(palette[int(rng.integers(len(palette)))])
            intensity = BASE_INTENSITY * float(rng.uniform(*INTENSITY_RANGE))
            depth = (pane.forward_m - BEHIND_GLASS_M) * scale[0]
            point = base[:2] + forward * depth + lateral_axis * (lateral * scale[1])
            glows.append(
                SceneGlow(
                    position=(float(point[0]), float(point[1]), float(base[2] + height * scale[2])),
                    color=color,
                    semi_axes_m=(
                        SLAB_HALF_DEPTH_M,
                        abs(half_width * scale[1]),
                        abs(half_height * scale[2]),
                    ),
                    rotation_rad=float(piece.rotation_rad),
                    intensity=intensity,
                    shape="box",
                )
            )
    return glows


def building_window_glows(
    pieces_by_building: Sequence[Sequence[FacadePiece]], seed: int
) -> List[SceneGlow]:
    """Lit-window glows for every building of a night scenario: one lit
    fraction per building, then an independent draw per window cell."""
    rng = np.random.Generator(np.random.PCG64([seed, 0x11D0]))
    glows: List[SceneGlow] = []
    for pieces in pieces_by_building:
        lit_fraction = float(rng.uniform(*LIT_FRACTION_RANGE))
        for piece in pieces:
            glows += _piece_glows(piece, lit_fraction, rng)
    return glows
