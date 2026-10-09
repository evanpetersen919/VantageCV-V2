### [RESOLVED] UE5 plugin compiled and loaded into a real UE 5.4.4 editor for the first time
Every prior entry in this file about `unreal_plugin/` being "unverified"
or "never compiled" is now stale for the compile/load step specifically
(runtime behavior of `BuildMeshSection`/`LoadProceduralScenario` is
still unverified -- see their own entries). Dogfooded for real: UE
5.4.4 installed, a fresh C++ host project created at
`F:\UE5Projects\VantageCV_UE5\`, `unreal_plugin/SyntheticDataGen/`
copied into its `Plugins/` folder, and compiled via a real Visual
Studio 2022 build -- not guessed at from documentation.

Found and fixed two real bugs the "never compiled" code had accumulated:
1. `ScenarioMeshBuilder.cpp`'s `BuildMeshSection` declared its empty
   vertex-colors array as `TArray<FLinearColor>`, but
   `UProceduralMeshComponent::CreateMeshSection`'s real signature takes
   `const TArray<FColor>&` (a different overload,
   `CreateMeshSection_LinearColor`, takes `FLinearColor` instead) --
   real compile error (`C2665: no overloaded function could convert all
   the argument types`), not a guess. Fixed by changing the array's
   element type to `FColor`.
2. `SyntheticDataGen.uplugin` used the built-in `ProceduralMeshComponent`
   plugin's module without declaring it as a plugin dependency in the
   `"Plugins"` array -- UnrealBuildTool warned about this rather than
   erroring, but it's the kind of thing that can silently break in a
   packaged build; fixed by adding the dependency entry.

Also required real environment fixes unrelated to this codebase's own
C++ (Visual Studio 2026 was too new for UE5.4's toolchain detection and
had to be uninstalled in favor of VS2022; UE5.4 additionally rejects
VS2022's own default MSVC v143 14.44 toolset with a real compile error
in Engine/Core headers, fixed by installing the older v14.38 toolset
and pinning `UnrealBuildTool`'s `BuildConfiguration.xml` to use it) --
none of that is specific to this project, so not detailed further here.

**Still open, separately**: the editor crashes on normal launch
(`EXCEPTION_ACCESS_VIOLATION` in the D3D12 shader compiler,
`UnrealEditor-ShaderPreprocessor.dll`) on this particular machine,
correlated with a very new (2026-era) NVIDIA driver and Windows 11
build against a mid-2024 engine. Workaround: launch with the `-d3d11`
flag. Not yet root-caused or fixed for real; see whoever picks this
back up for the exact driver/build versions involved before assuming
it's resolved.

