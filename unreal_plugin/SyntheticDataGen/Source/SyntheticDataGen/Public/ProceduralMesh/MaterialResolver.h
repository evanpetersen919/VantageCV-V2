// Resolves a material tag string (e.g. "brick", "asphalt" -- the same
// strings src/procedural/mesh_factory.py/building_placement.py emit as
// Mesh.material) to a real, migrated City Sample UMaterialInterface.
//
// Hand-authored against configs/material_tags.json rather than parsing
// that file at runtime -- deliberate, see
// configs/material_tags.json's own header comment and
// KNOWN_GAPS_AND_ISSUES.md for why no cross-language codegen is used
// for this scope. tests/unit/test_material_tags_coverage.py keeps the
// Python-side tag list from silently drifting out of coverage; keeping
// this TMap in sync with configs/material_tags.json on the C++ side is
// a manual, reviewable step (few entries, changes rarely).

#pragma once

#include "CoreMinimal.h"

class UMaterialInterface;

/**
 * Static tag -> UMaterialInterface resolver for procedural mesh
 * sections. A missing/unmapped tag is not fatal -- ScenarioMeshBuilder
 * falls back to the section's default material and logs a warning, the
 * same fail-soft convention as a missing static mesh part in
 * VehicleActorSpawner.
 */
class SYNTHETICDATAGEN_API FMaterialResolver
{
public:
	/**
	 * Resolves Tag to a real material asset, loading it on first use and
	 * caching the result for subsequent calls (LoadObject is not free,
	 * and the same handful of tags repeat across every mesh in a
	 * scenario -- e.g. every road lane resolves "asphalt").
	 *
	 * @return The resolved material, or nullptr if Tag is unmapped or
	 *         the mapped asset failed to load (e.g. not yet migrated
	 *         into this project -- see
	 *         KNOWN_GAPS_AND_ISSUES.md's manual migration steps).
	 */
	static UMaterialInterface* Resolve(const FString& Tag);

private:
	static TMap<FString, UMaterialInterface*>& GetCache();
};
