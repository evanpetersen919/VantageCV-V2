// Copyright: SyntheticDataGen plugin. See MASTER_PROMPT Section 2.3 for
// dependency justification. C++20, UE5.4 LTS.

using UnrealBuildTool;

public class SyntheticDataGen : ModuleRules
{
	public SyntheticDataGen(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		CppStandard = CppStandardVersion.Cpp20;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"ProceduralMeshComponent",
			"AIModule",
			"NavigationSystem",
			"RenderCore",
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"Networking",
			"Sockets",
			"Json",
			"JsonUtilities",
		});
	}
}
