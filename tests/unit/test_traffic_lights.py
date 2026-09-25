"""Unit tests for the real traffic signal poles at intersection approaches."""

import math

import numpy as np

from src.orchestration.dataset_generator import generate_scenario
from src.procedural.lane_topology import compute_node_clearance
from src.procedural.road_edge_kit import edge_runs
from src.procedural.traffic_lights import (
    TRAFFIC_LIGHT_END_MARGIN_M,
    TRAFFIC_LIGHT_OFFSET_M,
    TRAFFIC_LIGHT_STYLE_LONG,
    generate_traffic_light_pieces,
)
from tests.conftest import straight_road_lanes_and_edges as _straight_road


def test_no_edges_means_no_traffic_lights() -> None:
    """No roads, nothing to place a signal at."""
    assert not generate_traffic_light_pieces({}, {})


def test_one_pole_per_directed_edge_at_its_own_stop_line() -> None:
    """A single directed edge gets exactly one pole, unscaled, using the
    long-arm variant (every road has the same real width today, so only
    that arm reaches across it -- see module docstring)."""
    lanes, edges = _straight_road(100.0)
    pieces = generate_traffic_light_pieces(lanes, edges)
    assert len(pieces) == 1
    piece = pieces[0]
    assert piece.asset_path == TRAFFIC_LIGHT_STYLE_LONG
    assert piece.scale is None
    assert piece.position[2] == 0.0


def test_pole_sits_at_the_intersections_far_corner_offset_from_the_curb() -> None:
    """The pole sits `TRAFFIC_LIGHT_END_MARGIN_M` past the far corner of
    the intersection box (`2 * node_clearance` beyond the run's own,
    already-clearance-trimmed far end), offset outward from the curb
    line by exactly the real lamp offset -- reconstructed from the same
    `edge_runs`/`compute_node_clearance` geometry, not assumed. This is
    the real-world "far-side mast arm" mounting point, not directly over
    this approach's own stop line -- see module docstring."""
    lanes, edges = _straight_road(100.0)
    pieces = generate_traffic_light_pieces(lanes, edges)
    piece = pieces[0]

    run = edge_runs(lanes, edges)[0]
    end_node_id = edges[run.edge_id].end_node_id
    far_side_shift = 2.0 * compute_node_clearance(edges)[end_node_id]
    expected = (
        run.start
        + run.run_direction * (run.length + far_side_shift + TRAFFIC_LIGHT_END_MARGIN_M)
        + run.outward * TRAFFIC_LIGHT_OFFSET_M
    )
    assert np.allclose(piece.position[:2], expected)


def test_mast_arm_points_over_the_road_not_onto_the_sidewalk() -> None:
    """The pole's rotation is `run.rotation_rad + pi`, so its mast arm
    (which grows along local Y = outward at zero offset) points along
    `-outward` -- back over the road, confirmed live and derived
    algebraically (see this module's own docstring)."""
    lanes, edges = _straight_road(100.0)
    pieces = generate_traffic_light_pieces(lanes, edges)
    run = edge_runs(lanes, edges)[0]

    piece = pieces[0]
    local_y = np.array([math.sin(piece.rotation_rad), -math.cos(piece.rotation_rad)])
    assert np.allclose(local_y, -run.outward, atol=1e-9)


def test_short_road_gets_no_traffic_light() -> None:
    """A run too short to hold a pole clear of both trims gets none."""
    lanes, edges = _straight_road(1.0)
    assert not generate_traffic_light_pieces(lanes, edges)


def test_real_generated_scenario_places_a_light_per_directed_edge_with_room(
    urban_config, bounds
) -> None:
    """Smoke test against the real pipeline."""
    scenario = generate_scenario(42, urban_config, bounds, "traffic_light_test")
    assert scenario.traffic_light_pieces
    for piece in scenario.traffic_light_pieces:
        assert piece.asset_path == TRAFFIC_LIGHT_STYLE_LONG
        assert piece.scale is None
