"""Procedural vehicle and pedestrian placement at traffic spawn zones.

Not a bullet in any phase of MASTER_PROMPT_PROCEDURAL_AV_DATASET_GENERATOR.md's
own 8-phase roadmap -- the master prompt never specifies vehicle/pedestrian
placement anywhere, despite ``ScenarioTypeConfig.vehicle_mix`` existing
since Phase 1 and ``TrafficNetworkGenerator`` producing driving/pedestrian
``SpawnZone`` objects since Phase 3, both unused for their obvious purpose
until now (see KNOWN_GAPS_AND_ISSUES.md's "Ground truth extraction only
covers buildings" entry, which this module closes). Built with the same
rigor as every phase: real algorithm, real tests, no shortcuts.

Placement anchors: ``TrafficNetworkGenerator`` already places exactly one
``DRIVING`` spawn zone per lane (at the lane's start) and one
``PEDESTRIAN`` spawn zone per edge (offset onto its sidewalk) -- see
``traffic_network.py``. This module decides, for each spawn zone,
whether an actor occupies it and (for driving zones) which vehicle type,
sampled from ``config.vehicle_mix``.

Orientation is tracked (``heading_rad``, derived from the spawn zone's
own road edge direction) but ground-truth 3D boxes are otherwise
axis-aligned-box-shaped with a heading applied about their center --
see :class:`src.ground_truth.bbox_3d.BoundingBox3D`'s ``heading_rad``
field, added specifically to carry this.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import numpy.typing as npt

from src.procedural.city_sample_assets import (
    PEDESTRIAN_BODY_ASSET_PATHS,
    PEDESTRIAN_BOTTOM_ASSET_PATHS,
    PEDESTRIAN_DIMENSIONS_METERS,
    PEDESTRIAN_FACE_ASSET_PATHS,
    PEDESTRIAN_SHOE_ASSET_PATHS,
    PEDESTRIAN_STANDING_ACTIVITY_FRACTION,
    PEDESTRIAN_STANDING_CLIP,
    PEDESTRIAN_TOP_ASSET_PATHS,
    PEDESTRIAN_WALKING_CLIP,
    PEDESTRIAN_WALKING_DYNAMIC_WINDOWS,
    PEDESTRIAN_WALKING_POSE_BIAS_FRACTION,
    VEHICLE_ASSET_PATHS,
    pedestrian_face_and_hair,
)
from src.procedural.math_utils import compute_perpendicular
from src.procedural.road_edge_kit import SIDEWALK_TOP_HEIGHT_METERS
from src.procedural.road_network import RoadEdge
from src.procedural.scenario import ScenarioTypeConfig
from src.procedural.signal_phasing import (
    PhaseKind,
    SignalPhase,
    approach_direction_from_heading,
    build_signal_plans,
    classify_approach_direction,
    resolve_active_phases,
)
from src.procedural.traffic_network import SpawnZone, SpawnZoneType, TrafficNetwork

# The real road surface height -- matching the convention
# ``_vehicle_to_asset_json`` already uses (vehicles sit at z=0.0, "the
# flat road surface"). A CROSSING pedestrian stands on this same road
# surface, not the sidewalk -- see ``Pedestrian.surface_z``'s own
# docstring for the real bug this constant fixes (crossing pedestrians
# rendering at sidewalk height, visibly floating above the road).
PEDESTRIAN_ROAD_SURFACE_Z_METERS = 0.0

# (length, width, height) in meters, approximate real-world dimensions.
# Keys must match ScenarioTypeConfig.vehicle_mix's own keys exactly (see
# scenario.py and every scenario_templates/*.yaml's vehicle_mix block).
VEHICLE_DIMENSIONS: Dict[str, Tuple[float, float, float]] = {
    "sedan": (4.6, 1.8, 1.5),
    "suv": (4.8, 1.9, 1.7),
    "truck": (7.0, 2.3, 2.8),
    "bus": (12.0, 2.5, 3.2),
}

# Real measured bounds of the female VAT pedestrian mesh, via
# GetStaticMeshBounds against a live UE5 instance -- not a guess (the
# earlier 0.5/0.5/1.7 placeholder was). Used only as this dataclass's
# default field values (e.g. for tests that don't specify explicit
# dims); real placement always looks up PEDESTRIAN_DIMENSIONS_METERS by
# the pedestrian's own sampled gender instead. See
# city_sample_assets.py's PEDESTRIAN_DIMENSIONS_METERS docstring.
PEDESTRIAN_WIDTH_METERS = 0.33
PEDESTRIAN_DEPTH_METERS = 0.96
PEDESTRIAN_HEIGHT_METERS = 1.68

# Real gender/weight-class distribution -- not weighted, since no real
# City Sample or demographic data was found to weight one over another;
# an even split across genders and weight classes is the honest default
# absent that evidence (documented here, not silently assumed).
_PEDESTRIAN_GENDERS = ("f", "m")
_PEDESTRIAN_WEIGHTS = ("nrw", "ovw", "unw")

# Real ADA/PROWAG-consistent pedestrian shy distance from a sidewalk's
# own edges (curb line and building line): pedestrian planning
# literature (Fruin -- the same body of work already used elsewhere in
# this project for crosswalk sizing) commonly cites ~0.45-0.6m as the
# minimum clearance a person keeps from a vertical obstruction. The real
# sidewalk is SIDEWALK_WIDTH_METERS=3.0m wide (lane_topology.py),
# centered on SIDEWALK_OFFSET_METERS=1.5m (traffic_network.py); a 1.0m
# max jitter each way keeps every pedestrian at least 0.5m clear of both
# edges, matching that real figure, instead of every pedestrian standing
# at the exact same centerline (a real, reported "tightrope" look).
PEDESTRIAN_LATERAL_JITTER_METERS = 1.0

# Real, published mechanism (social-force/keep-right pedestrian
# dynamics literature -- see KNOWN_GAPS_AND_ISSUES.md for the research)
# for why real two-way foot traffic doesn't collide head-on: each
# pedestrian keeps to one side of the walkway depending on their own
# direction of travel. This project has no true multi-agent simulation
# (a frozen single-frame renderer, not a running one), so this is a
# statistical PLACEMENT bias, not simulated collision avoidance: each
# pedestrian's own real right-hand side (``compute_perpendicular`` of
# their own chosen walking direction, already this project's documented
# real right-hand convention) gets a consistent small offset, the same
# real emergent effect (opposite-direction foot traffic visually
# separating into two lanes) without simulating any actual interaction.
PEDESTRIAN_KEEP_RIGHT_BIAS_METERS = 0.4

# ScenarioTypeConfig has no pedestrian-density field (only
# traffic_density, for vehicles); a fixed fraction of traffic_density is
# used as a documented, deliberate approximation rather than inventing a
# new config field for one module. See KNOWN_GAPS_AND_ISSUES.md.
PEDESTRIAN_DENSITY_FRACTION_OF_TRAFFIC = 0.3

# Real, disclosed simplification: crossing a road is a brief transient
# event (a real crosswalk holds someone for the ~10-15 seconds it takes
# to walk it) compared to standing/walking a full sidewalk block, which
# a frozen single-frame scenario should reflect with a LOWER independent
# occupancy fraction than PEDESTRIAN_DENSITY_FRACTION_OF_TRAFFIC above --
# no real City Sample or demographic data was found for the exact real
# ratio between the two, so this is a deliberately conservative,
# disclosed guess at the right order of magnitude, not a precisely
# sourced figure like PEDESTRIAN_SPAWN_GAP_METERS is.
PEDESTRIAN_CROSSING_DENSITY_FRACTION_OF_TRAFFIC = 0.1


@dataclass(eq=False)
class Vehicle:  # pylint: disable=too-many-instance-attributes
    """A single procedurally placed vehicle.

    ``asset_path`` is a real City Sample vehicle static body-shell mesh
    path (see ``city_sample_assets.py``), sampled deterministically alongside
    ``vehicle_type``. ``length``/``width``/``height`` remain the
    placement-time computed box dimensions -- kept as the ground-truth
    bounding box for now (not the real spawned asset's own bounds; see
    KNOWN_GAPS_AND_ISSUES.md's bbox-precision decision), and still used
    for the AABB overlap pre-check below regardless of which asset ends
    up spawned.
    """

    vehicle_id: int
    vehicle_type: str
    asset_path: str
    center: npt.NDArray[np.float64]
    heading_rad: float
    length: float
    width: float
    height: float

    @property
    def aabb(self) -> Tuple[float, float, float, float]:
        """Axis-aligned bounding box of the *rotated* footprint --
        conservative (never smaller than the true rotated rectangle),
        used only for cheap overlap pre-checks between vehicles."""
        cos_h, sin_h = abs(np.cos(self.heading_rad)), abs(np.sin(self.heading_rad))
        half_extent_x = (self.length * cos_h + self.width * sin_h) / 2.0
        half_extent_y = (self.length * sin_h + self.width * cos_h) / 2.0
        x, y = self.center
        return (x - half_extent_x, y - half_extent_y, x + half_extent_x, y + half_extent_y)


@dataclass(eq=False)
class Pedestrian:  # pylint: disable=too-many-instance-attributes
    """A single procedurally placed pedestrian.

    ``asset_path`` is the real City Sample VAT bare-body static mesh for
    this pedestrian's own sampled gender+weight (see
    ``city_sample_assets.py``'s ``PEDESTRIAN_BODY_ASSET_PATHS``).
    ``part_paths`` is a real, independently-sampled top/bottom/shoe/face
    combination for that same gender+weight, spawned as sibling static
    mesh components at zero relative offset -- confirmed live to
    assemble correctly, the same mechanism ``VEHICLE_PART_PATHS`` already
    uses for wheels/doors (see that module's own docstring for the full
    real-asset investigation). ``pose_frame`` is a real, independently
    sampled baked-animation frame index (see
    ``city_sample_assets.py``'s ``PEDESTRIAN_WALKING_CLIP``/
    ``PEDESTRIAN_STANDING_CLIP``) applied as a material scalar override
    to the body AND every part, freezing this
    pedestrian at one specific, real, distinct static pose instead of
    every pedestrian sharing the exact same default frame.

    ``surface_z`` is the real world-space height this pedestrian's feet
    stand on: ``SIDEWALK_TOP_HEIGHT_METERS`` for a sidewalk walker, or
    ``PEDESTRIAN_ROAD_SURFACE_Z_METERS`` (0.0, matching how vehicles are
    placed) for a CROSSING pedestrian actually standing on the road at a
    crosswalk. A real bug, live-confirmed (2026-09-23): before this
    field existed, every pedestrian serialized at the sidewalk height
    unconditionally, so crossing pedestrians rendered visibly floating
    above the road surface.
    """

    pedestrian_id: int
    center: npt.NDArray[np.float64]
    heading_rad: float
    asset_path: str
    part_paths: List[str]
    pose_frame: float
    surface_z: float
    width: float = PEDESTRIAN_WIDTH_METERS
    depth: float = PEDESTRIAN_DEPTH_METERS
    height: float = PEDESTRIAN_HEIGHT_METERS


def _aabb_overlap(
    a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]
) -> bool:
    """True if two (x_min, y_min, x_max, y_max) boxes overlap."""
    a_x_min, a_y_min, a_x_max, a_y_max = a
    b_x_min, b_y_min, b_x_max, b_y_max = b
    return a_x_min < b_x_max and a_x_max > b_x_min and a_y_min < b_y_max and a_y_max > b_y_min


def _edge_heading(edge: RoadEdge) -> float:
    """Heading (radians, standard math convention) of a road edge's
    direction of travel."""
    direction = edge.centerline[-1] - edge.centerline[0]
    return float(np.arctan2(direction[1], direction[0]))


def _sample_vehicle_type(rng: np.random.Generator, vehicle_mix: Dict[str, float]) -> str:
    """Sample a vehicle type name from ``vehicle_mix``'s weighted
    distribution."""
    types = list(vehicle_mix.keys())
    weights = np.array([vehicle_mix[t] for t in types])
    weights = weights / weights.sum()  # renormalize: mix sums to ~1.0, not exactly
    return str(rng.choice(types, p=weights))


def _sample_asset_path(rng: np.random.Generator, vehicle_type: str) -> str:
    """Sample one real City Sample asset path for ``vehicle_type``,
    uniformly from ``VEHICLE_ASSET_PATHS[vehicle_type]`` -- deterministic
    given the same ``rng`` state, same as every other sampling step in
    this module."""
    paths = VEHICLE_ASSET_PATHS[vehicle_type]
    index = int(rng.integers(0, len(paths)))
    return paths[index]


class ActorPlacementGenerator:  # pylint: disable=too-few-public-methods
    """Place vehicles and pedestrians at a traffic network's spawn zones.

    Exposes a single public entry point (``generate``) by design; the
    rest of the class is private implementation detail of that operation.
    """

    def __init__(self, seed: int, config: ScenarioTypeConfig) -> None:
        self.seed = seed
        self.config = config
        self.rng = np.random.Generator(np.random.PCG64(seed))
        self._vehicle_counter = 0
        self._pedestrian_counter = 0
        self._last_pose_frame: Optional[float] = None

    def generate(
        self, edges: Dict[int, RoadEdge], traffic: TrafficNetwork
    ) -> Tuple[List[Vehicle], List[Pedestrian]]:
        """Place vehicles at a fraction of driving spawn zones and
        pedestrians at a fraction of pedestrian spawn zones, both
        consistent with one real, randomly-resolved instant in every
        signalized intersection's own real signal cycle (see
        ``signal_phasing.py``): a vehicle whose approach doesn't have the
        right of way at that instant is queued at its lane's real stop
        line instead of shown flowing, and a crossing pedestrian is only
        ever placed when their own crossing direction has the concurrent
        green (MUTCD's standard concurrent walk scheme) -- both derived
        from the exact same resolved phase per intersection, so vehicles,
        pedestrians, and (should traffic-light visual state ever be added)
        signal indications all agree with each other.

        Parameters
        ----------
        edges : Dict[int, RoadEdge]
            The road network's directed edges (used to derive each spawn
            zone's heading from its own edge's direction, and each
            driving zone's own approach direction).
        traffic : TrafficNetwork
            Provides the spawn zones to place actors at.

        Returns
        -------
        Tuple[List[Vehicle], List[Pedestrian]]
        """
        occupancy = self.rng.uniform(*self.config.traffic_density)

        signal_plans = build_signal_plans(edges, traffic)
        active_phases = resolve_active_phases(signal_plans, self.rng)

        vehicles: List[Vehicle] = []
        placed_vehicle_aabbs: List[Tuple[float, float, float, float]] = []
        pedestrians: List[Pedestrian] = []

        for zone in traffic.spawn_zones:
            if zone.zone_type == SpawnZoneType.DRIVING:
                vehicle = self._try_place_vehicle(
                    zone, edges, occupancy, placed_vehicle_aabbs, active_phases
                )
                if vehicle is not None:
                    vehicles.append(vehicle)
                    placed_vehicle_aabbs.append(vehicle.aabb)
            elif zone.zone_type == SpawnZoneType.PEDESTRIAN:
                pedestrian = self._try_place_sidewalk_pedestrian(zone, edges, occupancy)
                if pedestrian is not None:
                    pedestrians.append(pedestrian)
            elif zone.zone_type == SpawnZoneType.CROSSING:
                pedestrian = self._try_place_crossing_pedestrian(zone, occupancy, active_phases)
                if pedestrian is not None:
                    pedestrians.append(pedestrian)

        return vehicles, pedestrians

    @staticmethod
    def _vehicle_is_flowing(
        edge: RoadEdge, node_id: int, active_phases: Dict[int, SignalPhase]
    ) -> bool:
        """Whether a vehicle following ``edge`` toward ``node_id`` has the
        right of way at the currently-resolved instant. A node absent from
        ``active_phases`` (T-junction/stop-sign/uncontrolled -- see
        ``signal_phasing.py``'s scope note) always flows: this project
        doesn't model stop-sign right-of-way, only signalized
        intersections. At a signalized node, a vehicle flows only during
        its own axis's real ``GREEN`` phase -- yellow and all-red both
        mean "do not newly proceed" for placement purposes (this is a
        single-frame snapshot, not a simulation of vehicles already
        mid-intersection when the light changed)."""
        phase = active_phases.get(node_id)
        if phase is None:
            return True
        return phase.kind == PhaseKind.GREEN and classify_approach_direction(edge) in (
            phase.moving_approaches
        )

    def _try_place_vehicle(  # pylint: disable=too-many-arguments,too-many-locals
        self,
        zone: SpawnZone,
        edges: Dict[int, RoadEdge],
        occupancy: float,
        placed_vehicle_aabbs: List[Tuple[float, float, float, float]],
        active_phases: Dict[int, SignalPhase],
    ) -> Optional[Vehicle]:
        if self.rng.random() > occupancy:
            return None
        assert zone.edge_id is not None  # every DRIVING zone carries one

        edge = edges[zone.edge_id]
        vehicle_type = _sample_vehicle_type(self.rng, self.config.vehicle_mix)
        asset_path = _sample_asset_path(self.rng, vehicle_type)
        length, width, height = VEHICLE_DIMENSIONS[vehicle_type]
        heading = _edge_heading(edge)

        position = zone.position
        # Only the one lane-end zone closest to a signalized intersection
        # carries a real stop_line_position (see SpawnZone's own
        # docstring) -- earlier zones further back on the same lane keep
        # their normal tiled position regardless of phase (this pipeline
        # is a frozen snapshot, not a queue simulation; see
        # traffic_network.py's own docstring for why only the front
        # vehicle is precisely positioned).
        if zone.stop_line_position is not None and not self._vehicle_is_flowing(
            edge, edge.end_node_id, active_phases
        ):
            # The stop line itself is real, evidence-derived geometry
            # (flush with the crosswalk's own far edge -- see
            # VEHICLE_STOP_LINE_SETBACK_METERS's docstring), but it marks
            # where a vehicle's FRONT bumper stops, not its center. Offset
            # backward (opposite the direction of travel) by half this
            # vehicle's own real length so the front -- not the middle --
            # lands exactly there, keeping the whole vehicle behind the
            # crosswalk rather than straddling it.
            heading_vector = np.array([np.cos(heading), np.sin(heading)])
            position = zone.stop_line_position - heading_vector * (length / 2.0)

        candidate = Vehicle(
            vehicle_id=self._vehicle_counter,
            vehicle_type=vehicle_type,
            asset_path=asset_path,
            center=position.copy(),
            heading_rad=heading,
            length=length,
            width=width,
            height=height,
        )

        if any(_aabb_overlap(candidate.aabb, other) for other in placed_vehicle_aabbs):
            return None

        self._vehicle_counter += 1
        return candidate

    def _try_place_sidewalk_pedestrian(  # pylint: disable=too-many-locals
        self, zone: SpawnZone, edges: Dict[int, RoadEdge], occupancy: float
    ) -> Optional[Pedestrian]:
        pedestrian_occupancy = occupancy * PEDESTRIAN_DENSITY_FRACTION_OF_TRAFFIC
        if self.rng.random() > pedestrian_occupancy:
            return None
        assert zone.edge_id is not None  # every PEDESTRIAN zone carries one

        edge = edges[zone.edge_id]
        edge_direction = edge.centerline[-1] - edge.centerline[0]

        # Real two-way foot traffic: independent of this road's own
        # one-way vehicle-traffic direction, a real sidewalk carries
        # pedestrians going both ways. Even split -- no real distribution
        # data was found to weight one direction over the other
        # (disclosed, not silently assumed).
        walking_forward = bool(self.rng.integers(0, 2))
        heading = _edge_heading(edge) if walking_forward else _edge_heading(edge) + math.pi

        # Real ADA/PROWAG-consistent lateral jitter + keep-right bias
        # (see both constants' own docstrings): computed from the
        # WALKER's own facing direction, so opposite-direction
        # pedestrians naturally separate to opposite sides of the same
        # sidewalk, not a fixed centerline every pedestrian shares.
        walking_direction = edge_direction if walking_forward else -edge_direction
        walker_right = compute_perpendicular(walking_direction)
        jitter = self.rng.uniform(
            -PEDESTRIAN_LATERAL_JITTER_METERS, PEDESTRIAN_LATERAL_JITTER_METERS
        )
        lateral_offset = np.clip(
            PEDESTRIAN_KEEP_RIGHT_BIAS_METERS + jitter,
            -PEDESTRIAN_LATERAL_JITTER_METERS,
            PEDESTRIAN_LATERAL_JITTER_METERS,
        )
        position = zone.position + walker_right * lateral_offset

        return self._build_pedestrian(
            position, heading, SIDEWALK_TOP_HEIGHT_METERS, allow_standing=True
        )

    def _try_place_crossing_pedestrian(
        self, zone: SpawnZone, occupancy: float, active_phases: Dict[int, SignalPhase]
    ) -> Optional[Pedestrian]:
        """A pedestrian actually crossing a road, at one of the real,
        width-tiled candidate points along a real crosswalk (see
        ``traffic_network.TrafficNetworkGenerator._generate_crossing_
        zones``). Uses a real, lower, disclosed occupancy fraction than
        a sidewalk zone -- crossing is a brief transient event compared
        to standing/walking a full sidewalk block (see
        ``PEDESTRIAN_CROSSING_DENSITY_FRACTION_OF_TRAFFIC``'s own
        docstring).

        Gated on the same resolved signal phase vehicles use (see
        ``generate``): a crossing is only ever placed when the currently-
        resolved phase at this crosswalk's own intersection (``zone.
        node_id``) is a real ``GREEN`` phase whose moving axis matches
        this crossing's own direction of travel -- MUTCD's standard
        concurrent walk scheme (pedestrians cross a road exactly when the
        traffic THEY conflict with, i.e. that same road's own vehicle
        traffic, is stopped, which happens precisely when the
        perpendicular axis has the green -- and the perpendicular axis's
        green shares the same axis label as this crossing's own direction
        of travel, since a crosswalk's crossing direction is always
        perpendicular to the road it crosses, i.e. parallel to the road
        that's still moving). A node absent from ``active_phases``
        (uncontrolled/stop-sign -- see ``signal_phasing.py``'s scope
        note) always allows crossing, unaffected by this gate."""
        crossing_occupancy = occupancy * PEDESTRIAN_CROSSING_DENSITY_FRACTION_OF_TRAFFIC
        if self.rng.random() > crossing_occupancy:
            return None
        assert zone.heading_rad is not None  # every CROSSING zone carries one

        if zone.node_id is not None:
            phase = active_phases.get(zone.node_id)
            if phase is not None:
                crossing_axis = approach_direction_from_heading(zone.heading_rad)
                if not (phase.kind == PhaseKind.GREEN and crossing_axis in phase.moving_approaches):
                    return None

        # Real two-way crossing: crossing direction is independent of
        # either intersecting road's own vehicle-traffic direction (a
        # crosswalk runs perpendicular to the road it crosses, not along
        # it -- see crosswalks.py), so which side someone crosses FROM is
        # an even, undocumented-elsewhere split, not tied to traffic.
        crossing_forward = bool(self.rng.integers(0, 2))
        heading = zone.heading_rad if crossing_forward else zone.heading_rad + math.pi

        return self._build_pedestrian(
            zone.position.copy(), heading, PEDESTRIAN_ROAD_SURFACE_Z_METERS, allow_standing=False
        )

    def _sample_pose_frame(self, allow_standing: bool) -> float:
        """A real baked pose frame from the FULL real walk cycle (see
        ``city_sample_assets.py``'s ``PEDESTRIAN_WALKING_CLIP``), or,
        when ``allow_standing`` and with real, disclosed probability
        ``PEDESTRIAN_STANDING_ACTIVITY_FRACTION``, from the second real
        baked clip (``PEDESTRIAN_STANDING_CLIP``) -- a genuinely
        different activity (standing/idle), not a gait-phase variant of
        walking. ``allow_standing`` is only ever True for sidewalk
        pedestrians; a pedestrian actively crossing a road is
        definitionally walking, never assigned the standing clip.

        Uses the full real clip range rather than a curated "obviously
        dynamic" sub-window (an earlier same-day pass did that, then
        reversed it -- see ``PEDESTRIAN_STANDING_ACTIVITY_FRACTION``'s
        own docstring for why): real pedestrian photography is not
        dominated by dramatic mid-stride poses, so sampling the whole
        cycle is both more statistically representative and gives more
        true diversity than a curated highlight reel.

        Within the walking clip specifically, biases toward the two
        confirmed-dynamic sub-windows (``PEDESTRIAN_WALKING_DYNAMIC_
        WINDOWS``, live-verified via side-profile screenshots to read as
        clearly mid-stride) with real, disclosed probability
        ``PEDESTRIAN_WALKING_POSE_BIAS_FRACTION`` -- per explicit user
        request 2026-09-24 that most walking pedestrians read as
        obviously walking at a glance -- while still sampling the full
        clip the rest of the time so real diversity (including subtler,
        near-neutral stances) isn't lost entirely.

        Re-rolls (bounded, not an unbounded loop) against the
        immediately PRECEDING pedestrian's own frame (the one most
        likely to be spatially adjacent, since pedestrians are placed in
        order along the same real sidewalk/crossing zones) rather than a
        full duplicate-tracking structure across the whole scenario --
        this doesn't guarantee zero repeats scenario-wide, but directly
        targets the specific case a person would actually notice: two
        neighbors captured in the same glance. 8 attempts against the
        smaller real clip (110 values) keeps the chance of exhausting
        every retry astronomically small without ever looping
        unboundedly."""
        if allow_standing and self.rng.random() < PEDESTRIAN_STANDING_ACTIVITY_FRACTION:
            clip_start, clip_end = PEDESTRIAN_STANDING_CLIP
        elif self.rng.random() < PEDESTRIAN_WALKING_POSE_BIAS_FRACTION:
            window_index = int(self.rng.integers(0, len(PEDESTRIAN_WALKING_DYNAMIC_WINDOWS)))
            clip_start, clip_end = PEDESTRIAN_WALKING_DYNAMIC_WINDOWS[window_index]
        else:
            clip_start, clip_end = PEDESTRIAN_WALKING_CLIP
        pose_frame = float(self.rng.integers(clip_start, clip_end + 1))
        attempts = 0
        while pose_frame == self._last_pose_frame and attempts < 8:
            pose_frame = float(self.rng.integers(clip_start, clip_end + 1))
            attempts += 1
        self._last_pose_frame = pose_frame
        return pose_frame

    def _build_pedestrian(  # pylint: disable=too-many-locals
        self,
        position: npt.NDArray[np.float64],
        heading: float,
        surface_z: float,
        allow_standing: bool,
    ) -> Pedestrian:
        """Sample a real gender+weight+outfit+hair combination and build
        the ``Pedestrian`` at ``position``/``heading`` -- shared by both
        sidewalk and crossing placement, since appearance sampling
        doesn't depend on where/how a pedestrian was placed. ``surface_z``
        is passed straight through from the caller -- see
        ``Pedestrian.surface_z``'s own docstring. ``allow_standing`` is
        passed straight through to ``_sample_pose_frame``."""
        gender = _PEDESTRIAN_GENDERS[int(self.rng.integers(0, len(_PEDESTRIAN_GENDERS)))]
        weight = _PEDESTRIAN_WEIGHTS[int(self.rng.integers(0, len(_PEDESTRIAN_WEIGHTS)))]
        combo = (gender, weight)

        body_path = PEDESTRIAN_BODY_ASSET_PATHS[combo]
        top_options = PEDESTRIAN_TOP_ASSET_PATHS[combo]
        bottom_options = PEDESTRIAN_BOTTOM_ASSET_PATHS[combo]
        shoe_options = PEDESTRIAN_SHOE_ASSET_PATHS[combo]
        face_options = PEDESTRIAN_FACE_ASSET_PATHS[gender]
        face_path = face_options[int(self.rng.integers(0, len(face_options)))]
        hair_path = pedestrian_face_and_hair(gender, face_path)

        part_paths = [
            top_options[int(self.rng.integers(0, len(top_options)))],
            bottom_options[int(self.rng.integers(0, len(bottom_options)))],
            shoe_options[int(self.rng.integers(0, len(shoe_options)))],
            face_path,
        ]
        if hair_path is not None:
            part_paths.append(hair_path)
        width, depth, height = PEDESTRIAN_DIMENSIONS_METERS[gender]

        pose_frame = self._sample_pose_frame(allow_standing)

        pedestrian = Pedestrian(
            pedestrian_id=self._pedestrian_counter,
            center=position,
            heading_rad=heading,
            asset_path=body_path,
            part_paths=part_paths,
            pose_frame=pose_frame,
            surface_z=surface_z,
            width=width,
            depth=depth,
            height=height,
        )
        self._pedestrian_counter += 1
        return pedestrian
