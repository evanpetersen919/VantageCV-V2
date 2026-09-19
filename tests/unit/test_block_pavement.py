"""Unit tests for the sidewalk-height paving inside every city block."""

import numpy as np

from src.orchestration.dataset_generator import generate_scenario
from src.procedural.block_pavement import BLOCK_PAVEMENT_Z_METERS, build_block_pavement_meshes
from src.procedural.building_placement import identify_city_blocks
from src.procedural.lane_topology import LANE_WIDTH_METERS


def test_no_edges_means_no_pavement() -> None:
    """Nothing to bound a block, so nothing is built."""
    assert not build_block_pavement_meshes({}, {})


def test_one_quad_per_block_inset_by_the_road_half_width(urban_config, bounds) -> None:
    """Each block gets one upward-facing quad whose edges sit exactly one
    road half-width inside the block (the curb line), at sidewalk height."""
    scenario = generate_scenario(42, urban_config, bounds, "pavement_test")
    blocks = identify_city_blocks(scenario.nodes, scenario.edges)
    meshes = build_block_pavement_meshes(scenario.nodes, scenario.edges)
    inset = max(e.num_lanes for e in scenario.edges.values()) * LANE_WIDTH_METERS

    assert blocks
    assert len(meshes) == len(blocks)  # every block here is larger than the roads' pavement
    for block, mesh in zip(blocks, meshes):
        assert mesh.material == "pavement"
        assert np.allclose(mesh.vertices[:, 2], BLOCK_PAVEMENT_Z_METERS)
        assert np.allclose(mesh.vertices[:, :2].min(axis=0), block.min(axis=0) + inset)
        assert np.allclose(mesh.vertices[:, :2].max(axis=0), block.max(axis=0) - inset)
        for first in range(0, 6, 3):
            a, b, c = (mesh.vertices[i] for i in mesh.triangles[first : first + 3])
            assert (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) > 0  # faces up


def test_pavement_stays_below_the_sidewalk_slabs_top() -> None:
    """The fill must not poke through the real sidewalk slabs (top about
    10.8cm above the road crown)."""
    assert BLOCK_PAVEMENT_Z_METERS < 0.108
