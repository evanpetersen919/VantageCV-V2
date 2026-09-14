"""Per-scenario metadata aggregation for reproducibility tracking.

Implements MASTER_PROMPT Section 3.7's "Metadata aggregation" bullet,
directly per QOL_RESEARCH_CHECKLIST.md Section J.1's own prescribed
metadata shape (scenario_id, seed, git_commit, git_tag, config_version,
python_version, numpy_version).
"""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import numpy

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_git(*args: str) -> Optional[str]:
    """Run a git command anchored at the repo root (not the caller's own
    working directory, which may differ) and return its stripped stdout,
    or None if git isn't available or the command fails (e.g. no commits
    yet, or not actually a git repository) -- metadata should degrade
    gracefully rather than crash generation over a missing git tag."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() or None


@dataclass(frozen=True)
class ScenarioMetadata:
    """Everything needed to reproduce or trace one generated scenario."""

    scenario_id: str
    seed: int
    config_version: str
    git_commit: Optional[str]
    git_tag: Optional[str]
    python_version: str
    numpy_version: str

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation."""
        return {
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "config_version": self.config_version,
            "git_commit": self.git_commit,
            "git_tag": self.git_tag,
            "python_version": self.python_version,
            "numpy_version": self.numpy_version,
        }


def build_scenario_metadata(scenario_id: str, seed: int, config_version: str) -> ScenarioMetadata:
    """Build a ScenarioMetadata snapshot for the current environment.

    Parameters
    ----------
    scenario_id : str
        A stable identifier for this scenario (e.g. "proc_scenario_0001").
    seed : int
        The generation seed used.
    config_version : str
        The ``version`` field from the scenario's YAML config template
        (e.g. ``configs/scenario_templates/urban_dense.yaml``'s own
        ``version: "1.0"``).
    """
    return ScenarioMetadata(
        scenario_id=scenario_id,
        seed=seed,
        config_version=config_version,
        git_commit=_run_git("rev-parse", "HEAD"),
        git_tag=_run_git("describe", "--tags"),
        python_version=".".join(str(part) for part in sys.version_info[:3]),
        numpy_version=numpy.__version__,
    )
