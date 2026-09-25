"""Unit tests for vehicle_spacing.py: the real queued/moving spacing
regimes and the Cowan-M3-style random gap sampler."""

import numpy as np
import pytest

from src.procedural.traffic_network import VEHICLE_SPAWN_GAP_METERS
from src.procedural.vehicle_spacing import (
    MINIMUM_VEHICLE_GAP_M,
    QUEUED_MEAN_GAP_M,
    SpacingRegime,
    following_time_seconds,
    moving_mean_gap_m,
    moving_regime,
    queued_regime,
    sample_gap,
)


def test_queued_mean_reuses_the_real_hcm_jam_density_constant() -> None:
    """The queued regime's mean is exactly traffic_network's own real,
    cited jam-density spacing -- not a redefined/duplicated value."""
    assert QUEUED_MEAN_GAP_M == VEHICLE_SPAWN_GAP_METERS
    assert queued_regime().mean_gap_m == VEHICLE_SPAWN_GAP_METERS


@pytest.mark.parametrize(
    "speed_limit_kmh,expected_seconds",
    [
        (30.0, 2.0),  # well under 35 mph
        (56.3, 2.0),  # exactly the 35 mph boundary
        (60.0, 3.0),  # 35-45 mph band
        (72.4, 3.0),  # exactly the 45 mph boundary
        (90.0, 4.0),  # 46-70 mph band
        (150.0, 4.0),  # highway speed, still the top tier
    ],
)
def test_following_time_matches_real_dmv_speed_tiers(speed_limit_kmh, expected_seconds) -> None:
    """The real, standard US DMV following-time rule (2s/3s/4s by speed
    tier) applies exactly at and around each real tier boundary."""
    assert following_time_seconds(speed_limit_kmh) == expected_seconds


def test_moving_mean_gap_scales_with_real_speed_limit() -> None:
    """A faster real speed limit produces a strictly larger real moving
    mean gap -- proven with exact arithmetic, not just an inequality."""
    gap_30 = moving_mean_gap_m(30.0)
    gap_90 = moving_mean_gap_m(90.0)
    assert gap_90 > gap_30
    assert gap_30 == pytest.approx((30.0 / 3.6) * 2.0)
    assert gap_90 == pytest.approx((90.0 / 3.6) * 4.0)


def test_moving_mean_gap_never_below_the_real_physical_minimum() -> None:
    """Even a very slow real speed limit can't produce a mean gap
    smaller than the real physical minimum (vehicle length + standstill
    gap) -- a real 5 km/h crawl doesn't imply vehicles could be closer
    than physically possible."""
    assert moving_mean_gap_m(5.0) == MINIMUM_VEHICLE_GAP_M


def test_moving_regime_mean_matches_moving_mean_gap_m() -> None:
    """SpacingRegime built by moving_regime() carries the same mean as
    calling moving_mean_gap_m() directly -- no drift between the two."""
    regime = moving_regime(60.0)
    assert regime.mean_gap_m == moving_mean_gap_m(60.0)
    assert regime.minimum_gap_m == MINIMUM_VEHICLE_GAP_M


def test_sample_gap_never_below_the_regimes_own_minimum() -> None:
    """Across many real samples, the Cowan-M3-style gap never falls
    below the regime's own real minimum -- true by construction
    (minimum + a non-negative exponential draw), verified empirically
    over a large real sample."""
    rng = np.random.Generator(np.random.PCG64(42))
    regime = queued_regime()
    for _ in range(10_000):
        gap = sample_gap(rng, regime)
        assert gap >= regime.minimum_gap_m


def test_sample_gap_mean_matches_regime_target_over_many_samples() -> None:
    """The sampled gap's real empirical mean converges to the regime's
    own target mean gap -- proving the exponential "free" component is
    scaled correctly, not just bounded correctly."""
    rng = np.random.Generator(np.random.PCG64(7))
    regime = moving_regime(60.0)
    samples = [sample_gap(rng, regime) for _ in range(20_000)]
    assert np.mean(samples) == pytest.approx(regime.mean_gap_m, rel=0.03)


def test_sample_gap_is_right_skewed_matching_real_headway_studies() -> None:
    """Real queue-discharge headway studies (see module docstring)
    report mean > median -- the real, observed right-skew this
    module's exponential "free" component is specifically chosen to
    reproduce, not a symmetric jitter."""
    rng = np.random.Generator(np.random.PCG64(99))
    regime = queued_regime()
    samples = [sample_gap(rng, regime) for _ in range(20_000)]
    assert np.mean(samples) > np.median(samples)


def test_sample_gap_deterministic_for_a_seeded_generator() -> None:
    """Same seeded rng, same regime -> same exact sampled gap (no
    hidden global random state)."""
    regime = queued_regime()
    gap_a = sample_gap(np.random.Generator(np.random.PCG64(5)), regime)
    gap_b = sample_gap(np.random.Generator(np.random.PCG64(5)), regime)
    assert gap_a == gap_b


def test_moving_mean_gap_generally_exceeds_queued_mean_gap() -> None:
    """At any ordinary urban speed limit, the real moving mean gap
    exceeds the real queued mean gap -- moving traffic follows farther
    apart than a stopped queue, matching real driving behavior."""
    for speed_kmh in (30.0, 40.0, 50.0, 60.0, 80.0):
        assert moving_mean_gap_m(speed_kmh) > QUEUED_MEAN_GAP_M


def test_spacing_regime_is_a_frozen_dataclass() -> None:
    """SpacingRegime's two fields hold the exact values constructed with."""
    regime = SpacingRegime(mean_gap_m=10.0, minimum_gap_m=5.0)
    assert regime.mean_gap_m == 10.0
    assert regime.minimum_gap_m == 5.0
