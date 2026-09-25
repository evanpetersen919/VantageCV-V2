"""Unit tests for building_lights.py: night glass swapped into each wall
mesh's glass slot, with a random lit/dark choice per wall module."""

from src.orchestration.dataset_generator import generate_scenario
from src.orchestration.scenario_serializer import serialize_scenario
from src.procedural.building_lights import (
    GLASS_SLOT_NAME,
    LIT_FRACTION,
    NIGHT_GLASS_FOLDER,
    ROOM_ID_COUNT,
    building_piece_room_ids,
    building_pieces_lit,
    glass_scalar_overrides,
    night_glass_replacements,
)
from src.procedural.environment import TimeOfDay

WALL = "/Game/Building/CH/A/Kit_Bldg_CHA_L1_A/Mesh/SM_BLDG_CHA_L01_A_Wall_01_N1"


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


def test_about_the_configured_share_of_pieces_are_lit() -> None:
    """One flag per piece, with the lit share close to LIT_FRACTION (a
    large sample, so the binomial spread is well under a percent)."""
    lit = building_pieces_lit(20000, seed=4)
    assert len(lit) == 20000
    assert abs(sum(lit) / len(lit) - LIT_FRACTION) < 0.02


def test_lit_flags_are_deterministic_and_differ_by_seed() -> None:
    """Same seed, same flags; another seed lights a different set."""
    assert building_pieces_lit(500, seed=7) == building_pieces_lit(500, seed=7)
    assert building_pieces_lit(500, seed=7) != building_pieces_lit(500, seed=8)


def test_room_ids_are_valid_varied_and_deterministic() -> None:
    """One ID per piece inside the room count, every room used, the same for
    a seed and different for another."""
    ids = building_piece_room_ids(500, seed=3)
    assert len(ids) == 500
    assert set(ids) == set(range(ROOM_ID_COUNT))
    assert ids == building_piece_room_ids(500, seed=3)
    assert ids != building_piece_room_ids(500, seed=4)


def test_a_module_carries_its_lit_state_and_room() -> None:
    """LightsOff is 0 for a lit module and 1 for a dark one; the room ID
    passes through as ManualRoomID."""
    assert glass_scalar_overrides(True, 3) == {"LightsOff": 0.0, "ManualRoomID": 3.0}
    assert glass_scalar_overrides(False, 0)["LightsOff"] == 1.0


def test_night_payload_swaps_building_glass_and_day_payload_does_not(urban_config, bounds) -> None:
    """Only a night scenario carries glass replacements (on building-kit
    meshes), each lit or dark; a day payload has none."""
    day = generate_scenario(42, urban_config, bounds, "day")
    night = generate_scenario(42, urban_config, bounds, "night", time_of_day=TimeOfDay.NIGHT)
    assert not day.building_pieces_lit
    assert len(night.building_pieces_lit) == len(night.building_facade_pieces)
    assert len(night.building_piece_room_ids) == len(night.building_facade_pieces)
    assert not any("material_replacements" in a for a in serialize_scenario(day)["assets"])
    swapped = [a for a in serialize_scenario(night)["assets"] if "material_replacements" in a]
    assert swapped
    for asset in swapped:
        assert "/Kit_Bldg_" in asset["asset_path"]
        assert asset["material_scalar_overrides"]["LightsOff"] in (0.0, 1.0)
        assert 0.0 <= asset["material_scalar_overrides"]["ManualRoomID"] < ROOM_ID_COUNT
