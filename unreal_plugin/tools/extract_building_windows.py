"""Measure every City Sample building-facade module's real window panes.

Run in a headless editor session (the game/editor must not be running):

    set VANTAGECV_FACADE_PATHS=<json list of /Game/... facade mesh paths>
    set VANTAGECV_WINDOWS_OUT=<output json path>
    UnrealEditor.exe <project>.uproject -d3d11 -nosplash -unattended -nullrhi
        -ExecutePythonScript=<this file>

For each mesh it reads the glass section's triangles, welds them by
position, groups them into connected panes and records each pane's bounds
in centimeters (mesh-local frame). The output is the source data for
``src/procedural/building_window_geometry.py``.
"""

import json
import os
from typing import Any, Dict, List

import unreal  # type: ignore[import-not-found]  # pylint: disable=import-error


def _panes_for(mesh: Any, section: int) -> List[Dict[str, Any]]:
    """Connected glass panes of one mesh section, as bounds + mean normal."""
    verts, tris, normals, _uv, _tan = unreal.ProceduralMeshLibrary.get_section_from_static_mesh(
        mesh, 0, section
    )
    welded: Dict[Any, int] = {}
    ids = []
    for vertex in verts:
        key = (round(vertex.x, 1), round(vertex.y, 1), round(vertex.z, 1))
        ids.append(welded.setdefault(key, len(welded)))
    parent = list(range(len(welded)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for offset in range(0, len(tris), 3):
        first, second, third = (ids[tris[offset + i]] for i in range(3))
        parent[find(second)] = find(first)
        parent[find(third)] = find(first)

    components: Dict[int, List[Any]] = {}
    for index, vertex in enumerate(verts):
        components.setdefault(find(ids[index]), []).append((vertex, normals[index]))

    panes = []
    for members in components.values():
        xs = [m[0].x for m in members]
        ys = [m[0].y for m in members]
        zs = [m[0].z for m in members]
        panes.append(
            {
                "x": [min(xs), max(xs)],
                "y": [min(ys), max(ys)],
                "z": [min(zs), max(zs)],
                "n": [
                    sum(m[1].x for m in members) / len(members),
                    sum(m[1].y for m in members) / len(members),
                ],
                "verts": len(members),
            }
        )
    return panes


def main() -> None:
    """Measure every listed facade mesh, write the JSON, quit the editor."""
    with open(os.environ["VANTAGECV_FACADE_PATHS"], encoding="utf-8") as handle:
        paths = json.load(handle)
    result: Dict[str, Any] = {}
    for path in paths:
        mesh = unreal.load_object(None, path + "." + path.split("/")[-1])
        if mesh is None:
            result[path] = {"error": "not found"}
            continue
        slots = [
            str(slot.get_editor_property("material_slot_name"))
            for slot in mesh.get_editor_property("static_materials")
        ]
        glass_sections = [i for i, name in enumerate(slots) if "glass" in name.lower()]
        panes: List[Dict[str, Any]] = []
        for section in glass_sections:
            panes += _panes_for(mesh, section)
        result[path] = {"slots": slots, "glass_sections": glass_sections, "panes": panes}
    with open(os.environ["VANTAGECV_WINDOWS_OUT"], "w", encoding="utf-8") as handle:
        json.dump(result, handle)
    print("EXTRACT_DONE", len(result))
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


main()
