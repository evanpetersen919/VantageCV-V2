"""Unit tests for BuildingPlacementGenerator.

Covers QOL_RESEARCH_CHECKLIST.md Section B.3: no building-building
overlap, no building-road overlap, buildings within bounds, density
roughly matches config.
"""

import dataclasses

import numpy as np
import pytest
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
    _quantize_footprint_side,
    _quantize_height,
    _segment_intersects_aabb,
)
from src.procedural.city_sample_assets import BUILDING_KITS, DEFAULT_BUILDING_STYLE, BuildingStyle
from src.procedural.lane_topology import LaneTopologyGenerator
from src.procedural.mesh_factory import MeshFactory
from src.procedural.road_network import (
    IntersectionType,
    RoadEdge,
    RoadNetworkGenerator,
    RoadNode,
    RoadType,
)
from tests.conftest import mesh_to_shapely_footprint

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

    lane_shapes = [
        shape
        for shape in (
            mesh_to_shapely_footprint(MeshFactory.build_road_mesh(lane)) for lane in lanes.values()
        )
        if shape is not None
    ]
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


def test_building_width_and_depth_are_exact_facade_module_multiples(urban_config, bounds) -> None:
    """Every real generated building's width/depth land on an exact
    ``corner_reach + N*wall`` fit -- the real condition building_facade.py's
    tiling needs to close without a gap or overlap (see
    KNOWN_GAPS_AND_ISSUES.md's quantization entry)."""
    road_gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = road_gen.generate(bounds)

    buildings = BuildingPlacementGenerator(42, urban_config).generate(nodes, edges)
    assert len(buildings) > 0

    for building in buildings:
        for side in (building.width, building.depth):
            wall_count = DEFAULT_BUILDING_STYLE.wall_count_for_edge_length(side)
            assert wall_count >= 1
            assert DEFAULT_BUILDING_STYLE.edge_length_for_wall_count(wall_count) == pytest.approx(
                side, abs=1e-6
            )


def test_building_height_is_exact_floor_module_multiple(urban_config, bounds) -> None:
    """Every real generated building's height is exactly the cumulative
    height of a whole number of the style's floors."""
    road_gen = RoadNetworkGenerator(42, urban_config)
    nodes, edges = road_gen.generate(bounds)

    buildings = BuildingPlacementGenerator(42, urban_config).generate(nodes, edges)
    assert len(buildings) > 0

    for building in buildings:
        floor_count = DEFAULT_BUILDING_STYLE.floor_count_for_height(building.height)
        assert DEFAULT_BUILDING_STYLE.total_height(floor_count) == pytest.approx(
            building.height, abs=1e-6
        )


def test_quantize_footprint_side_never_shrinks_input() -> None:
    """Quantization only rounds up -- never produces a side shorter than
    what was sampled, preserving density/setback assumptions."""
    for sampled in (8.0, 10.06, 15.5, 25.0):
        assert _quantize_footprint_side(sampled, DEFAULT_BUILDING_STYLE) >= sampled


def test_quantize_height_never_shrinks_input() -> None:
    """Quantization only rounds up -- never produces a height shorter
    than what was sampled."""
    for sampled in (1.0, 4.9, 20.0, 39.9):
        assert _quantize_height(sampled, DEFAULT_BUILDING_STYLE, 1000.0) >= sampled


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


def test_quantize_height_never_exceeds_max_height() -> None:
    """When rounding up to the next real floor stack would overshoot
    ``max_height``, the tallest stack that fits is used instead -- so
    config.building_heights stays a hard upper bound even though real
    stack heights (5.0 + 3.0 * n) are not multiples of one floor height."""
    style = DEFAULT_BUILDING_STYLE
    for max_height in (10.0, 20.0, 40.0):
        for sampled in np.linspace(5.0, max_height, 25):
            quantized = _quantize_height(float(sampled), style, max_height)
            assert quantized <= max_height + 1e-9


def _wide_grid_style() -> BuildingStyle:
    """A second synthetic style with a different horizontal grid and
    different floor height, standing in for another building family."""
    kit = dataclasses.replace(
        BUILDING_KITS["CHA_L1"], wall_width_m=3.75, corner_to_first_wall_m=2.0, floor_height_m=4.0
    )
    return BuildingStyle(name="WIDE", levels=(kit,))


def test_multiple_styles_are_used_and_each_building_quantized_to_its_own(
    urban_config, bounds
) -> None:
    """With two styles, both appear, and every building's footprint and
    height are exact fits of the style recorded on that building."""
    nodes, edges = RoadNetworkGenerator(42, urban_config).generate(bounds)
    wide = _wide_grid_style()
    styles = {DEFAULT_BUILDING_STYLE.name: DEFAULT_BUILDING_STYLE, wide.name: wide}

    buildings = BuildingPlacementGenerator(42, urban_config, tuple(styles.values())).generate(
        nodes, edges
    )

    assert {b.style_name for b in buildings} == set(styles)
    for building in buildings:
        style = styles[building.style_name]
        for side in (building.width, building.depth):
            wall_count = style.wall_count_for_edge_length(side)
            assert style.edge_length_for_wall_count(wall_count) == pytest.approx(side, abs=1e-6)
        floors = style.floor_count_for_height(building.height)
        assert style.total_height(floors) == pytest.approx(building.height, abs=1e-6)


def test_multi_style_placement_is_deterministic(urban_config, bounds) -> None:
    """The same seed and styles give identical styles/footprints."""
    nodes, edges = RoadNetworkGenerator(42, urban_config).generate(bounds)
    styles = (DEFAULT_BUILDING_STYLE, _wide_grid_style())

    first = BuildingPlacementGenerator(42, urban_config, styles).generate(nodes, edges)
    second = BuildingPlacementGenerator(42, urban_config, styles).generate(nodes, edges)

    assert [(b.style_name, b.width, b.depth, b.height) for b in first] == [
        (b.style_name, b.width, b.depth, b.height) for b in second
    ]


def test_generator_rejects_empty_style_list(urban_config) -> None:
    """At least one style is required."""
    with pytest.raises(ValueError):
        BuildingPlacementGenerator(42, urban_config, ())


def test_styles_too_tall_for_the_height_cap_are_never_used(urban_config, bounds) -> None:
    """A style whose single-floor height exceeds config.building_heights'
    maximum (like SFA's 12.75m ground floor under a 10m cap) is skipped."""
    tall_ground = dataclasses.replace(BUILDING_KITS["CHA_L1"], floor_height_m=50.0)
    tall_style = BuildingStyle(name="TALL", levels=(tall_ground,))
    config = urban_config.model_copy(update={"building_heights": (10.0, 25.0)})
    nodes, edges = RoadNetworkGenerator(42, config).generate(bounds)

    buildings = BuildingPlacementGenerator(
        42, config, (DEFAULT_BUILDING_STYLE, tall_style)
    ).generate(nodes, edges)

    assert buildings
    assert all(b.style_name == DEFAULT_BUILDING_STYLE.name for b in buildings)
    assert all(b.height <= 25.0 + 1e-9 for b in buildings)
