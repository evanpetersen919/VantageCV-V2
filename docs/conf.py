"""Sphinx configuration for the Synthetic AV Dataset Generator docs.

Implements MASTER_PROMPT Section 3.9's "Complete API documentation
(Sphinx)" bullet. API reference pages are generated via ``autodoc`` +
``napoleon`` directly from this codebase's own docstrings (every module
in ``src/`` already carries full NumPy-style docstrings written during
Phases 1-7, so this configuration mostly just needs to point Sphinx at
them, not write new documentation content from scratch).
"""

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "Synthetic AV Dataset Generator"
copyright = "2026, Evan Petersen"  # pylint: disable=redefined-builtin
author = "Evan Petersen"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.doctest",
    "sphinxcontrib.mermaid",
]

# doctest: user_guide.rst's code examples are real `.. doctest::` blocks,
# actually executed by `sphinx-build -b doctest docs docs/_build/doctest`
# -- this is what makes MASTER_PROMPT Section 3.9's "Code examples in
# docs execute correctly" test bullet a real, automated check rather
# than a claim nobody verifies.
doctest_global_setup = "import numpy as np"

# Napoleon is configured for NumPy-style docstrings specifically, since
# that's the convention used throughout src/ (see e.g.
# road_network.py's own docstrings).
napoleon_numpy_docstring = True
napoleon_google_docstring = False
# napoleon's default "Attributes" rendering registers each dataclass
# field as its own cross-referenceable object, which then collides with
# autodoc's own (separate) documentation of the same dataclass fields --
# `sphinx-build` reported this as real "duplicate object description"
# warnings against this codebase's actual dataclasses (RoadNode,
# BoundingBox3D, LidarConfig, etc.), not a hypothetical. napoleon_use_ivar
# renders attributes as plain :ivar: field-list entries instead, which
# doesn't register a duplicate target.
napoleon_use_ivar = True

autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
# "signature" (type hints shown on the function signature line only)
# rather than "description" (hints also re-parsed into the body text,
# where a type like npt.NDArray[np.bool_] gets treated as an attempted
# cross-reference and broke the build with "Unknown target name: np.bool"
# -- confirmed by an actual sphinx-build run, not assumed).
autodoc_typehints = "signature"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
