#!/usr/bin/env python
"""Command-line entry point for procedural dataset generation.

Implements MASTER_PROMPT Section 3.1's file tree bullet
``bin/generate_dataset.py`` -- a thin argparse wrapper around
``src.orchestration.dataset_generator.generate_dataset``, the only
capability this pipeline needs a CLI for (see KNOWN_GAPS_AND_ISSUES.md:
the other four ``bin/*.py`` scripts the master prompt lists --
``validate_dataset.py``, ``profile_performance.py``,
``visualize_scenarios.py``, ``compare_sim2real.py`` -- have no
corresponding standalone capability in this codebase to wrap; building
them would mean inventing functionality this project doesn't otherwise
have, not exposing something that already exists).

Example
-------
.. code-block:: bash

   python bin/generate_dataset.py \\
       --config configs/scenario_templates/urban_dense.yaml \\
       --num-scenarios 10 \\
       --base-seed 0 \\
       --bounds -250 -250 250 250 \\
       --output-dir ./datasets/synthetic_v1
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

# Running this file directly (`python bin/generate_dataset.py`) puts
# bin/ itself on sys.path, not the repo root -- `import src...` would
# otherwise fail. Must happen before the src imports below.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# pylint: disable=wrong-import-position
from src.orchestration.dataset_generator import generate_dataset
from src.utils.config_loader import load_scenario_config

# pylint: enable=wrong-import-position


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a procedural synthetic AV perception dataset."
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to a configs/scenario_templates/-shaped YAML file "
        "(only urban_dense/urban_sparse-typed templates are currently "
        "generatable -- see KNOWN_GAPS_AND_ISSUES.md).",
    )
    parser.add_argument(
        "--num-scenarios", required=True, type=int, help="Number of scenarios to generate."
    )
    parser.add_argument(
        "--base-seed",
        default=0,
        type=int,
        help="First scenario's seed; scenario N uses seed base_seed + N. Default: 0.",
    )
    parser.add_argument(
        "--bounds",
        required=True,
        nargs=4,
        type=float,
        metavar=("X_MIN", "Y_MIN", "X_MAX", "Y_MAX"),
        help="Scenario generation bounds in meters.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory to write annotations.json and per-scenario metadata into "
        "(created if missing).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """Parse arguments, run generation, print a summary. Returns the
    process exit code (0 on success, 1 on an expected failure mode --
    bad config path/shape, generation itself raising -- printed as a
    clean message rather than a raw traceback)."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    try:
        config = load_scenario_config(args.config)
    except (FileNotFoundError, NotImplementedError, ValueError) as exc:
        print(f"Error loading --config {args.config}: {exc}", file=sys.stderr)
        return 1

    x_min, y_min, x_max, y_max = args.bounds

    try:
        result = generate_dataset(
            num_scenarios=args.num_scenarios,
            base_seed=args.base_seed,
            config=config,
            bounds=(x_min, y_min, x_max, y_max),
            output_dir=args.output_dir,
        )
    except ValueError as exc:
        print(f"Error during generation: {exc}", file=sys.stderr)
        return 1

    print(
        f"Generated {result.num_scenarios} scenarios ({result.num_frames} frames) "
        f"in {result.elapsed_seconds:.1f}s"
    )
    print(f"COCO annotations: {result.coco_path}")
    print(f"Metadata files: {len(result.metadata_paths)}")
    if not result.sanity_report.is_healthy:
        print(
            f"WARNING: {len(result.sanity_report.outlier_frame_ids)} frame(s) flagged as "
            "annotation-count outliers -- see the sanity report for details.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
