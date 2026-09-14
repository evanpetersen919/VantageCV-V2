User Guide
==========

Installation
------------

.. code-block:: bash

   git clone https://github.com/evanpetersen919/VantageCV-V2.git
   cd VantageCV-V2
   poetry install
   poetry run pytest --cov=src tests/

Requires Python 3.11.8 and `Poetry <https://python-poetry.org/>`_. See
``KNOWN_GAPS_AND_ISSUES.md`` if ``poetry run pytest`` (the bare form)
doesn't pick up a module you just added -- run ``poetry install`` again
first.

These exact steps are what every phase of this project was verified
against (a genuinely fresh ``git clone`` + ``poetry install``, not just
"works on my machine") before being pushed -- see the commit history for
the repeated fresh-clone verification this involved.

Quick start: generate a road network
--------------------------------------

Every code block on this page is a real ``doctest`` block, executed by
``sphinx-build -b doctest docs docs/_build/doctest`` as part of this
project's own CI-equivalent checks -- not prose that might silently go
stale. If you change the underlying API and these examples stop
matching, the docs build fails, the same way a broken test would.

.. doctest::

   >>> from src.procedural.scenario import ScenarioType, ScenarioTypeConfig
   >>> from src.procedural.road_network import RoadNetworkGenerator
   >>>
   >>> config = ScenarioTypeConfig(
   ...     scenario_type=ScenarioType.URBAN_DENSE,
   ...     avg_block_size=(100.0, 150.0),
   ...     avg_road_width=12.0,
   ...     num_intersections=(4, 9),
   ...     intersection_types=["4way", "3way"],
   ...     building_density=0.8,
   ...     building_heights=(20.0, 40.0),
   ...     traffic_density=(0.6, 1.0),
   ...     vehicle_mix={"sedan": 0.6, "suv": 0.25, "truck": 0.1, "bus": 0.05},
   ...     complexity_score=80,
   ... )
   >>> bounds = (-250.0, -250.0, 250.0, 250.0)
   >>>
   >>> generator = RoadNetworkGenerator(seed=42, config=config)
   >>> nodes, edges = generator.generate(bounds)
   >>> len(nodes) > 0
   True
   >>> len(edges) > 0
   True

``seed=42`` with this exact ``config``/``bounds`` always produces the
same network -- that's the whole point of seeded, deterministic
generation (see :doc:`architecture`). Run it again and you'll get
identical ``nodes``/``edges``, not just the same counts.

Generating a full scenario end-to-end
----------------------------------------

:func:`src.orchestration.dataset_generator.generate_scenario` chains
every procedural layer together (road network, lanes, buildings, traffic,
meshes) and validates the result before returning it:

.. doctest::

   >>> from src.orchestration.dataset_generator import generate_scenario
   >>>
   >>> scenario = generate_scenario(
   ...     seed=42, config=config, bounds=bounds, scenario_id="quickstart"
   ... )
   >>> scenario.validation_report.is_valid
   True
   >>> len(scenario.buildings) > 0
   True
   >>> len(scenario.meshes) > 0
   True

If the generated scenario fails :class:`src.procedural.validator.ScenarioValidator`
(shouldn't happen for any config this pipeline can produce today --
see :func:`src.procedural.road_network.RoadNetworkGenerator.generate`'s
own bounds-containment guarantee), ``generate_scenario`` raises
``ValueError`` rather than returning something invalid.

Generating and exporting a small dataset
-------------------------------------------

:func:`src.orchestration.dataset_generator.generate_dataset` generates
several scenarios, renders one camera frame each, and writes a COCO
dataset to disk:

.. code-block:: python

   from pathlib import Path
   from src.orchestration.dataset_generator import generate_dataset

   result = generate_dataset(
       num_scenarios=10,
       base_seed=0,
       config=config,
       bounds=bounds,
       output_dir=Path("./datasets/synthetic_v1"),
   )
   print(result.coco_path)        # datasets/synthetic_v1/annotations.json
   print(result.num_frames)       # 10
   print(result.sanity_report.is_healthy)

Not a doctest (writes real files to disk, which isn't appropriate for a
docs build) -- see
``tests/integration/test_dataset_generator.py::test_generate_dataset_end_to_end``
for the equivalent, actually-executed version of this exact call.

Parallel generation
----------------------

:func:`src.orchestration.distributed_runner.generate_dataset_distributed`
is a drop-in parallel replacement, using Ray's local (CPU-core) scheduler
-- no cluster or GPU required:

.. code-block:: python

   from src.orchestration.distributed_runner import generate_dataset_distributed

   result = generate_dataset_distributed(
       num_scenarios=100,
       base_seed=0,
       config=config,
       bounds=bounds,
       output_dir=Path("./datasets/synthetic_v1"),
       num_workers=4,
   )

Produces byte-identical output to the sequential version for the same
arguments -- verified directly in
``tests/integration/test_distributed_runner.py::test_output_consistency_single_vs_distributed``.
See :doc:`performance_tuning` for when this is actually worth using.

Resumable generation
------------------------

If a long-running generation job might be interrupted,
:func:`src.orchestration.resume_handler.generate_dataset_resumable` skips
scenarios already recorded as complete in a checkpoint file:

.. code-block:: python

   from src.orchestration.resume_handler import generate_dataset_resumable

   result = generate_dataset_resumable(
       num_scenarios=1000,
       base_seed=0,
       config=config,
       bounds=bounds,
       output_dir=Path("./datasets/synthetic_v1"),
   )
   # If interrupted (crash, Ctrl-C, out of time) and re-run with the same
   # arguments, already-completed scenarios are loaded from disk rather
   # than regenerated -- see test_resume_handler.py's mocked call-count
   # assertions, which confirm this isn't just re-deriving the same
   # result a second time.

Loading a scenario config from YAML
---------------------------------------

The five scenario templates under ``configs/scenario_templates/`` (urban
dense, urban sparse, highway, parking lot, roundabout) match
:class:`src.procedural.scenario.ScenarioTypeConfig`'s fields. Load one
with PyYAML plus a small mapping step -- there's no ``ScenarioTypeConfig
.from_yaml`` helper yet (this codebase reads the YAML config templates as
reference/documentation of each scenario type's intended parameters
rather than loading them directly at runtime; see
``KNOWN_GAPS_AND_ISSUES.md`` if you build one):

.. code-block:: python

   import yaml

   with open("configs/scenario_templates/urban_dense.yaml") as f:
       raw = yaml.safe_load(f)
   # raw["road_network"]["avg_block_size"], raw["buildings"]["building_density"],
   # etc. -- map these onto ScenarioTypeConfig's constructor fields yourself
   # for now.
