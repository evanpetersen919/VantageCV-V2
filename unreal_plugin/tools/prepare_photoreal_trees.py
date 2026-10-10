"""Download Poly Haven (CC0) scanned trees and plants, convert their textures, import them into Unreal.

Poly Haven publishes every asset under CC0 (https://polyhaven.com/license): no permission or attribution is
needed. The assets are photogrammetry scans with tens of thousands to millions of triangles, imported as Nanite
meshes (``setup_photoreal_trees.py``).

For each asset this script, with the game closed:

1. downloads the 2K FBX and its textures into the cache directory (default
   ``unreal_plugin/content/polyhaven_cache``, ignored by git: the files are large);
2. finds the asset's material parts from its texture names (``<asset>_<part>_diff_2k.png``, or
   ``<asset>_diff_2k.png`` for a single-material plant) and writes, per part, the colour with the opacity map as
   its alpha when there is one, an autumn hue-shifted copy of such a part, and the normal map with the green
   channel flipped (Poly Haven's are OpenGL, Unreal reads DirectX) when a PNG one exists;
3. writes ``textures.json`` (parts and their files) and imports the FBX into ``/Game/VantageCV/Trees`` with the
   ImportAssets commandlet.

Run with the project's Python from the repository root:

    PYTHONPATH=. python unreal_plugin/tools/prepare_photoreal_trees.py
"""

import colorsys
import json
import re
import urllib.request
from pathlib import Path
from typing import Dict

import numpy as np
from PIL import Image

from src.ue5.import_assets import import_group, report_import, run_import

ASSETS = (
    "jacaranda_tree",
    "tree_small_02",
    "searsia_lucida",
    "othonna_cerarioides",
    "fern_02",
)
CACHE = Path(__file__).resolve().parent.parent / "content" / "polyhaven_cache"
RESOLUTION = "2k"
DESTINATION = "/Game/VantageCV/Trees"
CONTENT = Path("F:/UE5Projects/VantageCV_UE5/Content/VantageCV/Trees")
FALL_HUE_SHIFT = 0.17  # green (0.28) to yellow-orange (0.11): hue is a fraction of a turn
FALL_SATURATION = 1.15
HEADERS = {"User-Agent": "Mozilla/5.0 (tree fetch script)"}


def download(url: str, target: Path) -> None:
    """Fetch ``url`` to ``target`` unless it is already there."""
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=900) as response:
        target.write_bytes(response.read())


def fetch(name: str) -> Path:
    """Download one asset's FBX and PNG textures; return its directory."""
    folder = CACHE / name
    folder.mkdir(parents=True, exist_ok=True)
    listing = folder / "files.json"
    download(f"https://api.polyhaven.com/files/{name}", listing)
    entry = json.loads(listing.read_text(encoding="utf-8"))["fbx"][RESOLUTION]["fbx"]
    download(entry["url"], folder / f"{name}_{RESOLUTION}.fbx")
    for relative, item in entry["include"].items():
        if relative.endswith((".png", ".jpg")):
            download(item["url"], folder / relative)
    return folder


def hue_shift(image: Image.Image) -> Image.Image:
    """The colour turned toward autumn yellow-orange (alpha kept)."""
    rgb = np.array(image.convert("RGB")).astype(np.float64) / 255.0
    flat = rgb.reshape(-1, 3)
    shifted = np.empty_like(flat)
    for index, (red, green, blue) in enumerate(flat):
        hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)
        shifted[index] = colorsys.hsv_to_rgb(
            (hue - FALL_HUE_SHIFT) % 1.0, min(saturation * FALL_SATURATION, 1.0), value
        )
    out = Image.fromarray((shifted.reshape(rgb.shape) * 255.0).astype(np.uint8), "RGB")
    out.putalpha(image.getchannel("A"))
    return out


def convert(name: str, folder: Path) -> Dict[str, Dict[str, str]]:
    """Write the textures Unreal imports; return ``{part: {role: path}}``."""
    textures = folder / "textures"
    pattern = re.compile(rf"^{re.escape(name)}_(?:(.+)_)?diff_{RESOLUTION}\.(?:png|jpg)$")
    parts: Dict[str, Dict[str, str]] = {}
    for path in sorted(textures.glob(f"{name}_*diff_{RESOLUTION}.*")):
        match = pattern.match(path.name)
        if match is None:
            continue
        part = match.group(1) or "main"
        stem = f"{name}_{match.group(1)}_" if match.group(1) else f"{name}_"
        colour = Image.open(path).convert("RGB")
        files: Dict[str, str] = {}
        alpha_path = textures / f"{stem}alpha_{RESOLUTION}.png"
        if alpha_path.exists():
            colour.putalpha(Image.open(alpha_path).convert("L").resize(colour.size))
            fall = folder / f"{part}_diff_fall_rgba.png"
            hue_shift(colour.resize((1024, 1024), Image.Resampling.LANCZOS)).save(fall)
            files["diff_fall"] = fall.as_posix()
        diffuse = folder / f"{part}_diff_rgba.png"
        colour.save(diffuse)
        files["diff"] = diffuse.as_posix()
        normal_path = textures / f"{stem}nor_gl_{RESOLUTION}.png"
        if normal_path.exists():
            normal = np.array(Image.open(normal_path).convert("RGB"))
            normal[..., 1] = 255 - normal[..., 1]  # OpenGL to DirectX: flip the green channel
            normal_out = folder / f"{part}_nor_dx.png"
            Image.fromarray(normal, "RGB").save(normal_out)
            files["nor"] = normal_out.as_posix()
        rough_path = textures / f"{stem}rough_{RESOLUTION}.png"
        if rough_path.exists():
            files["rough"] = rough_path.as_posix()
        parts[part] = files
    return parts


def write_placeholders() -> Dict[str, str]:
    """A flat normal map and a mid-grey roughness map for parts that have none."""
    CACHE.mkdir(parents=True, exist_ok=True)
    flat = CACHE / "placeholder_normal.png"
    grey = CACHE / "placeholder_rough.png"
    diffuse = CACHE / "placeholder_diffuse.png"
    Image.new("RGB", (4, 4), (128, 128, 255)).save(flat)
    Image.new("RGB", (4, 4), (160, 160, 160)).save(grey)
    Image.new("RGBA", (4, 4), (128, 128, 128, 255)).save(diffuse)
    return {"nor": flat.as_posix(), "rough": grey.as_posix(), "diff": diffuse.as_posix()}


def main() -> None:
    """Fetch, convert and import every asset."""
    placeholders = write_placeholders()
    groups = []
    for name in ASSETS:
        folder = fetch(name)
        parts = convert(name, folder)
        (folder / "textures.json").write_text(
            json.dumps({"placeholders": placeholders, "parts": parts}, indent=1), encoding="utf-8"
        )
        print(name, "parts:", sorted(parts))
        if (CONTENT / f"{name}_{RESOLUTION}.uasset").exists():
            print(name, "is already imported; delete its asset to import it again")
            continue
        groups.append(
            import_group(name, [(folder / f"{name}_{RESOLUTION}.fbx").as_posix()], DESTINATION)
        )
    if groups:
        code, errors = run_import(groups, CACHE / "import_settings.json")
        report_import(code, errors, len(groups))


if __name__ == "__main__":
    main()
