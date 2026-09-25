#include "ProceduralMesh/MaterialResolver.h"
#include "Materials/MaterialInterface.h"

DEFINE_LOG_CATEGORY_STATIC(LogMaterialResolver, Log, All);

namespace
{
	// Mirrors configs/material_tags.json's "tags" object's "asset_path"
	// values exactly -- see that file and MaterialResolver.h's own
	// comments for why this is hand-kept in sync rather than parsed at
	// runtime. tests/unit/test_material_tags_coverage.py (Python side)
	// keeps every tag src/procedural can actually emit present in that
	// JSON file; keeping this TMap's keys matching that file's keys is
	// this function's own responsibility.
	const TMap<FString, FString>& GetTagToAssetPath()
	{
		static const TMap<FString, FString> TagToAssetPath = {
			{TEXT("asphalt"), TEXT("/Game/Road/Material/MI/M_Asphalt_Master_Inst_ParkingLots")},
			{TEXT("ground"), TEXT("/Game/Road/Material/MI/M_Asphalt_Master_Inst_ParkingLots")},
			{TEXT("pavement"), TEXT("/Game/Road/Material/MI/M_Sidewalk_Master_Inst")},
			{TEXT("paint_white"), TEXT("/Game/VantageCV/M_PaintWhite")},
			{TEXT("roof_0"), TEXT("/Game/Environment/RoofTop/Material/MI/MI_Rooftop_BitumenRoofing")},
			{TEXT("roof_1"), TEXT("/Game/Environment/RoofTop/Material/MI/MI_Rooftop_DirtyConcreteTiles")},
			{TEXT("roof_2"), TEXT("/Game/Environment/RoofTop/Material/MI/MI_Rooftop_PebbleDash")},
			{TEXT("roof_3"), TEXT("/Game/Environment/RoofTop/Material/MI/MI_Rooftop_RoofTile")},
			{TEXT("brick"), TEXT("/Game/Building/Material/MI/Brick/MI_Bldg_BrickOffset_Red")},
			{TEXT("wood_siding"), TEXT("/Game/Building/Material/MI/Wood/MI_Bldg_Wood_Cedar")},
			{TEXT("stucco"), TEXT("/Game/Building/Material/MI/Paint/MI_Bldg_PaintedStone_Beige")},
			{TEXT("concrete"), TEXT("/Game/Building/Material/MI/Concrete/MI_Bldg_Concrete_Dirty")},
			{TEXT("glass_curtain_wall"), TEXT("/Game/Building/Material/MI/Glass/MI_Bldg_glass_opaque")},
			{TEXT("metal_panel"), TEXT("/Game/Building/Material/MI/Metal/MI_Bldg_Metal_Brushed")},
			{TEXT("vehicle_paint"), TEXT("/Game/Building/Material/MI/Paint/MI_Bldg_PaintedMetal_Red")},
			{TEXT("pedestrian"), TEXT("/Game/Building/Material/MI/Paint/MI_Bldg_PaintedMetal_Grey")},
		};
		return TagToAssetPath;
	}
} // namespace

TMap<FString, UMaterialInterface*>& FMaterialResolver::GetCache()
{
	static TMap<FString, UMaterialInterface*> Cache;
	return Cache;
}

UMaterialInterface* FMaterialResolver::Resolve(const FString& Tag)
{
	TMap<FString, UMaterialInterface*>& Cache = GetCache();
	if (UMaterialInterface** CachedMaterial = Cache.Find(Tag))
	{
		// A cached pointer is only trusted while the object is still alive. Materials
		// are rooted below, so this only fails for a cached miss (nullptr), which
		// stays a miss.
		if (*CachedMaterial == nullptr || IsValid(*CachedMaterial))
		{
			return *CachedMaterial;
		}
		Cache.Remove(Tag);
	}

	const FString* AssetPath = GetTagToAssetPath().Find(Tag);
	if (AssetPath == nullptr)
	{
		UE_LOG(LogMaterialResolver, Warning, TEXT("Resolve: no known asset path for material tag %s"), *Tag);
		Cache.Add(Tag, nullptr);
		return nullptr;
	}

	UMaterialInterface* Material = LoadObject<UMaterialInterface>(nullptr, **AssetPath);
	if (Material == nullptr)
	{
		UE_LOG(
			LogMaterialResolver,
			Warning,
			TEXT("Resolve: failed to load material %s for tag %s -- has it been migrated into this project? See KNOWN_GAPS_AND_ISSUES.md."),
			**AssetPath,
			*Tag);
	}

	if (Material != nullptr)
	{
		// This static cache is invisible to the garbage collector. Without a root
		// reference, a material used only by a previous scenario's (now destroyed)
		// components is freed on the next GC pass and a later scenario load would
		// read the dangling pointer (crash in BuildMeshSection). Reproduced by
		// loading a scenario, an empty one, waiting out a GC pass, then reloading.
		Material->AddToRoot();
	}
	Cache.Add(Tag, Material);
	return Material;
}
