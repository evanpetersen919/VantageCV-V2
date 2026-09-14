API Reference
=============

Every page below is generated directly from this codebase's own
docstrings via Sphinx's ``autodoc`` + ``napoleon`` extensions -- nothing
here is hand-duplicated documentation that could drift from the actual
code. If a docstring is wrong or missing here, fix it in the module
itself, not this file.

Procedural Generation (Phases 1-3)
-----------------------------------

.. automodule:: src.procedural.road_network
   :members:

.. automodule:: src.procedural.scenario
   :members:

.. automodule:: src.procedural.math_utils
   :members:

.. automodule:: src.procedural.lane_topology
   :members:

.. automodule:: src.procedural.building_placement
   :members:

.. automodule:: src.procedural.traffic_network
   :members:

.. automodule:: src.procedural.actor_placement
   :members:

.. automodule:: src.procedural.mesh_factory
   :members:

.. automodule:: src.procedural.validator
   :members:

UE5 Integration (Phase 4)
--------------------------

.. automodule:: src.ue5.backend
   :members:

Sensors & Ground Truth (Phase 5)
----------------------------------

.. automodule:: src.sensors.camera_model
   :members:

.. automodule:: src.sensors.lidar_model
   :members:

.. automodule:: src.ground_truth.categories
   :members:

.. automodule:: src.ground_truth.bbox_3d
   :members:

.. automodule:: src.ground_truth.bbox_2d
   :members:

.. automodule:: src.ground_truth.depth_map
   :members:

.. automodule:: src.ground_truth.segmentation
   :members:

Export & Validation (Phase 6)
-------------------------------

.. automodule:: src.export.coco_exporter
   :members:

.. automodule:: src.export.metadata_manager
   :members:

.. automodule:: src.validation.sanity_checker
   :members:

Orchestration & Distributed Generation (Phases 6-7)
-----------------------------------------------------

.. automodule:: src.orchestration.dataset_generator
   :members:

.. automodule:: src.orchestration.distributed_runner
   :members:

.. automodule:: src.orchestration.resume_handler
   :members:
