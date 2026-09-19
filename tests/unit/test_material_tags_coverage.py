"""Coverage test for configs/material_tags.json.

configs/material_tags.json is the single source of truth for every
material tag string the Python side can emit as a Mesh.material value;
the C++ MaterialResolver is hand-authored against the same file (see
KNOWN_GAPS_AND_ISSUES.md for why no cross-language codegen is used for
this scope). This test asserts that file's own coverage stays complete
as new tags are added on the Python side, so a missing entry is caught
here rather than silently falling back to UE5's default material at
runtime.
"""

import json
from pathlib import Path

from src.procedural.building_placement import BUILDING_MATERIALS_BY_TYPE

_MATERIAL_TAGS_PATH = Path(__file__).resolve().parents[2] / "configs" / "material_tags.json"

# Tags mesh_factory.py emits as fixed string literals, not derived from
# building_placement.py's own per-type material table -- see
# MeshFactory.build_road_mesh/build_vehicle_mesh/build_pedestrian_mesh.
_FIXED_MESH_FACTORY_TAGS = {
    "asphalt",
    "vehicle_paint",
    "pedestrian",
    "ground",
    "pavement",
    "roof_0",
    "roof_1",
    "roof_2",
    "roof_3",
}


def _load_material_tags() -> dict:
    with open(_MATERIAL_TAGS_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def test_material_tags_json_is_valid_and_loadable() -> None:
    """configs/material_tags.json exists and parses as valid JSON with a
    "tags" object."""
    data = _load_material_tags()
    assert "tags" in data
    assert isinstance(data["tags"], dict)
    assert len(data["tags"]) > 0


def test_every_building_material_tag_is_covered() -> None:
    """Every material string BUILDING_MATERIALS_BY_TYPE can sample for
    any BuildingType has a configs/material_tags.json entry."""
    data = _load_material_tags()
    covered_tags = set(data["tags"].keys())

    emittable_tags = {
        material for materials in BUILDING_MATERIALS_BY_TYPE.values() for material in materials
    }
    missing = emittable_tags - covered_tags
    assert not missing, f"configs/material_tags.json is missing building material tag(s): {missing}"


def test_every_fixed_mesh_factory_tag_is_covered() -> None:
    """Every fixed-string material tag MeshFactory itself can emit
    (independent of building_placement.py) has a
    configs/material_tags.json entry."""
    data = _load_material_tags()
    covered_tags = set(data["tags"].keys())

    missing = _FIXED_MESH_FACTORY_TAGS - covered_tags
    assert (
        not missing
    ), f"configs/material_tags.json is missing fixed mesh_factory tag(s): {missing}"


def test_every_material_tag_entry_has_a_real_game_asset_path() -> None:
    """Every entry's asset_path looks like a real UE5 /Game/ content
    path, not a placeholder -- catches an accidentally-empty or
    malformed entry."""
    data = _load_material_tags()
    for tag, entry in data["tags"].items():
        assert "asset_path" in entry, f"tag {tag!r} has no asset_path"
        assert entry["asset_path"].startswith("/Game/"), (
            f"tag {tag!r}'s asset_path {entry['asset_path']!r} doesn't look like a real "
            "UE5 content path"
        )
