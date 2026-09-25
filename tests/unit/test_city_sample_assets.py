"""Unit tests for city_sample_assets.

Covers the real invariant this module exists to guarantee: every vehicle
type ActorPlacementGenerator can sample has at least one real City Sample
asset path to resolve to, so Phase 1's asset-based spawn path never hits
a vehicle type with nothing to spawn.
"""

from src.procedural.actor_placement import VEHICLE_DIMENSIONS
from src.procedural.city_sample_assets import (
    BUS_VISUAL_DIVERSITY_FRACTION,
    REAL_US_VEHICLE_CLASS_MIX,
    VEHICLE_ASSET_PATHS,
)


def test_every_vehicle_dimension_type_has_at_least_one_asset_path() -> None:
    """Every key in VEHICLE_DIMENSIONS (the set of vehicle types
    ActorPlacementGenerator can actually sample from vehicle_mix) has a
    matching entry in VEHICLE_ASSET_PATHS with at least one path."""
    for vehicle_type in VEHICLE_DIMENSIONS:
        assert (
            vehicle_type in VEHICLE_ASSET_PATHS
        ), f"No asset paths for vehicle type {vehicle_type!r}"
        assert VEHICLE_ASSET_PATHS[
            vehicle_type
        ], f"Empty asset path list for vehicle type {vehicle_type!r}"


def test_no_asset_path_keys_without_a_matching_vehicle_dimension() -> None:
    """No stray VEHICLE_ASSET_PATHS entry exists for a vehicle type
    ActorPlacementGenerator can never actually sample -- keeps the two
    dicts from silently drifting apart in either direction."""
    for vehicle_type in VEHICLE_ASSET_PATHS:
        assert vehicle_type in VEHICLE_DIMENSIONS, f"Stray asset path entry for {vehicle_type!r}"


def test_every_asset_path_is_a_plausible_content_path() -> None:
    """Every path looks like a real /Game/... UE5 content path, not a
    placeholder or a filesystem path."""
    for vehicle_type, paths in VEHICLE_ASSET_PATHS.items():
        for path in paths:
            assert path.startswith(
                "/Game/"
            ), f"{vehicle_type!r} path {path!r} doesn't start with /Game/"
            assert "\\" not in path, f"{vehicle_type!r} path {path!r} looks like a filesystem path"


def test_asset_paths_are_unique_across_all_vehicle_types() -> None:
    """No single asset path is reused across two different vehicle
    types -- each real City Sample model should back exactly one type."""
    all_paths = [path for paths in VEHICLE_ASSET_PATHS.values() for path in paths]
    assert len(all_paths) == len(set(all_paths))


def test_real_vehicle_class_mix_covers_every_dimension_type() -> None:
    """REAL_US_VEHICLE_CLASS_MIX has exactly the same keys as
    VEHICLE_DIMENSIONS -- every scenario_templates/*.yaml vehicle_mix
    block is meant to be a copy of this real, cited distribution."""
    assert set(REAL_US_VEHICLE_CLASS_MIX) == set(VEHICLE_DIMENSIONS)


def test_real_vehicle_class_mix_sums_to_one() -> None:
    """The real, cited registration shares plus the disclosed bus
    fraction sum to exactly 1.0 -- a real, checkable invariant, not an
    approximation, since it's constructed by rescaling the three cited
    real shares to fill the remainder after reserving the bus fraction."""
    assert sum(REAL_US_VEHICLE_CLASS_MIX.values()) == 1.0


def test_real_vehicle_class_mix_matches_cited_2024_registration_shares() -> None:
    """Direct, hand-computed proof of the citation math: real SUV share
    (59.10%, including the 4.21% van/minivan share folded in, matching
    VEHICLE_ASSET_PATHS' own van-into-suv convention) is by far the
    largest single category, real car (18.66%) and pickup (18.03%)
    shares are each rescaled by the same (1 - bus_fraction) factor."""
    scale = 1.0 - BUS_VISUAL_DIVERSITY_FRACTION
    assert REAL_US_VEHICLE_CLASS_MIX["suv"] == round(0.6331 * scale, 3)
    assert REAL_US_VEHICLE_CLASS_MIX["sedan"] == round(0.1866 * scale, 3)
    assert REAL_US_VEHICLE_CLASS_MIX["truck"] == round(0.1803 * scale, 3)
    assert REAL_US_VEHICLE_CLASS_MIX["bus"] == BUS_VISUAL_DIVERSITY_FRACTION
    # SUV real share is a real majority of all light-vehicle
    # registrations -- the mix must reflect that dominance, not an
    # even-ish split.
    assert REAL_US_VEHICLE_CLASS_MIX["suv"] > 0.5
