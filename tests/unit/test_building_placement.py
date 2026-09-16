"""Unit tests for BuildingPlacementGenerator.

Covers QOL_RESEARCH_CHECKLIST.md Section B.3: no building-building
overlap, no building-road overlap, buildings within bounds, density
roughly matches config.
"""

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from src.procedural.building_placement import (
    BUILDING_MATERIALS_BY_TYPE,
    Building,
    BuildingPlacementGenerator,
    BuildingType,
    _aabb_overlap,
    _classify_building_type,
    _point_segment_distance,
    _polygon_area,
    _polygon_contains_point,
    _segment_intersects_aabb,
)
from src.procedural.lane_topology import LaneTopologyGenerator
from src.procedural.mesh_factory import MeshFactory
from src.procedural.road_network import (
    IntersectionType,
    RoadEdge,
    RoadNetworkGenerator,
    RoadNode,
    RoadType,
)

# urban_config, bounds fixtures: see tests/conftest.py


def test_no_building_to_building_overlap(urban_config, bounds) -> None:
    """No two placed buildings' AABBs overlap."""
    road_gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = road_gen.generate(bounds)

    buildings = BuildingPlacementGenerator(42, urban_config).generate(nodes, edges)

    for i, building1 in enumerate(buildings):
        for building2 in buildings[i + 1 :]:
            assert not _aabb_overlap(
                building1.aabb, building2.aabb
            ), f"Buildings {building1.building_id} and {building2.building_id} overlap"


def test_no_building_within_road_setback(  # pylint: disable=too-many-locals
    urban_config, bounds
) -> None:
    """No building footprint corner comes within
    config.road_setback_meters of a road centerline."""
    road_gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = road_gen.generate(bounds)

    buildings = BuildingPlacementGenerator(42, urban_config).generate(nodes, edges)
    road_segments = [
        (nodes[e.start_node_id].position, nodes[e.end_node_id].position) for e in edges.values()
    ]
    setback = urban_config.road_setback_meters

    for building in buildings:
        x_min, y_min, x_max, y_max = building.aabb
        corners = [
            np.array([x_min, y_min]),
            np.array([x_min, y_max]),
            np.array([x_max, y_min]),
            np.array([x_max, y_max]),
        ]
        for seg_a, seg_b in road_segments:
            for corner in corners:
                dist = _point_segment_distance(corner, seg_a, seg_b)
                assert dist >= setback - 1e-6, (
                    f"Building {building.building_id} corner {corner} is {dist}m "
                    f"from a road, closer than the {setback}m setback"
                )


def test_custom_road_setback_meters_is_actually_respected(  # pylint: disable=too-many-locals
    urban_config, bounds
) -> None:
    """A non-default road_setback_meters genuinely changes generated
    placement, not just validated and then silently ignored in favor of
    a hardcoded value -- the exact regression this field's own addition
    was meant to close (see KNOWN_GAPS_AND_ISSUES.md)."""
    wide_setback_config = urban_config.model_copy(update={"road_setback_meters": 8.0})
    road_gen = RoadNetworkGenerator(42, wide_setback_config)
    nodes, edges = road_gen.generate(bounds)

    buildings = BuildingPlacementGenerator(42, wide_setback_config).generate(nodes, edges)
    assert buildings  # sanity: this config/seed still places some

    road_segments = [
        (nodes[e.start_node_id].position, nodes[e.end_node_id].position) for e in edges.values()
    ]
    for building in buildings:
        x_min, y_min, x_max, y_max = building.aabb
        corners = [
            np.array([x_min, y_min]),
            np.array([x_min, y_max]),
            np.array([x_max, y_min]),
            np.array([x_max, y_max]),
        ]
        for seg_a, seg_b in road_segments:
            for corner in corners:
                dist = _point_segment_distance(corner, seg_a, seg_b)
                assert dist >= 8.0 - 1e-6


def test_no_building_overlaps_actual_lane_pavement(  # pylint: disable=too-many-locals
    urban_config, bounds
) -> None:
    """No building footprint overlaps the real, rendered lane-mesh
    geometry (not just a fixed distance from the road centerline).

    Regression test for a real bug found via UE5 dogfooding: with only
    `config.road_setback_meters` (a small fixed margin, 2-4m for this
    project's templates) enforced from the centerline, buildings could
    -- and in a real generated scenario, did (194 of 283 buildings, ~69%)
    -- end up standing inside a multi-lane road's actual paved area,
    since a road's real physical half-width from centerline is
    `edge.num_lanes * LANE_WIDTH_METERS` (up to 14m for a 4-lane edge),
    not just the fixed setback margin. Fixed by adding each edge's own
    lane half-width to the setback enforced against it. This test
    checks the real, rendered geometry (via Shapely, unioning actual
    mesh triangles), not just a reimplementation of the fixed-distance
    formula the bug was in.
    """
    road_gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = road_gen.generate(bounds)
    lanes = LaneTopologyGenerator().generate(nodes, edges)
    buildings = BuildingPlacementGenerator(42, urban_config).generate(nodes, edges)
    assert buildings  # sanity: this config/seed still places some

    lane_shapes = []
    for lane in lanes.values():
        mesh = MeshFactory.build_road_mesh(lane)
        triangles = []
        vertices_2d = mesh.vertices[:, :2]
        for i in range(0, len(mesh.triangles), 3):
            a, b, c = mesh.triangles[i : i + 3]
            triangle = Polygon([vertices_2d[a], vertices_2d[b], vertices_2d[c]])
            if triangle.area > 1e-9:
                triangles.append(triangle)
        if triangles:
            lane_shapes.append(unary_union(triangles))
    all_lane_area = unary_union(lane_shapes)

    for building in buildings:
        x_min, y_min, x_max, y_max = building.aabb
        footprint = Polygon([(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)])
        overlap = footprint.intersection(all_lane_area)
        assert overlap.area < 0.1, (
            f"Building {building.building_id} overlaps {overlap.area:.2f} sq m of real "
            "lane pavement"
        )


def test_building_heights_within_config_range(urban_config, bounds) -> None:
    """Every building's height falls within config.building_heights."""
    road_gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = road_gen.generate(bounds)

    buildings = BuildingPlacementGenerator(42, urban_config).generate(nodes, edges)

    min_height, max_height = urban_config.building_heights
    for building in buildings:
        assert min_height <= building.height <= max_height


def test_building_dimensions_are_positive(urban_config, bounds) -> None:
    """Width, depth, and height are all strictly positive."""
    road_gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = road_gen.generate(bounds)

    buildings = BuildingPlacementGenerator(42, urban_config).generate(nodes, edges)

    assert len(buildings) > 0, "Expected at least one building at this seed/bounds/density"
    for building in buildings:
        assert building.width > 0
        assert building.depth > 0
        assert building.height > 0


def test_building_ids_unique(urban_config, bounds) -> None:
    """No two buildings share a building_id."""
    road_gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = road_gen.generate(bounds)

    buildings = BuildingPlacementGenerator(42, urban_config).generate(nodes, edges)

    ids = [b.building_id for b in buildings]
    assert len(ids) == len(set(ids))


def test_determinism_same_seed_same_buildings(urban_config, bounds) -> None:
    """Same seed produces an identical set of buildings."""
    road_gen1 = RoadNetworkGenerator(42, urban_config)
    nodes1, edges1 = road_gen1.generate(bounds)
    buildings1 = BuildingPlacementGenerator(99, urban_config).generate(nodes1, edges1)

    road_gen2 = RoadNetworkGenerator(42, urban_config)
    nodes2, edges2 = road_gen2.generate(bounds)
    buildings2 = BuildingPlacementGenerator(99, urban_config).generate(nodes2, edges2)

    assert len(buildings1) == len(buildings2)
    for b1, b2 in zip(buildings1, buildings2):
        assert np.allclose(b1.center, b2.center)
        assert b1.width == b2.width
        assert b1.height == b2.height


def test_zero_density_config_places_no_buildings(urban_config, bounds) -> None:
    """A config with building_density=0 places zero buildings."""
    zero_density_config = urban_config.model_copy(update={"building_density": 0.0})
    road_gen = RoadNetworkGenerator(42, zero_density_config)
    nodes, edges = road_gen.generate(bounds)

    buildings = BuildingPlacementGenerator(42, zero_density_config).generate(nodes, edges)

    assert len(buildings) == 0


def test_too_few_nodes_yields_no_blocks(urban_config) -> None:
    """Fewer than 3 nodes cannot be triangulated into any block."""
    gen = BuildingPlacementGenerator(42, urban_config)
    blocks = gen._identify_blocks({}, {})  # pylint: disable=protected-access
    assert not blocks


def _make_node(node_id: int, x: float, y: float) -> RoadNode:
    return RoadNode(node_id=node_id, position=np.array([x, y]), node_type=IntersectionType.ISOLATED)


def _make_edge(edge_id: int, start: int, end: int, length: float) -> RoadEdge:
    return RoadEdge(
        edge_id=edge_id,
        start_node_id=start,
        end_node_id=end,
        road_type=RoadType.MAJOR,
        centerline=np.array([[0.0, 0.0], [0.0, 0.0]]),
        length=length,
        num_lanes=2,
        speed_limit_kmh=50,
        width_meters=10.0,
    )


def test_collinear_nodes_yield_no_blocks_not_a_crash(urban_config) -> None:
    """Collinear node positions make Delaunay fail internally
    (QhullError); _identify_blocks catches it and returns no blocks rather
    than propagating the exception -- see road_network.py's own
    collinear-point test for the same underlying degeneracy."""
    nodes = {0: _make_node(0, 0.0, 0.0), 1: _make_node(1, 10.0, 0.0), 2: _make_node(2, 20.0, 0.0)}
    edges = {
        0: _make_edge(0, 0, 1, 10.0),
        1: _make_edge(1, 1, 2, 10.0),
    }
    gen = BuildingPlacementGenerator(42, urban_config)
    blocks = gen._identify_blocks(nodes, edges)  # pylint: disable=protected-access
    assert not blocks


def test_triangle_with_missing_edge_excluded_from_blocks(urban_config) -> None:
    """A Delaunay triangle whose 3rd edge was filtered out of the road
    graph (e.g. for exceeding MAX_ROAD_LENGTH_METERS) is not treated as a
    city block, even though the other two edges exist."""
    nodes = {
        0: _make_node(0, 0.0, 0.0),
        1: _make_node(1, 100.0, 0.0),
        2: _make_node(2, 50.0, 80.0),
    }
    # Only 2 of the 3 triangle edges exist in the graph.
    edges = {
        0: _make_edge(0, 0, 1, 100.0),
        1: _make_edge(1, 1, 2, 94.3),
    }
    gen = BuildingPlacementGenerator(42, urban_config)
    blocks = gen._identify_blocks(nodes, edges)  # pylint: disable=protected-access
    assert not blocks


def test_degenerate_area_triangle_excluded_from_blocks(urban_config) -> None:
    """A near-zero-area (sliver) triangle, even with all 3 edges present,
    is excluded as too small to place a building in."""
    nodes = {
        0: _make_node(0, 0.0, 0.0),
        1: _make_node(1, 1.0, 0.0),
        2: _make_node(2, 2.0, 0.01),
    }
    edges = {
        0: _make_edge(0, 0, 1, 1.0),
        1: _make_edge(1, 1, 2, 1.0),
        2: _make_edge(2, 2, 0, 2.0),
    }
    gen = BuildingPlacementGenerator(42, urban_config)
    blocks = gen._identify_blocks(nodes, edges)  # pylint: disable=protected-access
    assert not blocks


# --- Geometry helper unit tests -------------------------------------------


def test_polygon_area_unit_square() -> None:
    """Shoelace formula on a known unit square gives area 1."""
    square = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    assert np.isclose(_polygon_area(square), 1.0)


def test_polygon_area_triangle() -> None:
    """Shoelace formula on a right triangle with legs 3, 4 gives area 6."""
    triangle = np.array([[0.0, 0.0], [4.0, 0.0], [0.0, 3.0]])
    assert np.isclose(_polygon_area(triangle), 6.0)


def test_polygon_contains_point_inside_and_outside() -> None:
    """Ray-casting correctly classifies interior vs. exterior points."""
    square = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]])
    assert _polygon_contains_point(square, np.array([5.0, 5.0]))
    assert not _polygon_contains_point(square, np.array([15.0, 5.0]))


def test_point_segment_distance_perpendicular_and_endpoint_cases() -> None:
    """Distance to a segment is correct for a perpendicular foot on the
    segment, and clamps to an endpoint when the foot falls outside it."""
    seg_a = np.array([0.0, 0.0])
    seg_b = np.array([10.0, 0.0])

    assert np.isclose(_point_segment_distance(np.array([5.0, 3.0]), seg_a, seg_b), 3.0)
    assert np.isclose(_point_segment_distance(np.array([-4.0, 0.0]), seg_a, seg_b), 4.0)


def test_segment_intersects_aabb_when_passing_through() -> None:
    """A segment that passes straight through a box is detected."""
    box = (0.0, 0.0, 10.0, 10.0)
    assert _segment_intersects_aabb(np.array([-5.0, 5.0]), np.array([15.0, 5.0]), box)


def test_segment_intersects_aabb_near_parallel_to_one_side() -> None:
    """A segment running parallel to, and close beside, one side of the
    box -- but far from every corner -- is still detected as intersecting
    once the box is inflated by the setback distance. This is the exact
    failure mode test_no_building_to_building_overlap caught: a
    corner-only distance check misses this case entirely."""
    box = (0.0, 0.0, 10.0, 10.0)
    inflated = (box[0] - 2.0, box[1] - 2.0, box[2] + 2.0, box[3] + 2.0)
    # Horizontal segment 1m above the box's top edge, spanning only its
    # middle third -- nowhere near either top corner.
    segment_a = np.array([4.0, 11.0])
    segment_b = np.array([6.0, 11.0])
    assert _segment_intersects_aabb(segment_a, segment_b, inflated)


def test_segment_intersects_aabb_far_away_returns_false() -> None:
    """A segment far from the box does not intersect it."""
    box = (0.0, 0.0, 10.0, 10.0)
    assert not _segment_intersects_aabb(np.array([100.0, 100.0]), np.array([200.0, 200.0]), box)


def test_segment_intersects_aabb_axis_aligned_segment() -> None:
    """A perfectly vertical or horizontal segment (zero-division risk in
    the slab method) is handled without error."""
    box = (0.0, 0.0, 10.0, 10.0)
    assert _segment_intersects_aabb(np.array([5.0, -5.0]), np.array([5.0, 15.0]), box)
    assert not _segment_intersects_aabb(np.array([50.0, -5.0]), np.array([50.0, 15.0]), box)


def test_point_segment_distance_degenerate_segment() -> None:
    """A zero-length segment (seg_a == seg_b) falls back to point distance
    rather than dividing by zero."""
    point = np.array([3.0, 4.0])
    seg_a = np.array([0.0, 0.0])
    seg_b = np.array([0.0, 0.0])
    assert np.isclose(_point_segment_distance(point, seg_a, seg_b), 5.0)


def test_classify_building_type_bottom_third_is_residential() -> None:
    """Heights in the bottom third of the configured range classify RESIDENTIAL."""
    assert _classify_building_type(10.0, (10.0, 40.0)) == BuildingType.RESIDENTIAL
    assert _classify_building_type(19.9, (10.0, 40.0)) == BuildingType.RESIDENTIAL


def test_classify_building_type_middle_third_is_mixed_use() -> None:
    """Heights in the middle third of the configured range classify MIXED_USE."""
    assert _classify_building_type(20.0, (10.0, 40.0)) == BuildingType.MIXED_USE
    assert _classify_building_type(25.0, (10.0, 40.0)) == BuildingType.MIXED_USE


def test_classify_building_type_top_third_is_commercial() -> None:
    """Heights in the top third of the configured range classify COMMERCIAL."""
    assert _classify_building_type(30.0, (10.0, 40.0)) == BuildingType.COMMERCIAL
    assert _classify_building_type(40.0, (10.0, 40.0)) == BuildingType.COMMERCIAL


def test_classify_building_type_degenerate_range_defaults_to_mixed_use() -> None:
    """A config with min == max building height has no meaningful
    relative position -- defaults to the taxonomy's neutral category
    rather than dividing by zero."""
    assert _classify_building_type(15.0, (15.0, 15.0)) == BuildingType.MIXED_USE


def test_every_building_type_has_at_least_one_material() -> None:
    """Every BuildingType has a real, non-empty material set defined."""
    for building_type in BuildingType:
        assert building_type in BUILDING_MATERIALS_BY_TYPE
        assert len(BUILDING_MATERIALS_BY_TYPE[building_type]) > 0


def test_generated_buildings_have_type_and_material_consistent_with_height(
    urban_config, bounds
) -> None:
    """Every generated building's type matches its own height's relative
    position in config.building_heights, and its material is one this
    codebase actually declares for that type."""
    road_gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = road_gen.generate(bounds)
    buildings = BuildingPlacementGenerator(42, urban_config).generate(nodes, edges)

    assert buildings  # sanity: this config/seed places some
    for building in buildings:
        expected_type = _classify_building_type(building.height, urban_config.building_heights)
        assert building.building_type == expected_type
        assert building.material in BUILDING_MATERIALS_BY_TYPE[building.building_type]


def test_generated_building_types_are_not_all_the_same(urban_config, bounds) -> None:
    """A real scenario's buildings span more than one type -- confirms
    the height-driven classification actually varies, not just that it
    runs without error."""
    road_gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = road_gen.generate(bounds)
    buildings = BuildingPlacementGenerator(42, urban_config).generate(nodes, edges)

    observed_types = {b.building_type for b in buildings}
    assert len(observed_types) > 1


def test_building_type_and_material_deterministic_across_seeds(urban_config, bounds) -> None:
    """Same seed produces identical building_type/material assignments."""
    road_gen = RoadNetworkGenerator(7, urban_config)
    nodes, edges = road_gen.generate(bounds)

    buildings1 = BuildingPlacementGenerator(7, urban_config).generate(nodes, edges)
    buildings2 = BuildingPlacementGenerator(7, urban_config).generate(nodes, edges)

    assert len(buildings1) == len(buildings2)
    for b1, b2 in zip(buildings1, buildings2):
        assert b1.building_type == b2.building_type
        assert b1.material == b2.material


def test_building_default_type_and_material() -> None:
    """A Building constructed without explicit building_type/material
    (e.g. in tests that only care about geometry) gets the documented
    defaults -- every pre-existing caller keeps working unchanged."""
    building = Building(
        building_id=0, center=np.array([0.0, 0.0]), width=10.0, depth=10.0, height=20.0
    )
    assert building.building_type == BuildingType.MIXED_USE
    assert building.material == "concrete"
