"""Unit tests for ActorPlacementGenerator.

Covers correctness of vehicle/pedestrian placement at real spawn zones
(built via the full road/lane/traffic pipeline, as in
test_traffic_network.py): occupancy sampling, vehicle-type sampling from
config.vehicle_mix, heading derivation, overlap rejection, determinism,
and edge cases.
"""

# pylint: disable=duplicate-code
# _edge_heading's hand-built RoadEdge fixtures inevitably resemble
# test_traffic_network.py's own hand-built RoadEdge fixtures -- a shared
# fixture would couple those unrelated test files together for no benefit.

import numpy as np
import pytest

from src.procedural.actor_placement import (
    PEDESTRIAN_KEEP_RIGHT_BIAS_METERS,
    PEDESTRIAN_LATERAL_JITTER_METERS,
    PEDESTRIAN_ROAD_SURFACE_Z_METERS,
    VEHICLE_DIMENSIONS,
    ActorPlacementGenerator,
    Pedestrian,
    Vehicle,
    _aabb_overlap,
    _edge_heading,
    _sample_vehicle_type,
)
from src.procedural.city_sample_assets import (
    PEDESTRIAN_BODY_ASSET_PATHS,
    PEDESTRIAN_BOTTOM_ASSET_PATHS,
    PEDESTRIAN_DIMENSIONS_METERS,
    PEDESTRIAN_FACE_ASSET_PATHS,
    PEDESTRIAN_SHOE_ASSET_PATHS,
    PEDESTRIAN_STANDING_CLIP,
    PEDESTRIAN_TOP_ASSET_PATHS,
    PEDESTRIAN_WALKING_CLIP,
    PEDESTRIAN_WALKING_DYNAMIC_WINDOWS,
    PEDESTRIAN_WALKING_POSE_BIAS_FRACTION,
    VEHICLE_ASSET_PATHS,
    pedestrian_face_and_hair,
)
from src.procedural.lane_topology import LaneTopologyGenerator
from src.procedural.road_edge_kit import SIDEWALK_TOP_HEIGHT_METERS
from src.procedural.road_network import RoadEdge, RoadNetworkGenerator, RoadType
from src.procedural.scenario import ScenarioType, ScenarioTypeConfig
from src.procedural.signal_phasing import (
    PhaseKind,
    approach_direction_from_heading,
    build_signal_plans,
    resolve_active_phases,
)
from src.procedural.traffic_network import SpawnZoneType, TrafficNetwork, TrafficNetworkGenerator

# urban_config, bounds fixtures: see tests/conftest.py


def _generate_full_network(seed: int, config, bounds):
    road_gen = RoadNetworkGenerator(seed, config)
    nodes, edges = road_gen.generate(bounds)
    lanes = LaneTopologyGenerator().generate(nodes, edges)
    traffic = TrafficNetworkGenerator().generate(nodes, edges, lanes)
    return edges, traffic


def _match_vehicle_to_zone(vehicle, driving_zones):
    """The one real DRIVING zone a placed ``vehicle`` came from: either its
    normal flowing position (exact match), or -- when queued at a red
    light -- its own zone's stop_line_position offset back by half the
    vehicle's own real length (see ``_try_place_vehicle``'s docstring for
    why the offset exists: the stop line marks where the front bumper,
    not the center, stops). Returns ``(zone, is_queued)``."""
    heading_vector = np.array([np.cos(vehicle.heading_rad), np.sin(vehicle.heading_rad)])
    for zone in driving_zones:
        if np.allclose(zone.position, vehicle.center):
            return zone, False
        if zone.stop_line_position is not None:
            expected_queued = zone.stop_line_position - heading_vector * (vehicle.length / 2.0)
            if np.allclose(expected_queued, vehicle.center):
                return zone, True
    raise AssertionError(f"vehicle {vehicle.vehicle_id} matches no real DRIVING zone")


def test_vehicles_only_at_driving_zones(urban_config, bounds) -> None:
    """Every placed vehicle's spawn position matches a real DRIVING zone's
    own position -- either its normal flowing-traffic spot, or (when its
    own approach is stopped at the currently-resolved signal phase --
    see signal_phasing.py) its own lane's real stop_line_position (offset
    back by half the vehicle's own length, so its front bumper -- not
    center -- lands there), never an unrelated point."""
    edges, traffic = _generate_full_network(42, urban_config, bounds)
    driving_zones = [z for z in traffic.spawn_zones if z.zone_type == SpawnZoneType.DRIVING]

    vehicles, _ = ActorPlacementGenerator(42, urban_config).generate(edges, traffic)
    assert vehicles  # sanity

    for vehicle in vehicles:
        _match_vehicle_to_zone(vehicle, driving_zones)  # raises if no real zone matches


def test_front_of_queue_vehicle_always_behind_real_stop_line(urban_config, bounds) -> None:
    """The one vehicle at the front of each lane (the zone whose
    ``stop_line_position`` is not ``None``) is ALWAYS placed with its
    front bumper flush with that real stop line, regardless of the
    currently-resolved signal phase -- per explicit request 2026-09-24
    ("all vehicles unless crossing should be behind the crosswalk"): a
    real bug, reported live via screenshot (vehicles from every approach
    simultaneously visible inside the intersection/on the crosswalk),
    traced to the FLOWING case never having been capped by the stop line
    at all, only the stopped case. Fixed by bounding the tiling itself at
    the real stop line for every point (see traffic_network.py's
    ``_generate_driving_zones``), so flowing and stopped vehicles now
    converge on the exact same front-of-queue position -- this test
    checks that convergence directly, independent of phase."""
    edges, traffic = _generate_full_network(42, urban_config, bounds)
    driving_zones = [z for z in traffic.spawn_zones if z.zone_type == SpawnZoneType.DRIVING]
    front_zones = [z for z in driving_zones if z.stop_line_position is not None]
    assert front_zones  # sanity

    vehicles, _ = ActorPlacementGenerator(42, urban_config).generate(edges, traffic)
    assert vehicles  # sanity

    checked_any = False
    for vehicle in vehicles:
        zone, _ = _match_vehicle_to_zone(vehicle, driving_zones)
        if zone.stop_line_position is None:
            continue  # not a front-of-queue vehicle -- unconstrained tiled position
        checked_any = True
        heading_vector = np.array([np.cos(vehicle.heading_rad), np.sin(vehicle.heading_rad)])
        front_bumper = vehicle.center + heading_vector * (vehicle.length / 2.0)
        assert np.allclose(front_bumper, zone.stop_line_position, atol=1e-6)
    assert checked_any  # sanity: at least one placed vehicle is a front-of-queue vehicle


def test_driving_zone_stop_line_equals_its_own_position(urban_config, bounds) -> None:
    """Direct check on the real spawn-zone geometry itself (not on which
    vehicles got placed): every DRIVING zone that carries a
    stop_line_position has that value exactly equal to its own
    ``position`` -- proving the tiling bound (traffic_network.py) and the
    stop-line computation converge on the same real point, so a vehicle's
    normal/flowing placement and its queued placement can never diverge
    into two different spots (one possibly inside the crosswalk)."""
    _, traffic = _generate_full_network(42, urban_config, bounds)
    driving_zones = [z for z in traffic.spawn_zones if z.zone_type == SpawnZoneType.DRIVING]
    front_zones = [z for z in driving_zones if z.stop_line_position is not None]
    assert front_zones  # sanity

    for zone in front_zones:
        assert np.allclose(zone.position, zone.stop_line_position)


def test_crossing_pedestrian_only_placed_when_axis_has_green(  # pylint: disable=too-many-locals
    urban_config, bounds
) -> None:
    """A crossing pedestrian at a signalized intersection is only ever
    placed when the currently-resolved phase for that intersection is a
    real GREEN phase whose moving axis matches the crossing's own
    direction of travel (MUTCD concurrent walk scheme) -- see
    ``_try_place_crossing_pedestrian``'s docstring. Uses full occupancy so
    the phase gate (not the occupancy roll) is what's being exercised."""
    full_config = urban_config.model_copy(update={"traffic_density": (1.0, 1.0)})
    edges, traffic = _generate_full_network(42, full_config, bounds)
    _, pedestrians = ActorPlacementGenerator(42, full_config).generate(edges, traffic)

    replay = ActorPlacementGenerator(42, full_config)
    replay.rng.uniform(*full_config.traffic_density)
    plans = build_signal_plans(edges, traffic)
    active_phases = resolve_active_phases(plans, replay.rng)

    crossing_zones = [z for z in traffic.spawn_zones if z.zone_type == SpawnZoneType.CROSSING]
    crossing_by_position = {tuple(z.position): z for z in crossing_zones}
    crossing_pedestrians = [p for p in pedestrians if tuple(p.center) in crossing_by_position]

    checked_any_signalized = False
    for pedestrian in crossing_pedestrians:
        zone = crossing_by_position[tuple(pedestrian.center)]
        if zone.node_id is None:
            continue
        phase = active_phases.get(zone.node_id)
        if phase is None:
            continue
        checked_any_signalized = True
        assert zone.heading_rad is not None
        axis = approach_direction_from_heading(zone.heading_rad)
        assert phase.kind == PhaseKind.GREEN
        assert axis in phase.moving_approaches
    assert checked_any_signalized  # sanity: this config/seed has a signalized crossing


def test_pedestrians_only_at_pedestrian_or_crossing_zones(urban_config, bounds) -> None:
    """Every placed pedestrian's spawn position is within the real,
    documented lateral jitter distance of a real PEDESTRIAN or CROSSING
    zone -- not an exact match to a PEDESTRIAN zone, since real lateral
    jitter/keep-right bias (see PEDESTRIAN_LATERAL_JITTER_METERS's own
    docstring) now perturbs each sidewalk pedestrian off the zone's own
    exact centerline position (a crossing pedestrian gets no such
    jitter, so its distance to its own CROSSING zone is exactly 0)."""
    edges, traffic = _generate_full_network(42, urban_config, bounds)
    zone_positions = [
        z.position
        for z in traffic.spawn_zones
        if z.zone_type in (SpawnZoneType.PEDESTRIAN, SpawnZoneType.CROSSING)
    ]

    _, pedestrians = ActorPlacementGenerator(42, urban_config).generate(edges, traffic)

    assert pedestrians  # sanity: this config/seed actually places some
    max_offset = PEDESTRIAN_KEEP_RIGHT_BIAS_METERS + PEDESTRIAN_LATERAL_JITTER_METERS
    for pedestrian in pedestrians:
        distances = [
            float(np.linalg.norm(pedestrian.center - zone_position))
            for zone_position in zone_positions
        ]
        assert min(distances) <= max_offset + 1e-6


def test_pedestrian_surface_z_matches_zone_type(urban_config, bounds) -> None:
    """A CROSSING pedestrian's surface_z is the real road surface height
    (PEDESTRIAN_ROAD_SURFACE_Z_METERS, 0.0 -- matching how vehicles are
    placed), never the sidewalk height -- a real bug, live-confirmed
    (crossing pedestrians visibly floating above the road), fixed by
    giving Pedestrian its own surface_z instead of a single hardcoded
    constant applied to every pedestrian regardless of placement. A
    sidewalk pedestrian's surface_z is still the real sidewalk height. A
    crossing pedestrian's own center exactly matches its real CROSSING
    zone position (zero jitter, per this zone type's own placement
    logic), which is what lets this test identify which pedestrians were
    actually placed on the road without needing zone type stored on
    Pedestrian itself."""
    edges, traffic = _generate_full_network(42, urban_config, bounds)
    crossing_positions = [
        tuple(z.position) for z in traffic.spawn_zones if z.zone_type == SpawnZoneType.CROSSING
    ]

    _, pedestrians = ActorPlacementGenerator(42, urban_config).generate(edges, traffic)

    crossing_pedestrians = [p for p in pedestrians if tuple(p.center) in crossing_positions]
    sidewalk_pedestrians = [p for p in pedestrians if tuple(p.center) not in crossing_positions]
    assert crossing_pedestrians  # sanity: this config/seed places at least one
    assert sidewalk_pedestrians  # sanity: this config/seed places at least one

    for pedestrian in crossing_pedestrians:
        assert pedestrian.surface_z == PEDESTRIAN_ROAD_SURFACE_Z_METERS
    for pedestrian in sidewalk_pedestrians:
        assert pedestrian.surface_z == SIDEWALK_TOP_HEIGHT_METERS


def test_pedestrian_body_and_parts_are_consistent(  # pylint: disable=too-many-locals
    urban_config, bounds
) -> None:
    """Every placed pedestrian's asset_path (body) is a real registered
    body for some gender+weight combo, its first 4 part_paths (top/
    bottom/shoe/face) are each real options for that SAME combo (never
    e.g. a male top on a female body), and its width/depth/height match
    that body's own real measured dimensions (PEDESTRIAN_DIMENSIONS_
    METERS, keyed by gender) -- never a mismatch. A 5th part_path
    (hair), when present, is exactly that same sampled face's own real
    paired hairstyle -- never an unrelated character's hair."""
    edges, traffic = _generate_full_network(42, urban_config, bounds)

    _, pedestrians = ActorPlacementGenerator(42, urban_config).generate(edges, traffic)

    assert pedestrians  # sanity: this config/seed actually places some
    body_path_to_combo = {path: combo for combo, path in PEDESTRIAN_BODY_ASSET_PATHS.items()}
    seen_combos = set()
    saw_hair = False
    for pedestrian in pedestrians:
        assert pedestrian.asset_path in body_path_to_combo
        gender, weight = body_path_to_combo[pedestrian.asset_path]
        seen_combos.add((gender, weight))

        assert len(pedestrian.part_paths) in (4, 5)
        top, bottom, shoe, face = pedestrian.part_paths[:4]
        assert top in PEDESTRIAN_TOP_ASSET_PATHS[(gender, weight)]
        assert bottom in PEDESTRIAN_BOTTOM_ASSET_PATHS[(gender, weight)]
        assert shoe in PEDESTRIAN_SHOE_ASSET_PATHS[(gender, weight)]
        assert face in PEDESTRIAN_FACE_ASSET_PATHS[gender]

        expected_hair = pedestrian_face_and_hair(gender, face)
        if expected_hair is None:
            assert len(pedestrian.part_paths) == 4
        else:
            assert pedestrian.part_paths[4] == expected_hair
            saw_hair = True

        assert (
            pedestrian.width,
            pedestrian.depth,
            pedestrian.height,
        ) == PEDESTRIAN_DIMENSIONS_METERS[gender]
    assert len(seen_combos) > 1  # sanity: this config/seed covers more than one combo
    assert saw_hair  # sanity: this config/seed places at least one real hairstyle


def test_pedestrian_pose_frame_is_real_and_diverse(urban_config, bounds) -> None:
    """Every placed pedestrian's pose_frame falls inside one of the two
    real baked clips (PEDESTRIAN_WALKING_CLIP or PEDESTRIAN_STANDING_CLIP
    -- see PEDESTRIAN_ANIM_CLIPS' own docstring for the evidence they're
    real, distinct clips), and this config/seed places more than one
    distinct frame -- proving pose sampling is real and active, not a
    constant default (the exact bug this feature fixes: every pedestrian
    previously rendered the same frozen default pose)."""
    edges, traffic = _generate_full_network(42, urban_config, bounds)

    _, pedestrians = ActorPlacementGenerator(42, urban_config).generate(edges, traffic)

    assert pedestrians  # sanity: this config/seed actually places some
    seen_frames = set()
    for pedestrian in pedestrians:
        in_walking_clip = (
            PEDESTRIAN_WALKING_CLIP[0] <= pedestrian.pose_frame <= PEDESTRIAN_WALKING_CLIP[1]
        )
        in_standing_clip = (
            PEDESTRIAN_STANDING_CLIP[0] <= pedestrian.pose_frame <= PEDESTRIAN_STANDING_CLIP[1]
        )
        assert in_walking_clip or in_standing_clip
        seen_frames.add(pedestrian.pose_frame)
    assert len(seen_frames) > 1  # sanity: real diversity, not one constant frame


def test_crossing_pedestrians_are_always_walking(urban_config, bounds) -> None:
    """A CROSSING pedestrian's pose_frame is always inside
    PEDESTRIAN_WALKING_CLIP, never PEDESTRIAN_STANDING_CLIP -- a
    pedestrian actively crossing a road is definitionally walking, so
    ``_try_place_crossing_pedestrian`` always passes
    ``allow_standing=False``. Identifies crossing pedestrians the same
    way ``test_pedestrian_surface_z_matches_zone_type`` does: by exact
    center match to a real CROSSING zone position (zero jitter, per that
    zone type's own placement logic)."""
    edges, traffic = _generate_full_network(42, urban_config, bounds)
    crossing_positions = [
        tuple(z.position) for z in traffic.spawn_zones if z.zone_type == SpawnZoneType.CROSSING
    ]

    _, pedestrians = ActorPlacementGenerator(42, urban_config).generate(edges, traffic)

    crossing_pedestrians = [p for p in pedestrians if tuple(p.center) in crossing_positions]
    assert crossing_pedestrians  # sanity: this config/seed places at least one

    for pedestrian in crossing_pedestrians:
        assert PEDESTRIAN_WALKING_CLIP[0] <= pedestrian.pose_frame <= PEDESTRIAN_WALKING_CLIP[1]


def test_sidewalk_pedestrians_include_both_activities() -> None:
    """Sidewalk pedestrians show a real mix of both activities -- at
    least one walking, at least one standing -- proving
    PEDESTRIAN_STANDING_ACTIVITY_FRACTION is genuinely sometimes
    triggered, not a dead code path. Uses a wider config/seed than the
    other tests in this file (0.2 probability needs a large enough
    sidewalk-pedestrian sample to reliably include both outcomes)."""
    config = ScenarioTypeConfig(
        scenario_type=ScenarioType.URBAN_DENSE,
        avg_block_size=(100.0, 150.0),
        avg_road_width=12.0,
        num_intersections=(3, 6),
        intersection_types=["4way", "3way"],
        building_density=0.6,
        building_heights=(20.0, 40.0),
        traffic_density=(0.6, 1.0),
        vehicle_mix={"sedan": 0.6, "suv": 0.25, "truck": 0.1, "bus": 0.05},
        complexity_score=60,
    )
    wide_bounds = (-200.0, -200.0, 200.0, 200.0)
    edges, traffic = _generate_full_network(7, config, wide_bounds)
    crossing_positions = [
        tuple(z.position) for z in traffic.spawn_zones if z.zone_type == SpawnZoneType.CROSSING
    ]

    _, pedestrians = ActorPlacementGenerator(7, config).generate(edges, traffic)
    sidewalk_pedestrians = [p for p in pedestrians if tuple(p.center) not in crossing_positions]

    saw_walking = any(
        PEDESTRIAN_WALKING_CLIP[0] <= p.pose_frame <= PEDESTRIAN_WALKING_CLIP[1]
        for p in sidewalk_pedestrians
    )
    saw_standing = any(
        PEDESTRIAN_STANDING_CLIP[0] <= p.pose_frame <= PEDESTRIAN_STANDING_CLIP[1]
        for p in sidewalk_pedestrians
    )
    assert saw_walking
    assert saw_standing


def test_walking_pose_frame_is_biased_toward_confirmed_dynamic_windows() -> None:
    """Most walking pedestrians land in one of the two confirmed-dynamic
    sub-windows (PEDESTRIAN_WALKING_DYNAMIC_WINDOWS), per
    PEDESTRIAN_WALKING_POSE_BIAS_FRACTION -- real, evidence-backed
    per-frame verdicts (live side-profile screenshots), not a guess.
    Checks the ACTUAL fraction lands close to the configured bias rather
    than just "at least one", since a bias that silently didn't apply
    would still pass a weaker assertion."""
    config = ScenarioTypeConfig(
        scenario_type=ScenarioType.URBAN_DENSE,
        avg_block_size=(100.0, 150.0),
        avg_road_width=12.0,
        num_intersections=(3, 6),
        intersection_types=["4way", "3way"],
        building_density=0.6,
        building_heights=(20.0, 40.0),
        traffic_density=(0.6, 1.0),
        vehicle_mix={"sedan": 0.6, "suv": 0.25, "truck": 0.1, "bus": 0.05},
        complexity_score=60,
    )
    wide_bounds = (-200.0, -200.0, 200.0, 200.0)
    edges, traffic = _generate_full_network(7, config, wide_bounds)

    _, pedestrians = ActorPlacementGenerator(7, config).generate(edges, traffic)
    walking_pedestrians = [
        p
        for p in pedestrians
        if PEDESTRIAN_WALKING_CLIP[0] <= p.pose_frame <= PEDESTRIAN_WALKING_CLIP[1]
    ]
    assert len(walking_pedestrians) > 20  # sanity: a large enough sample to check a fraction

    in_dynamic_window = sum(
        1
        for p in walking_pedestrians
        if any(start <= p.pose_frame <= end for start, end in PEDESTRIAN_WALKING_DYNAMIC_WINDOWS)
    )
    observed_fraction = in_dynamic_window / len(walking_pedestrians)
    assert observed_fraction == pytest.approx(PEDESTRIAN_WALKING_POSE_BIAS_FRACTION, abs=0.1)


def test_pedestrian_pose_frame_avoids_immediate_repeat(urban_config, bounds) -> None:
    """No two consecutively-placed pedestrians share the exact same
    pose_frame -- a real, live-confirmed issue with a single narrow
    window (only ~26 distinct values for 40+ instances meant frequent
    exact duplicates among spatially adjacent pedestrians, reading as
    visually identical clones) that ``_sample_pose_frame``'s one-retry
    guard specifically targets. This checks pedestrians in PLACEMENT
    order (the order most likely to reflect real spatial adjacency,
    since pedestrians are placed walking along the same real zones),
    not sorted by position."""
    edges, traffic = _generate_full_network(42, urban_config, bounds)

    _, pedestrians = ActorPlacementGenerator(42, urban_config).generate(edges, traffic)

    assert len(pedestrians) > 1  # sanity: this config/seed places more than one
    for previous, current in zip(pedestrians, pedestrians[1:]):
        assert previous.pose_frame != current.pose_frame


def test_vehicle_types_are_from_vehicle_mix(urban_config, bounds) -> None:
    """Every placed vehicle's type is one of config.vehicle_mix's keys."""
    edges, traffic = _generate_full_network(42, urban_config, bounds)

    vehicles, _ = ActorPlacementGenerator(42, urban_config).generate(edges, traffic)

    assert vehicles  # sanity: this config/seed actually places some
    for vehicle in vehicles:
        assert vehicle.vehicle_type in urban_config.vehicle_mix
        assert (vehicle.length, vehicle.width, vehicle.height) == VEHICLE_DIMENSIONS[
            vehicle.vehicle_type
        ]


def test_vehicle_asset_path_matches_its_own_vehicle_type(urban_config, bounds) -> None:
    """Every placed vehicle's asset_path is one of the real City Sample
    paths registered for its own vehicle_type -- never a mismatch (e.g.
    a "sedan" vehicle_type resolving to a "bus" asset)."""
    edges, traffic = _generate_full_network(42, urban_config, bounds)

    vehicles, _ = ActorPlacementGenerator(42, urban_config).generate(edges, traffic)

    assert vehicles  # sanity: this config/seed actually places some
    for vehicle in vehicles:
        assert vehicle.asset_path in VEHICLE_ASSET_PATHS[vehicle.vehicle_type]


def test_vehicle_asset_path_deterministic_across_runs(urban_config, bounds) -> None:
    """Same seed gives the same asset_path per vehicle, not just the
    same vehicle_type -- the asset sampling step is deterministic too."""
    edges1, traffic1 = _generate_full_network(42, urban_config, bounds)
    edges2, traffic2 = _generate_full_network(42, urban_config, bounds)

    vehicles1, _ = ActorPlacementGenerator(42, urban_config).generate(edges1, traffic1)
    vehicles2, _ = ActorPlacementGenerator(42, urban_config).generate(edges2, traffic2)

    assert [v.asset_path for v in vehicles1] == [v.asset_path for v in vehicles2]


def test_vehicle_ids_unique(urban_config, bounds) -> None:
    """No two placed vehicles share a vehicle_id."""
    edges, traffic = _generate_full_network(42, urban_config, bounds)
    vehicles, _ = ActorPlacementGenerator(42, urban_config).generate(edges, traffic)

    ids = [v.vehicle_id for v in vehicles]
    assert len(ids) == len(set(ids))


def test_pedestrian_ids_unique(urban_config, bounds) -> None:
    """No two placed pedestrians share a pedestrian_id."""
    edges, traffic = _generate_full_network(42, urban_config, bounds)
    _, pedestrians = ActorPlacementGenerator(42, urban_config).generate(edges, traffic)

    ids = [p.pedestrian_id for p in pedestrians]
    assert len(ids) == len(set(ids))


def test_no_two_vehicles_overlap(urban_config, bounds) -> None:
    """Placed vehicles' rotated-footprint AABBs never overlap each other."""
    edges, traffic = _generate_full_network(42, urban_config, bounds)
    vehicles, _ = ActorPlacementGenerator(42, urban_config).generate(edges, traffic)

    for i, a in enumerate(vehicles):
        for b in vehicles[i + 1 :]:
            assert not _aabb_overlap(a.aabb, b.aabb)


def test_pedestrian_count_roughly_matches_reduced_density(urban_config, bounds) -> None:
    """Pedestrian placement rate is well below vehicle placement rate,
    consistent with PEDESTRIAN_DENSITY_FRACTION_OF_TRAFFIC < 1."""
    edges, traffic = _generate_full_network(42, urban_config, bounds)
    driving_zones = sum(1 for z in traffic.spawn_zones if z.zone_type == SpawnZoneType.DRIVING)
    pedestrian_zones = sum(
        1 for z in traffic.spawn_zones if z.zone_type == SpawnZoneType.PEDESTRIAN
    )

    vehicles, pedestrians = ActorPlacementGenerator(42, urban_config).generate(edges, traffic)

    vehicle_rate = len(vehicles) / driving_zones
    pedestrian_rate = len(pedestrians) / pedestrian_zones
    assert pedestrian_rate < vehicle_rate


def test_headings_are_finite(urban_config, bounds) -> None:
    """Every placed actor's heading is a finite float."""
    edges, traffic = _generate_full_network(42, urban_config, bounds)
    vehicles, pedestrians = ActorPlacementGenerator(42, urban_config).generate(edges, traffic)

    for vehicle in vehicles:
        assert np.isfinite(vehicle.heading_rad)
    for pedestrian in pedestrians:
        assert np.isfinite(pedestrian.heading_rad)


def test_positions_finite(urban_config, bounds) -> None:
    """Every placed actor's center is finite (no NaN/Inf)."""
    edges, traffic = _generate_full_network(42, urban_config, bounds)
    vehicles, pedestrians = ActorPlacementGenerator(42, urban_config).generate(edges, traffic)

    for vehicle in vehicles:
        assert np.isfinite(vehicle.center).all()
    for pedestrian in pedestrians:
        assert np.isfinite(pedestrian.center).all()


@pytest.mark.parametrize("seed", [0, 1, 99])
def test_determinism_across_seeds(urban_config, bounds, seed) -> None:
    """Same seed produces identical vehicle/pedestrian placement."""
    edges, traffic = _generate_full_network(seed, urban_config, bounds)

    vehicles1, pedestrians1 = ActorPlacementGenerator(seed, urban_config).generate(edges, traffic)
    vehicles2, pedestrians2 = ActorPlacementGenerator(seed, urban_config).generate(edges, traffic)

    assert len(vehicles1) == len(vehicles2)
    for a, b in zip(vehicles1, vehicles2):
        assert a.vehicle_id == b.vehicle_id
        assert a.vehicle_type == b.vehicle_type
        assert np.array_equal(a.center, b.center)
        assert a.heading_rad == b.heading_rad

    assert len(pedestrians1) == len(pedestrians2)
    for a, b in zip(pedestrians1, pedestrians2):
        assert a.pedestrian_id == b.pedestrian_id
        assert np.array_equal(a.center, b.center)


def test_no_spawn_zones_yields_no_actors(urban_config) -> None:
    """An empty traffic network produces no vehicles or pedestrians."""
    empty_traffic = TrafficNetwork(traffic_controls={}, spawn_zones=[], navigation_graph=None)

    vehicles, pedestrians = ActorPlacementGenerator(42, urban_config).generate({}, empty_traffic)

    assert not vehicles
    assert not pedestrians


def test_zero_occupancy_places_nothing(urban_config, bounds) -> None:
    """A config whose traffic_density is fixed at 0.0 places no actors."""
    zero_density_config = urban_config.model_copy(update={"traffic_density": (0.0, 0.0)})
    edges, traffic = _generate_full_network(42, zero_density_config, bounds)

    vehicles, pedestrians = ActorPlacementGenerator(42, zero_density_config).generate(
        edges, traffic
    )

    assert not vehicles
    assert not pedestrians


def test_full_occupancy_places_at_every_driving_zone_unless_overlapping(
    urban_config, bounds
) -> None:
    """With traffic_density fixed at 1.0, every driving zone either gets a
    vehicle or is rejected purely for overlapping an already-placed one."""
    full_density_config = urban_config.model_copy(update={"traffic_density": (1.0, 1.0)})
    edges, traffic = _generate_full_network(42, full_density_config, bounds)
    driving_zones = [z for z in traffic.spawn_zones if z.zone_type == SpawnZoneType.DRIVING]

    vehicles, _ = ActorPlacementGenerator(42, full_density_config).generate(edges, traffic)

    assert len(vehicles) <= len(driving_zones)
    assert len(vehicles) > 0


def test_edge_heading_matches_direction() -> None:
    """_edge_heading returns atan2 of the edge's start->end direction."""
    edge = RoadEdge(
        edge_id=0,
        start_node_id=0,
        end_node_id=1,
        road_type=RoadType.MAJOR,
        centerline=np.array([[0.0, 0.0], [10.0, 10.0]]),
        length=14.14,
        num_lanes=2,
        speed_limit_kmh=50,
        width_meters=10.0,
    )
    assert _edge_heading(edge) == pytest.approx(np.pi / 4)


def test_edge_heading_horizontal() -> None:
    """A purely horizontal edge has heading 0."""
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
    assert _edge_heading(edge) == pytest.approx(0.0)


def test_sample_vehicle_type_respects_mix_keys() -> None:
    """Sampled type is always a key of the given vehicle_mix."""
    rng = np.random.Generator(np.random.PCG64(0))
    mix = {"sedan": 0.6, "suv": 0.25, "truck": 0.1, "bus": 0.05}
    for _ in range(50):
        assert _sample_vehicle_type(rng, mix) in mix


def test_sample_vehicle_type_single_option() -> None:
    """A single-entry mix always samples that one type."""
    rng = np.random.Generator(np.random.PCG64(0))
    assert _sample_vehicle_type(rng, {"bus": 1.0}) == "bus"


def test_aabb_overlap_detects_overlap() -> None:
    """Two genuinely overlapping boxes are detected as overlapping."""
    assert _aabb_overlap((0.0, 0.0, 2.0, 2.0), (1.0, 1.0, 3.0, 3.0))


def test_aabb_overlap_detects_no_overlap() -> None:
    """Two disjoint boxes are not detected as overlapping."""
    assert not _aabb_overlap((0.0, 0.0, 1.0, 1.0), (2.0, 2.0, 3.0, 3.0))


def test_aabb_overlap_touching_edges_not_overlapping() -> None:
    """Boxes that merely touch at an edge (no interior intersection) don't
    count as overlapping -- strict inequality, matching the same
    convention used elsewhere in this codebase for AABB overlap tests."""
    assert not _aabb_overlap((0.0, 0.0, 1.0, 1.0), (1.0, 0.0, 2.0, 1.0))


def test_vehicle_aabb_axis_aligned_matches_half_extents() -> None:
    """A heading=0 vehicle's aabb is exactly its length/width extents."""
    vehicle = Vehicle(
        vehicle_id=0,
        vehicle_type="sedan",
        asset_path="/Game/Vehicle/vehCar_vehicle02/BP_vehCar_vehicle02_Sandbox",
        center=np.array([10.0, 20.0]),
        heading_rad=0.0,
        length=4.6,
        width=1.8,
        height=1.5,
    )
    x_min, y_min, x_max, y_max = vehicle.aabb
    assert x_min == pytest.approx(10.0 - 2.3)
    assert x_max == pytest.approx(10.0 + 2.3)
    assert y_min == pytest.approx(20.0 - 0.9)
    assert y_max == pytest.approx(20.0 + 0.9)


def test_vehicle_aabb_rotated_swaps_extents() -> None:
    """A heading=pi/2 vehicle's aabb has length/width extents swapped
    relative to heading=0 (rotated 90 degrees)."""
    vehicle = Vehicle(
        vehicle_id=0,
        vehicle_type="sedan",
        asset_path="/Game/Vehicle/vehCar_vehicle02/BP_vehCar_vehicle02_Sandbox",
        center=np.array([0.0, 0.0]),
        heading_rad=np.pi / 2,
        length=4.6,
        width=1.8,
        height=1.5,
    )
    x_min, y_min, x_max, y_max = vehicle.aabb
    assert (x_max - x_min) == pytest.approx(1.8, abs=1e-9)
    assert (y_max - y_min) == pytest.approx(4.6, abs=1e-9)


def test_pedestrian_default_dimensions() -> None:
    """A Pedestrian built without explicit dimensions gets the module's
    default width/depth/height constants."""
    pedestrian = Pedestrian(
        pedestrian_id=0,
        center=np.array([0.0, 0.0]),
        heading_rad=0.0,
        asset_path=PEDESTRIAN_BODY_ASSET_PATHS[("f", "nrw")],
        part_paths=[],
        pose_frame=0.0,
        surface_z=0.108,
    )
    assert pedestrian.width == 0.33
    assert pedestrian.depth == 0.96
    assert pedestrian.height == 1.68
