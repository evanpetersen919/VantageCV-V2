#include "SyntheticDataGenModule.h"

void FSyntheticDataGenModule::StartupModule()
{
	// Procedural mesh, sensor simulation, traffic behavior, and data export
	// subsystems are registered here as they are implemented in Phases 3-6.
}

void FSyntheticDataGenModule::ShutdownModule()
{
}

IMPLEMENT_MODULE(FSyntheticDataGenModule, SyntheticDataGen)
