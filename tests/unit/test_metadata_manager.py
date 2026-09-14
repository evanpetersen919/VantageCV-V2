"""Unit tests for scenario metadata aggregation."""

import json
import sys

from src.export.metadata_manager import build_scenario_metadata


def test_metadata_fields_populated() -> None:
    """All required fields are present in the resulting metadata."""
    metadata = build_scenario_metadata("proc_scenario_0001", seed=42, config_version="1.0")

    assert metadata.scenario_id == "proc_scenario_0001"
    assert metadata.seed == 42
    assert metadata.config_version == "1.0"


def test_metadata_python_version_matches_runtime() -> None:
    """python_version matches the interpreter actually running the test."""
    metadata = build_scenario_metadata("s", seed=1, config_version="1.0")
    expected = ".".join(str(part) for part in sys.version_info[:3])
    assert metadata.python_version == expected


def test_metadata_numpy_version_is_nonempty_string() -> None:
    """numpy_version is populated (exact value not asserted -- pinned in
    pyproject.toml, not this test's concern)."""
    metadata = build_scenario_metadata("s", seed=1, config_version="1.0")
    assert isinstance(metadata.numpy_version, str)
    assert len(metadata.numpy_version) > 0


def test_metadata_git_commit_populated_in_this_repo() -> None:
    """Running inside an actual git repo with commits, git_commit is a
    40-character hex SHA, not None."""
    metadata = build_scenario_metadata("s", seed=1, config_version="1.0")
    assert metadata.git_commit is not None
    assert len(metadata.git_commit) == 40
    assert all(c in "0123456789abcdef" for c in metadata.git_commit)


def test_metadata_to_dict_is_json_serializable() -> None:
    """to_dict() produces a plain dict of JSON-safe values."""
    metadata = build_scenario_metadata("s", seed=1, config_version="1.0")
    data = metadata.to_dict()

    assert isinstance(data, dict)
    json_str = json.dumps(data)
    parsed = json.loads(json_str)
    assert parsed["scenario_id"] == "s"
    assert parsed["seed"] == 1


def test_metadata_different_seeds_independent() -> None:
    """Metadata correctly reflects different seeds without leaking state
    between calls."""
    meta1 = build_scenario_metadata("s1", seed=1, config_version="1.0")
    meta2 = build_scenario_metadata("s2", seed=2, config_version="2.0")

    assert meta1.seed == 1
    assert meta2.seed == 2
    assert meta1.config_version == "1.0"
    assert meta2.config_version == "2.0"
