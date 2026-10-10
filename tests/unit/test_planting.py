"""Unit tests for the curb-side grass patches, shrubs and hedges (``planting.py``)."""

import numpy as np
import pytest

from src.ground_truth.semantic_classes import TERRAIN, VEGETATION, mesh_class
from src.orchestration.dataset_generator import generate_scenario
from src.procedural import planting
from src.procedural.environment import Season, TimeOfDay
from src.procedural.lane_topology import LaneTopologyGenerator
from src.procedural.road_network import RoadNetworkGenerator
from src.utils.config_loader import load_scenario_config

OLD_TEMPLATE = "configs/scenario_templates/urban_dense_v15.yaml"
TEMPLATE = "configs/scenario_templates/urban_dense_v16.yaml"
BOUNDS = (-150.0, -150.0, 150.0, 150.0)


def _network(seed: int = 80003):
    config = load_scenario_config(TEMPLATE)
    nodes, edges = RoadNetworkGenerator(seed, config).generate(BOUNDS)
    return edges, LaneTopologyGenerator().generate(nodes, edges)


def test_patches_are_deterministic_and_seed_dependent() -> None:
    """The same seed gives the same layout, another seed another one."""
    edges, lanes = _network()
    first = planting.plan_patches(lanes, edges, [], 5)
    assert first == planting.plan_patches(lanes, edges, [], 5)
    assert first != planting.plan_patches(lanes, edges, [], 6)
    assert len(first) > 10
    assert {patch.style for patch in first} == set(planting.STYLES)


def test_patches_keep_clear_of_keep_out_rectangles() -> None:
    """No patch comes within the buffer of a driveway rectangle, and some are removed by one."""
    edges, lanes = _network()
    free = planting.plan_patches(lanes, edges, [], 5)
    centre = free[len(free) // 2].rect
    keep_out = (centre[0] - 0.5, centre[1] - 0.5, centre[2] + 0.5, centre[3] + 0.5)
    blocked = planting.plan_patches(lanes, edges, [keep_out], 5)
    assert all(planting.rect_gap(p.rect, keep_out) >= planting.KEEP_OUT_BUFFER_M for p in blocked)
    assert len(blocked) < len(free)
    assert all(patch in free for patch in blocked)  # a keep-out only removes patches


def test_patch_geometry_is_a_narrow_strip_on_the_sidewalk() -> None:
    """Each patch is a strip as wide as the design says and between the length limits."""
    edges, lanes = _network()
    width = planting.STRIP_OFFSET_M[1] - planting.STRIP_OFFSET_M[0]
    for patch in planting.plan_patches(lanes, edges, [], 5):
        x_min, y_min, x_max, y_max = patch.rect
        sides = sorted([x_max - x_min, y_max - y_min])
        assert sides[0] == pytest.approx(width, abs=1e-6)
        assert planting.PATCH_LENGTH_M[0] - 1e-6 <= sides[1] <= planting.PATCH_LENGTH_M[1] + 1e-6


def test_grass_mesh_is_upward_flat_and_labelled_terrain() -> None:
    """One mesh of upward quads at the grass height; the class is terrain."""
    edges, lanes = _network()
    patches = planting.plan_patches(lanes, edges, [], 5)
    meshes = planting.grass_mesh(patches)
    assert len(meshes) == 1 and meshes[0].material == "grass"
    mesh = meshes[0]
    assert len(mesh.vertices) == 4 * len(patches)
    assert np.allclose(mesh.vertices[:, 2], planting.GRASS_Z_M)
    assert mesh.triangles.max() < len(mesh.vertices)
    corners = mesh.vertices[mesh.triangles.reshape(-1, 3)]  # [triangles, 3 corners, xyz]
    edge_a, edge_b = corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]
    assert (
        edge_a[:, 0] * edge_b[:, 1] - edge_a[:, 1] * edge_b[:, 0] > 0
    ).all()  # counter-clockwise
    assert mesh_class("grass") == TERRAIN
    assert not planting.grass_mesh([])


def test_shrubs_only_in_leafy_seasons_and_only_where_planted() -> None:
    """No shrubs in winter, none on lawn patches, a foliage mesh otherwise."""
    edges, lanes = _network()
    patches = planting.plan_patches(lanes, edges, [], 5)
    assert not planting.shrub_meshes(patches, Season.WINTER, 5)
    lawns = [patch for patch in patches if patch.style == "lawn"]
    assert not planting.shrub_meshes(lawns, Season.SUMMER, 5)
    meshes = planting.shrub_meshes(patches, Season.SUMMER, 5)
    assert len(meshes) == 1 and meshes[0].material == "foliage_summer"
    assert mesh_class(meshes[0].material) == VEGETATION
    assert meshes[0].vertices[:, 2].max() < 2.5


def _scenario(template: str, season: Season):
    return generate_scenario(
        80003, load_scenario_config(template), BOUNDS, "s", season=season, time_of_day=TimeOfDay.DAY
    )


def test_off_by_default_and_on_in_the_v16_template() -> None:
    """Earlier templates get no grass; v16 adds it in every season (a lawn needs no leaves)."""
    assert load_scenario_config(OLD_TEMPLATE).planting is False
    assert load_scenario_config(TEMPLATE).planting is True
    assert not any(m.material == "grass" for m in _scenario(OLD_TEMPLATE, Season.SUMMER).meshes)
    for season in (Season.SUMMER, Season.WINTER):
        assert any(m.material == "grass" for m in _scenario(TEMPLATE, season).meshes)
