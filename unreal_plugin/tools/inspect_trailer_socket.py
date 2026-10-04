"""Read-only: where the City Sample tractor cab (vehTruck_vehicle08) couples its trailer.

Prints, for the cab's skeletal mesh and skeleton, which socket and bone methods the editor's
Python API exposes, then tries them: the socket named ``Trailer_Socket`` (bone, relative location
in cm, relative rotation), the bone names, and each bone's reference transform. Run in a headless
editor session (the game/editor must not be running):

    UnrealEditor.exe <project>.uproject -d3d11 -nosplash -unattended -nullrhi
        -ExecutePythonScript=<this file>

Writes the report to ``VANTAGECV_SOCKET_REPORT`` (default ``C:/Temp/trailer_socket.txt``); makes no
change to any asset.
"""

import os

import unreal  # type: ignore[import-not-found]  # pylint: disable=import-error

ASSETS = (
    "/Game/Vehicle/vehTruck_vehicle08/Mesh/SKM_vehTruck_vehicle08",
    "/Game/Vehicle/vehTruck_vehicle08/Skeleton/SK_vehTruck_vehicle08",
    "/Game/Vehicle/vehTruck_trailer01/Mesh/SKM_vehTruck_trailer01",
)
REPORT = os.environ.get("VANTAGECV_SOCKET_REPORT", "C:/Temp/trailer_socket.txt")


def _try(out: list, label: str, call) -> None:  # type: ignore[no-untyped-def]
    try:
        out.append(f"    {label}: {call()}")
    except Exception as error:  # pylint: disable=broad-except
        out.append(f"    {label}: ERROR {str(error)[:120]}")


def main() -> None:
    """Write the report, then quit the editor."""
    out = []
    for path in ASSETS:
        asset = unreal.EditorAssetLibrary.load_asset(path)
        out.append(f"== {path}  class={asset.get_class().get_name() if asset else None}")
        if asset is None:
            continue
        names = [m for m in dir(asset) if any(k in m.lower() for k in ("socket", "bone", "ref_"))]
        out.append(f"    methods: {names}")
        for method in ("num_sockets", "get_num_sockets"):
            if hasattr(asset, method):
                _try(out, method, getattr(asset, method))
        if hasattr(asset, "find_socket"):
            _try(out, "find_socket('Trailer_Socket')", lambda a=asset: a.find_socket("Trailer_Socket"))
        if hasattr(asset, "get_socket_by_index"):
            for index in range(8):
                _try(out, f"socket[{index}]", lambda a=asset, i=index: _describe(a.get_socket_by_index(i)))
        if hasattr(asset, "get_editor_property"):
            _try(out, "bone_tree names", lambda a=asset: [str(n.get_editor_property("name")) for n in a.get_editor_property("bone_tree")])
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as handle:
        handle.write("\n".join(out))
    unreal.SystemLibrary.quit_editor()


def _describe(socket) -> str:  # type: ignore[no-untyped-def]
    if socket is None:
        return "None"
    return (
        f"{socket.get_editor_property('socket_name')} bone={socket.get_editor_property('bone_name')} "
        f"loc={socket.get_editor_property('relative_location')} "
        f"rot={socket.get_editor_property('relative_rotation')}"
    )


main()
