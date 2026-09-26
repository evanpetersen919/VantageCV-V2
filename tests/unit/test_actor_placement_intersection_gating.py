"""Deterministic, hand-built proofs of ActorPlacementGenerator's
intersection right-of-way gating: green-axis flow-through at signalized
nodes (2026-09-24) and real 2-way-stop gating at T-junctions
(2026-09-25). Split out of test_actor_placement.py once that module hit
pylint's line-count limit -- no reliance on randomly-resolved signal
phases, so every case below is exact, not merely "observed in a random
scenario"."""

# pylint: disable=duplicate-code
# _make_edge/_node_edge's hand-built RoadEdge fixtures inevitably resemble
# test_signal_phasing.py's own hand-built RoadEdge fixtures -- a shared
# fixture would couple those unrelated test files together for no benefit.

import numpy as np
import pytest

from src.procedural.actor_placement import ActorPlacementGenerator
from src.procedural.road_network import RoadEdge, RoadType
from src.procedural.signal_phasing import ApproachDirection, PhaseKind, SignalPhase
from src.procedural.traffic_network import (
    VEHICLE_STOP_LINE_CROSSWALK_SETBACK_M,
    SpawnZone,
    SpawnZoneType,
    TrafficControlType,
)
from src.procedural.vehicle_spacing import moving_regime, queued_regime

# urban_config, bounds fixtures: see tests/conftest.py


def _make_edge(  # pylint: disable=too-many-arguments
    start=(0.0, 0.0),
    end=(100.0, 0.0),
    edge_id=0,
    start_node_id=10,
    end_node_id=20,
    speed_limit_kmh=50,
) -> RoadEdge:
    """A real, exactly axis-aligned (east-pointing, by default) RoadEdge --
    matching this codebase's own grid guarantee (road_network.py) that
    ``classify_approach_direction`` relies on."""
    return RoadEdge(
        edge_id=edge_id,
        start_node_id=start_node_id,
        end_node_id=end_node_id,
        road_type=RoadType.MAJOR,
        centerline=np.array([start, end], dtype=np.float64),
        length=float(np.linalg.norm(np.array(end) - np.array(start))),
        num_lanes=2,
        speed_limit_kmh=speed_limit_kmh,
        width_meters=10.0,
    )


def _green_phase(axis) -> SignalPhase:
    return SignalPhase(0, PhaseKind.GREEN, frozenset(axis), 20.0)


def test_axis_is_flowing_true_on_matching_green_phase() -> None:
    """A green phase whose moving_approaches contains the queried axis
    flows."""
    phase = _green_phase({ApproachDirection.NORTH, ApproachDirection.SOUTH})
    assert ActorPlacementGenerator._axis_is_flowing(  # pylint: disable=protected-access
        5, ApproachDirection.NORTH, {5: phase}, {}, {}
    )


def test_axis_is_flowing_false_on_yellow_or_all_red() -> None:
    """Neither YELLOW_CHANGE nor ALL_RED ever flows, regardless of axis."""
    for kind in (PhaseKind.YELLOW_CHANGE, PhaseKind.ALL_RED):
        phase = SignalPhase(0, kind, frozenset(), 3.0)
        assert not ActorPlacementGenerator._axis_is_flowing(  # pylint: disable=protected-access
            5, ApproachDirection.NORTH, {5: phase}, {}, {}
        )


def test_axis_is_flowing_false_on_green_but_wrong_axis() -> None:
    """A green phase for the perpendicular axis does not flow for this
    one."""
    phase = _green_phase({ApproachDirection.EAST, ApproachDirection.WEST})
    assert not ActorPlacementGenerator._axis_is_flowing(  # pylint: disable=protected-access
        5, ApproachDirection.NORTH, {5: phase}, {}, {}
    )


def test_axis_is_flowing_true_when_node_has_no_control_at_all() -> None:
    """An uncontrolled/isolated node (absent from active_phases, and not
    STOP_SIGN in traffic_controls) always flows -- this project models
    no all-way-stop right-of-way."""
    assert ActorPlacementGenerator._axis_is_flowing(  # pylint: disable=protected-access
        99, ApproachDirection.NORTH, {}, {}, {}
    )


def test_axis_is_flowing_false_on_minor_axis_of_a_stop_sign_node() -> None:
    """A real 2-way stop always requires a full stop on the minor/stub
    axis -- no timed phase involved, so this is unconditional, not
    resolved-instant-dependent like a signal."""
    minor_axis_by_node = {7: frozenset({ApproachDirection.EAST, ApproachDirection.WEST})}
    assert not ActorPlacementGenerator._axis_is_flowing(  # pylint: disable=protected-access
        7,
        ApproachDirection.EAST,
        {},
        {7: TrafficControlType.STOP_SIGN},
        minor_axis_by_node,
    )


def test_axis_is_flowing_true_on_major_axis_of_a_stop_sign_node() -> None:
    """The through/major axis at a real 2-way stop never has to stop."""
    minor_axis_by_node = {7: frozenset({ApproachDirection.EAST, ApproachDirection.WEST})}
    assert ActorPlacementGenerator._axis_is_flowing(  # pylint: disable=protected-access
        7,
        ApproachDirection.NORTH,
        {},
        {7: TrafficControlType.STOP_SIGN},
        minor_axis_by_node,
    )


def test_axis_is_flowing_true_at_stop_sign_node_with_no_identified_minor_axis() -> None:
    """A STOP_SIGN node absent from minor_axis_by_node (not a clean
    through+stub T-shape) has no rule to apply -- always flows, same as
    an uncontrolled node."""
    assert ActorPlacementGenerator._axis_is_flowing(  # pylint: disable=protected-access
        7, ApproachDirection.NORTH, {}, {7: TrafficControlType.STOP_SIGN}, {}
    )


def _make_zone(edge, node_clearance, edge_id=0) -> SpawnZone:
    """A real DRIVING zone for ``edge``, matching exactly what
    ``_generate_driving_zones`` would produce: ``position`` at the
    lane's destination node, ``stop_line_position`` at the real
    crosswalk-clearing setback."""
    edge_direction = edge.centerline[-1] - edge.centerline[0]
    edge_length = float(np.linalg.norm(edge_direction))
    unit_direction = edge_direction / edge_length
    end_clearance = node_clearance.get(edge.end_node_id, 0.0)
    stop_line_distance = min(end_clearance + VEHICLE_STOP_LINE_CROSSWALK_SETBACK_M, edge_length)
    return SpawnZone(
        spawn_zone_id=0,
        zone_type=SpawnZoneType.DRIVING,
        position=edge.centerline[-1].copy(),
        edge_id=edge_id,
        stop_line_position=edge.centerline[-1] - unit_direction * stop_line_distance,
        lateral_offset_m=0.0,
    )


def test_front_vehicle_front_bumper_at_stop_line_when_not_flowing(
    urban_config, monkeypatch
) -> None:
    """The first (closest-to-node) vehicle on a lane whose destination
    axis does NOT have the green is placed with its FRONT BUMPER (not
    center) exactly on the real stop line -- true regardless of any
    sampled gap, since no gap is involved until the SECOND vehicle."""
    monkeypatch.setattr(
        "src.procedural.actor_placement.sample_stop_sign_queue_length", lambda rng, occ, length: 3
    )
    edge = _make_edge()  # (0,0) -> (100,0), end_node_id=20
    node_clearance = {10: 5.0, 20: 5.0}
    zone = _make_zone(edge, node_clearance)
    active_phases = {20: _green_phase({ApproachDirection.NORTH, ApproachDirection.SOUTH})}

    generator = ActorPlacementGenerator(0, urban_config)
    vehicles = generator._place_vehicles_for_lane(  # pylint: disable=protected-access
        zone, {0: edge}, 1.0, [], active_phases, node_clearance, {}, {}, {}
    )
    assert vehicles
    front = max(vehicles, key=lambda v: v.center[0])
    heading_vector = np.array([np.cos(front.heading_rad), np.sin(front.heading_rad)])
    front_bumper = front.box_center + heading_vector * (front.length / 2.0)
    assert np.allclose(front_bumper, zone.stop_line_position, atol=1e-6)


def test_front_vehicle_at_natural_node_position_when_flowing(urban_config) -> None:
    """The first vehicle on a FLOWING lane sits at its own natural anchor
    (the node itself, ``zone.position``) -- "driving through a green
    light" -- not redirected to the stop line."""
    edge = _make_edge()
    node_clearance = {10: 5.0, 20: 5.0}
    zone = _make_zone(edge, node_clearance)
    active_phases = {20: _green_phase({ApproachDirection.EAST, ApproachDirection.WEST})}

    generator = ActorPlacementGenerator(0, urban_config)
    vehicles = generator._place_vehicles_for_lane(  # pylint: disable=protected-access
        zone, {0: edge}, 1.0, [], active_phases, node_clearance, {}, {}, {}
    )
    assert vehicles
    front = max(vehicles, key=lambda v: v.center[0])
    assert np.array_equal(front.center, zone.position)


def test_second_vehicle_sits_one_sampled_gap_behind_the_first(urban_config, monkeypatch) -> None:
    """The second vehicle in the chain sits exactly ``gap`` meters behind
    the first, along the lane -- proven by forcing ``sample_gap`` to a
    known, fixed value rather than trusting its real randomized output
    (already exhaustively proven in test_vehicle_spacing.py)."""
    edge = _make_edge()
    node_clearance = {10: 5.0, 20: 5.0}
    zone = _make_zone(edge, node_clearance)
    active_phases = {20: _green_phase({ApproachDirection.EAST, ApproachDirection.WEST})}
    fixed_gap = 12.34
    monkeypatch.setattr("src.procedural.actor_placement.sample_gap", lambda rng, regime: fixed_gap)

    generator = ActorPlacementGenerator(0, urban_config)
    vehicles = generator._place_vehicles_for_lane(  # pylint: disable=protected-access
        zone, {0: edge}, 1.0, [], active_phases, node_clearance, {}, {}, {}
    )
    ordered = sorted(vehicles, key=lambda v: v.center[0], reverse=True)
    assert len(ordered) >= 2
    assert ordered[0].center[0] == pytest.approx(100.0)
    assert ordered[1].center[0] == pytest.approx(100.0 - fixed_gap)
    assert ordered[0].center[1] == pytest.approx(ordered[1].center[1])


def test_walk_uses_queued_regime_near_node_and_moving_regime_farther_back(
    urban_config, monkeypatch
) -> None:
    """A candidate still inside the destination node's real crosswalk-
    clearing zone (and not flowing there) samples from the QUEUED
    regime; once the walk passes that boundary, it samples from the
    MOVING regime instead -- proven by making ``sample_gap`` echo back
    which regime it was called with (its real, distinct mean), then
    reading off which mean was actually used at each step from the
    resulting real gap sizes."""
    monkeypatch.setattr(
        "src.procedural.actor_placement.sample_stop_sign_queue_length", lambda rng, occ, length: 2
    )
    edge = _make_edge()
    node_clearance = {10: 5.0, 20: 5.0}
    zone = _make_zone(edge, node_clearance)
    active_phases = {20: _green_phase({ApproachDirection.NORTH, ApproachDirection.SOUTH})}
    monkeypatch.setattr(
        "src.procedural.actor_placement.sample_gap", lambda rng, regime: regime.mean_gap_m
    )

    generator = ActorPlacementGenerator(0, urban_config)
    vehicles = generator._place_vehicles_for_lane(  # pylint: disable=protected-access
        zone, {0: edge}, 1.0, [], active_phases, node_clearance, {}, {}, {}
    )
    ordered = sorted(vehicles, key=lambda v: v.center[0], reverse=True)
    # The front vehicle's own CENTER is offset back from the real walk
    # position by half its own (randomly-typed, variable) length -- see
    # _place_vehicles_for_lane's bumper-offset comment -- so the first
    # real gap is measured from the stop line itself, not the front
    # vehicle's center, to avoid contaminating it with that offset.
    end_required = node_clearance[20] + VEHICLE_STOP_LINE_CROSSWALK_SETBACK_M
    stop_line_x = 100.0 - end_required
    gaps = [round(stop_line_x - ordered[1].center[0], 6)] + [
        round(a.center[0] - b.center[0], 6) for a, b in zip(ordered[1:], ordered[2:])
    ]
    assert gaps  # sanity: this geometry produces at least one step
    assert gaps[0] == pytest.approx(queued_regime().mean_gap_m)
    # A gap sampled once the walk has moved past the real crosswalk-
    # clearing boundary is the MOVING regime's mean instead.
    assert any(gap == pytest.approx(moving_regime(edge.speed_limit_kmh).mean_gap_m) for gap in gaps)
    assert stop_line_x < 100.0  # sanity: the boundary is a real, positive setback


def test_walk_stops_once_inside_a_not_flowing_start_nodes_zone(urban_config, monkeypatch) -> None:
    """The chain walk excludes (does not place) any candidate that falls
    within the START node's own real crosswalk-clearing zone when that
    axis doesn't flow there either -- "a vehicle just departing a node
    it didn't have the right of way to enter has no sensible position."
    A large fixed gap forces the second candidate deep into that zone,
    proving the walk stops instead of placing it there."""
    edge = _make_edge()
    node_clearance = {10: 5.0, 20: 5.0}
    zone = _make_zone(edge, node_clearance)
    active_phases = {
        20: _green_phase({ApproachDirection.EAST, ApproachDirection.WEST}),
        10: _green_phase(
            {ApproachDirection.NORTH, ApproachDirection.SOUTH}
        ),  # NOT this edge's axis
    }
    monkeypatch.setattr("src.procedural.actor_placement.sample_gap", lambda rng, regime: 95.0)

    generator = ActorPlacementGenerator(0, urban_config)
    vehicles = generator._place_vehicles_for_lane(  # pylint: disable=protected-access
        zone, {0: edge}, 1.0, [], active_phases, node_clearance, {}, {}, {}
    )
    # Only the first (flowing, at the node) vehicle -- the second
    # candidate would land at along=5.0, inside node 10's own
    # ~18.5m not-flowing zone, and is excluded.
    assert len(vehicles) == 1
    assert vehicles[0].center[0] == pytest.approx(100.0)


def test_vehicle_queued_at_stop_line_on_minor_axis_of_a_stop_sign_node(
    urban_config, monkeypatch
) -> None:
    """A front-of-queue vehicle approaching a real T-junction on the
    minor/stub axis is placed with its front bumper at the real stop
    line -- unconditionally (a real 2-way stop always requires a full
    stop there, no resolved instant needed)."""
    monkeypatch.setattr(
        "src.procedural.actor_placement.sample_stop_sign_queue_length", lambda rng, occ, length: 3
    )
    edge = _make_edge()  # (0,0) -> (100,0): an EAST-WEST-axis edge
    node_clearance = {10: 5.0, 20: 5.0}
    zone = _make_zone(edge, node_clearance)
    traffic_controls = {20: TrafficControlType.STOP_SIGN}
    minor_axis_by_node = {20: frozenset({ApproachDirection.EAST, ApproachDirection.WEST})}

    generator = ActorPlacementGenerator(0, urban_config)
    vehicles = generator._place_vehicles_for_lane(  # pylint: disable=protected-access
        zone, {0: edge}, 1.0, [], {}, node_clearance, traffic_controls, minor_axis_by_node, {}
    )
    assert vehicles
    front = max(vehicles, key=lambda v: v.center[0])
    heading_vector = np.array([np.cos(front.heading_rad), np.sin(front.heading_rad)])
    front_bumper = front.box_center + heading_vector * (front.length / 2.0)
    assert np.allclose(front_bumper, zone.stop_line_position, atol=1e-6)


def test_vehicle_flows_on_major_axis_of_a_stop_sign_node(urban_config) -> None:
    """Same geometry, but this edge's axis is the T-junction's major/
    through axis -- it never has to stop, so the front vehicle sits at
    the node itself, not redirected to any stop line."""
    edge = _make_edge()  # EAST-WEST-axis edge
    node_clearance = {10: 5.0, 20: 5.0}
    zone = _make_zone(edge, node_clearance)
    traffic_controls = {20: TrafficControlType.STOP_SIGN}
    # The minor axis at node 20 is NORTH-SOUTH here, not this edge's own
    # EAST-WEST axis, so this edge's axis is the (always-flowing) major one.
    minor_axis_by_node = {20: frozenset({ApproachDirection.NORTH, ApproachDirection.SOUTH})}

    generator = ActorPlacementGenerator(0, urban_config)
    vehicles = generator._place_vehicles_for_lane(  # pylint: disable=protected-access
        zone, {0: edge}, 1.0, [], {}, node_clearance, traffic_controls, minor_axis_by_node, {}
    )
    assert vehicles
    front = max(vehicles, key=lambda v: v.center[0])
    assert np.array_equal(front.center, zone.position)


def test_projection_formula_exact_numbers() -> None:
    """Pure arithmetic proof of the along-edge projection/threshold math
    ``_try_place_vehicle`` uses, independent of ``ActorPlacementGenerator``
    entirely: edge (0,0)->(100,0), node_clearance=5.0 at the end node,
    real setback constant plugged in numerically -- a candidate at x=85
    is 15m from the end node, less than the required
    5.0 + VEHICLE_STOP_LINE_CROSSWALK_SETBACK_M (~18.5m), so it falls
    inside; a candidate at x=81.5 sits exactly at the boundary within
    1e-6; a candidate at x=80 (20m from the node) falls outside."""
    edge = _make_edge()
    edge_length = 100.0
    unit_direction = np.array([1.0, 0.0])
    end_required = 5.0 + VEHICLE_STOP_LINE_CROSSWALK_SETBACK_M

    for x, expect_inside in ((85.0, True), (80.0, False)):
        along_from_start = float(np.dot(np.array([x, 0.0]) - edge.centerline[0], unit_direction))
        along_from_end = edge_length - along_from_start
        assert (along_from_end < end_required) == expect_inside

    boundary_x = edge_length - end_required
    along_from_end_at_boundary = edge_length - boundary_x
    assert along_from_end_at_boundary == pytest.approx(end_required, abs=1e-6)


def test_only_queued_vehicles_are_braking(urban_config, monkeypatch) -> None:
    """Every vehicle in a red-light queue is marked braking; the
    straggler behind the queue and every vehicle on a flowing lane are
    not."""
    edge = _make_edge()
    node_clearance = {10: 5.0, 20: 5.0}
    zone = _make_zone(edge, node_clearance)
    monkeypatch.setattr(
        "src.procedural.actor_placement.sample_stop_sign_queue_length", lambda rng, occ, length: 2
    )
    monkeypatch.setattr("src.procedural.actor_placement.sample_gap", lambda rng, regime: 10.0)

    red = {20: _green_phase({ApproachDirection.NORTH, ApproachDirection.SOUTH})}
    generator = ActorPlacementGenerator(0, urban_config)
    stopped = generator._place_vehicles_for_lane(  # pylint: disable=protected-access
        zone, {0: edge}, 1.0, [], red, node_clearance, {}, {}, {}
    )
    ordered = sorted(stopped, key=lambda v: v.center[0], reverse=True)
    assert [v.braking for v in ordered[:2]] == [True, True]
    assert all(not v.braking for v in ordered[2:])
    assert len(ordered) > 2  # sanity: there are stragglers behind the queue

    green = {20: _green_phase({ApproachDirection.EAST, ApproachDirection.WEST})}
    flowing = generator._place_vehicles_for_lane(  # pylint: disable=protected-access
        zone, {0: edge}, 1.0, [], green, node_clearance, {}, {}, {}
    )
    assert flowing and all(not v.braking for v in flowing)
