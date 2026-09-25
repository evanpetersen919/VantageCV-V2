"""Load a ``ScenarioTypeConfig`` from one of ``configs/scenario_templates/``'s
own YAML files.

Closes the "YAML templates are reference-only" gap (see
KNOWN_GAPS_AND_ISSUES.md): before this module existed, nothing in the
codebase actually read these files -- every ``ScenarioTypeConfig`` used
in tests, examples, and the user guide was constructed directly in
Python (``docs/user_guide.rst``'s own "Loading a scenario config from
YAML" section documented this as a known gap with a manual workaround).

Only two of the five templates map onto a real, generatable scenario:
``urban_dense.yaml`` and ``urban_sparse.yaml``. ``RoadNetworkGenerator``
implements exactly one generation strategy (perturbed-grid + Delaunay
triangulation, driven by ``avg_block_size``/``num_intersections``/etc.)
regardless of ``ScenarioTypeConfig.scenario_type`` -- it does not branch
on scenario type at all. ``highway.yaml``, ``parking_lot.yaml``, and
``roundabout.yaml`` describe entirely different road-generation
strategies (parallel lanes, a parking stall lattice, a central island)
that were never implemented (see KNOWN_GAPS_AND_ISSUES.md's
"BLOCKER-for-later" entry on Highway and the "No parking spawn zones"
entry) -- their own YAML schemas don't even share ``ScenarioTypeConfig``'s
field names. Loading one of those three raises ``NotImplementedError``
with a message pointing at why, rather than either crashing on a
confusing ``pydantic.ValidationError`` or silently producing a
nonsensical config.
"""

from pathlib import Path
from typing import Any, Dict, Union

import yaml

from src.procedural.scenario import ScenarioType, ScenarioTypeConfig

# The only scenario types RoadNetworkGenerator can actually generate --
# see this module's own docstring.
_SUPPORTED_SCENARIO_TYPES = frozenset({ScenarioType.URBAN_DENSE, ScenarioType.URBAN_SPARSE})


def load_scenario_config(path: Union[str, Path]) -> ScenarioTypeConfig:
    """Load a ``ScenarioTypeConfig`` from a ``configs/scenario_templates/``-
    shaped YAML file.

    Parameters
    ----------
    path : str or Path
        Path to a YAML file shaped like ``configs/scenario_templates/
        urban_dense.yaml`` or ``urban_sparse.yaml`` (a ``road_network:``,
        ``buildings:``, ``traffic:`` section, plus top-level
        ``scenario_type``/``complexity_score``).

    Returns
    -------
    ScenarioTypeConfig

    Raises
    ------
    NotImplementedError
        If the file's ``scenario_type`` is ``highway``, ``parking_lot``,
        or ``roundabout`` -- see this module's own docstring for why.
    ValueError
        If ``scenario_type`` is missing or not a recognized
        ``ScenarioType`` value at all.
    pydantic.ValidationError
        If the mapped fields don't satisfy ``ScenarioTypeConfig``'s own
        validation (e.g. ``vehicle_mix`` not summing to ~1.0).
    """
    with Path(path).open(encoding="utf-8") as handle:
        raw: Dict[str, Any] = yaml.safe_load(handle)

    scenario_type = ScenarioType(raw["scenario_type"])
    if scenario_type not in _SUPPORTED_SCENARIO_TYPES:
        raise NotImplementedError(
            f"ScenarioType.{scenario_type.name} has no real road-network generation "
            "strategy implemented yet (RoadNetworkGenerator only supports the "
            "perturbed-grid + Delaunay approach urban_dense/urban_sparse use) -- "
            "see KNOWN_GAPS_AND_ISSUES.md. Cannot load "
            f"'{raw['scenario_type']}' as a generatable config."
        )

    road_network = raw["road_network"]
    buildings = raw["buildings"]
    traffic = raw["traffic"]

    kwargs: Dict[str, Any] = {
        "scenario_type": scenario_type,
        "avg_block_size": tuple(road_network["avg_block_size"]),
        "avg_road_width": road_network["avg_road_width"],
        "num_intersections": tuple(road_network["num_intersections"]),
        "intersection_types": road_network["intersection_types"],
        "building_density": buildings["building_density"],
        "building_heights": tuple(buildings["building_heights"]),
        "traffic_density": tuple(traffic["traffic_density"]),
        "vehicle_mix": traffic["vehicle_mix"],
        "complexity_score": raw["complexity_score"],
    }
    # Optional: omitted entirely (not defaulted to a literal here) so a
    # template that doesn't set it gets ScenarioTypeConfig's own default
    # from one single place, not two copies of "2.0" that could drift.
    if "road_setback_meters" in buildings:
        kwargs["road_setback_meters"] = buildings["road_setback_meters"]
    if "parking_lot_fraction" in buildings:
        kwargs["parking_lot_fraction"] = buildings["parking_lot_fraction"]

    return ScenarioTypeConfig(**kwargs)
