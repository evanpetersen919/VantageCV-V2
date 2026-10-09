### [DEFERRED] Master prompt Section 3.3 (Phase 2) has no algorithms, formulas, code, or tests -- unlike Phase 1
MASTER_PROMPT_PROCEDURAL_AV_DATASET_GENERATOR.md's Phase 2 section is
literally four bullet points per sub-area (lane topology, building
placement) plus a one-line "Tests:" list of topics, with a note saying
"(Similar structure to Phase 1, with extensive mathematical formulations
and tests)" that is never actually delivered. This is a real gap in the
spec itself. `lane_topology.py` and `building_placement.py` were designed
from scratch this phase, informed by QOL_RESEARCH_CHECKLIST.md Section B.2
(lane boundaries) and B.3 (building placement), which do give concrete
formulas/example tests (with two more bugs of their own -- see Resolved).

