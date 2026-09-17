"""Unit tests for city_sample_assets.

Covers the real invariant this module exists to guarantee: every vehicle
type ActorPlacementGenerator can sample has at least one real City Sample
asset path to resolve to, so Phase 1's asset-based spawn path never hits
a vehicle type with nothing to spawn.
"""

from src.procedural.actor_placement import VEHICLE_DIMENSIONS
from src.procedural.city_sample_assets import VEHICLE_ASSET_PATHS


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
