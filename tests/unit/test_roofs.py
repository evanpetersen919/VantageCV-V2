"""Unit tests for the flat roof slabs that close the open building tops."""

import numpy as np
import pytest

from src.orchestration.dataset_generator import generate_scenario
from src.procedural.building_placement import Building
from src.procedural.city_sample_assets import BUILDING_STYLES
from src.procedural.roofs import (
    MAX_ROOF_PROPS,
    ROOF_EDGE_CLEARANCE_METERS,
    ROOF_PLANE_LIFT_METERS,
    ROOF_PROP_MIN_SPACING_METERS,
    ROOF_PROPS,
    build_roof_meshes,
    generate_roof_prop_pieces,
)


@pytest.mark.parametrize("style_name", sorted(BUILDING_STYLES))
def test_roof_slab_sits_at_the_top_of_the_last_floor_inside_the_walls(style_name: str) -> None:
    """One upward-facing quad per building, at the top of the last floor
    plus Epic's 5cm, inset from the walls by the family's roof inset."""
    style = BUILDING_STYLES[style_name]
    floors = 4
    building = Building(
        0,
        np.array([10.0, -5.0]),
        style.edge_length_for_wall_count(3),
        style.edge_length_for_wall_count(2),
        style.total_height(floors),
        style_name=style_name,
    )

    meshes = build_roof_meshes([building])
    assert len(meshes) == 1
    mesh = meshes[0]

    assert mesh.material == "roof_0"  # building_id 0 -> the first roof material
    expected_z = style.roof_plane_height(floors) + ROOF_PLANE_LIFT_METERS
    assert np.allclose(mesh.vertices[:, 2], expected_z)
    x_min, y_min, x_max, y_max = building.aabb
    inset = style.roof_inset_m
    assert np.allclose(mesh.vertices[:, :2].min(axis=0), [x_min + inset, y_min + inset])
    assert np.allclose(mesh.vertices[:, :2].max(axis=0), [x_max - inset, y_max - inset])
    a, b, c = (mesh.vertices[i] for i in mesh.triangles[:3])
    assert (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) > 0  # faces up


def test_every_generated_building_gets_a_roof(urban_config, bounds) -> None:
    """A real generated scenario yields one roof per building."""
    scenario = generate_scenario(42, urban_config, bounds, "roof_test")

    assert scenario.buildings
    assert len(build_roof_meshes(scenario.buildings)) == len(scenario.buildings)


def _building(building_id: int, style_name: str = "CHA", walls: int = 4) -> Building:
    style = BUILDING_STYLES[style_name]
    size = style.edge_length_for_wall_count(walls)
    return Building(
        building_id, np.array([0.0, 0.0]), size, size, style.total_height(3), style_name=style_name
    )


def test_roof_material_cycles_through_the_four_migrated_variants_by_building_id() -> None:
    """Epic picks the roof material per building by id; four are migrated."""
    meshes = build_roof_meshes([_building(i) for i in range(8)])

    assert [m.material for m in meshes] == [f"roof_{i % 4}" for i in range(8)]


def test_rooftop_props_stay_on_the_slab_apart_from_each_other_and_deterministic() -> None:
    """Props sit on the roof plane, clear of the edge, at least 3m apart,
    at most the cap, and the same building always gets the same props."""
    building = _building(7, walls=6)
    first = generate_roof_prop_pieces([building])
    second = generate_roof_prop_pieces([building])
    style = BUILDING_STYLES[building.style_name]
    z = style.roof_plane_height(style.floor_count_for_height(building.height))
    x_min, y_min, x_max, y_max = building.aabb
    assets = {path for path, _, _ in ROOF_PROPS}

    assert first
    assert len(first) <= MAX_ROOF_PROPS
    assert [(p.asset_path, tuple(p.position), p.rotation_rad) for p in first] == [
        (p.asset_path, tuple(p.position), p.rotation_rad) for p in second
    ]
    for piece in first:
        assert piece.asset_path in assets
        assert piece.position[2] == pytest.approx(z + ROOF_PLANE_LIFT_METERS)
        assert x_min + ROOF_EDGE_CLEARANCE_METERS <= piece.position[0] <= x_max - 1.5
        assert y_min + ROOF_EDGE_CLEARANCE_METERS <= piece.position[1] <= y_max - 1.5
    points = np.array([p.position[:2] for p in first])
    for i, a in enumerate(points):
        for b in points[i + 1 :]:
            assert np.linalg.norm(a - b) >= ROOF_PROP_MIN_SPACING_METERS - 1e-9


def test_a_roof_too_small_for_props_gets_none() -> None:
    """A tiny roof (under one prop's worth of area) gets no equipment."""
    style = BUILDING_STYLES["CHA"]
    size = style.edge_length_for_wall_count(1)
    tiny = Building(0, np.array([0.0, 0.0]), size, size, style.total_height(1), style_name="CHA")

    assert not generate_roof_prop_pieces([tiny])
