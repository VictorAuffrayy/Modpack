"""Fetch multiblock shapes from the mods' and pack's own files, for the guide schematics.

Every structure is saved as packs/<pack>/structures/<name>.json:
  {"layers": [bottom layer first; each layer = rows (z) of chars (x)],
   "keys": {char: {"block": "mod:block_or_#tag", "hatch": bool}}, "source": url}

Three formats are read:
- ATM10 KubeJS startup scripts using Modern Industrialization's layeredShape (Runic Star Altar)
- Occultism pentacles, shipped as Modonomicon multiblock JSON
- Nature's Aura's Multiblocks.java, a Patchouli-style String[][] per structure

    python3 scripts/fetch_structures.py atm10
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ATM_RAW = "https://raw.githubusercontent.com/AllTheMods/ATM-10/main/"
MI_SCRIPTS = {"runic_star_altar": "kubejs/startup_scripts/Modern-Industrialization/multiblocks/runic_star_altar.js"}

OCC_REF = "release/v1.21.1-1.224.5"
OCC_RAW = f"https://raw.githubusercontent.com/klikli-dev/occultism/{OCC_REF}/src/generated/resources/data/occultism/modonomicon/multiblocks/"
PENTACLES = ["craft_foliot", "craft_djinni", "craft_afrit", "craft_marid", "contact_eldritch_spirit"]

NA_REF = "41.10"
NA_RAW = f"https://raw.githubusercontent.com/Ellpeck/NaturesAura/{NA_REF}/src/main/java/de/ellpeck/naturesaura/blocks/multi/Multiblocks.java"
NA_STRUCTURES = {"ALTAR": "altar", "TREE_RITUAL": "tree_ritual", "OFFERING_TABLE": "offering_table"}


def get(url):
    return urllib.request.urlopen(url, timeout=30).read().decode()


def blob(raw_url):
    """GitHub page for a raw.githubusercontent.com URL."""
    _, rest = raw_url.split("raw.githubusercontent.com/", 1)
    owner, repo, rest = rest.split("/", 2)
    return f"https://github.com/{owner}/{repo}/blob/{rest}"


def mi_layered_shape(src):
    """layeredShape(casing, [slice...]) where each slice is a z row holding one string per y level."""
    members = dict(re.findall(r"const (\w+) = \w+\.memberOfBlock\('([^']+)'\)", src))
    shape = re.search(r"layeredShape\('[^']+',\s*\[(.*?)\]\s*\)\s*\.key", src, re.S).group(1)
    slices = [re.findall(r"'([^']*)'", part) for part in re.findall(r"\[([^\[\]]*)\]", shape)]
    keys = {}
    for char, var, hatch in re.findall(r"\.key\('(.)',\s*(\w+),\s*(?:\w+\.)?(\w+)\(?", src):
        keys[char] = {"block": members.get(var, var), "hatch": hatch != "noHatch"}
    layers = [[sl[y] for sl in slices] for y in range(len(slices[0]))]
    return {"layers": layers, "keys": keys}


def modonomicon(data):
    mapping = data["mapping"]
    decorative = {c for c, e in mapping.items() if e.get("type") == "modonomicon:display"}
    layers = [layer for layer in data["pattern"] if set("".join(layer)) - decorative - {"_", " "}]
    keys = {c: {"block": e.get("display") or e.get("tag") or e.get("block", "?"), "hatch": False}
            for c, e in mapping.items() if c not in decorative}
    # Modonomicon lists layers top first
    return {"layers": [[row.replace("_", " ") for row in layer] for layer in reversed(layers)], "keys": keys}


def naturesaura(src, field):
    body = re.search(rf"IMultiblock {field} = .*?new String\[\]\[\]\{{((?:\s*\{{[^{{}}]*\}}\s*,?)+)\}}\s*,(.*?)\);", src, re.S)
    layers = [re.findall(r'"([^"]*)"', part) for part in re.findall(r"\{([^{}]*)\}", body.group(1))]
    keys = {}
    for char, owner, name in re.findall(r"'(.)',\s*(?:Matcher\.tag\(|new Matcher\()?(Blocks|ModBlocks)\.(\w+)", body.group(2)):
        ns = "minecraft" if owner == "Blocks" else "naturesaura"
        keys[char] = {"block": f"{ns}:{name.lower()}", "hatch": False}
    return {"layers": list(reversed(layers)), "keys": keys}


def main(slug):
    out_dir = ROOT / "packs" / slug / "structures"
    out_dir.mkdir(parents=True, exist_ok=True)
    found = {}
    for name, path in MI_SCRIPTS.items():
        found[name] = {**mi_layered_shape(get(ATM_RAW + path)), "source": blob(ATM_RAW + path)}
    for name in PENTACLES:
        found[f"occultism_{name}"] = {**modonomicon(json.loads(get(OCC_RAW + name + ".json"))), "source": blob(OCC_RAW + name + ".json")}
    na_src = get(NA_RAW)
    for field, name in NA_STRUCTURES.items():
        found[f"naturesaura_{name}"] = {**naturesaura(na_src, field), "source": blob(NA_RAW)}
    for name, data in found.items():
        (out_dir / f"{name}.json").write_text(json.dumps(data, indent=1) + "\n")
        layer = data["layers"][0]
        print(f"{name}: {len(data['layers'])} layer(s) of {len(layer[0])}x{len(layer)}, keys {''.join(sorted(data['keys']))}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "atm10")
