"""Integration tests for bin/generate_dataset.py.

Runs the actual CLI as a subprocess (not by importing its main()
directly) -- this is the only way to genuinely verify argparse wiring,
the sys.path fixup for running the script directly, and the process
exit code a real user would see.
"""

import json
import subprocess
import sys
from pathlib import Path

from pycocotools.coco import COCO

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CLI_PATH = _REPO_ROOT / "bin" / "generate_dataset.py"
_URBAN_DENSE_CONFIG = _REPO_ROOT / "configs" / "scenario_templates" / "urban_dense.yaml"
_HIGHWAY_CONFIG = _REPO_ROOT / "configs" / "scenario_templates" / "highway.yaml"


def _run_cli(args: list) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_CLI_PATH), *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_cli_generates_real_dataset(tmp_path) -> None:
    """A successful run exits 0, prints a summary, and writes a real,
    schema-valid COCO dataset plus metadata files."""
    output_dir = tmp_path / "out"
    result = _run_cli(
        [
            "--config",
            str(_URBAN_DENSE_CONFIG),
            "--num-scenarios",
            "2",
            "--base-seed",
            "0",
            "--bounds",
            "-250",
            "-250",
            "250",
            "250",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert result.returncode == 0, result.stderr
    assert "Generated 2 scenarios" in result.stdout

    coco_path = output_dir / "annotations.json"
    assert coco_path.exists()
    coco = COCO(str(coco_path))
    assert len(coco.getImgIds()) == 2

    for i in range(2):
        metadata_path = output_dir / f"proc_scenario_{i:04d}_metadata.json"
        data = json.loads(metadata_path.read_text())
        assert data["seed"] == i


def test_cli_unsupported_scenario_type_exits_nonzero_with_clean_message(tmp_path) -> None:
    """An unsupported scenario type (highway/parking_lot/roundabout)
    exits 1 with a clear stderr message, not a raw traceback."""
    result = _run_cli(
        [
            "--config",
            str(_HIGHWAY_CONFIG),
            "--num-scenarios",
            "1",
            "--bounds",
            "-100",
            "-100",
            "100",
            "100",
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "no real road-network generation" in result.stderr


def test_cli_missing_config_exits_nonzero_with_clean_message(tmp_path) -> None:
    """A nonexistent --config path exits 1 with a clean message, not a
    raw traceback."""
    result = _run_cli(
        [
            "--config",
            str(tmp_path / "does_not_exist.yaml"),
            "--num-scenarios",
            "1",
            "--bounds",
            "-100",
            "-100",
            "100",
            "100",
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )

    assert result.returncode == 1
    assert "Traceback" not in result.stderr


def test_cli_missing_required_argument_exits_nonzero() -> None:
    """argparse itself rejects a missing required argument (--bounds)
    with the standard argparse exit code (2), before generation ever runs."""
    result = _run_cli(
        [
            "--config",
            str(_URBAN_DENSE_CONFIG),
            "--num-scenarios",
            "1",
            "--output-dir",
            "/tmp/unused",
        ]
    )

    assert result.returncode == 2
    assert "--bounds" in result.stderr


def test_cli_default_base_seed_is_zero(tmp_path) -> None:
    """Omitting --base-seed defaults to 0, matching generate_dataset's own default."""
    output_dir = tmp_path / "out"
    result = _run_cli(
        [
            "--config",
            str(_URBAN_DENSE_CONFIG),
            "--num-scenarios",
            "1",
            "--bounds",
            "-250",
            "-250",
            "250",
            "250",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert result.returncode == 0, result.stderr
    metadata = json.loads((output_dir / "proc_scenario_0000_metadata.json").read_text())
    assert metadata["seed"] == 0
