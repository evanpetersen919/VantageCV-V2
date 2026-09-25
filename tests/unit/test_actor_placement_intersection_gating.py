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


def test_vehicle_excluded_at_start_end_when_not_flowing_and_within_clearance(
    urban_config,
) -> None:
    """A candidate whose along-edge distance from its lane's own START
    node is within that node's real crosswalk-clearing zone, and whose
    axis does NOT have the green there, is never placed."""
    edge = _make_edge()  # (0,0) -> (100,0), start_node_id=10, end_node_id=20
    zone = SpawnZone(
        spawn_zone_id=0,
        zone_type=SpawnZoneType.DRIVING,
        position=np.array([10.0, 0.0]),  # 10m from start node -- inside clearance+setback (~18.5m)
        edge_id=0,
    )
    active_phases = {10: _green_phase({ApproachDirection.NORTH, ApproachDirection.SOUTH})}
    node_clearance = {10: 5.0, 20: 5.0}

    generator = ActorPlacementGenerator(0, urban_config)
    result = generator._try_place_vehicle(  # pylint: disable=protected-access
        zone, {0: edge}, 1.0, [], active_phases, node_clearance, {}, {}
    )
    assert result is None


def test_vehicle_allowed_at_start_end_when_flowing_even_within_clearance(
    urban_config,
) -> None:
    """Same geometry as above, but the start node's axis DOES have the
    green there -- the vehicle is placed at its exact natural tiled
    position, even though it sits within what would otherwise be the
    crosswalk-clearing zone ("driving through a green light")."""
    edge = _make_edge()
    zone = SpawnZone(
        spawn_zone_id=0,
        zone_type=SpawnZoneType.DRIVING,
        position=np.array([10.0, 0.0]),
        edge_id=0,
    )
    active_phases = {10: _green_phase({ApproachDirection.EAST, ApproachDirection.WEST})}
    node_clearance = {10: 5.0, 20: 5.0}

    generator = ActorPlacementGenerator(0, urban_config)
    result = generator._try_place_vehicle(  # pylint: disable=protected-access
        zone, {0: edge}, 1.0, [], active_phases, node_clearance, {}, {}
    )
    assert result is not None
    assert np.array_equal(result.center, zone.position)


def test_vehicle_redirected_to_stop_line_at_destination_end_when_not_flowing(
    urban_config,
) -> None:
    """A front-of-queue candidate (real ``stop_line_position``) within its
    destination node's crosswalk-clearing zone, on an axis that does NOT
    have the green there, is redirected so its FRONT BUMPER (not center)
    lands exactly on the real stop line."""
    edge = _make_edge()  # end_node_id=20 at (100, 0)
    stop_line_position = np.array([81.5, 0.0])  # 100 - (5.0 clearance + 13.5 setback)
    zone = SpawnZone(
        spawn_zone_id=0,
        zone_type=SpawnZoneType.DRIVING,
        position=np.array([85.0, 0.0]),  # 15m from end node -- inside the ~18.5m zone
        edge_id=0,
        stop_line_position=stop_line_position,
    )
    active_phases = {20: _green_phase({ApproachDirection.NORTH, ApproachDirection.SOUTH})}
    node_clearance = {10: 5.0, 20: 5.0}

    generator = ActorPlacementGenerator(0, urban_config)
    result = generator._try_place_vehicle(  # pylint: disable=protected-access
        zone, {0: edge}, 1.0, [], active_phases, node_clearance, {}, {}
    )
    assert result is not None
    heading_vector = np.array([np.cos(result.heading_rad), np.sin(result.heading_rad)])
    front_bumper = result.center + heading_vector * (result.length / 2.0)
    assert np.allclose(front_bumper, stop_line_position, atol=1e-6)


def test_vehicle_uses_natural_position_at_destination_end_when_flowing(
    urban_config,
) -> None:
    """Same front-of-queue geometry, but the destination node's axis DOES
    have the green -- the vehicle is placed at its own natural tiled
    position (85m), further into the intersection than the real stop
    line (81.5m) would allow, proving it actually "drives through"."""
    edge = _make_edge()
    stop_line_position = np.array([81.5, 0.0])
    zone = SpawnZone(
        spawn_zone_id=0,
        zone_type=SpawnZoneType.DRIVING,
        position=np.array([85.0, 0.0]),
        edge_id=0,
        stop_line_position=stop_line_position,
    )
    active_phases = {20: _green_phase({ApproachDirection.EAST, ApproachDirection.WEST})}
    node_clearance = {10: 5.0, 20: 5.0}

    generator = ActorPlacementGenerator(0, urban_config)
    result = generator._try_place_vehicle(  # pylint: disable=protected-access
        zone, {0: edge}, 1.0, [], active_phases, node_clearance, {}, {}
    )
    assert result is not None
    assert np.array_equal(result.center, zone.position)


def test_non_front_zone_excluded_at_destination_end_when_not_flowing(urban_config) -> None:
    """A mid-lane zone (no real stop_line_position) within its destination
    node's crosswalk-clearing zone, on an axis without the green there,
    has no precise fallback position and is simply excluded."""
    edge = _make_edge()
    zone = SpawnZone(
        spawn_zone_id=0,
        zone_type=SpawnZoneType.DRIVING,
        position=np.array([85.0, 0.0]),
        edge_id=0,
        stop_line_position=None,
    )
    active_phases = {20: _green_phase({ApproachDirection.NORTH, ApproachDirection.SOUTH})}
    node_clearance = {10: 5.0, 20: 5.0}

    generator = ActorPlacementGenerator(0, urban_config)
    result = generator._try_place_vehicle(  # pylint: disable=protected-access
        zone, {0: edge}, 1.0, [], active_phases, node_clearance, {}, {}
    )
    assert result is None


def test_vehicle_queued_at_stop_line_on_minor_axis_of_a_stop_sign_node(
    urban_config,
) -> None:
    """A front-of-queue candidate approaching a real T-junction on the
    minor/stub axis is redirected to its own stop line -- unconditionally
    (a real 2-way stop always requires a full stop there, no resolved
    instant needed)."""
    edge = _make_edge()  # (0,0) -> (100,0): an EAST-WEST-axis edge
    stop_line_position = np.array([81.5, 0.0])
    zone = SpawnZone(
        spawn_zone_id=0,
        zone_type=SpawnZoneType.DRIVING,
        position=np.array([85.0, 0.0]),
        edge_id=0,
        stop_line_position=stop_line_position,
    )
    node_clearance = {10: 5.0, 20: 5.0}
    traffic_controls = {20: TrafficControlType.STOP_SIGN}
    minor_axis_by_node = {20: frozenset({ApproachDirection.EAST, ApproachDirection.WEST})}

    generator = ActorPlacementGenerator(0, urban_config)
    result = generator._try_place_vehicle(  # pylint: disable=protected-access
        zone, {0: edge}, 1.0, [], {}, node_clearance, traffic_controls, minor_axis_by_node
    )
    assert result is not None
    heading_vector = np.array([np.cos(result.heading_rad), np.sin(result.heading_rad)])
    front_bumper = result.center + heading_vector * (result.length / 2.0)
    assert np.allclose(front_bumper, stop_line_position, atol=1e-6)


def test_vehicle_flows_on_major_axis_of_a_stop_sign_node(urban_config) -> None:
    """Same geometry, but this edge's axis is the T-junction's major/
    through axis -- it never has to stop, so the vehicle keeps its
    natural tiled position even inside what would otherwise be the
    crosswalk-clearing zone."""
    edge = _make_edge()  # EAST-WEST-axis edge
    zone = SpawnZone(
        spawn_zone_id=0,
        zone_type=SpawnZoneType.DRIVING,
        position=np.array([85.0, 0.0]),
        edge_id=0,
        stop_line_position=np.array([81.5, 0.0]),
    )
    node_clearance = {10: 5.0, 20: 5.0}
    traffic_controls = {20: TrafficControlType.STOP_SIGN}
    # The minor axis at node 20 is NORTH-SOUTH here, not this edge's own
    # EAST-WEST axis, so this edge's axis is the (always-flowing) major one.
    minor_axis_by_node = {20: frozenset({ApproachDirection.NORTH, ApproachDirection.SOUTH})}

    generator = ActorPlacementGenerator(0, urban_config)
    result = generator._try_place_vehicle(  # pylint: disable=protected-access
        zone, {0: edge}, 1.0, [], {}, node_clearance, traffic_controls, minor_axis_by_node
    )
    assert result is not None
    assert np.array_equal(result.center, zone.position)


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
