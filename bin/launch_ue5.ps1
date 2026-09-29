# Launches the VantageCV_UE5 standalone game session the live-rendering pipeline talks to
# over its WebSocket RPC bridge (src/ue5/backend.py).
#
# Two real, previously-hand-applied fixes are baked in here so they can't be silently
# skipped or drift between sessions:
#
# 1. ELECTRON_RUN_AS_NODE=1 (inherited from a VS Code/Cursor extension-host process tree)
#    silently breaks UnrealEditor.exe -- its CEF-based components try to run as Node. Must
#    be removed from the child process's environment before launch, not just unset in the
#    calling shell (that alone doesn't stop it being inherited).
# 2. -ResX=1920 -ResY=1080 pins the render resolution explicitly. Without this, the game
#    window (in windowed-fullscreen mode) matches the current desktop resolution instead --
#    confirmed to silently produce a different resolution/FOV than every real dataset
#    generated so far (which are all 1920x1080; a manual launch without this flag on
#    2026-09-28 produced 3440x1440 ultrawide frames instead).
#
# Usage: powershell -File bin/launch_ue5.ps1

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "F:\UE_5.4\Engine\Binaries\Win64\UnrealEditor.exe"
$psi.Arguments = '"F:\UE5Projects\VantageCV_UE5\VantageCV_UE5.uproject" -game -d3d11 -ResX=1920 -ResY=1080 -WINDOWED'
$psi.UseShellExecute = $false
$psi.EnvironmentVariables.Remove("ELECTRON_RUN_AS_NODE")
$proc = [System.Diagnostics.Process]::Start($psi)
Write-Output "Started UnrealEditor.exe PID $($proc.Id) at 1920x1080"
