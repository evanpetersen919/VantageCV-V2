"""Unit tests for the street furniture placed along every sidewalk."""

from typing import Dict, Tuple

import numpy as np

from src.orchestration.dataset_generator import generate_scenario
from src.procedural.lane_topology import LANE_WIDTH_METERS, Lane, LaneTopologyGenerator
from src.procedural.road_network import IntersectionType, RoadEdge, RoadNode, RoadType
from src.procedural.street_furniture import (
    END_MARGIN_METERS,
    LAMP_STYLES,
    furniture_rules,
    generate_street_furniture_pieces,
)


def _straight_road(length: float) -> Tuple[Dict[int, Lane], Dict[int, RoadEdge]]:
    """One directed edge along +x from the origin with its real lanes."""
    nodes = {
        0: RoadNode(0, np.array([0.0, 0.0]), IntersectionType.ISOLATED),
        1: RoadNode(1, np.array([length, 0.0]), IntersectionType.ISOLATED),
    }
    edge = RoadEdge(
        0, 0, 1, RoadType.MINOR, np.array([[0.0, 0.0], [length, 0.0]]), length, 2, 50, 7.0
    )
    edges = {0: edge}
    return LaneTopologyGenerator().generate(nodes, edges), edges


def test_pieces_sit_beside_the_curb_line_at_epics_measured_offsets() -> None:
    """Each item is offset outward from the pavement edge by its rule's
    measured distance (the right-hand side of a +x edge is -y), unscaled,
    at road-crown height."""
    lanes, edges = _straight_road(200.0)
    pieces = generate_street_furniture_pieces(lanes, edges)
    offsets = {rule.asset_path: rule.offset_m for rule in furniture_rules()}
    curb_y = -2 * LANE_WIDTH_METERS

    assert pieces
    for piece in pieces:
        assert piece.scale is None
        assert piece.position[2] == 0.0
        assert abs((curb_y - float(piece.position[1])) - offsets[piece.asset_path]) < 1e-9


def test_meters_are_exactly_seven_metres_apart_where_unobstructed() -> None:
    """Epic's parking meters are exactly 700cm apart; consecutive meters
    on a run keep that spacing except where a higher-priority item took
    the spot."""
    lanes, edges = _straight_road(200.0)
    meter_path = furniture_rules()[-1].asset_path
    xs = sorted(
        float(p.position[0])
        for p in generate_street_furniture_pieces(lanes, edges)
        if p.asset_path == meter_path
    )

    gaps = np.diff(xs)
    assert len(xs) > 10
    assert np.isclose(gaps, 7.0).sum() > 0.4 * len(gaps)
    assert all(np.isclose(gap % 7.0, 0.0) or np.isclose(gap % 7.0, 7.0) for gap in gaps)


def test_furniture_keeps_clear_of_the_run_ends_and_of_each_other() -> None:
    """Nothing is placed within the end margin (intersection zone), and no
    two items come closer than the lower-priority rule's clearance."""
    lanes, edges = _straight_road(150.0)
    pieces = generate_street_furniture_pieces(lanes, edges)
    outer = next(iter(lanes.values())).left_boundary
    start_x = float(min(outer[:, 0]))
    end_x = float(max(outer[:, 0]))
    xs = sorted(float(p.position[0]) for p in pieces)

    assert xs[0] >= start_x + END_MARGIN_METERS - 1e-9
    assert xs[-1] <= end_x - END_MARGIN_METERS + 1e-9
    assert min(np.diff(xs)) >= 1.0 - 1e-9


def test_lamp_style_selects_the_lamp_and_only_the_lamp() -> None:
    """Different lamp styles swap the lamp model; nothing else changes."""
    lanes, edges = _straight_road(150.0)
    lamp_paths = {path for path, _ in LAMP_STYLES}
    baseline = None
    for style, (lamp_asset, _) in enumerate(LAMP_STYLES):
        pieces = generate_street_furniture_pieces(lanes, edges, lamp_style=style)
        lamps = [p for p in pieces if p.asset_path in lamp_paths]
        assert {p.asset_path for p in lamps} == {lamp_asset}
        others = [(p.asset_path, tuple(np.round(p.position, 6))) for p in pieces if p not in lamps]
        baseline = baseline or others
        assert others == baseline


def test_cobra_lamp_arm_points_over_the_road_and_others_use_run_rotation() -> None:
    """The cobra-head lamp is turned half a turn from the run rotation
    (verified live: its arm then points over the road); everything else
    uses the run's own rotation."""
    lanes, edges = _straight_road(150.0)
    cobra = LAMP_STYLES[0][0]
    for piece in generate_street_furniture_pieces(lanes, edges, lamp_style=0):
        expected = np.pi if piece.asset_path == cobra else 0.0
        assert np.isclose(piece.rotation_rad, expected)


def test_generated_scenario_has_street_furniture_with_one_lamp_style(urban_config, bounds) -> None:
    """A real scenario gets furniture, with a single lamp model."""
    scenario = generate_scenario(42, urban_config, bounds, "furniture_test")
    lamp_paths = {path for path, _ in LAMP_STYLES}
    lamps = {p.asset_path for p in scenario.street_furniture_pieces if p.asset_path in lamp_paths}

    assert scenario.street_furniture_pieces
    assert len(lamps) == 1
