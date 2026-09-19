"""Unit tests for the flat roof slabs that close the open building tops."""

import numpy as np
import pytest

from src.orchestration.dataset_generator import generate_scenario
from src.procedural.building_placement import Building
from src.procedural.city_sample_assets import BUILDING_STYLES
from src.procedural.roofs import ROOF_PLANE_LIFT_METERS, build_roof_meshes


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

    assert mesh.material == "roof"
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
