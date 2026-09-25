"""Unit tests for building_colors.py: palette draws by share, the slot-vector
entries and their payload placement, and that window frames are left alone."""

import pytest

from src.orchestration.dataset_generator import generate_scenario
from src.orchestration.scenario_serializer import serialize_scenario
from src.procedural.building_colors import (
    PAINT_SLOT_PATTERN,
    PAINT_TINT_PARAMETER,
    STONE_SLOT_PATTERNS,
    STONE_TINT_PARAMETER,
    WALL_PALETTES,
    draw_building_palettes,
    piece_palettes,
    wall_slot_vectors,
)


def test_palette_shares_sum_to_one_and_the_stock_finish_has_none() -> None:
    """Shares are a distribution; only the stock entry has no tints."""
    assert sum(palette.share for palette in WALL_PALETTES) == pytest.approx(1.0)
    stock = [palette for palette in WALL_PALETTES if palette.stone is None]
    assert [palette.name for palette in stock] == ["stock"]
    assert all(palette.paint is not None for palette in WALL_PALETTES if palette.stone is not None)


def test_draws_are_deterministic_by_seed_and_follow_the_shares() -> None:
    """Same seed, same draws; a large sample matches each share."""
    assert draw_building_palettes(50, 3) == draw_building_palettes(50, 3)
    assert draw_building_palettes(50, 3) != draw_building_palettes(50, 4)
    draws = draw_building_palettes(8000, 1)
    for index, palette in enumerate(WALL_PALETTES):
        assert draws.count(index) / len(draws) == pytest.approx(palette.share, abs=0.02)


def test_the_stock_palette_adds_nothing_and_others_recolour_stone_and_paint_only() -> None:
    """The stock finish has no entry; a coloured one sets the stone tint on
    block and brick slots and the paint tint on painted-stone slots, and
    nothing that would recolour window frames (painted metal)."""
    assert wall_slot_vectors(0) is None
    vectors = wall_slot_vectors(1)
    assert vectors is not None
    assert set(vectors) == set(STONE_SLOT_PATTERNS) | {PAINT_SLOT_PATTERN}
    for pattern in STONE_SLOT_PATTERNS:
        assert vectors[pattern] == {STONE_TINT_PARAMETER: list(WALL_PALETTES[1].stone)}
    assert vectors[PAINT_SLOT_PATTERN] == {PAINT_TINT_PARAMETER: list(WALL_PALETTES[1].paint)}
    assert not any("etal" in pattern for pattern in vectors)


def test_piece_palettes_follow_each_pieces_building() -> None:
    """Every piece takes its building's palette."""
    assert piece_palettes([0, 0, 1, 2, 2], [5, 3, 7]) == [5, 5, 3, 7, 7]


def test_a_scenarios_buildings_are_recoloured_consistently(urban_config, bounds) -> None:
    """One palette per building (all its pieces share it); several colours
    appear across buildings; only building assets carry the override, and
    the stock buildings carry none."""
    result = generate_scenario(42, urban_config, bounds, "x")
    assert len(result.building_piece_palettes) == len(result.building_facade_pieces)
    assert len(set(result.building_piece_palettes)) > 3
    payload = serialize_scenario(result)
    building_assets = [
        asset for asset in payload["assets"] if asset["asset_path"].startswith("/Game/Building/")
    ][: len(result.building_facade_pieces)]
    assert len(building_assets) == len(result.building_facade_pieces)
    for asset, palette in zip(building_assets, result.building_piece_palettes):
        assert asset["asset_path"].startswith("/Game/Building/")
        if palette == 0:
            assert "material_slot_vectors" not in asset
        else:
            assert asset["material_slot_vectors"] == wall_slot_vectors(palette)
    others = [a for a in payload["assets"] if not a["asset_path"].startswith("/Game/Building/")]
    assert not any("Bldg_block*" in asset.get("material_slot_vectors", {}) for asset in others)
