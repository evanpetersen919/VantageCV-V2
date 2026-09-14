"""Integration tests that the Sphinx documentation actually builds.

Covers MASTER_PROMPT Section 3.9's own "Documentation builds without
errors" and "Code examples in docs execute correctly" test bullets as
real, CI-enforced checks -- not something verified once by hand and then
left to drift. If a docstring or a user_guide.rst doctest example stops
matching the real API, these tests fail the same way any other test
would.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"


def test_docs_html_build_succeeds(tmp_path) -> None:
    """`sphinx-build -b html` completes with exit code 0 and no warnings
    -- autodoc successfully imports every module in src/ (a real import
    error there would fail this), and every cross-reference resolves."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-b",
            "html",
            "-W",  # treat warnings as errors: a silent new warning should fail this test
            str(DOCS_DIR),
            str(tmp_path / "html"),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert (
        result.returncode == 0
    ), f"sphinx-build -b html failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert (tmp_path / "html" / "index.html").exists()


def test_docs_doctest_examples_execute_correctly(tmp_path) -> None:
    """`sphinx-build -b doctest` actually runs every `.. doctest::` block
    in user_guide.rst and confirms its printed output matches -- these
    are real, executed code examples, not documentation prose that could
    silently stop matching the real API."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-b",
            "doctest",
            str(DOCS_DIR),
            str(tmp_path / "doctest"),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert (
        result.returncode == 0
    ), f"sphinx-build -b doctest failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    output_file = tmp_path / "doctest" / "output.txt"
    assert output_file.exists()
    output_text = output_file.read_text(encoding="utf-8")
    assert "0 failures in tests" in output_text
