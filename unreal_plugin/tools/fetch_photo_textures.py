"""Download the photographic textures the foliage uses from ambientCG (CC0) into ``content/photo``.

Every file comes from https://ambientcg.com, whose assets are all under the Creative Commons CC0 1.0
licence (https://docs.ambientcg.com/license/): copying, modifying and redistributing them, even
commercially, needs no permission and no attribution. The sets, and what they are:

- ``LeafSet024`` (beech) and ``LeafSet014`` (hornbeam): photogrammetry atlases of single green leaves.
- ``LeafSet027`` (maple): autumn and green maple leaves, for fall.
- ``Grass005``: a clean lawn, tileable.
- ``Ground003`` (worn grass with bare earth), ``Grass007`` (weedy lawn), ``Grass004`` (dense dark lawn):
  the three lawn variants of the cyclist template.
- ``Bark012``: oak-like bark, photogrammetry, tileable.

Only the 1K colour, opacity, DirectX normal and roughness maps are kept. Run with the project's
Python; the output is committed so a checkout needs no network. ``build_foliage_textures.py`` then
turns the leaf atlases into leaf-cluster cards.

    python unreal_plugin/tools/fetch_photo_textures.py
"""

import io
import json
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, Tuple

API = "https://ambientcg.com/api/v2/full_json?id={id}&include=downloadData"
HEADERS = {"User-Agent": "Mozilla/5.0 (texture fetch script)"}  # the site refuses the default one
RESOLUTION = "1K-JPG"
OUTPUT = Path(__file__).resolve().parent.parent / "content" / "photo"
# set id -> the map suffixes to keep
SETS: Dict[str, Tuple[str, ...]] = {
    "LeafSet024": ("Color", "Opacity"),
    "LeafSet014": ("Color", "Opacity"),
    "LeafSet027": ("Color", "Opacity"),
    "Grass005": ("Color", "NormalDX", "Roughness"),
    "Bark012": ("Color", "NormalDX", "Roughness"),
    "Ground003": ("Color", "NormalDX", "Roughness"),
    "Grass007": ("Color", "NormalDX", "Roughness"),
    "Grass004": ("Color", "NormalDX", "Roughness"),
}


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers=HEADERS)


def fetch(asset_id: str, maps: Tuple[str, ...]) -> None:
    """Download one asset's 1K pack and keep the wanted maps as ``<id>_<map>.jpg``."""
    with urllib.request.urlopen(_request(API.format(id=asset_id)), timeout=60) as response:
        asset = json.load(response)["foundAssets"][0]
    downloads = asset["downloadFolders"]["default"]["downloadFiletypeCategories"]["zip"][
        "downloads"
    ]
    link = next(d["downloadLink"] for d in downloads if d["attribute"] == RESOLUTION)
    with urllib.request.urlopen(_request(link), timeout=300) as response:
        pack = zipfile.ZipFile(io.BytesIO(response.read()))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in pack.namelist():
        for suffix in maps:
            if name.endswith(f"_{RESOLUTION}_{suffix}.jpg"):
                (OUTPUT / f"{asset_id}_{suffix}.jpg").write_bytes(pack.read(name))
                print("kept", asset_id, suffix)


def main() -> None:
    """Fetch every set."""
    for asset_id, maps in SETS.items():
        fetch(asset_id, maps)


if __name__ == "__main__":
    main()
