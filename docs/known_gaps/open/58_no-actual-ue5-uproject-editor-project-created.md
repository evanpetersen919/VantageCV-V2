### [RESOLVED] No actual UE5 `.uproject` / editor project created
Was: MASTER_PROMPT 3.1.1 calls for creating the UE5 project itself via
`RunUAT.sh BuildProject`; not done since no UE5 was installed anywhere
this project had been worked on.

Resolved 2026-09-15: a real host C++ project now exists at
`F:\UE5Projects\VantageCV_UE5\` (created via the editor's New Project
flow rather than `RunUAT BuildProject`, since that's the normal
interactive path and nothing required the automated one specifically)
with `unreal_plugin/SyntheticDataGen/` installed into its `Plugins/`
folder and compiling successfully.

