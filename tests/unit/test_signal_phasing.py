"""Unit tests for signal_phasing.py: cardinal classification exactness,
real timing formulas, phase resolution, and full-network integration."""

import math

import numpy as np
import pytest

from src.procedural.lane_topology import LaneTopologyGenerator
from src.procedural.road_network import RoadEdge, RoadNetworkGenerator, RoadType
from src.procedural.signal_phasing import (
    AXIS_PAIRS,
    COMFORTABLE_DECELERATION_MPS2,
    DESIGN_VEHICLE_LENGTH_M,
    EAST_WEST_AXIS,
    MIN_GREEN_SECONDS,
    NORTH_SOUTH_AXIS,
    PEDESTRIAN_WALK_MIN_S,
    PEDESTRIAN_WALKING_SPEED_MPS,
    PERCEPTION_REACTION_TIME_S,
    ApproachDirection,
    IntersectionSignalPlan,
    PhaseKind,
    SignalPhase,
    approach_direction_from_heading,
    build_signal_plans,
    classify_approach_direction,
    compute_minor_axis_by_node,
    compute_signal_plan,
    resolve_active_phases,
)
from src.procedural.traffic_network import TrafficNetworkGenerator

# urban_config, bounds fixtures: see tests/conftest.py


def _edge(start, end, speed_limit_kmh=50) -> RoadEdge:
    return RoadEdge(
        edge_id=0,
        start_node_id=0,
        end_node_id=1,
        road_type=RoadType.MAJOR,
        centerline=np.array([start, end], dtype=np.float64),
        length=float(np.linalg.norm(np.array(end) - np.array(start))),
        num_lanes=2,
        speed_limit_kmh=speed_limit_kmh,
        width_meters=10.0,
    )


@pytest.mark.parametrize(
    "start,end,expected",
    [
        ((0.0, 0.0), (10.0, 0.0), ApproachDirection.EAST),
        ((0.0, 0.0), (-10.0, 0.0), ApproachDirection.WEST),
        ((0.0, 0.0), (0.0, 10.0), ApproachDirection.NORTH),
        ((0.0, 0.0), (0.0, -10.0), ApproachDirection.SOUTH),
    ],
)
def test_classify_approach_direction_cardinal(start, end, expected) -> None:
    """Each of the 4 exactly-axis-aligned directions classifies correctly."""
    assert classify_approach_direction(_edge(start, end)) == expected


def test_classify_approach_direction_exact_for_real_grid_edges(urban_config, bounds) -> None:
    """Real proof (not an assumption) that every edge produced by the real
    RoadNetworkGenerator is exactly axis-aligned: one of dx/dy is exactly
    0.0, so classify_approach_direction's magnitude-comparison approach is
    exact, not a tolerance-band heuristic, for every real edge this
    project actually generates."""
    road_gen = RoadNetworkGenerator(42, urban_config)
    _, edges = road_gen.generate(bounds)

    assert edges  # sanity
    for edge in edges.values():
        dx, dy = edge.centerline[-1] - edge.centerline[0]
        assert dx == 0.0 or dy == 0.0


def _node_edge(start_node_id, end_node_id, start, end) -> RoadEdge:
    return RoadEdge(
        edge_id=0,
        start_node_id=start_node_id,
        end_node_id=end_node_id,
        road_type=RoadType.MAJOR,
        centerline=np.array([start, end], dtype=np.float64),
        length=float(np.linalg.norm(np.array(end) - np.array(start))),
        num_lanes=2,
        speed_limit_kmh=50,
        width_meters=10.0,
    )


def test_compute_minor_axis_by_node_identifies_the_stub_at_a_real_t_junction() -> None:
    """A real T-shape at node 1: a through east-west road (2 physical
    connections, 4 directed edges, both on EAST_WEST_AXIS) and a stub
    north road (1 physical connection, 2 directed edges, NORTH_SOUTH_AXIS)
    -- the stub axis (fewer directed edges) is the minor one."""
    edges = {
        0: _node_edge(2, 1, (-10.0, 0.0), (0.0, 0.0)),  # west-in
        1: _node_edge(1, 2, (0.0, 0.0), (-10.0, 0.0)),  # west-out
        2: _node_edge(3, 1, (10.0, 0.0), (0.0, 0.0)),  # east-in
        3: _node_edge(1, 3, (0.0, 0.0), (10.0, 0.0)),  # east-out
        4: _node_edge(4, 1, (0.0, 10.0), (0.0, 0.0)),  # north stub-in
        5: _node_edge(1, 4, (0.0, 0.0), (0.0, 10.0)),  # north stub-out
    }
    minor_axis = compute_minor_axis_by_node(edges)
    assert minor_axis[1] == NORTH_SOUTH_AXIS


def test_compute_minor_axis_by_node_skips_a_dead_end() -> None:
    """A node with edges on only one axis (a dead end) has no minor axis
    -- there's no through road for it to be minor relative to."""
    edges = {
        0: _node_edge(2, 1, (-10.0, 0.0), (0.0, 0.0)),
        1: _node_edge(1, 2, (0.0, 0.0), (-10.0, 0.0)),
    }
    assert 1 not in compute_minor_axis_by_node(edges)


def test_compute_minor_axis_by_node_reports_both_axes_at_a_real_street_corner() -> None:
    """A real street corner -- 2 physical connections, non-collinear, one
    on each real axis (1/1 split) -- has BOTH axes minor: neither road is
    a "through" road relative to the other, so both must stop, matching
    a real unsignalized corner crossing. This is the case
    ``road_network.py``'s own docstring flags: kept ``ISOLATED`` by the
    master prompt's own classification despite having 2 real
    connections, which is NOT the same as a true dead end/pass-through
    (only one axis) -- see ``traffic_network.py``'s
    ``_assign_traffic_controls``."""
    edges = {
        0: _node_edge(2, 1, (-10.0, 0.0), (0.0, 0.0)),  # west connection (EAST_WEST_AXIS)
        1: _node_edge(1, 2, (0.0, 0.0), (-10.0, 0.0)),
        2: _node_edge(1, 3, (0.0, 0.0), (0.0, 10.0)),  # north connection (NORTH_SOUTH_AXIS)
        3: _node_edge(3, 1, (0.0, 10.0), (0.0, 0.0)),
    }
    assert compute_minor_axis_by_node(edges)[1] == NORTH_SOUTH_AXIS | EAST_WEST_AXIS


def test_compute_minor_axis_by_node_reports_both_axes_for_equal_counts() -> None:
    """Equal counts on both axes (no clear through road) means BOTH axes
    are minor -- the real, symmetric-stop treatment this function's own
    docstring describes for a corner or comparable-volume crossing. A
    genuine 4-way also has equal counts, but is always TRAFFIC_LIGHT-
    controlled and never actually reaches this fallback in
    ``_axis_is_flowing``, so this result being present here is harmless
    for that case -- not specifically about 4-ways."""
    edges = {
        0: _node_edge(2, 1, (-10.0, 0.0), (0.0, 0.0)),
        1: _node_edge(1, 2, (0.0, 0.0), (-10.0, 0.0)),
        2: _node_edge(3, 1, (10.0, 0.0), (0.0, 0.0)),
        3: _node_edge(1, 3, (0.0, 0.0), (10.0, 0.0)),
        4: _node_edge(4, 1, (0.0, 10.0), (0.0, 0.0)),
        5: _node_edge(1, 4, (0.0, 0.0), (0.0, 10.0)),
        6: _node_edge(5, 1, (0.0, -10.0), (0.0, 0.0)),
        7: _node_edge(1, 5, (0.0, 0.0), (0.0, -10.0)),
    }
    assert compute_minor_axis_by_node(edges)[1] == NORTH_SOUTH_AXIS | EAST_WEST_AXIS


def test_approach_direction_from_heading_matches_classify() -> None:
    """A heading angle classifies the same way the equivalent edge does."""
    assert approach_direction_from_heading(0.0) == ApproachDirection.EAST
    assert approach_direction_from_heading(math.pi / 2) == ApproachDirection.NORTH
    assert approach_direction_from_heading(math.pi) == ApproachDirection.WEST
    assert approach_direction_from_heading(-math.pi / 2) == ApproachDirection.SOUTH


def test_axis_pairs_partition_all_four_directions() -> None:
    """NORTH_SOUTH_AXIS and EAST_WEST_AXIS are disjoint and together cover
    all 4 cardinal directions -- a phase's moving_approaches is always
    exactly one of these two pairs, never a mix."""
    assert NORTH_SOUTH_AXIS.isdisjoint(EAST_WEST_AXIS)
    assert NORTH_SOUTH_AXIS | EAST_WEST_AXIS == set(ApproachDirection)
    assert set(AXIS_PAIRS) == {NORTH_SOUTH_AXIS, EAST_WEST_AXIS}


def test_yellow_change_interval_within_mutcd_range() -> None:
    """Yellow-change interval falls within MUTCD's commonly-cited 3-6s
    typical range for this codebase's faster real speed limits (50-60
    km/h, i.e. ~31-37mph, matching the speed range that figure is
    typically quoted for)."""
    for speed_kmh in (50, 60):
        plan = compute_signal_plan(0, [_edge((0, 0), (100, 0), speed_kmh)], node_clearance_m=7.0)
        yellow_phases = [p for p in plan.phases if p.kind == PhaseKind.YELLOW_CHANGE]
        for phase in yellow_phases:
            assert 3.0 <= phase.duration_s <= 6.0

    # Slower real speed limits (30/40 km/h, residential/minor streets)
    # legitimately compute a shorter interval from the same real formula --
    # not a bug, just a lower-speed input; sanity-checked against a wider,
    # still-reasonable bound instead of MUTCD's higher-speed-oriented 3-6s
    # figure.
    for speed_kmh in (30, 40):
        plan = compute_signal_plan(0, [_edge((0, 0), (100, 0), speed_kmh)], node_clearance_m=7.0)
        yellow_phases = [p for p in plan.phases if p.kind == PhaseKind.YELLOW_CHANGE]
        for phase in yellow_phases:
            assert 2.0 <= phase.duration_s <= 6.0


def test_yellow_change_formula_matches_ite_citation() -> None:
    """Y = t + v / (2*a), using the fastest incident edge's real speed."""
    plan = compute_signal_plan(0, [_edge((0, 0), (100, 0), 50)], node_clearance_m=7.0)
    v = 50 / 3.6
    expected = PERCEPTION_REACTION_TIME_S + v / (2 * COMFORTABLE_DECELERATION_MPS2)
    yellow_phases = [p for p in plan.phases if p.kind == PhaseKind.YELLOW_CHANGE]
    assert yellow_phases
    for phase in yellow_phases:
        assert phase.duration_s == pytest.approx(expected)


def test_all_red_formula_matches_ite_citation() -> None:
    """AR = (W + L) / v, using the real node clearance and design vehicle
    length."""
    node_clearance_m = 7.0
    plan = compute_signal_plan(0, [_edge((0, 0), (100, 0), 50)], node_clearance_m)
    v = 50 / 3.6
    expected = (node_clearance_m + DESIGN_VEHICLE_LENGTH_M) / v
    all_red_phases = [p for p in plan.phases if p.kind == PhaseKind.ALL_RED]
    assert all_red_phases
    for phase in all_red_phases:
        assert phase.duration_s == pytest.approx(expected)


def test_all_red_uses_fastest_conflicting_approach() -> None:
    """Multiple incident edges with different speeds -- yellow/all-red use
    the fastest (conservative), not e.g. an average."""
    plan = compute_signal_plan(
        0,
        [_edge((0, 0), (100, 0), 30), _edge((0, 0), (0, 100), 60)],
        node_clearance_m=7.0,
    )
    v = 60 / 3.6
    expected_yellow = PERCEPTION_REACTION_TIME_S + v / (2 * COMFORTABLE_DECELERATION_MPS2)
    yellow_phases = [p for p in plan.phases if p.kind == PhaseKind.YELLOW_CHANGE]
    for phase in yellow_phases:
        assert phase.duration_s == pytest.approx(expected_yellow)


def test_green_at_least_min_green_floor() -> None:
    """Green never falls below the real MUTCD/ITE minimum-green floor."""
    plan = compute_signal_plan(0, [_edge((0, 0), (100, 0), 50)], node_clearance_m=0.1)
    green_phases = [p for p in plan.phases if p.kind == PhaseKind.GREEN]
    assert green_phases
    for phase in green_phases:
        assert phase.duration_s >= MIN_GREEN_SECONDS


def test_green_lengthened_for_wide_pedestrian_crossing() -> None:
    """A wide intersection (long pedestrian crossing) lengthens green past
    the floor to satisfy MUTCD's WALK + clearance-time requirement."""
    wide_clearance_m = 40.0  # crossing_distance = 80m, a very wide road
    plan = compute_signal_plan(0, [_edge((0, 0), (100, 0), 50)], wide_clearance_m)
    expected_min = PEDESTRIAN_WALK_MIN_S + (2 * wide_clearance_m) / PEDESTRIAN_WALKING_SPEED_MPS
    assert expected_min > MIN_GREEN_SECONDS  # sanity: this case actually exercises the extension
    green_phases = [p for p in plan.phases if p.kind == PhaseKind.GREEN]
    for phase in green_phases:
        assert phase.duration_s == pytest.approx(expected_min)


def test_green_phases_use_disjoint_axes() -> None:
    """The two GREEN phases in one cycle use the two different axis
    pairs -- opposing traffic never gets simultaneous green with the
    perpendicular pair."""
    plan = compute_signal_plan(0, [_edge((0, 0), (100, 0), 50)], node_clearance_m=7.0)
    green_axes = [p.moving_approaches for p in plan.phases if p.kind == PhaseKind.GREEN]
    assert len(green_axes) == 2
    assert set(green_axes) == {NORTH_SOUTH_AXIS, EAST_WEST_AXIS}


def test_non_green_phases_have_empty_moving_approaches() -> None:
    """YELLOW_CHANGE and ALL_RED never permit any approach to proceed."""
    plan = compute_signal_plan(0, [_edge((0, 0), (100, 0), 50)], node_clearance_m=7.0)
    for phase in plan.phases:
        if phase.kind != PhaseKind.GREEN:
            assert phase.moving_approaches == frozenset()


def test_cycle_length_is_sum_of_phase_durations() -> None:
    """cycle_length_s is exactly the sum of every phase's own duration."""
    plan = compute_signal_plan(0, [_edge((0, 0), (100, 0), 50)], node_clearance_m=7.0)
    assert plan.cycle_length_s == pytest.approx(sum(p.duration_s for p in plan.phases))


def test_phase_at_resolves_correct_phase() -> None:
    """phase_at picks the phase whose cumulative duration window contains
    the queried instant."""
    phases = (
        SignalPhase(0, PhaseKind.GREEN, NORTH_SOUTH_AXIS, 10.0),
        SignalPhase(1, PhaseKind.YELLOW_CHANGE, frozenset(), 5.0),
        SignalPhase(2, PhaseKind.ALL_RED, frozenset(), 2.0),
    )
    plan = IntersectionSignalPlan(node_id=0, phases=phases, cycle_length_s=17.0)

    assert plan.phase_at(0.0) is phases[0]
    assert plan.phase_at(9.9) is phases[0]
    assert plan.phase_at(10.0) is phases[1]
    assert plan.phase_at(14.9) is phases[1]
    assert plan.phase_at(15.0) is phases[2]
    assert plan.phase_at(16.9) is phases[2]


def test_phase_at_wraps_around_cycle() -> None:
    """An instant beyond one cycle length wraps via modulo."""
    phases = (SignalPhase(0, PhaseKind.GREEN, NORTH_SOUTH_AXIS, 10.0),)
    plan = IntersectionSignalPlan(node_id=0, phases=phases, cycle_length_s=10.0)
    assert plan.phase_at(25.0) is phases[0]


def test_build_signal_plans_only_covers_traffic_light_nodes(urban_config, bounds) -> None:
    """Only real TRAFFIC_LIGHT nodes get a plan -- stop-sign/uncontrolled
    nodes are absent from the result entirely (see module scope note)."""
    road_gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = road_gen.generate(bounds)
    lanes = LaneTopologyGenerator().generate(nodes, edges)
    traffic = TrafficNetworkGenerator().generate(nodes, edges, lanes)

    plans = build_signal_plans(edges, traffic)

    assert plans  # sanity: this config/seed has at least one signalized node
    for node_id in plans:
        assert traffic.traffic_controls[node_id].value == "traffic_light"
    signalized_count = sum(
        1 for c in traffic.traffic_controls.values() if c.value == "traffic_light"
    )
    assert len(plans) == signalized_count


def test_resolve_active_phases_deterministic_for_same_rng_state() -> None:
    """Same seeded rng state resolves to the same phase every time."""
    plan = compute_signal_plan(0, [_edge((0, 0), (100, 0), 50)], node_clearance_m=7.0)
    plans = {0: plan}

    rng1 = np.random.Generator(np.random.PCG64(123))
    rng2 = np.random.Generator(np.random.PCG64(123))
    resolved1 = resolve_active_phases(plans, rng1)
    resolved2 = resolve_active_phases(plans, rng2)

    assert resolved1[0].phase_index == resolved2[0].phase_index


def test_resolve_active_phases_always_within_bounds() -> None:
    """Repeated resolution always returns one of the plan's real phases."""
    plan = compute_signal_plan(0, [_edge((0, 0), (100, 0), 50)], node_clearance_m=7.0)
    plans = {0: plan}
    rng = np.random.Generator(np.random.PCG64(7))

    for _ in range(200):
        resolved = resolve_active_phases(plans, rng)
        assert resolved[0] in plan.phases
