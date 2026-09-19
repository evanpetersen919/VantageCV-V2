"""Unit tests for the real curb/sidewalk pieces along road edges."""

import math
from typing import Dict, Tuple

import numpy as np

from src.orchestration.dataset_generator import generate_scenario
from src.procedural.building_facade import FacadePiece
from src.procedural.lane_topology import (
    LANE_WIDTH_METERS,
    SIDEWALK_WIDTH_METERS,
    Lane,
    LaneTopologyGenerator,
)
from src.procedural.road_edge_kit import DEFAULT_ROAD_EDGE_KIT, generate_road_edge_pieces
from src.procedural.road_network import IntersectionType, RoadEdge, RoadNode, RoadType


def _straight_road(
    length: float, num_lanes: int = 2
) -> Tuple[Dict[int, Lane], Dict[int, RoadEdge]]:
    """One directed edge along +x from the origin, with its real lanes
    (trimmed by the node clearance exactly as in a generated network)."""
    nodes = {
        0: RoadNode(0, np.array([0.0, 0.0]), IntersectionType.ISOLATED),
        1: RoadNode(1, np.array([length, 0.0]), IntersectionType.ISOLATED),
    }
    edge = RoadEdge(
        edge_id=0,
        start_node_id=0,
        end_node_id=1,
        road_type=RoadType.MINOR,
        centerline=np.array([[0.0, 0.0], [length, 0.0]]),
        length=length,
        num_lanes=num_lanes,
        speed_limit_kmh=50,
        width_meters=num_lanes * LANE_WIDTH_METERS,
    )
    edges = {0: edge}
    return LaneTopologyGenerator().generate(nodes, edges), edges


def _local_axes(rotation_rad: float) -> Tuple[np.ndarray, np.ndarray]:
    """A mesh's local X and Y in the python frame (verified live)."""
    x_axis = np.array([math.cos(rotation_rad), math.sin(rotation_rad)])
    y_axis = np.array([math.sin(rotation_rad), -math.cos(rotation_rad)])
    return x_axis, y_axis


def test_pieces_sit_on_the_pavement_outer_edge() -> None:
    """Every curb/sidewalk pivot lies on the outermost lane's outer
    boundary: num_lanes * 3.5m from the centerline."""
    lanes, edges = _straight_road(100.0, num_lanes=2)
    pieces = generate_road_edge_pieces(lanes, edges)

    assert pieces
    offsets = {round(abs(float(p.position[1])), 6) for p in pieces}
    assert offsets == {2 * LANE_WIDTH_METERS}


def test_curb_and_sidewalk_runs_fill_the_trimmed_length_exactly() -> None:
    """Stretched pieces exactly tile the run between the trimmed ends."""
    lanes, edges = _straight_road(100.0)
    pieces = generate_road_edge_pieces(lanes, edges)
    outer = next(iter(lanes.values())).left_boundary
    run_length = float(np.linalg.norm(outer[-1] - outer[0]))

    for asset_paths, tile in (
        (DEFAULT_ROAD_EDGE_KIT.curb_asset_paths, DEFAULT_ROAD_EDGE_KIT.curb_length_m),
        (DEFAULT_ROAD_EDGE_KIT.sidewalk_asset_paths, DEFAULT_ROAD_EDGE_KIT.sidewalk_length_m),
    ):
        run = [p for p in pieces if p.asset_path in asset_paths]
        assert run
        stretches = [p.scale[0] for p in run if p.scale is not None]
        assert abs(sum(stretch * tile for stretch in stretches) - run_length) < 1e-9
        assert all(0.8 < stretch < 1.25 for stretch in stretches)


def test_curb_uses_epics_mirror_and_shrink_scale() -> None:
    """Curbs carry (stretch, -0.75, 0.75); sidewalks (stretch, 1, 1)."""
    lanes, edges = _straight_road(60.0)
    pieces = generate_road_edge_pieces(lanes, edges)

    for piece in pieces:
        assert piece.scale is not None
        if piece.asset_path in DEFAULT_ROAD_EDGE_KIT.curb_asset_paths:
            assert piece.scale[1:] == (-0.75, 0.75)
        else:
            assert piece.scale[1:] == (1.0, 1.0)


def test_local_y_points_outward_and_local_x_runs_along_the_road() -> None:
    """Sidewalks extend outward from the curb line: each piece's local Y
    must point away from the road (right-hand side of the +x edge is -y),
    and its local X must run along the road."""
    lanes, edges = _straight_road(80.0)
    pieces = generate_road_edge_pieces(lanes, edges)

    for piece in pieces:
        x_axis, y_axis = _local_axes(piece.rotation_rad)
        assert np.allclose(y_axis, [0.0, -1.0], atol=1e-9)  # outward = right of +x
        assert np.isclose(abs(x_axis[0]), 1.0)


def test_heights_put_sidewalk_and_curb_just_above_the_road() -> None:
    """z offsets are the measured ones (sidewalk top ~10.8cm, curb top
    ~11cm above the road crown)."""
    lanes, edges = _straight_road(60.0)
    pieces = generate_road_edge_pieces(lanes, edges)

    for piece in pieces:
        expected = (
            DEFAULT_ROAD_EDGE_KIT.curb_z_m
            if piece.asset_path in DEFAULT_ROAD_EDGE_KIT.curb_asset_paths
            else DEFAULT_ROAD_EDGE_KIT.sidewalk_z_m
        )
        assert piece.position[2] == expected


def test_generated_scenario_has_road_edge_pieces_and_buildings_clear_the_sidewalk(
    urban_config, bounds
) -> None:
    """A real generated scenario gets curb/sidewalk pieces, and no
    building intrudes on the 3m sidewalk beside a road's pavement."""
    scenario = generate_scenario(42, urban_config, bounds, "road_edge_test")

    assert scenario.road_edge_pieces
    assert all(isinstance(p, FacadePiece) for p in scenario.road_edge_pieces)
    clearance = 2 * LANE_WIDTH_METERS + SIDEWALK_WIDTH_METERS
    for building in scenario.buildings:
        x_min, y_min, x_max, y_max = building.aabb
        for edge in scenario.edges.values():
            a, b = edge.centerline[0], edge.centerline[-1]
            if abs(a[0] - b[0]) < 1e-6:  # vertical road
                gap = max(x_min - a[0], a[0] - x_max, 0.0)
                spans = not (y_max < min(a[1], b[1]) or y_min > max(a[1], b[1]))
            elif abs(a[1] - b[1]) < 1e-6:  # horizontal road
                gap = max(y_min - a[1], a[1] - y_max, 0.0)
                spans = not (x_max < min(a[0], b[0]) or x_min > max(a[0], b[0]))
            else:
                continue
            if spans and edge.num_lanes == 2:
                assert gap >= clearance - 1e-6
