"""Unit tests for the street furniture placed along every sidewalk."""

from typing import List, Tuple

import numpy as np

from src.orchestration.dataset_generator import generate_scenario
from src.procedural.building_facade import FacadePiece
from src.procedural.lane_topology import LANE_WIDTH_METERS
from src.procedural.street_furniture import (
    END_MARGIN_METERS,
    LAMP_STYLES,
    TREE_BASE_STYLES,
    FurnitureRule,
    TreeRule,
    furniture_rules,
    generate_street_furniture_pieces,
)
from tests.conftest import straight_road_lanes_and_edges as _straight_road


def _is_tree_piece(piece: FacadePiece) -> bool:
    """Tree bases and birch trees (everything scaled or in a tree kit)."""
    return "/Kit_Tree" in piece.asset_path


def _furniture_only(pieces: List[FacadePiece]) -> List[FacadePiece]:
    return [p for p in pieces if not _is_tree_piece(p)]


def test_pieces_sit_beside_the_curb_line_at_epics_measured_offsets() -> None:
    """Each item is offset outward from the pavement edge by its rule's
    measured distance (the right-hand side of a +x edge is -y), unscaled,
    at road-crown height."""
    lanes, edges = _straight_road(200.0)
    pieces = _furniture_only(generate_street_furniture_pieces(lanes, edges))
    offsets = {
        rule.asset_path: rule.offset_m
        for rule in furniture_rules()
        if isinstance(rule, FurnitureRule)
    }
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
    meter_rule = next(
        r for r in furniture_rules() if isinstance(r, FurnitureRule) and r.name == "meter"
    )
    meter_path = meter_rule.asset_path
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
    pieces = _furniture_only(generate_street_furniture_pieces(lanes, edges))
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
    for piece in _furniture_only(generate_street_furniture_pieces(lanes, edges, lamp_style=0)):
        expected = np.pi if piece.asset_path == cobra else 0.0
        assert np.isclose(piece.rotation_rad, expected)


def test_generated_scenario_has_street_furniture_with_one_lamp_style(urban_config, bounds) -> None:
    """A real scenario gets furniture, with a single lamp model."""
    scenario = generate_scenario(42, urban_config, bounds, "furniture_test")
    lamp_paths = {path for path, _ in LAMP_STYLES}
    lamps = {p.asset_path for p in scenario.street_furniture_pieces if p.asset_path in lamp_paths}

    assert scenario.street_furniture_pieces
    assert len(lamps) == 1


def _trees_and_bases(pieces: List[FacadePiece]) -> Tuple[List[FacadePiece], List[FacadePiece]]:
    bases = [p for p in pieces if p.asset_path in TREE_BASE_STYLES]
    trees = [p for p in pieces if _is_tree_piece(p) and p.asset_path not in TREE_BASE_STYLES]
    return bases, trees


def test_every_tree_pairs_with_a_base_at_the_same_spot_with_epics_scales() -> None:
    """Epic pairs each birch 1:1 with a tree base at the same position:
    base scaled 1.2, tree scaled uniformly within 0.8-1.1, sitting on the
    sidewalk top and 1.5m from the curb line."""
    lanes, edges = _straight_road(200.0)
    rule = next(r for r in furniture_rules() if isinstance(r, TreeRule))
    bases, trees = _trees_and_bases(generate_street_furniture_pieces(lanes, edges, seed=3))
    curb_y = -2 * LANE_WIDTH_METERS

    assert bases and len(bases) == len(trees)
    for base, tree in zip(bases, trees):
        assert np.allclose(base.position, tree.position)
        assert base.scale == (1.2, 1.2, 1.2)
        assert tree.scale is not None
        low, high = rule.tree_scale_range
        assert low <= tree.scale[0] <= high
        assert tree.scale[0] == tree.scale[1] == tree.scale[2]
        assert base.position[2] == rule.z_m
        assert np.isclose(curb_y - float(base.position[1]), 1.5)


def test_tree_pits_are_about_twenty_metres_apart_and_clear_of_lamps() -> None:
    """Consecutive tree pits are one spacing (measured median 2021cm)
    apart, nudged by at most 3.5m off a lamp, and never within 2.5m of one."""
    lanes, edges = _straight_road(300.0)
    pieces = generate_street_furniture_pieces(lanes, edges)
    bases, _ = _trees_and_bases(pieces)
    tree_xs = sorted(float(b.position[0]) for b in bases)
    lamp_xs = [float(p.position[0]) for p in pieces if p.asset_path == LAMP_STYLES[0][0]]

    gaps = np.diff(tree_xs)
    assert len(tree_xs) >= 12
    assert gaps.min() >= 20.21 - 5.5 - 1e-9 and gaps.max() <= 20.21 + 5.5 + 1e-9
    assert all(abs(t - lamp) >= 2.5 - 1e-9 for t in tree_xs for lamp in lamp_xs)


def test_tree_scale_yaw_and_variant_vary_with_the_seed_but_positions_do_not() -> None:
    """Each seed gives different tree scales, yaws and variants; the tree
    positions (and the other furniture) are identical."""
    lanes, edges = _straight_road(300.0)
    first = generate_street_furniture_pieces(lanes, edges, seed=1)
    second = generate_street_furniture_pieces(lanes, edges, seed=2)
    again = generate_street_furniture_pieces(lanes, edges, seed=1)

    assert [tuple(p.position) for p in first] == [tuple(p.position) for p in second]
    assert [(p.asset_path, p.rotation_rad, p.scale) for p in first] == [
        (p.asset_path, p.rotation_rad, p.scale) for p in again
    ]
    _, trees_a = _trees_and_bases(first)
    _, trees_b = _trees_and_bases(second)
    assert [t.scale for t in trees_a] != [t.scale for t in trees_b]


def test_tree_base_style_selects_the_base_model() -> None:
    """Different base styles swap only the base model."""
    lanes, edges = _straight_road(200.0)
    for style, base_asset in enumerate(TREE_BASE_STYLES):
        bases, _ = _trees_and_bases(
            generate_street_furniture_pieces(lanes, edges, tree_base_style=style)
        )
        assert bases
        assert {b.asset_path for b in bases} == {base_asset}
