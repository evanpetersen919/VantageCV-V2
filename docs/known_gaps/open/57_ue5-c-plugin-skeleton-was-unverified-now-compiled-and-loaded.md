### [RESOLVED] UE5 C++ plugin skeleton was unverified — now compiled and loaded for real
Was: `unreal_plugin/SyntheticDataGen/` structurally looked like standard
UE5 module boilerplate but had never been opened in Unreal Editor or
compiled, since no UE5 install existed in any environment this project
had been built in.

Resolved 2026-09-15: a real UE 5.4.4 install + Visual Studio 2022
toolchain was set up, the plugin was compiled, and it loads cleanly
into the editor with no errors. Two real bugs were found and fixed in
the process (an `FColor`/`FLinearColor` mismatch in
`CreateMeshSection`'s call site; a missing `ProceduralMeshComponent`
plugin dependency declaration) -- see the "[RESOLVED] UE5 plugin
compiled and loaded" entry above for full detail. Confirms the risk
this entry predicted ("Build.cs dependency names... could be subtly
wrong in ways only the UE5 toolchain would catch") was real, not
hypothetical.

