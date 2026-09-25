"""Tests for the street-furniture keep-out (driveways): the distance-to-rectangle
math, that props respect the margin exactly, and that everything else is kept."""

import math

import numpy as np
import pytest

from src.orchestration.dataset_generator import generate_scenario
from src.procedural.lane_topology import LaneTopologyGenerator
from src.procedural.road_network import RoadNetworkGenerator
from src.procedural.street_furniture import (
    KEEP_OUT_BUFFER_M,
    distance_to_rect,
    furniture_rules,
    generate_street_furniture_pieces,
    keep_out_margin_m,
)

RECT = (10.0, 20.0, 14.0, 26.0)


@pytest.mark.parametrize(
    "point, expected",
    [
        ((12.0, 23.0), 0.0),  # inside
        ((10.0, 20.0), 0.0),  # on a corner
        ((14.0, 23.0), 0.0),  # on an edge
        ((17.0, 23.0), 3.0),  # right of the rectangle, level with it
        ((12.0, 16.0), 4.0),  # below it
        ((6.0, 17.0), 5.0),  # off a corner: a 3-4-5 triangle
        ((17.0, 30.0), 5.0),  # off the opposite corner: 3, 4
    ],
)
def test_distance_to_rect_is_the_shortest_distance(point, expected) -> None:
    """Zero on or inside the rectangle, the straight gap beside it, and the
    diagonal to the nearest corner past a corner."""
    assert distance_to_rect(np.array(point), RECT) == pytest.approx(expected)


def test_margin_is_half_the_rules_clearance_plus_the_buffer() -> None:
    """Each rule's margin follows its own clearance; a tree's is the widest."""
    rules = furniture_rules()
    for rule in rules:
        assert keep_out_margin_m(rule) == pytest.approx(rule.clearance_m / 2.0 + KEEP_OUT_BUFFER_M)
    margins = {rule.name: keep_out_margin_m(rule) for rule in rules}
    assert margins["tree"] == max(margins.values())
    assert margins["tree"] == pytest.approx(1.5)


def _network(urban_config, bounds):
    nodes, edges = RoadNetworkGenerator(7, urban_config).generate(bounds)
    return LaneTopologyGenerator().generate(nodes, edges), edges


def test_no_prop_is_placed_within_its_margin_of_a_keep_out_rect(urban_config, bounds) -> None:
    """With a keep-out rectangle laid over a stretch of curb, every piece of
    the smallest margin is at least that far from it, and props well clear of
    it are all still placed (the keep-out only removes what it must)."""
    lanes, edges = _network(urban_config, bounds)
    free = generate_street_furniture_pieces(lanes, edges, seed=3)
    anchor = free[len(free) // 2].position
    rect = (anchor[0] - 6.0, anchor[1] - 6.0, anchor[0] + 6.0, anchor[1] + 6.0)
    kept = generate_street_furniture_pieces(lanes, edges, seed=3, keep_out_rects=[rect])
    smallest = min(keep_out_margin_m(rule) for rule in furniture_rules())
    assert len(kept) < len(free)
    for piece in kept:
        assert distance_to_rect(piece.position[:2], rect) >= smallest - 1e-9
    kept_positions = {
        (round(float(p.position[0]), 6), round(float(p.position[1]), 6)) for p in kept
    }
    widest = max(keep_out_margin_m(rule) for rule in furniture_rules())
    for piece in free:
        if distance_to_rect(piece.position[:2], rect) >= widest + 2.5:
            key = (round(float(piece.position[0]), 6), round(float(piece.position[1]), 6))
            assert key in kept_positions


def test_an_empty_keep_out_changes_nothing(urban_config, bounds) -> None:
    """Without keep-out rectangles the output is exactly as before."""
    lanes, edges = _network(urban_config, bounds)
    a = generate_street_furniture_pieces(lanes, edges, seed=3)
    b = generate_street_furniture_pieces(lanes, edges, seed=3, keep_out_rects=())
    assert [(p.asset_path, tuple(p.position)) for p in a] == [
        (p.asset_path, tuple(p.position)) for p in b
    ]


def test_no_street_prop_stands_on_a_parking_lot_driveway(urban_config, bounds) -> None:
    """In generated scenarios with lots, no street furniture or tree sits
    within the smallest prop margin of any driveway's gap rectangle."""
    smallest = min(keep_out_margin_m(rule) for rule in furniture_rules())
    checked = 0
    for seed in (42, 7, 19):
        config = urban_config.model_copy(update={"parking_lot_fraction": 0.7})
        result = generate_scenario(seed, config, bounds, "x")
        for lot in result.parking_lots:
            gap = lot.driveway.gap
            for piece in result.street_furniture_pieces:
                assert distance_to_rect(piece.position[:2], gap) >= smallest - 1e-9
                checked += 1
    assert checked > 0
    assert math.isfinite(smallest)
