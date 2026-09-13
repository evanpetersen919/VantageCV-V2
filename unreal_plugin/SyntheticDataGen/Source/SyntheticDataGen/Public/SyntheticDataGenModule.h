#pragma once

#include "Modules/ModuleManager.h"

class FSyntheticDataGenModule final : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
};
