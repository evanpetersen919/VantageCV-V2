"""Import files into the Unreal project with the ImportAssets commandlet (game closed)."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

UE_EDITOR_CMD = Path("F:/UE_5.4/Engine/Binaries/Win64/UnrealEditor-Cmd.exe")
UE_PROJECT = Path("F:/UE5Projects/VantageCV_UE5/VantageCV_UE5.uproject")


def import_group(name: str, files: Sequence[str], destination: str) -> Dict[str, Any]:
    """One ImportAssets group: ``files`` brought into the content folder ``destination``."""
    return {
        "GroupName": name,
        "Filenames": list(files),
        "DestinationPath": destination,
        "bReplaceExisting": True,
        "bSkipReadOnly": True,
    }


def run_import(groups: List[Dict[str, Any]], settings: Path) -> Tuple[int, List[str]]:
    """Write ``settings`` and run the commandlet; return (exit code, error lines)."""
    settings.write_text(json.dumps({"ImportGroups": groups}, indent=1), encoding="utf-8")
    environment = {k: v for k, v in os.environ.items() if k != "ELECTRON_RUN_AS_NODE"}
    command = [
        str(UE_EDITOR_CMD),
        str(UE_PROJECT),
        "-run=ImportAssets",
        f"-importsettings={settings.resolve().as_posix()}",
        "-unattended",
        "-nosplash",
        "-nullrhi",
    ]
    result = subprocess.run(command, env=environment, capture_output=True, text=True, check=False)
    errors = [
        line
        for line in result.stdout.splitlines()
        if "Error" in line and "revision control" not in line
    ]
    return result.returncode, errors


def report_import(code: int, errors: List[str], count: int) -> None:
    """Print one line for the import and the first error lines."""
    print(f"exit {code}; {count} files; {len(errors)} error lines")
    for line in errors[:10]:
        print("  ", line[:200])
