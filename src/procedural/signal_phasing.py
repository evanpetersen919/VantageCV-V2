"""Real 4-way traffic-signal phase timing and per-instant phase resolution.

This project's scenarios are frozen single-frame captures, not a running
simulation (``dataset_generator.generate_scenario`` never advances time --
see ``KNOWN_GAPS_AND_ISSUES.md``'s discussion of why ``ACitySampleVehicleBase``
was never ported). The correct model for "realistic" signal behavior is
therefore not to simulate an intersection, but to treat each scenario as
one randomly-arriving snapshot of an intersection's real, repeating signal
cycle: sample a uniformly random instant within the cycle's real length
(so a phase that lasts twice as long is, correctly, twice as likely to be
the one captured -- exactly matching how a real dashcam/CCTV frame would
land), resolve which phase is active at that instant, and place vehicles/
pedestrians consistently with it.

Scope, deliberately: only ``RoadNode``s with ``TrafficControlType.
TRAFFIC_LIGHT`` (four-way intersections -- see ``traffic_network.py``) get
a full timed signal plan. Left-turn phasing is out of scope for this
first pass (this project does not yet place any turning vehicles at all
-- see ``lane_connectivity.TurnType``, not used here); every moving
direction on a green axis is treated as permissive (proceed when clear),
which is itself a real, common, MUTCD-legal configuration, just not the
only one real intersections use.

``TrafficControlType.STOP_SIGN`` (T-junctions) get a simpler, static rule
instead of a timed plan (see ``compute_minor_axis_by_node`` below): a
real 2-way stop only controls the minor/stub road, never the major/
through road, and -- unlike a signal -- always requires a full stop, not
a timed share of green. Since this pipeline can't model "stops, then
proceeds" within one frozen frame, the correct single-frame equivalent is
that the minor axis is ALWAYS treated as not having the right of way
(permanently queued at its own stop line), while the through axis always
flows -- this is the static, MUTCD-consistent limit of a 2-way stop, not
an invented rule. A genuine all-way stop is not modeled (no per-approach
arrival-order tracking exists), so ``TrafficControlType.NONE`` (any
other/uncontrolled node) still always flows, unchanged.

Real road network guarantee this module leans on (see
``road_network.py``'s own module docstring): every edge is exactly
axis-aligned (straight roads, square intersections only, by deliberate
design -- no perturbed-grid/Delaunay layout is used). This makes
classifying an edge's own approach direction into one of exactly 4
cardinal bins (``ApproachDirection``) exact, not a heuristic angle-snap --
proven directly from how the edge's own direction vector is constructed
(one of its two components is always exactly zero), not merely assumed;
covered by ``test_signal_phasing.py``.

Standard 2-phase NEMA operation (opposing through-movements share a
phase, the perpendicular pair gets the other phase) is what this module
implements: one ``IntersectionSignalPlan`` per signalized node cycles
GREEN(north-south) -> YELLOW_CHANGE -> ALL_RED -> GREEN(east-west) ->
YELLOW_CHANGE -> ALL_RED -> (repeat).

All timing values are either real, cited standard figures (ITE Traffic
Engineering Handbook / MUTCD) or values already computed elsewhere in
this codebase from real per-scenario geometry (speed limits, intersection
width) -- never invented. See each constant's own comment for its
citation, and this module's functions for the formulas.
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, FrozenSet, List, Tuple

import numpy as np

from src.procedural.lane_topology import compute_node_clearance
from src.procedural.road_network import RoadEdge
from src.procedural.traffic_network import TrafficControlType, TrafficNetwork

# --- Real, cited timing constants (ITE Traffic Engineering Handbook / MUTCD) ---

# ITE-cited typical urban minimum green range is 15-60s depending on
# approach demand; this pipeline has no real per-approach traffic-volume
# model (only a scenario-wide occupancy fraction, see actor_placement.py),
# so the floor of that range is used rather than inventing a demand-
# responsive split. May be lengthened per intersection to satisfy the real
# pedestrian-clearance constraint below -- never shortened past this floor.
MIN_GREEN_SECONDS = 15.0

# ITE perception-reaction time, standard value used in the yellow-change
# formula below.
PERCEPTION_REACTION_TIME_S = 1.0

# ITE-cited comfortable deceleration rate (11.2 ft/s^2), the most-cited
# figure in the ITE yellow-change-interval formula.
COMFORTABLE_DECELERATION_MPS2 = 3.4

# Design vehicle length for the all-red clearance formula below. Reuses
# this project's own real "sedan" length (VEHICLE_DIMENSIONS["sedan"][0]
# in actor_placement.py) as the design vehicle -- duplicated as a literal
# here rather than imported, to avoid a signal_phasing <-> actor_placement
# import cycle (actor_placement imports this module, not the reverse).
DESIGN_VEHICLE_LENGTH_M = 4.6

# MUTCD Section 4E.06(3): minimum pedestrian WALK interval.
PEDESTRIAN_WALK_MIN_S = 7.0

# MUTCD Section 4E.06: standard pedestrian walking speed used for timing
# calculations (3.5 ft/s). PROWAG's slower, accessibility-oriented 0.914
# m/s (3.0 ft/s) is a real, documented alternative for ADA-conservative
# clearance timing -- not used here, flagged as a disclosed choice.
PEDESTRIAN_WALKING_SPEED_MPS = 1.07


class ApproachDirection(str, Enum):
    """The cardinal compass direction a vehicle on a given directed edge
    is travelling, for edges that arrive at (rather than depart from) an
    intersection node."""

    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


# The two real "opposing through-movement" axis pairs a standard 2-phase
# signal cycles between (MUTCD/ITE standard NEMA 2-phase operation):
# north/south share a phase, east/west share the other.
NORTH_SOUTH_AXIS: FrozenSet[ApproachDirection] = frozenset(
    {ApproachDirection.NORTH, ApproachDirection.SOUTH}
)
EAST_WEST_AXIS: FrozenSet[ApproachDirection] = frozenset(
    {ApproachDirection.EAST, ApproachDirection.WEST}
)
AXIS_PAIRS: Tuple[FrozenSet[ApproachDirection], ...] = (NORTH_SOUTH_AXIS, EAST_WEST_AXIS)


def _classify_direction_vector(dx: float, dy: float) -> ApproachDirection:
    """Classify a real, axis-aligned (dx, dy) direction vector into one of
    the 4 cardinal ``ApproachDirection`` values.

    Uses magnitude comparison (not angle-snapping): ``road_network.py``'s
    grid guarantees every real edge direction has one component exactly
    (or, after floating-point centerline subtraction, effectively) zero,
    so whichever of ``dx``/``dy`` is larger unambiguously identifies the
    axis, and its sign identifies the direction along that axis. This is
    exact for this project's real, deliberately-axis-aligned road network,
    not a tolerance-band heuristic for an arbitrary-angle one -- see
    ``test_signal_phasing.py``'s exactness proof.
    """
    if abs(dx) >= abs(dy):
        return ApproachDirection.EAST if dx > 0 else ApproachDirection.WEST
    return ApproachDirection.NORTH if dy > 0 else ApproachDirection.SOUTH


def classify_approach_direction(edge: RoadEdge) -> ApproachDirection:
    """The cardinal direction of travel of a directed ``RoadEdge`` -- i.e.
    the approach direction of a vehicle following it toward its own
    ``end_node_id``."""
    dx, dy = edge.centerline[-1] - edge.centerline[0]
    return _classify_direction_vector(float(dx), float(dy))


def approach_direction_from_heading(heading_rad: float) -> ApproachDirection:
    """The cardinal direction of a real heading angle (radians, standard
    math convention) -- used for a ``CROSSING`` zone's own crossing
    direction (``SpawnZone.heading_rad``), which has no directed edge of
    its own to classify via ``classify_approach_direction``. Exact for the
    same reason: every real crossing heading in this codebase is derived
    from ``compute_perpendicular`` of an axis-aligned road direction, so
    it is itself exactly axis-aligned."""
    return _classify_direction_vector(math.cos(heading_rad), math.sin(heading_rad))


def compute_minor_axis_by_node(
    edges: Dict[int, RoadEdge]
) -> Dict[int, FrozenSet[ApproachDirection]]:
    """For a real T-junction (exactly one through axis, one stub axis),
    the axis pair that is the minor/stub road -- the one a real 2-way
    stop sign controls (see module docstring). Derived purely from
    geometry, not ``TrafficControlType``: at any node, group every
    incident directed edge (as either its ``start_node_id`` or
    ``end_node_id``) by which of the two real ``AXIS_PAIRS`` its
    direction vector falls on (exact for this project's axis-aligned grid
    -- same guarantee ``classify_approach_direction`` relies on). A real
    T-shape is exactly 3 physical two-way connections: 2 collinear
    (through, contributing 4 directed edges) and 1 perpendicular (stub,
    contributing 2) -- so the axis with the smaller of two unequal counts
    is the stub, and only that axis has to stop.

    Equal counts on both axes means there's no through road at all --
    either a real STREET CORNER (two separate roads meeting at a right
    angle, each contributing one real connection: 2/2) or a genuine
    4-way (each direction contributing one: 4/4, moot in practice, since
    a real 4-way is always ``TRAFFIC_LIGHT``-controlled and never
    reaches this fallback -- see ``_axis_is_flowing``). With no through
    road to prioritize, BOTH axes are the "minor" one -- a real corner
    or comparable-volume crossing needs a full stop on every approach,
    the same real MUTCD-consistent standard this module's docstring
    already describes for a 2-way stop, just applied symmetrically. The
    result carries the union of both axes for such a node.

    A node with edges on only one axis at all (a true dead end, or a
    straight pass-through where both connections are collinear) has no
    minor axis and is absent from the result -- callers must treat a
    missing node_id like ``active_phases`` treats one: no rule applies
    there."""
    axis_counts: Dict[int, Dict[FrozenSet[ApproachDirection], int]] = {}
    for edge in edges.values():
        dx, dy = edge.centerline[-1] - edge.centerline[0]
        axis_pair = EAST_WEST_AXIS if abs(dx) >= abs(dy) else NORTH_SOUTH_AXIS
        for node_id in (edge.start_node_id, edge.end_node_id):
            counts = axis_counts.setdefault(node_id, {})
            counts[axis_pair] = counts.get(axis_pair, 0) + 1

    minor_axis: Dict[int, FrozenSet[ApproachDirection]] = {}
    for node_id, counts in axis_counts.items():
        if len(counts) != 2:
            continue
        (axis_a, count_a), (axis_b, count_b) = counts.items()
        if count_a == count_b:
            minor_axis[node_id] = axis_a | axis_b
            continue
        minor_axis[node_id] = axis_a if count_a < count_b else axis_b
    return minor_axis


class PhaseKind(str, Enum):
    """What an intersection's signal is doing during one phase."""

    GREEN = "green"
    YELLOW_CHANGE = "yellow_change"
    ALL_RED = "all_red"


@dataclass(frozen=True)
class SignalPhase:
    """One phase of a signal cycle. ``moving_approaches`` is the axis pair
    permitted to proceed -- always empty for ``YELLOW_CHANGE``/``ALL_RED``
    (nothing may newly enter the intersection while it's clearing), and
    always one of ``AXIS_PAIRS`` for ``GREEN``."""

    phase_index: int
    kind: PhaseKind
    moving_approaches: FrozenSet[ApproachDirection]
    duration_s: float


@dataclass(frozen=True)
class IntersectionSignalPlan:
    """One real, repeating signal cycle for a single intersection node."""

    node_id: int
    phases: Tuple[SignalPhase, ...]
    cycle_length_s: float

    def phase_at(self, t_in_cycle_s: float) -> SignalPhase:
        """Which phase is active at ``t_in_cycle_s`` seconds into the
        (repeating) cycle -- ``t_in_cycle_s`` is wrapped via modulo, so any
        real, non-negative offset (not just one already within a single
        cycle) resolves correctly."""
        t = t_in_cycle_s % self.cycle_length_s
        elapsed = 0.0
        for phase in self.phases:
            elapsed += phase.duration_s
            if t < elapsed:
                return phase
        return self.phases[-1]  # floating-point edge case: t == cycle_length_s exactly


def compute_signal_plan(
    node_id: int, incident_edges: List[RoadEdge], node_clearance_m: float
) -> IntersectionSignalPlan:
    """Build one real, evidence-backed signal plan for a single four-way
    node, from its own real incident-edge speed limits and real
    intersection clearance width.

    Yellow-change interval (ITE Traffic Engineering Handbook formula,
    flat-grade case): ``Y = t + v / (2*a)``, using the highest real
    ``speed_limit_kmh`` among this node's own incident edges (conservative
    -- standard practice designs the interval for the fastest conflicting
    approach, not a per-approach value, since every approach shares the
    same all-red/yellow window).

    All-red clearance interval (ITE formula): ``AR = (W + L) / v``, where
    ``W`` is this node's own real ``compute_node_clearance`` value (the
    physical half-width of the widest road meeting here -- already used
    by 3+ other modules as the real intersection-box size) and ``L`` is
    the real design vehicle length.

    Green duration: the real ``MIN_GREEN_SECONDS`` floor, unless the real
    pedestrian walk-plus-clearance requirement for this same green phase
    (MUTCD 4E.06: ``WALK_min + crossing_distance / walking_speed``) would
    exceed it -- in which case green is lengthened to satisfy pedestrians
    (never shortened below the MUTCD WALK floor). ``crossing_distance``
    is ``2 * node_clearance_m``: this project's own
    ``compute_node_clearance`` already defines a node's clearance as one
    direction's own lane half-width (``num_lanes * LANE_WIDTH_METERS``),
    and every road in this codebase carries the same lane count in both
    directions (``UNIFORM_LANE_COUNT``, see ``road_network.py``) -- so
    doubling it is exactly (not approximately) the same real
    ``road_width_m`` value ``crosswalks.py`` computes for the same node's
    own crosswalks, not a fresh approximation.
    """
    speeds_ms = [edge.speed_limit_kmh / 3.6 for edge in incident_edges] or [50.0 / 3.6]
    design_speed_ms = max(speeds_ms)

    yellow_s = PERCEPTION_REACTION_TIME_S + design_speed_ms / (2 * COMFORTABLE_DECELERATION_MPS2)
    all_red_s = (node_clearance_m + DESIGN_VEHICLE_LENGTH_M) / design_speed_ms

    crossing_distance_m = 2.0 * node_clearance_m
    pedestrian_clearance_s = crossing_distance_m / PEDESTRIAN_WALKING_SPEED_MPS
    green_s = max(MIN_GREEN_SECONDS, PEDESTRIAN_WALK_MIN_S + pedestrian_clearance_s)

    phases: List[SignalPhase] = []
    for axis in AXIS_PAIRS:
        phases.append(SignalPhase(len(phases), PhaseKind.GREEN, axis, green_s))
        phases.append(SignalPhase(len(phases), PhaseKind.YELLOW_CHANGE, frozenset(), yellow_s))
        phases.append(SignalPhase(len(phases), PhaseKind.ALL_RED, frozenset(), all_red_s))

    cycle_length_s = sum(phase.duration_s for phase in phases)
    return IntersectionSignalPlan(node_id, tuple(phases), cycle_length_s)


def build_signal_plans(
    edges: Dict[int, RoadEdge], traffic: TrafficNetwork
) -> Dict[int, IntersectionSignalPlan]:
    """One ``IntersectionSignalPlan`` per real ``TrafficControlType.
    TRAFFIC_LIGHT`` node in ``traffic.traffic_controls`` -- T-junctions/
    stop-signs/uncontrolled nodes get no plan at all (see module
    docstring's scope note), so callers must treat a missing node_id as
    "no signal governs this location", not an error."""
    incident_by_node: Dict[int, List[RoadEdge]] = {}
    for edge in edges.values():
        incident_by_node.setdefault(edge.end_node_id, []).append(edge)

    node_clearance = compute_node_clearance(edges)

    plans: Dict[int, IntersectionSignalPlan] = {}
    for node_id, control in traffic.traffic_controls.items():
        if control != TrafficControlType.TRAFFIC_LIGHT:
            continue
        plans[node_id] = compute_signal_plan(
            node_id, incident_by_node.get(node_id, []), node_clearance.get(node_id, 0.0)
        )
    return plans


def resolve_active_phases(
    plans: Dict[int, IntersectionSignalPlan], rng: np.random.Generator
) -> Dict[int, SignalPhase]:
    """Sample one uniformly random instant within each plan's own real
    cycle length and resolve it to the phase active at that instant -- see
    module docstring for why uniform-in-time sampling (not e.g. uniform
    phase-choice) is the mathematically correct way to model "one
    randomly-arriving snapshot" of a repeating cycle."""
    return {
        node_id: plan.phase_at(float(rng.uniform(0.0, plan.cycle_length_s)))
        for node_id, plan in plans.items()
    }


def red_time_seconds(plan: IntersectionSignalPlan, axis: ApproachDirection) -> float:
    """The real time per cycle a lane on cardinal ``axis`` is stopped:
    the whole cycle minus its own axis pair's GREEN and YELLOW_CHANGE
    phases (its own all-red clearance, and everything the perpendicular
    axis owns, is time this axis waits). Uses the same fixed 6-phase
    layout ``compute_signal_plan`` builds -- ``phase_index //
    len(PhaseKind)`` recovers which ``AXIS_PAIRS`` entry owns a phase."""
    axis_pair = next(pair for pair in AXIS_PAIRS if axis in pair)
    moving_time_s = sum(
        phase.duration_s
        for phase in plan.phases
        if AXIS_PAIRS[phase.phase_index // len(PhaseKind)] == axis_pair
        and phase.kind in (PhaseKind.GREEN, PhaseKind.YELLOW_CHANGE)
    )
    return plan.cycle_length_s - moving_time_s
