"""Unit tests for TrafficNetworkGenerator.

Covers MASTER_PROMPT Section 3.4's own listed test topics ("Traffic rule
validity", "Navigation path existence") plus QOL_RESEARCH_CHECKLIST.md
Section G considerations.
"""

# pylint: disable=duplicate-code
# test_driving_spawn_zones_tiled_along_each_lane deliberately recomputes
# _generate_driving_zones's own real usable-length formula, independently,
# to verify production code against -- a shared helper would just move the
# formula somewhere both sides import, defeating the point of an
# independent check.

import math
from typing import Dict, List, Optional

import numpy as np
import pytest

from src.procedural.crosswalks import CROSSWALK_DEPTH_M, compute_crosswalk_anchors
from src.procedural.lane_topology import (
    LANE_WIDTH_METERS,
    MAX_TRIM_FRACTION_OF_EDGE_LENGTH,
    LaneTopologyGenerator,
    compute_node_clearance,
)
from src.procedural.math_utils import compute_perpendicular
from src.procedural.road_network import IntersectionType, RoadEdge, RoadNetworkGenerator, RoadType
from src.procedural.traffic_network import (
    PEDESTRIAN_SPAWN_GAP_METERS,
    VEHICLE_SPAWN_GAP_METERS,
    VEHICLE_STOP_LINE_CROSSWALK_SETBACK_M,
    NavigationGraph,
    SpawnZone,
    SpawnZoneType,
    TrafficControlType,
    TrafficNetworkGenerator,
)

# urban_config, bounds fixtures: see tests/conftest.py


def _generate_full_network(seed: int, config, bounds):
    road_gen = RoadNetworkGenerator(seed, config)
    nodes, edges = road_gen.generate(bounds)
    lanes = LaneTopologyGenerator().generate(nodes, edges)
    traffic = TrafficNetworkGenerator().generate(nodes, edges, lanes)
    return nodes, edges, lanes, traffic


def test_traffic_control_matches_node_type(urban_config, bounds) -> None:
    """Traffic rule validity: FOUR_WAY nodes get a traffic light,
    T_JUNCTION nodes get a stop sign, everything else gets no control."""
    nodes, _, _, traffic = _generate_full_network(42, urban_config, bounds)

    for node_id, node in nodes.items():
        control = traffic.traffic_controls[node_id]
        if node.node_type == IntersectionType.FOUR_WAY:
            assert control == TrafficControlType.TRAFFIC_LIGHT
            assert node.traffic_light is True
            assert node.stop_sign is False
        elif node.node_type == IntersectionType.T_JUNCTION:
            assert control == TrafficControlType.STOP_SIGN
            assert node.stop_sign is True
            assert node.traffic_light is False
        else:
            assert control == TrafficControlType.NONE
            assert node.traffic_light is False
            assert node.stop_sign is False


def test_every_node_gets_exactly_one_control(urban_config, bounds) -> None:
    """Every node has a traffic control assignment, and never both a
    traffic light and a stop sign simultaneously."""
    nodes, _, _, traffic = _generate_full_network(42, urban_config, bounds)

    assert set(traffic.traffic_controls.keys()) == set(nodes.keys())
    for node in nodes.values():
        assert not (node.traffic_light and node.stop_sign)


def test_navigation_path_exists_between_connected_nodes(urban_config, bounds) -> None:
    """Navigation path existence: since the road network is validated
    connected (RoadNetworkGenerator._validate_network), a shortest path
    must exist between any two of its nodes."""
    nodes, _, _, traffic = _generate_full_network(42, urban_config, bounds)

    node_ids = list(nodes.keys())
    start, end = node_ids[0], node_ids[-1]

    path = traffic.navigation_graph.shortest_path(start, end)

    assert path is not None
    assert path[0] == start
    assert path[-1] == end


def test_navigation_path_is_contiguous(urban_config, bounds) -> None:
    """Every consecutive pair of nodes in a returned path is joined by a
    real directed edge in the network."""
    nodes, edges, _, traffic = _generate_full_network(42, urban_config, bounds)

    node_ids = list(nodes.keys())
    path = traffic.navigation_graph.shortest_path(node_ids[0], node_ids[-1])
    assert path is not None

    directed_pairs = {(e.start_node_id, e.end_node_id) for e in edges.values()}
    for i in range(len(path) - 1):
        assert (path[i], path[i + 1]) in directed_pairs


def test_shortest_path_same_start_and_end() -> None:
    """A trivial path (start == end) is a single-node path, not None."""
    graph = NavigationGraph(edges={}, weights_seconds={})
    path = graph.shortest_path(5, 5)
    assert path == [5]


def test_shortest_path_no_route_returns_none() -> None:
    """An unreachable target returns None rather than raising."""
    edge = RoadEdge(
        edge_id=0,
        start_node_id=0,
        end_node_id=1,
        road_type=RoadType.MAJOR,
        centerline=np.array([[0.0, 0.0], [10.0, 0.0]]),
        length=10.0,
        num_lanes=2,
        speed_limit_kmh=50,
        width_meters=10.0,
    )
    graph = NavigationGraph(edges={0: edge}, weights_seconds={0: 1.0})
    path = graph.shortest_path(0, 99)
    assert path is None


def _along_lane(position: np.ndarray, lane) -> Optional[float]:
    """Distance of ``position`` along ``lane``'s own centerline direction
    from its start, or ``None`` if ``position`` isn't exactly collinear
    with it (used to attribute a DRIVING zone to the one specific lane it
    belongs to, since two lanes on the same edge are parallel but offset,
    and zones don't carry a lane_id directly)."""
    direction = lane.centerline[-1] - lane.centerline[0]
    length = float(np.linalg.norm(direction))
    if length < 1e-9:
        return None
    unit_direction = direction / length
    offset = position - lane.centerline[0]
    projected = float(np.dot(offset, unit_direction))
    if not np.allclose(lane.centerline[0] + unit_direction * projected, position):
        return None
    return projected


def _zones_for_lane(zones: List[SpawnZone], lane) -> List[SpawnZone]:
    """The subset of ``zones`` (already filtered to one edge_id) whose
    position lies exactly on ``lane``'s own offset centerline line."""
    return [
        z for z in zones if z.edge_id == lane.edge_id and _along_lane(z.position, lane) is not None
    ]


def test_driving_spawn_zones_tiled_along_each_lane(  # pylint: disable=too-many-locals
    urban_config, bounds
) -> None:
    """Every lane gets at least one DRIVING zone, and a lane longer than
    VEHICLE_SPAWN_GAP_METERS gets more than one, tiled at that real
    interval -- not just a single slot at the lane's intersection-facing
    end (a real bug, reported live: vehicles clustered only at
    intersections, leaving entire mid-block lane lengths empty). The
    expected count is derived from the real, bounded ``usable_length``
    (the edge's own real crosswalk-clearing setback at BOTH its start and
    end node -- see ``VEHICLE_STOP_LINE_CROSSWALK_SETBACK_M``'s own
    docstring), not from ``Lane.centerline``'s own (possibly clamped)
    span -- see traffic_network.py's ``_generate_driving_zones`` docstring
    for why those two can differ."""
    _, edges, lanes, traffic = _generate_full_network(42, urban_config, bounds)
    node_clearance = compute_node_clearance(edges)
    driving_zones = [z for z in traffic.spawn_zones if z.zone_type == SpawnZoneType.DRIVING]

    saw_multi_tiled_lane = False
    for lane in lanes.values():
        edge = edges[lane.edge_id]
        edge_direction = edge.centerline[-1] - edge.centerline[0]
        edge_length = float(np.linalg.norm(edge_direction))
        start_clearance = node_clearance.get(edge.start_node_id, 0.0)
        start_boundary_along = min(
            start_clearance + VEHICLE_STOP_LINE_CROSSWALK_SETBACK_M, edge_length
        )
        end_clearance = node_clearance.get(edge.end_node_id, 0.0)
        end_boundary_along = edge_length - min(
            end_clearance + VEHICLE_STOP_LINE_CROSSWALK_SETBACK_M, edge_length
        )
        usable_length = max(end_boundary_along - start_boundary_along, 0.0)

        expected_count = max(1, int(usable_length // VEHICLE_SPAWN_GAP_METERS) + 1)
        matching = _zones_for_lane(driving_zones, lane)
        assert len(matching) == expected_count
        if expected_count > 1:
            saw_multi_tiled_lane = True
    assert saw_multi_tiled_lane  # sanity: this config/seed has long enough lanes to tile


def test_driving_zones_never_inside_crosswalk_at_either_end(  # pylint: disable=too-many-locals
    urban_config, bounds
) -> None:
    """Every DRIVING zone on every lane -- not just the front-of-queue
    one -- clears the real crosswalk-respecting setback
    (VEHICLE_STOP_LINE_CROSSWALK_SETBACK_M) at BOTH the lane's start node
    and its end node. Real bug, found from live re-testing (2026-09-24,
    direct in-engine actor-position cross-check): an earlier version only
    bounded the destination (stop-line) end, leaving a lane's own START
    tile (right after departing the OPPOSITE node) still anchored on the
    plain, crosswalk-unaware node clearance -- a typical clearance (7m)
    sits well inside a real crosswalk's real span (5.5m-20.5m from the
    node in this project's own figures), so a just-departed vehicle could
    still land on the same crosswalk from the other side."""
    _, edges, lanes, traffic = _generate_full_network(42, urban_config, bounds)
    node_clearance = compute_node_clearance(edges)
    driving_zones = [z for z in traffic.spawn_zones if z.zone_type == SpawnZoneType.DRIVING]

    checked_any = False
    for lane in lanes.values():
        edge = edges[lane.edge_id]
        edge_direction = edge.centerline[-1] - edge.centerline[0]
        edge_length = float(np.linalg.norm(edge_direction))
        if edge_length < 1e-9:
            continue
        unit_direction = edge_direction / edge_length
        start_clearance = node_clearance.get(edge.start_node_id, 0.0)
        start_required = min(start_clearance + VEHICLE_STOP_LINE_CROSSWALK_SETBACK_M, edge_length)
        end_clearance = node_clearance.get(edge.end_node_id, 0.0)
        end_required = min(end_clearance + VEHICLE_STOP_LINE_CROSSWALK_SETBACK_M, edge_length)

        for zone in _zones_for_lane(driving_zones, lane):
            checked_any = True
            along_from_start = float(np.dot(zone.position - edge.centerline[0], unit_direction))
            along_from_end = edge_length - along_from_start
            assert along_from_start >= start_required - 1e-6
            assert along_from_end >= end_required - 1e-6
    assert checked_any  # sanity


def test_driving_spawn_zone_carries_real_stop_line_position(  # pylint: disable=too-many-locals
    urban_config, bounds
) -> None:
    """Only the single DRIVING zone closest to each lane's own destination
    node carries a real stop_line_position -- computed straight from the
    edge's own real (untrimmed) endpoint and the real, unclamped
    ``compute_node_clearance`` value (never from
    ``Lane.centerline[-1]``, which can itself be clamped short -- see
    ``VEHICLE_STOP_LINE_CROSSWALK_SETBACK_M``'s own docstring for the real
    bug this avoids), so it lands flush BEHIND the crosswalk's own far
    edge rather than on/past it, even on a dense small-block layout where
    the lane's own trim clamp would otherwise put its raw far end inside
    the intersection box. Every other DRIVING zone on the same lane
    carries None."""
    _, edges, lanes, traffic = _generate_full_network(42, urban_config, bounds)
    node_clearance = compute_node_clearance(edges)
    driving_zones = [z for z in traffic.spawn_zones if z.zone_type == SpawnZoneType.DRIVING]
    assert driving_zones  # sanity

    saw_a_stop_line = False
    for lane in lanes.values():
        edge = edges[lane.edge_id]
        lane_zones = _zones_for_lane(driving_zones, lane)
        with_stop_line = [z for z in lane_zones if z.stop_line_position is not None]
        assert len(with_stop_line) == 1  # exactly one per lane
        zone = with_stop_line[0]
        saw_a_stop_line = True

        direction = edge.centerline[-1] - edge.centerline[0]
        edge_length = float(np.linalg.norm(direction))
        unit_direction = direction / edge_length
        perp = compute_perpendicular(direction)
        offset_distance = (lane.lane_index + 0.5) * LANE_WIDTH_METERS
        clearance = node_clearance.get(edge.end_node_id, 0.0)
        distance_from_node = min(clearance + VEHICLE_STOP_LINE_CROSSWALK_SETBACK_M, edge_length)
        expected = (
            edge.centerline[-1] - unit_direction * distance_from_node + perp * offset_distance
        )
        assert np.allclose(zone.stop_line_position, expected)
    assert saw_a_stop_line  # sanity


def test_stop_line_never_inside_real_crosswalk(  # pylint: disable=too-many-locals
    urban_config, bounds
) -> None:
    """Independent check against the real crosswalk anchors (not a
    re-derivation of this module's own formula): every DRIVING zone's
    stop_line_position sits at or beyond the actual crosswalk's own far
    edge for its node -- computed via ``compute_crosswalk_anchors``, the
    same function that places the real painted crosswalk bars -- so a
    queued vehicle is provably never rendered overlapping the crosswalk,
    even on this project's densest, smallest-block layouts where
    lane-trim clamping previously masked this (see
    ``VEHICLE_STOP_LINE_CROSSWALK_SETBACK_M``'s own docstring)."""
    nodes, edges, lanes, traffic = _generate_full_network(42, urban_config, bounds)
    anchors = compute_crosswalk_anchors(nodes, edges)
    driving_zones = [z for z in traffic.spawn_zones if z.zone_type == SpawnZoneType.DRIVING]

    checked_any = False
    for lane in lanes.values():
        edge = edges[lane.edge_id]
        lane_zones = _zones_for_lane(driving_zones, lane)
        with_stop_line = [z for z in lane_zones if z.stop_line_position is not None]
        assert len(with_stop_line) == 1
        zone = with_stop_line[0]

        # The real anchor for THIS edge's approach to its own end node:
        # the one whose pivot lies along this edge's own incoming
        # direction from that node (an anchor's own `perp` is
        # perpendicular to the road it crosses, so projecting the
        # node->pivot vector onto this edge's unit_direction picks out
        # the matching anchor, not an unrelated road at the same node).
        direction = edge.centerline[-1] - edge.centerline[0]
        edge_length = float(np.linalg.norm(direction))
        unit_direction = direction / edge_length
        node_position = edge.centerline[-1]
        matching_anchor = next(
            (
                a
                for a in anchors
                if a.node_id == edge.end_node_id
                and np.dot(a.pivot - node_position, unit_direction) < 0
                and abs(np.dot(a.pivot - node_position, compute_perpendicular(direction))) < 1e-6
            ),
            None,
        )
        if matching_anchor is None:
            continue  # this road end has no real crosswalk (too short -- see crosswalks.py)
        checked_any = True

        # far edge = pivot's own along-edge distance from node, plus half
        # the real crosswalk depth (CROSSWALK_DEPTH_M/2), since pivot is
        # centered on the bar (see crosswalks.py's own docstring).
        far_edge_distance_from_node = (
            float(np.dot(node_position - matching_anchor.pivot, unit_direction))
            + CROSSWALK_DEPTH_M / 2.0
        )

        stop_distance_from_node = float(
            np.dot(node_position - zone.stop_line_position, unit_direction)
        )
        assert stop_distance_from_node >= far_edge_distance_from_node - 1e-6
    assert checked_any  # sanity: at least one real crosswalk was matched and checked


def test_crossing_zone_carries_real_node_id(urban_config, bounds) -> None:
    """Every CROSSING zone's node_id matches a real crosswalk anchor's own
    node_id -- the intersection this crossing belongs to, needed to look
    up which signal phase governs it."""
    nodes, edges, _, traffic = _generate_full_network(42, urban_config, bounds)
    anchors = compute_crosswalk_anchors(nodes, edges)
    real_node_ids = {anchor.node_id for anchor in anchors}

    crossing_zones = [z for z in traffic.spawn_zones if z.zone_type == SpawnZoneType.CROSSING]
    assert crossing_zones  # sanity

    for zone in crossing_zones:
        assert zone.node_id is not None
        assert zone.node_id in real_node_ids


def test_pedestrian_spawn_zones_tiled_along_each_edge(  # pylint: disable=too-many-locals
    urban_config, bounds
) -> None:
    """Pedestrian spawn zones are tiled along every edge that has lanes,
    at the real PEDESTRIAN_SPAWN_GAP_METERS interval (see that constant's
    own docstring) -- not just one fixed slot per edge -- and stop short
    of each end node by that node's own real clearance, so no zone lands
    inside the intersection box (a real bug found live: pedestrians
    appearing to stand in the road at intersections)."""
    _, edges, lanes, traffic = _generate_full_network(42, urban_config, bounds)

    edges_with_lanes = {lane.edge_id for lane in lanes.values()}
    pedestrian_zones = [z for z in traffic.spawn_zones if z.zone_type == SpawnZoneType.PEDESTRIAN]
    assert len(edges_with_lanes) <= len(edges)
    assert len(pedestrian_zones) > len(edges_with_lanes)  # more than one slot per edge now

    zones_by_edge: Dict[int, List[SpawnZone]] = {}
    for zone in pedestrian_zones:
        zones_by_edge.setdefault(zone.edge_id, []).append(zone)
    assert set(zones_by_edge) <= edges_with_lanes

    node_clearance = compute_node_clearance(edges)
    for edge_id, zones in zones_by_edge.items():
        edge = edges[edge_id]
        edge_length = float(np.linalg.norm(edge.centerline[-1] - edge.centerline[0]))
        max_trim_each_side = edge_length * MAX_TRIM_FRACTION_OF_EDGE_LENGTH
        start_trim = min(node_clearance.get(edge.start_node_id, 0.0), max_trim_each_side)
        end_trim = min(node_clearance.get(edge.end_node_id, 0.0), max_trim_each_side)
        usable_length = edge_length - start_trim - end_trim
        expected_count = int(usable_length // PEDESTRIAN_SPAWN_GAP_METERS) + 1
        assert len(zones) == expected_count
        for zone_a, zone_b in zip(zones, zones[1:]):
            gap = float(np.linalg.norm(zone_b.position - zone_a.position))
            assert gap == pytest.approx(PEDESTRIAN_SPAWN_GAP_METERS)

        # No zone lands inside the intersection box: the first zone's
        # along-edge distance from the start node must equal the real
        # start_trim exactly (projected onto the edge's own direction,
        # since the sidewalk's perpendicular offset doesn't affect this).
        unit_direction = (edge.centerline[-1] - edge.centerline[0]) / edge_length
        along_distance = float(np.dot(zones[0].position - edge.centerline[0], unit_direction))
        assert along_distance == pytest.approx(start_trim, abs=1e-6)


def test_crossing_zones_tiled_across_real_crosswalk_width(urban_config, bounds) -> None:
    """CROSSING spawn zones exist, are tiled at the real
    PEDESTRIAN_SPAWN_GAP_METERS interval across each real crosswalk's own
    combined-road width, and each carries a real heading_rad (the
    crosswalk's own across-the-road crossing direction) instead of an
    edge_id (a crosswalk spans a whole road at a node, not one directed
    edge)."""
    nodes, edges, _, traffic = _generate_full_network(42, urban_config, bounds)

    crossing_zones = [z for z in traffic.spawn_zones if z.zone_type == SpawnZoneType.CROSSING]
    assert crossing_zones  # sanity: this config/seed has real crosswalks

    anchors = compute_crosswalk_anchors(nodes, edges)
    assert anchors

    for zone in crossing_zones:
        assert zone.edge_id is None
        assert zone.heading_rad is not None

    for anchor in anchors:
        expected_heading = math.atan2(float(anchor.perp[1]), float(anchor.perp[0]))
        num_points = max(1, round(anchor.road_width_m / PEDESTRIAN_SPAWN_GAP_METERS))
        matching_zones = [
            z
            for z in crossing_zones
            if np.isclose(z.heading_rad, expected_heading)
            and np.linalg.norm(z.position - anchor.pivot) <= anchor.road_width_m / 2.0 + 1e-6
        ]
        assert len(matching_zones) == num_points


def test_spawn_zone_ids_unique(urban_config, bounds) -> None:
    """No two spawn zones share a spawn_zone_id."""
    _, _, _, traffic = _generate_full_network(42, urban_config, bounds)

    ids = [z.spawn_zone_id for z in traffic.spawn_zones]
    assert len(ids) == len(set(ids))


def test_spawn_zone_positions_finite(urban_config, bounds) -> None:
    """All spawn zone positions are finite (no NaN/Inf)."""
    _, _, _, traffic = _generate_full_network(42, urban_config, bounds)

    for zone in traffic.spawn_zones:
        assert np.isfinite(zone.position).all()


def test_no_lanes_yields_no_driving_or_pedestrian_spawn_zones(urban_config, bounds) -> None:
    """An empty lane dict produces no DRIVING/PEDESTRIAN spawn zones (both
    are derived from lane geometry) -- but CROSSING zones may still exist,
    since crosswalk geometry (crosswalks.compute_crosswalk_anchors) comes
    from nodes/edges directly, independent of lanes."""
    road_gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = road_gen.generate(bounds)

    traffic = TrafficNetworkGenerator().generate(nodes, edges, {})

    assert not any(
        z.zone_type in (SpawnZoneType.DRIVING, SpawnZoneType.PEDESTRIAN)
        for z in traffic.spawn_zones
    )


@pytest.mark.parametrize("seed", [0, 1, 99])
def test_determinism_across_seeds(urban_config, bounds, seed) -> None:
    """Same seed produces identical traffic control assignments."""
    nodes1, _, _, traffic1 = _generate_full_network(seed, urban_config, bounds)
    nodes2, _, _, traffic2 = _generate_full_network(seed, urban_config, bounds)

    assert traffic1.traffic_controls == traffic2.traffic_controls
    assert len(nodes1) == len(nodes2)
