"""Phase 0 exit-criteria tests: project structure, config, environment."""

import sys
from pathlib import Path

import pytest
import toml

REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_DIRS = [
    "src/procedural",
    "src/ue5",
    "src/sensors",
    "src/ground_truth",
    "src/export",
    "src/validation",
    "src/orchestration",
    "src/utils",
    "tests/unit",
    "tests/integration",
    "tests/performance",
    "configs/scenario_templates",
    "configs/sensor_profiles",
    "docs",
    "bin",
    "unreal_plugin/SyntheticDataGen/Source/SyntheticDataGen",
]

REQUIRED_PYTHON_PACKAGES = [
    "src",
    "src/procedural",
    "src/ue5",
    "src/sensors",
    "src/ground_truth",
    "src/export",
    "src/validation",
    "src/orchestration",
    "src/utils",
]


@pytest.mark.parametrize("dir_name", REQUIRED_DIRS)
def test_required_directory_exists(dir_name: str) -> None:
    """Every directory in the Phase 0 project layout must exist."""
    assert (REPO_ROOT / dir_name).is_dir(), f"Missing directory: {dir_name}"


@pytest.mark.parametrize("pkg_dir", REQUIRED_PYTHON_PACKAGES)
def test_python_package_has_init(pkg_dir: str) -> None:
    """Every src/ subpackage must have an __init__.py."""
    init_file = REPO_ROOT / pkg_dir / "__init__.py"
    assert init_file.is_file(), f"Missing __init__.py: {pkg_dir}"


def test_pyproject_toml_valid() -> None:
    """pyproject.toml must be valid TOML with the expected Poetry metadata."""
    config = toml.load(REPO_ROOT / "pyproject.toml")
    assert "tool" in config
    assert "poetry" in config["tool"]
    assert config["tool"]["poetry"]["version"] == "0.1.0"
    assert config["tool"]["poetry"]["dependencies"]["python"] == "^3.11"


def test_git_initialized() -> None:
    """The project must be under git version control."""
    assert (REPO_ROOT / ".git").exists(), "Git not initialized"


def test_gitignore_exists() -> None:
    """A .gitignore must be present to exclude build artifacts."""
    assert (REPO_ROOT / ".gitignore").is_file()


def test_python_version() -> None:
    """The interpreter running the tests must be Python 3.11.x."""
    assert sys.version_info >= (3, 11), "Python version too old"
    assert sys.version_info < (3, 13), "Python version too new for pinned dependencies"


def test_ue5_plugin_descriptor_exists() -> None:
    """The UE5 plugin .uplugin descriptor must exist."""
    plugin_file = REPO_ROOT / "unreal_plugin" / "SyntheticDataGen" / "SyntheticDataGen.uplugin"
    assert plugin_file.is_file(), "Missing .uplugin descriptor"


def test_ue5_build_cs_exists() -> None:
    """The UE5 plugin module's Build.cs must exist."""
    build_cs = (
        REPO_ROOT
        / "unreal_plugin"
        / "SyntheticDataGen"
        / "Source"
        / "SyntheticDataGen"
        / "SyntheticDataGen.Build.cs"
    )
    assert build_cs.is_file(), "Missing SyntheticDataGen.Build.cs"


def test_ci_workflow_exists() -> None:
    """The GitHub Actions lint/test workflow must exist."""
    workflow = REPO_ROOT / ".github" / "workflows" / "lint_and_test.yml"
    assert workflow.is_file(), "Missing CI workflow"


def test_scenario_template_configs_exist() -> None:
    """All five scenario taxonomy templates from Section 1.3 must exist."""
    templates_dir = REPO_ROOT / "configs" / "scenario_templates"
    expected = {
        "urban_dense.yaml",
        "urban_sparse.yaml",
        "highway.yaml",
        "parking_lot.yaml",
        "roundabout.yaml",
    }
    actual = {p.name for p in templates_dir.glob("*.yaml")}
    missing = expected - actual
    assert not missing, f"Missing scenario templates: {missing}"
