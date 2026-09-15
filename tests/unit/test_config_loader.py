"""Unit tests for load_scenario_config.

Covers loading the two real ``configs/scenario_templates/`` files that
map onto RoadNetworkGenerator's actual (grid + Delaunay) generation
strategy, and the deliberate NotImplementedError for the three that
don't -- see src/utils/config_loader.py's own module docstring.
"""

from pathlib import Path

import pytest

from src.procedural.road_network import RoadNetworkGenerator
from src.procedural.scenario import ScenarioType
from src.utils.config_loader import load_scenario_config

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "configs" / "scenario_templates"


def test_load_urban_dense_matches_file_contents() -> None:
    """Every field of the loaded config matches urban_dense.yaml's own values."""
    config = load_scenario_config(_TEMPLATES_DIR / "urban_dense.yaml")

    assert config.scenario_type == ScenarioType.URBAN_DENSE
    assert config.avg_block_size == (80.0, 150.0)
    assert config.avg_road_width == 12.0
    assert config.num_intersections == (4, 9)
    assert config.intersection_types == ["4way", "3way"]
    assert config.building_density == 0.8
    assert config.building_heights == (20.0, 40.0)
    assert config.traffic_density == (0.6, 1.0)
    assert config.vehicle_mix == {"sedan": 0.6, "suv": 0.25, "truck": 0.10, "bus": 0.05}
    assert config.complexity_score == 80
    assert config.road_setback_meters == 2.0


def test_load_urban_sparse_matches_file_contents() -> None:
    """Every field of the loaded config matches urban_sparse.yaml's own values."""
    config = load_scenario_config(_TEMPLATES_DIR / "urban_sparse.yaml")

    assert config.scenario_type == ScenarioType.URBAN_SPARSE
    assert config.avg_block_size == (200.0, 400.0)
    assert config.num_intersections == (2, 4)
    assert config.building_density == 0.35
    assert config.complexity_score == 45
    assert config.road_setback_meters == 4.0


def test_load_omitted_road_setback_meters_uses_scenario_type_config_default(tmp_path) -> None:
    """A template that doesn't set buildings.road_setback_meters at all
    gets ScenarioTypeConfig's own default, not a silently-missing value."""
    yaml_path = tmp_path / "no_setback.yaml"
    yaml_path.write_text(
        """
scenario_type: urban_dense
road_network:
  avg_block_size: [80.0, 150.0]
  avg_road_width: 12.0
  num_intersections: [4, 9]
  intersection_types: ["4way", "3way"]
buildings:
  building_density: 0.8
  building_heights: [20.0, 40.0]
traffic:
  traffic_density: [0.6, 1.0]
  vehicle_mix:
    sedan: 1.0
complexity_score: 80
"""
    )
    config = load_scenario_config(yaml_path)
    assert config.road_setback_meters == 2.0


def test_load_urban_dense_config_is_usable_by_real_generator(bounds) -> None:
    """The loaded config actually works end-to-end with RoadNetworkGenerator
    -- not just structurally valid, but functionally correct."""
    config = load_scenario_config(_TEMPLATES_DIR / "urban_dense.yaml")
    nodes, edges = RoadNetworkGenerator(42, config).generate(bounds)

    assert len(nodes) > 0
    assert len(edges) > 0


@pytest.mark.parametrize("filename", ["highway.yaml", "parking_lot.yaml", "roundabout.yaml"])
def test_load_unsupported_scenario_type_raises_not_implemented(filename: str) -> None:
    """highway/parking_lot/roundabout templates raise NotImplementedError,
    not a confusing pydantic/KeyError -- their schemas don't even match
    ScenarioTypeConfig's fields (see config_loader.py's own docstring)."""
    with pytest.raises(NotImplementedError, match="no real road-network generation"):
        load_scenario_config(_TEMPLATES_DIR / filename)


def test_load_nonexistent_file_raises_file_not_found() -> None:
    """A missing config path raises FileNotFoundError, not some
    lower-level YAML/OS error."""
    with pytest.raises(FileNotFoundError):
        load_scenario_config(_TEMPLATES_DIR / "does_not_exist.yaml")


def test_load_accepts_str_path() -> None:
    """load_scenario_config accepts a plain str path, not just Path."""
    config = load_scenario_config(str(_TEMPLATES_DIR / "urban_dense.yaml"))
    assert config.scenario_type == ScenarioType.URBAN_DENSE


def test_load_invalid_vehicle_mix_raises_validation_error(tmp_path) -> None:
    """A malformed vehicle_mix (not summing to ~1.0) still surfaces
    ScenarioTypeConfig's own pydantic validation, not silently passing."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text(
        """
scenario_type: urban_dense
road_network:
  avg_block_size: [80.0, 150.0]
  avg_road_width: 12.0
  num_intersections: [4, 9]
  intersection_types: ["4way", "3way"]
buildings:
  building_density: 0.8
  building_heights: [20.0, 40.0]
traffic:
  traffic_density: [0.6, 1.0]
  vehicle_mix:
    sedan: 0.1
complexity_score: 80
"""
    )
    with pytest.raises(ValueError, match="vehicle_mix"):
        load_scenario_config(bad_yaml)


def test_load_missing_scenario_type_raises(tmp_path) -> None:
    """A YAML file with no scenario_type field raises a clear KeyError
    rather than an obscure downstream failure."""
    bad_yaml = tmp_path / "no_type.yaml"
    bad_yaml.write_text("complexity_score: 10\n")
    with pytest.raises(KeyError):
        load_scenario_config(bad_yaml)
