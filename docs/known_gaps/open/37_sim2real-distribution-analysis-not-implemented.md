### [DEFERRED] Sim2real distribution analysis not implemented
MASTER_PROMPT Section 3.7 lists "Sim2real distribution analysis" as a
bullet, and Section 1.1's architecture diagram lists a "Sim2Real
Validator (domain gap analysis)." Not implemented: doing this
meaningfully requires a real reference dataset to compare distributions
against (e.g. real building-height distributions, real traffic patterns),
and none exists anywhere in this codebase or its dependencies -- CLAUDE_
SKILLS_AND_PROMPTS.md's own Skill 13 (Sim2Real Validation) prompt template
explicitly expects the user to supply reference data, which nobody has
in this context. `sanity_checker.py`'s `check_building_height_distribution`
is the closest analogue actually implemented: it compares generated
output against the *configured* distribution (not a real-world one),
which is a real, useful check but not sim2real analysis in the sense the
spec means.

