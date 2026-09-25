"""Unit tests for building_lights.py: night glass swapped into each wall
mesh's glass slot, with a per-building randomized lit fraction."""

import numpy as np

from src.orchestration.dataset_generator import generate_scenario
from src.orchestration.scenario_serializer import serialize_scenario
from src.procedural.building_facade import FacadePiece
from src.procedural.building_lights import (
    GLASS_SLOT_NAME,
    LIT_FRACTION_RANGE,
    NIGHT_GLASS_FOLDER,
    building_piece_lit_fractions,
    glass_scalar_overrides,
    night_glass_replacements,
)
from src.procedural.environment import TimeOfDay

WALL = "/Game/Building/CH/A/Kit_Bldg_CHA_L1_A/Mesh/SM_BLDG_CHA_L01_A_Wall_01_N1"


def _piece(asset_path: str = WALL) -> FacadePiece:
    return FacadePiece(asset_path, np.array([0.0, 0.0, 0.0]), 0.0)


def test_a_wall_swaps_its_glass_slot_for_its_own_kits_lit_copy() -> None:
    """The replacement is keyed by the glass slot's name and points at the
    project-owned copy named after the wall's kit folder."""
    assert night_glass_replacements(WALL) == {
        GLASS_SLOT_NAME: f"{NIGHT_GLASS_FOLDER}/Kit_Bldg_CHA_L1_A_M_Bldg_glass"
        ".Kit_Bldg_CHA_L1_A_M_Bldg_glass"
    }


def test_non_building_assets_get_no_glass_replacement() -> None:
    """Curbs, lamps and the like are not building-kit meshes."""
    assert night_glass_replacements("/Game/Prop/Kit_StreetLamp_A/Mesh/SM_Lamp") is None
    assert night_glass_replacements("/Game/Vehicle/vehCar_vehicle02/Mesh/SM_Frame") is None


def test_lit_fraction_is_one_value_per_building_within_range() -> None:
    """Every piece of a building shares its building's fraction, one entry
    per piece, all inside the configured range."""
    buildings = [[_piece() for _ in range(n)] for n in (3, 5, 1)]
    fractions = building_piece_lit_fractions(buildings, seed=4)
    assert len(fractions) == 9
    assert len(set(fractions[:3])) == 1
    assert len(set(fractions[3:8])) == 1
    low, high = LIT_FRACTION_RANGE
    assert all(low <= fraction <= high for fraction in fractions)


def test_lit_fractions_are_deterministic_and_differ_by_seed_and_building() -> None:
    """Same seed, same fractions; another seed or another building differs."""
    buildings = [[_piece()] for _ in range(6)]
    first = building_piece_lit_fractions(buildings, seed=7)
    assert first == building_piece_lit_fractions(buildings, seed=7)
    assert first != building_piece_lit_fractions(buildings, seed=8)
    assert len(set(first)) > 1


def test_glass_scalars_leave_the_lit_fraction_of_rooms_on() -> None:
    """AmountOff is the dark fraction, so it is one minus the lit fraction,
    and no room is forced off."""
    assert glass_scalar_overrides(0.25) == {"LightsOff": 0.0, "AmountOff": 0.75}


def test_night_payload_swaps_building_glass_and_day_payload_does_not(urban_config, bounds) -> None:
    """Only a night scenario carries glass replacements (on building-kit
    meshes), each with its building's dark fraction; a day payload has none."""
    day = generate_scenario(42, urban_config, bounds, "day")
    night = generate_scenario(42, urban_config, bounds, "night", time_of_day=TimeOfDay.NIGHT)
    assert not day.building_lit_fractions
    assert len(night.building_lit_fractions) == len(night.building_facade_pieces)
    assert not any("material_replacements" in a for a in serialize_scenario(day)["assets"])
    swapped = [a for a in serialize_scenario(night)["assets"] if "material_replacements" in a]
    assert swapped
    for asset in swapped:
        assert "/Kit_Bldg_" in asset["asset_path"]
        assert asset["material_scalar_overrides"]["LightsOff"] == 0.0
        assert 0.0 <= asset["material_scalar_overrides"]["AmountOff"] <= 1.0
