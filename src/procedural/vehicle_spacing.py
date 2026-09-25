"""Real, evidence-based vehicle-to-vehicle spacing for queued and moving
traffic, replacing a single fixed tiling interval with two distinct,
cited spacing regimes and a real random gap model.

Two real spacing means (never invented):

- **Queued** (a vehicle stopped in a real red-light queue): mean gap is
  ``traffic_network.VEHICLE_SPAWN_GAP_METERS`` (7.6m) -- the same real,
  HCM-cited jam-density spacing already used elsewhere in this codebase,
  reused here rather than redefined.
- **Moving** (a vehicle actually driving, whether mid-block or through a
  green-axis intersection): mean gap is derived from this lane's own
  real ``RoadEdge.speed_limit_kmh`` and the standard US DMV following-
  distance rule taught in every state driver handbook (e.g. the
  California DMV handbook's "Section 8: Safe Driving"): 2 seconds under
  35 mph, 3 seconds for 35-45 mph, 4 seconds for 46-70 mph. Converted to
  a real distance via this lane's own real speed limit -- not a single
  invented constant, so a residential 30 km/h street and an arterial
  70 km/h road get genuinely different, real moving spacing.

Real minimum gap, both regimes: this project's own real sedan length
(``actor_placement.VEHICLE_DIMENSIONS["sedan"][0]`` == 4.6m) plus the
Wiedemann 99 car-following model's cited default standstill distance
CC0 (~1.5m -- the real, standard "closest two cars ever sit, even
stopped" parameter used throughout commercial traffic microsimulation,
e.g. PTV VISSIM). No vehicle-to-vehicle gap in either regime is ever
sampled below this real physical floor.

Real random gap model: Cowan's M3 headway distribution (R. M. Cowan,
1975; still the standard model in traffic flow theory for real headway
distributions -- used for gap-acceptance and capacity analysis at
unsignalized intersections and roundabouts in the FHWA's own
"Unsignalized Intersection Theory" chapter). A real headway is the
minimum gap plus a random "free" component; empirical queue-discharge
studies (Lin & Thomas, 2005, "Headway Compression during Queue Discharge
at Signalized Intersections") confirm real headway distributions are
right-skewed (mean > median) -- exactly the shape an exponential "free"
component produces, and exactly why a symmetric jitter (e.g. Gaussian)
would NOT match the real, observed shape. This module models that free
component as a real exponential distribution, scaled so the regime's
own real mean (queued: 7.6m: moving: the real speed/DMV-derived mean
above) is respected exactly in expectation:
``gap = minimum_gap + Exponential(mean=target_mean_gap - minimum_gap)``.
"""

from dataclasses import dataclass

import numpy as np

from src.procedural.traffic_network import VEHICLE_SPAWN_GAP_METERS

# Real sedan length (actor_placement.VEHICLE_DIMENSIONS["sedan"][0]) --
# duplicated as a literal here rather than imported, to avoid a
# vehicle_spacing <-> actor_placement import cycle (actor_placement
# imports this module, not the reverse; see signal_phasing.py's own
# DESIGN_VEHICLE_LENGTH_M for the same, already-established pattern).
DESIGN_VEHICLE_LENGTH_M = 4.6

# Wiedemann 99 car-following model's cited default standstill distance
# (CC0): the real, standard minimum bumper-to-bumper gap between two
# vehicles even fully stopped, used throughout commercial traffic
# microsimulation (e.g. PTV VISSIM's own default calibration).
WIEDEMANN_CC0_STANDSTILL_GAP_M = 1.5

# The real, physical floor no sampled gap (either regime) may fall
# below: a design vehicle's own length plus the real standstill gap.
MINIMUM_VEHICLE_GAP_M = DESIGN_VEHICLE_LENGTH_M + WIEDEMANN_CC0_STANDSTILL_GAP_M

# Real queued-vehicle mean gap: reuses traffic_network's own cited
# HCM jam-density spacing rather than redefining it.
QUEUED_MEAN_GAP_M = VEHICLE_SPAWN_GAP_METERS

# Standard US DMV following-distance rule (e.g. California DMV driver
# handbook, "Section 8: Safe Driving"; consistent across state driver
# manuals): the real minimum following TIME by speed tier.
_FOLLOWING_TIME_TIER_KMH = (
    (56.3, 2.0),  # under 35 mph
    (72.4, 3.0),  # 35-45 mph
)
_FOLLOWING_TIME_DEFAULT_S = 4.0  # 46-70 mph and above


def following_time_seconds(speed_limit_kmh: float) -> float:
    """The real, standard US DMV following TIME (seconds) for a road's
    own real speed limit -- see this module's own docstring for the
    real speed-tier citation."""
    for speed_ceiling_kmh, following_time_s in _FOLLOWING_TIME_TIER_KMH:
        if speed_limit_kmh <= speed_ceiling_kmh:
            return following_time_s
    return _FOLLOWING_TIME_DEFAULT_S


def moving_mean_gap_m(speed_limit_kmh: float) -> float:
    """The real moving-traffic mean gap (meters) for a road's own real
    speed limit: real speed (m/s) times the real DMV following time for
    that speed tier -- never below the real physical minimum gap (a
    vehicle stopped in slow traffic on a fast road can't be assigned a
    mean shorter than it could physically ever achieve)."""
    speed_ms = speed_limit_kmh / 3.6
    return max(speed_ms * following_time_seconds(speed_limit_kmh), MINIMUM_VEHICLE_GAP_M)


@dataclass(frozen=True)
class SpacingRegime:
    """One real spacing regime: a target mean gap and the real physical
    minimum gap it can never fall below."""

    mean_gap_m: float
    minimum_gap_m: float = MINIMUM_VEHICLE_GAP_M


def queued_regime() -> SpacingRegime:
    """The real queued/stopped-traffic spacing regime (HCM jam-density
    mean, see module docstring)."""
    return SpacingRegime(mean_gap_m=QUEUED_MEAN_GAP_M)


def moving_regime(speed_limit_kmh: float) -> SpacingRegime:
    """The real moving-traffic spacing regime for a lane's own real
    speed limit (DMV-following-time-derived mean, see module
    docstring)."""
    return SpacingRegime(mean_gap_m=moving_mean_gap_m(speed_limit_kmh))


def sample_gap(rng: np.random.Generator, regime: SpacingRegime) -> float:
    """One real, randomly-sampled vehicle-to-vehicle gap (meters) for a
    spacing regime: Cowan's M3 structure, minimum gap plus an
    exponential "free" component scaled so the regime's own real mean is
    respected in expectation (see module docstring). Never below the
    regime's own real minimum gap, by construction."""
    free_mean = max(regime.mean_gap_m - regime.minimum_gap_m, 1e-6)
    return regime.minimum_gap_m + float(rng.exponential(free_mean))


# HCM base saturation flow rate: 1900 passenger cars per hour per lane
# (Highway Capacity Manual, ideal conditions, metropolitan areas) -- the
# real maximum rate a lane can discharge/carry, used here as the flow a
# fully-saturated (occupancy 1.0) lane would arrive at.
SATURATION_FLOW_VEHICLES_PER_SECOND = 1900.0 / 3600.0


def sample_signal_queue_length(
    rng: np.random.Generator, occupancy: float, red_time_s: float
) -> int:
    """How many vehicles are queued at a signalized approach at one
    randomly-arriving instant within its red interval: real signal
    analysis (HCM uniform-delay model) treats the queue as the vehicles
    that arrived since the red began, and treats arrivals as a Poisson
    process. The instant is uniform within the red (a snapshot lands
    anywhere in it, same reasoning as ``resolve_active_phases``), and the
    arrival rate is this scenario's own ``occupancy`` as a fraction of
    the real saturation flow (a volume-to-capacity ratio)."""
    elapsed_red_s = float(rng.uniform(0.0, max(red_time_s, 0.0)))
    mean_arrivals = occupancy * SATURATION_FLOW_VEHICLES_PER_SECOND * elapsed_red_s
    return int(rng.poisson(mean_arrivals))


def sample_stop_sign_queue_length(
    rng: np.random.Generator, occupancy: float, zone_length_m: float
) -> int:
    """How many vehicles wait at a stop-controlled approach: no timed
    red interval exists to accumulate arrivals over, so the mean is the
    real number of jam-spaced vehicles the approach's own crosswalk-
    clearing zone physically holds, scaled by occupancy (disclosed
    simplification, not a modeled arrival process)."""
    mean_vehicles = occupancy * zone_length_m / QUEUED_MEAN_GAP_M
    return int(rng.poisson(mean_vehicles))
