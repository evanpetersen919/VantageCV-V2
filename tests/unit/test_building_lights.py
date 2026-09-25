"""Unit tests for building_lights.py: randomized lit windows placed behind
each facade module's own measured window panes."""

import numpy as np
import pytest

from src.orchestration.dataset_generator import generate_scenario
from src.procedural.building_facade import FacadePiece
from src.procedural.building_lights import (
    BEHIND_GLASS_M,
    LATERAL_SIGN,
    MAX_CELL_HEIGHT_M,
    MAX_CELL_WIDTH_M,
    SLAB_HALF_DEPTH_M,
    _cells,
    _graded,
    building_window_glows,
)
from src.procedural.building_window_geometry import BUILDING_WINDOW_PANES, WindowPane
from src.procedural.environment import NIGHT_ENVIRONMENT, TimeOfDay

# A wall module with several real panes (measured), and one with none.
WALL = next(path for path, panes in BUILDING_WINDOW_PANES.items() if len(panes) >= 3)
NO_GLASS = "/Game/Building/CH/A/Kit_Bldg_CHA_L1_A/Mesh/SM_BLDG_CHA_L01_A_Column_01_N1"


def _piece(asset_path: str = WALL, rotation_rad: float = 0.0) -> FacadePiece:
    return FacadePiece(asset_path, np.array([10.0, 20.0, 0.0]), rotation_rad)


def test_window_geometry_table_is_physically_sensible() -> None:
    """Every measured pane has positive half extents, sits at a plausible
    height, and only glass-bearing wall modules are listed."""
    assert BUILDING_WINDOW_PANES
    assert NO_GLASS not in BUILDING_WINDOW_PANES
    for panes in BUILDING_WINDOW_PANES.values():
        for pane in panes:
            assert pane.half_width_m > 0.0 and pane.half_height_m > 0.0
            assert 0.0 <= pane.height_m - pane.half_height_m < 12.0


def test_a_small_pane_is_one_cell_and_a_large_pane_is_split_into_bounded_cells() -> None:
    """A normal window is a single lit cell; a curtain wall or tall SFA
    window splits into cells no bigger than the max cell size, tiling the
    pane's own extent exactly."""
    small = WindowPane(0.0, 0.0, 1.0, 0.5, 0.7)
    assert len(_cells(small)) == 1

    big = WindowPane(0.0, -1.6, 2.0, 1.6, 1.9)
    cells = _cells(big)
    assert len(cells) > 1
    for _, _, half_w, half_h in cells:
        assert 2.0 * half_w <= MAX_CELL_WIDTH_M + 1e-9
        assert 2.0 * half_h <= MAX_CELL_HEIGHT_M + 1e-9
    laterals = [lateral for lateral, _, _, _ in cells]
    assert min(laterals) > big.lateral_m - big.half_width_m
    assert max(laterals) < big.lateral_m + big.half_width_m


def test_a_module_with_no_glass_never_gets_a_lit_window() -> None:
    """Columns, corners and glass-less wall styles produce nothing."""
    assert not building_window_glows([[_piece(NO_GLASS)]], seed=1)


def test_lit_windows_sit_just_behind_the_real_pane_in_the_modules_frame(monkeypatch) -> None:
    """With every window lit (rotation 0, so the module's outward normal is
    +x): each slab is exactly at a pane cell's centre -- just behind the
    glass along the outward normal, along the wall by the cell's lateral
    offset (with the measured axis sign), at the cell's height -- and is a
    thin box turned to the piece's heading."""
    monkeypatch.setattr("src.procedural.building_lights.LIT_FRACTION_RANGE", (1.0, 1.0))
    glows = building_window_glows([[_piece(WALL, rotation_rad=0.0)]], seed=3)

    expected = set()
    for pane in BUILDING_WINDOW_PANES[WALL]:
        for lateral, height, _, _ in _cells(pane):
            expected.add(
                (
                    round(10.0 + pane.forward_m - BEHIND_GLASS_M, 6),
                    round(20.0 - LATERAL_SIGN * lateral, 6),
                    round(height, 6),
                )
            )
    got = {
        (round(g.position[0], 6), round(g.position[1], 6), round(g.position[2], 6)) for g in glows
    }
    assert got == expected
    for glow in glows:
        assert glow.shape == "box"
        assert glow.semi_axes_m[0] == SLAB_HALF_DEPTH_M
        assert glow.rotation_rad == 0.0


def test_windows_are_deterministic_for_a_seed_and_differ_between_seeds() -> None:
    """Same seed, same lit windows; a different seed lights a different
    set."""
    pieces = [[_piece(WALL, r) for r in (0.0, 1.0, 2.0, 3.0)] for _ in range(4)]
    first = [g.to_json() for g in building_window_glows(pieces, seed=7)]
    again = [g.to_json() for g in building_window_glows(pieces, seed=7)]
    other = [g.to_json() for g in building_window_glows(pieces, seed=8)]
    assert first == again
    assert first != other


def test_each_building_draws_its_own_lit_fraction() -> None:
    """Buildings differ in how many windows are lit -- some nearly dark,
    some mostly lit -- not one global rate."""
    pieces = [[_piece(WALL, r) for r in np.linspace(0.0, 6.0, 40)] for _ in range(12)]
    rng_counts = []
    for building in range(12):
        glows = building_window_glows([pieces[building]], seed=100 + building)
        rng_counts.append(len(glows))
    assert max(rng_counts) > 2 * max(min(rng_counts), 1)


def test_graded_colors_cancel_the_night_grades_blue_gain() -> None:
    """After pre-compensation, multiplying by the night grade's own gain
    gives back the original colour's hue (ratios preserved)."""
    gain = NIGHT_ENVIRONMENT.color_gain
    assert gain is not None
    original = (1.0, 0.44, 0.08)
    graded = _graded(original)
    after_grade = np.array(graded) * np.array(gain)
    expected_ratio = np.array(original) / original[0]
    assert (after_grade / after_grade[0]) == pytest.approx(expected_ratio)


def test_day_scenario_has_no_window_glows_and_night_has_many(urban_config, bounds) -> None:
    """Lit windows are a night-only feature, and a night scenario actually
    gets them."""
    day = generate_scenario(42, urban_config, bounds, "day")
    night = generate_scenario(42, urban_config, bounds, "night", time_of_day=TimeOfDay.NIGHT)
    assert not day.window_glows
    assert night.window_glows
    assert {glow.shape for glow in night.window_glows} == {"box"}
