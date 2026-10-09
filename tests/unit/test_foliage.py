"""Unit tests for the leafy procedural street trees (``foliage.py``) and their scenario wiring."""

import numpy as np
import pytest

from src.ground_truth.semantic_classes import VEGETATION, mesh_class
from src.orchestration.dataset_generator import generate_scenario
from src.procedural import foliage
from src.procedural.environment import Season, TimeOfDay
from src.procedural.street_furniture import TREE_ASSET_PATHS
from src.utils.config_loader import load_scenario_config

OLD_TEMPLATE = "configs/scenario_templates/urban_dense_v15.yaml"
TEMPLATE = "configs/scenario_templates/urban_dense_v16.yaml"
BOUNDS = (-150.0, -150.0, 150.0, 150.0)
SPOTS = [(0.0, 0.0), (12.0, 0.0), (24.0, 3.0)]


def test_winter_has_no_leafy_trees() -> None:
    """No leaves in winter (the bare Epic trees stay), and no spots gives no meshes."""
    assert not foliage.foliage_meshes(SPOTS, Season.WINTER, 1)
    assert not foliage.foliage_meshes([], Season.SUMMER, 1)


@pytest.mark.parametrize("season", [Season.SPRING, Season.SUMMER, Season.FALL])
def test_a_bark_mesh_and_a_foliage_mesh_per_season(season) -> None:
    """Two meshes, bark first, with the season's own foliage tag and consistent buffers."""
    meshes = foliage.foliage_meshes(SPOTS, season, 1)
    assert [m.material for m in meshes] == ["bark", foliage.FOLIAGE_MATERIALS[season]]
    for mesh in meshes:
        assert mesh.vertices.shape[1] == 3 and len(mesh.uvs) == len(mesh.vertices)
        assert len(mesh.triangles) % 3 == 0
        assert mesh.triangles.min() >= 0 and mesh.triangles.max() < len(mesh.vertices)
        assert mesh_class(mesh.material) == VEGETATION


def test_deterministic_and_seed_dependent() -> None:
    """The same seed gives the same trees; another seed gives other trees."""
    first = foliage.foliage_meshes(SPOTS, Season.SUMMER, 7)
    again = foliage.foliage_meshes(SPOTS, Season.SUMMER, 7)
    other = foliage.foliage_meshes(SPOTS, Season.SUMMER, 8)
    assert all(np.array_equal(a.vertices, b.vertices) for a, b in zip(first, again))
    assert not np.array_equal(first[1].vertices, other[1].vertices)


def test_trees_stand_on_their_spots_within_the_design_size() -> None:
    """Each trunk starts at its spot on the ground; the tree is no taller than the design range
    plus a card's reach, and no leaf hangs below 1.8 m (people and vehicles pass under)."""
    meshes = foliage.foliage_meshes([(5.0, -3.0)], Season.SUMMER, 3)
    bark, leaves = meshes[0], meshes[1]
    assert np.isclose(bark.vertices[:, 2].min(), 0.0)
    ground = bark.vertices[bark.vertices[:, 2] == 0.0]
    assert np.allclose(ground[:, :2].mean(axis=0), [5.0, -3.0], atol=1e-6)
    assert leaves.vertices[:, 2].min() > 1.8
    assert leaves.vertices[:, 2].max() < foliage.TOTAL_HEIGHT_M[1] + 2.0
    span = np.ptp(leaves.vertices[:, :2], axis=0)
    assert span.max() < 2 * foliage.CANOPY_RADIUS_M[1] * 1.7 + 4.0


def test_each_tree_has_roughly_the_designed_number_of_cards() -> None:
    """About ``LEAF_CARDS`` quads of four vertices per tree, in lumps."""
    leaves = foliage.foliage_meshes(SPOTS, Season.SUMMER, 1)[1]
    per_tree = len(leaves.vertices) / 4 / len(SPOTS)
    assert foliage.LEAF_CARDS - foliage.LOBES[1] <= per_tree <= foliage.LEAF_CARDS


def _scenario(template: str, season: Season, seed: int = 80003):
    return generate_scenario(
        seed, load_scenario_config(template), BOUNDS, "s", season=season, time_of_day=TimeOfDay.DAY
    )


def _tree_pieces(scenario) -> int:
    return sum(
        1 for piece in scenario.street_furniture_pieces if piece.asset_path in TREE_ASSET_PATHS
    )


def test_off_by_default_and_unchanged_for_old_templates() -> None:
    """Earlier templates keep their Epic trees (none in summer) and get no foliage meshes."""
    assert load_scenario_config(OLD_TEMPLATE).foliage is False
    assert load_scenario_config(TEMPLATE).foliage is True
    old = _scenario(OLD_TEMPLATE, Season.SUMMER)
    assert _tree_pieces(old) == 0
    assert not any(m.material in ("bark", "foliage_summer") for m in old.meshes)


@pytest.mark.parametrize("season", [Season.SPRING, Season.SUMMER, Season.FALL])
def test_v16_replaces_the_bare_trees_with_leafy_ones(season) -> None:
    """Leafy trees in these seasons: foliage meshes present, no bare Epic tree left."""
    scenario = _scenario(TEMPLATE, season)
    tags = {m.material for m in scenario.meshes}
    assert {"bark", foliage.FOLIAGE_MATERIALS[season]} <= tags
    assert _tree_pieces(scenario) == 0


def test_v16_keeps_bare_trees_in_winter() -> None:
    """No leaves in winter: the Epic trees stay and no foliage mesh is added."""
    scenario = _scenario(TEMPLATE, Season.WINTER)
    assert _tree_pieces(scenario) > 0
    assert not any(m.material == "bark" for m in scenario.meshes)


def test_denser_spacing_gives_more_trees() -> None:
    """v16's 12 m spacing puts more trees on the same streets than Epic's measured 20.21 m."""
    config = load_scenario_config(TEMPLATE)
    assert config.street_tree_spacing_m == 12.0
    sparse = config.model_copy(update={"street_tree_spacing_m": 20.21})
    dense = generate_scenario(80003, config, BOUNDS, "s", season=Season.WINTER)
    wide = generate_scenario(80003, sparse, BOUNDS, "s", season=Season.WINTER)
    assert _tree_pieces(dense) > 1.3 * _tree_pieces(wide)
