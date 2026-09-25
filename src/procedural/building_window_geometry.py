"""Real window-pane rectangles for the City Sample building-facade modules
that have glass, measured from each mesh's own glass-section geometry in a
headless UE5 editor session (``bin/extract_building_windows.py``): the
glass section's triangles are welded and grouped into connected panes, and
each pane's bounds are recorded here.

Every number is in meters in the facade module's own local frame -- the
same frame ``FacadePiece`` places (local +X is the wall's outward normal,
local +Y runs along the wall, Z is up). ``forward_m`` is the pane's
glass-plane depth (its nearest-to-inside face), ``lateral_m`` / ``height_m``
its centre, ``half_width_m`` / ``half_height_m`` its half extents. Only
wall modules have glass: columns, corners and a few wall styles have no
glass section and are absent. Angled bay-window panes are recorded by their
axis-aligned bounds (an approximation).
"""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class WindowPane:
    """One glass pane's position and size in a facade module's local frame."""

    forward_m: float
    lateral_m: float
    height_m: float
    half_width_m: float
    half_height_m: float


BUILDING_WINDOW_PANES: Dict[str, Tuple[WindowPane, ...]] = {
    "/Game/Building/CH/A/Kit_Bldg_CHA_L10_A/Mesh/SM_BLDG_CHA_L10_A_Wall_01_N1": (
        WindowPane(-0.204, -2.434, 1.106, 0.624, 0.768),
        WindowPane(-0.204, -0.816, 1.106, 0.627, 0.771),
    ),
    "/Game/Building/CH/A/Kit_Bldg_CHA_L1_A/Mesh/SM_BLDG_CHA_L01_A_Wall_01_N1": (
        WindowPane(-0.148, -1.625, 2.117, 1.625, 1.724),
    ),
    "/Game/Building/CH/A/Kit_Bldg_CHA_L2_A/Mesh/SM_BLDG_CHA_L02_A_Wall_01_N1": (
        WindowPane(-0.501, -0.689, 0.997, 0.409, 0.862),
        WindowPane(-0.502, -2.564, 0.997, 0.408, 0.861),
        WindowPane(-0.217, -1.627, 0.996, 0.416, 0.862),
    ),
    "/Game/Building/CH/A/Kit_Bldg_CHA_L3_A/Mesh/SM_BLDG_CHA_L03_A_Wall_01_N1": (
        WindowPane(-0.217, -1.627, 0.997, 0.416, 0.866),
        WindowPane(-0.501, -0.689, 0.996, 0.41, 0.865),
        WindowPane(-0.502, -2.564, 0.997, 0.408, 0.866),
    ),
    "/Game/Building/CH/A/Kit_Bldg_CHA_L4_A/Mesh/SM_BLDG_CHA_L04_A_Wall_01_N1": (
        WindowPane(-0.448, -2.548, 1.459, 0.365, 0.404),
        WindowPane(-0.447, -0.693, 1.459, 0.367, 0.404),
        WindowPane(-0.447, -0.693, 0.61, 0.367, 0.396),
        WindowPane(-0.184, -1.62, 1.036, 0.351, 0.809),
        WindowPane(-0.448, -2.548, 0.61, 0.365, 0.396),
    ),
    "/Game/Building/CH/A/Kit_Bldg_CHA_L5_A/Mesh/SM_BLDG_CHA_L05_A_Wall_01_N1": (
        WindowPane(-0.204, -2.489, 1.077, 0.59, 0.804),
        WindowPane(-0.204, -0.766, 1.078, 0.59, 0.804),
    ),
    "/Game/Building/CH/A/Kit_Bldg_CHA_L6_A/Mesh/SM_BLDG_CHA_L06_A_Wall_01_N1": (
        WindowPane(-0.205, -1.609, 1.952, 0.678, 0.847),
    ),
    "/Game/Building/CH/A/Kit_Bldg_CHA_L7_A/Mesh/SM_BLDG_CHA_L07_A_Wall_01_N1": (
        WindowPane(-0.15, -2.518, 1.497, 0.338, 0.362),
        WindowPane(-0.15, -0.732, 1.496, 0.339, 0.36),
        WindowPane(-0.15, -0.732, 0.645, 0.339, 0.453),
        WindowPane(-0.15, -2.518, 0.645, 0.338, 0.452),
    ),
    "/Game/Building/CH/A/Kit_Bldg_CHA_L8_A/Mesh/SM_BLDG_CHA_L08_A_Wall_01_N1": (
        WindowPane(-0.204, -2.488, 1.079, 0.592, 0.807),
        WindowPane(-0.204, -0.768, 1.079, 0.592, 0.808),
    ),
    "/Game/Building/CH/A/Kit_Bldg_CHA_L9_A/Mesh/SM_BLDG_CHA_L09_A_Wall_01_N1": (
        WindowPane(-0.204, -2.472, 1.165, 0.589, 0.827),
        WindowPane(-0.204, -0.81, 1.166, 0.627, 0.827),
    ),
    "/Game/Building/CH/H/Kit_Bldg_CHH_L1_A/Mesh/SM_BLDG_CHH_L01_A_Wall_02_N1": (
        WindowPane(-0.329, -2.605, 1.516, 0.327, 1.366),
        WindowPane(-0.329, -0.645, 1.516, 0.326, 1.366),
        WindowPane(-0.329, -1.624, 1.516, 0.542, 1.366),
    ),
    "/Game/Building/CH/H/Kit_Bldg_CHH_L3_A/Mesh/SM_BLDG_CHH_L03_A_Wall_02_N1": (
        WindowPane(-0.196, -1.624, 1.369, 0.545, 1.276),
        WindowPane(-0.196, -2.603, 1.369, 0.332, 1.288),
        WindowPane(-0.196, -0.647, 1.369, 0.331, 1.281),
    ),
    "/Game/Building/CH/H/Kit_Bldg_CHH_L4_A/Mesh/SM_BLDG_CHH_L04_A_Wall_02_N1": (
        WindowPane(0.059, -2.809, 2.782, 0.341, 1.369),
        WindowPane(0.057, -0.443, 2.782, 0.342, 1.369),
        WindowPane(0.496, -1.625, 2.781, 0.695, 1.365),
    ),
    "/Game/Building/SF/A/Kit_Bldg_SFA_L1_A/Mesh/SM_BLDG_SFA_L1_A_Wall_01_N1": (
        WindowPane(-0.492, -1.007, 2.826, 0.191, 1.916),
        WindowPane(-0.492, -2.243, 2.826, 0.191, 1.916),
        WindowPane(-0.492, -1.625, 2.826, 0.345, 1.916),
        WindowPane(-0.492, -2.243, 5.704, 0.191, 0.874),
        WindowPane(-0.492, -1.625, 5.704, 0.345, 0.874),
        WindowPane(-0.492, -1.007, 5.704, 0.191, 0.874),
        WindowPane(-0.495, -2.248, 8.993, 0.197, 1.432),
        WindowPane(-0.495, -1.625, 8.993, 0.352, 1.432),
        WindowPane(-0.495, -1.002, 8.993, 0.194, 1.432),
        WindowPane(-0.495, -1.625, 10.907, 0.352, 0.412),
        WindowPane(-0.495, -1.002, 10.907, 0.194, 0.412),
        WindowPane(-0.495, -2.248, 10.907, 0.197, 0.412),
    ),
    "/Game/Building/SF/A/Kit_Bldg_SFA_L2_A/Mesh/SM_BLDG_SFA_L2_A_Wall_01_N1": (
        WindowPane(-0.546, -1.625, 2.481, 0.528, 0.243),
        WindowPane(-0.613, -1.625, 4.866, 0.528, 0.504),
        WindowPane(-0.613, -1.625, 1.585, 0.528, 0.504),
        WindowPane(-0.546, -1.625, 5.761, 0.528, 0.243),
    ),
    "/Game/Building/SF/A/Kit_Bldg_SFA_L3_A/Mesh/SM_BLDG_SFA_L3_A_Wall_01_N1": (
        WindowPane(-0.479, -1.625, 4.9, 0.494, 0.609),
        WindowPane(-0.479, -1.625, 1.211, 0.494, 0.586),
        WindowPane(-0.464, -1.625, 9.526, 0.494, 0.274),
        WindowPane(-0.531, -1.625, 8.499, 0.494, 0.567),
        WindowPane(-0.412, -1.625, 6.002, 0.494, 0.294),
        WindowPane(-0.412, -1.625, 2.272, 0.494, 0.283),
    ),
    "/Game/Building/SF/A/Kit_Bldg_SFA_L4_A/Mesh/SM_BLDG_SFA_L4_A_Wall_01_N1": (
        WindowPane(-0.484, -1.625, 2.329, 0.494, 0.289),
        WindowPane(-0.55, -1.625, 1.243, 0.494, 0.6),
    ),
    "/Game/Building/SF/A/Kit_Bldg_SFA_L5_A/Mesh/SM_BLDG_SFA_L5_A_Wall_01_N1": (
        WindowPane(-0.479, -1.625, 2.405, 0.492, 0.304),
        WindowPane(-0.546, -1.625, 1.274, 0.492, 0.623),
    ),
}
