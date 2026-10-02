"""Pre-flight check for the cluster: every image and label file each data file refers to exists.

Run after ``hpc_make_data.py`` and before submitting jobs, so a wrong path shows up in seconds
instead of after a job has queued and failed. Prints the number of training and validation
images per data file (compare with the expected counts in ``hpc/README.md``) and exits non-zero
if anything is missing.

    python bin/hpc_check_data.py --yaml-dir /scratch/me/vantagecv_yaml
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

from src.evaluation.portable import missing_files


def _as_list(value: Any) -> List[Path]:
    """A data file's ``train`` entry (one path or a list of paths) as a list of paths."""
    return [Path(item) for item in (value if isinstance(value, list) else [value])]


def main() -> None:
    """Check every ``*.yaml`` in the folder; exit 1 if any referenced file is missing."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--yaml-dir", type=Path, required=True)
    args = parser.parse_args()

    failed = False
    for path in sorted(args.yaml_dir.glob("*.yaml")):
        spec: Dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
        counts, problems = [], []
        for entry in (spec["train"], spec["val"]):
            lists = _as_list(entry)
            counts.append(
                sum(
                    len(item.read_text(encoding="utf-8").split()) for item in lists if item.exists()
                )
            )
            for list_path in lists:
                problems += (
                    missing_files(list_path)
                    if list_path.exists()
                    else [f"list missing: {list_path}"]
                )
        status = "OK" if not problems else f"{len(problems)} PROBLEM(S)"
        print(f"{path.name:22s} train {counts[0]:5d}  val {counts[1]:4d}  {status}")
        for problem in problems[:5]:
            print(f"    {problem}")
        failed = failed or bool(problems)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
