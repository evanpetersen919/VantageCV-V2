"""Unit tests for the scanned photographic street trees (``photoreal_trees.py``)."""

import numpy as np
import pytest

from src.ground_truth.semantic_classes import VEGETATION, asset_class
from src.orchestration.dataset_generator import generate_scenario
from src.orchestration.scenario_serializer import serialize_scenario
from src.procedural import photoreal_trees as pt
from src.procedural.environment import Season, TimeOfDay
from src.procedural.street_furniture import TREE_ASSET_PATHS
from src.utils.config_loader import load_scenario_config

TEMPLATE = "configs/scenario_templates/urban_dense_v17.yaml"
CARD_TEMPLATE = "configs/scenario_templates/urban_dense_v16.yaml"
BOUNDS = (-150.0, -150.0, 150.0, 150.0)
SPOTS = [(0.0, 0.0), (13.0, 0.0), (26.0, 4.0)]


def test_winter_and_no_spots_give_no_trees() -> None:
    """No leaves in winter (the bare Epic trees stay), nothing without spots."""
    assert not pt.photoreal_tree_pieces(SPOTS, Season.WINTER, 1)
    assert not pt.photoreal_tree_pieces([], Season.SUMMER, 1)


@pytest.mark.parametrize("season", [Season.SPRING, Season.SUMMER, Season.FALL])
def test_each_tree_carries_its_seasons_leaf_material(season) -> None:
    """One piece per spot, on it, street-tree sized, with the season's leaf material."""
    pieces = pt.photoreal_tree_pieces(SPOTS, season, 1)
    assert len(pieces) == len(SPOTS)
    for piece, spot in zip(pieces, SPOTS):
        assert np.allclose(piece.position[:2], spot) and piece.position[2] == 0.0
        height = piece.scale[0] * pt.TREES["jacaranda_tree"][2]
        assert pt.TREE_HEIGHT_M[0] - 1e-6 <= height <= pt.TREE_HEIGHT_M[1] + 1e-6
        assert piece.scale[0] == piece.scale[1] == piece.scale[2]
        assert piece.material_replacements == {
            "jacaranda_tree_leaves": pt.leaf_material("jacaranda_tree", season)
        }
        assert asset_class(piece.asset_path) == VEGETATION


def test_deterministic_and_seed_dependent() -> None:
    """The same seed gives the same trees, another seed other sizes and turns."""
    first = pt.photoreal_tree_pieces(SPOTS, Season.SUMMER, 7)
    again = pt.photoreal_tree_pieces(SPOTS, Season.SUMMER, 7)
    other = pt.photoreal_tree_pieces(SPOTS, Season.SUMMER, 8)
    assert [p.scale for p in first] == [p.scale for p in again]
    assert [p.rotation_rad for p in first] != [p.rotation_rad for p in other]


def _scenario(template: str, season: Season):
    return generate_scenario(
        80003, load_scenario_config(template), BOUNDS, "s", season=season, time_of_day=TimeOfDay.DAY
    )


def test_template_replaces_card_trees_with_scanned_ones() -> None:
    """v17 puts scanned trees where v16 puts card meshes; the Epic trees are gone either way."""
    config = load_scenario_config(TEMPLATE)
    assert config.photoreal_trees is True and config.foliage is True
    assert load_scenario_config(CARD_TEMPLATE).photoreal_trees is False
    scanned = _scenario(TEMPLATE, Season.SUMMER)
    cards = _scenario(CARD_TEMPLATE, Season.SUMMER)
    trees = [
        p
        for p in scanned.street_furniture_pieces
        if p.asset_path.startswith(pt.TREES["jacaranda_tree"][0])
    ]
    assert trees
    assert not any(p.asset_path in TREE_ASSET_PATHS for p in scanned.street_furniture_pieces)
    assert not any(m.material == "bark" for m in scanned.meshes)  # no card trunks
    assert any(m.material == "bark" for m in cards.meshes)


def test_winter_keeps_the_bare_epic_trees() -> None:
    """No scanned trees in winter; the Epic trees remain."""
    scenario = _scenario(TEMPLATE, Season.WINTER)
    assert not any(
        p.asset_path.startswith(pt.TREES["jacaranda_tree"][0])
        for p in scenario.street_furniture_pieces
    )
    assert any(p.asset_path in TREE_ASSET_PATHS for p in scenario.street_furniture_pieces)


def test_payload_carries_the_leaf_swap_for_street_furniture() -> None:
    """The serializer sends each scanned tree's replacement; other furniture gets none."""
    scenario = _scenario(TEMPLATE, Season.SUMMER)
    payload = serialize_scenario(scenario, None)
    trees = [a for a in payload["assets"] if a["asset_path"] == pt.TREES["jacaranda_tree"][0]]
    assert trees and all("jacaranda_tree_leaves" in a["material_replacements"] for a in trees)
    others = [
        a
        for a in payload["assets"]
        if "Trees" not in a["asset_path"] and "Signals" in str(a.get("material_replacements", ""))
    ]
    assert not [a for a in others if "StopLight" not in a["asset_path"]]
