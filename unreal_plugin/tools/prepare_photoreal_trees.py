"""Download Poly Haven (CC0) scanned trees, convert their textures, and import them into Unreal.

Poly Haven publishes every asset under CC0 (https://polyhaven.com/license): no permission or
attribution is needed. The trees used here are photogrammetry scans with hundreds of thousands to
millions of triangles, so they are imported as Nanite meshes (``setup_photoreal_trees.py``).

For each tree this script, with the game closed:

1. downloads the 2K FBX and its textures into the cache directory (default
   ``unreal_plugin/content/polyhaven_cache``, ignored by git: the FBX alone is over 100 MB);
2. writes the textures Unreal needs: the leaf colour with the leaf opacity as its alpha, normal maps with the
   green channel flipped (Poly Haven's are OpenGL, Unreal reads DirectX), and a yellow-orange hue-shifted copy
   of the leaf colour for fall;
3. imports the FBX into ``/Game/VantageCV/Trees`` with the ImportAssets commandlet.

Run with the project's Python from the repository root:

    PYTHONPATH=. python unreal_plugin/tools/prepare_photoreal_trees.py
"""

import colorsys
import json
import urllib.request
from pathlib import Path
from typing import Dict

import numpy as np
from PIL import Image

from src.ue5.import_assets import import_group, report_import, run_import

TREES = ("jacaranda_tree",)
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
    with urllib.request.urlopen(request, timeout=600) as response:
        target.write_bytes(response.read())


def fetch_tree(name: str) -> Path:
    """Download one tree's FBX and textures; return its directory."""
    folder = CACHE / name
    folder.mkdir(parents=True, exist_ok=True)
    listing = folder / "files.json"
    download(f"https://api.polyhaven.com/files/{name}", listing)
    entry = json.loads(listing.read_text(encoding="utf-8"))["fbx"][RESOLUTION]["fbx"]
    download(entry["url"], folder / f"{name}_{RESOLUTION}.fbx")
    for relative, item in entry["include"].items():
        download(item["url"], folder / relative)
    return folder


def hue_shift(image: Image.Image) -> Image.Image:
    """The leaf colour turned toward autumn yellow-orange (alpha kept)."""
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


def convert_textures(name: str, folder: Path) -> Dict[str, Path]:
    """Write the textures Unreal imports next to the downloads; return their paths by role."""
    textures = folder / "textures"
    prefix = f"{name}_"
    suffix = f"_{RESOLUTION}.png"
    out: Dict[str, Path] = {}
    leaves = Image.open(textures / f"{prefix}leaves_diff{suffix}").convert("RGB")
    alpha = Image.open(textures / f"{prefix}leaves_alpha{suffix}").convert("L")
    leaves.putalpha(alpha)
    out["leaves_diff"] = folder / "leaves_diff_rgba.png"
    leaves.save(out["leaves_diff"])
    out["leaves_diff_fall"] = folder / "leaves_diff_fall_rgba.png"
    hue_shift(leaves.resize((1024, 1024), Image.Resampling.LANCZOS)).save(out["leaves_diff_fall"])
    for part in ("leaves", "branches", "trunk"):
        normal = np.array(Image.open(textures / f"{prefix}{part}_nor_gl{suffix}").convert("RGB"))
        normal[..., 1] = 255 - normal[..., 1]  # OpenGL to DirectX: flip the green channel
        out[f"{part}_nor"] = folder / f"{part}_nor_dx.png"
        Image.fromarray(normal, "RGB").save(out[f"{part}_nor"])
        out[f"{part}_rough"] = textures / f"{prefix}{part}_rough{suffix}"
        if part != "leaves":
            out[f"{part}_diff"] = textures / f"{prefix}{part}_diff{suffix}"
    return out


def main() -> None:
    """Fetch, convert and import every tree; print where the textures are."""
    groups = []
    for name in TREES:
        folder = fetch_tree(name)
        paths = convert_textures(name, folder)
        (folder / "textures.json").write_text(
            json.dumps({role: path.as_posix() for role, path in paths.items()}, indent=1),
            encoding="utf-8",
        )
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
