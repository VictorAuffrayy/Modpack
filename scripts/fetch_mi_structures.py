"""Extract Modern Industrialization multiblock shapes defined in a pack's KubeJS startup scripts.

ATM10 builds its "runic" multiblocks (Runic Star Altar...) with MI's KubeJS API:
`layeredShape(casing, [...])` plus `.key('x', memberOfBlock('mod:block'), ...)`.
This script downloads those scripts and writes packs/<pack>/structures/<name>.json:
the layers (z slices, each a list of y rows of x chars) and what each char stands for.

    python3 scripts/fetch_mi_structures.py atm10
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = "https://raw.githubusercontent.com/AllTheMods/ATM-10/main/"
SCRIPTS = {"runic_star_altar": "kubejs/startup_scripts/Modern-Industrialization/multiblocks/runic_star_altar.js"}


def parse(src):
    members = dict(re.findall(r"const (\w+) = \w+\.memberOfBlock\('([^']+)'\)", src))
    shape = re.search(r"layeredShape\('[^']+',\s*\[(.*?)\]\s*\)\s*\.key", src, re.S).group(1)
    slices = [re.findall(r"'([^']*)'", block) for block in re.findall(r"\[([^\[\]]*)\]", shape)]
    keys = {}
    for char, var, hatch in re.findall(r"\.key\('(.)',\s*(\w+),\s*\w+\.(noHatch|\w+)\(", src):
        keys[char] = {"block": members.get(var, var), "hatch": hatch != "noHatch"}
    # A hatch key reuses a block variable but accepts hatches too
    for char, var in re.findall(r"\.key\('(.)',\s*(\w+),\s*hatchBlock\)", src):
        keys[char] = {"block": members.get(var, var), "hatch": True}
    return {"slices": slices, "keys": keys}


def main(slug):
    out_dir = ROOT / "packs" / slug / "structures"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, path in SCRIPTS.items():
        src = urllib.request.urlopen(RAW + path, timeout=30).read().decode()
        data = parse(src)
        data["source"] = RAW.replace("raw.githubusercontent.com", "github.com").replace("/main/", "/blob/main/") + path
        (out_dir / f"{name}.json").write_text(json.dumps(data, indent=1) + "\n")
        print(f"{name}: {len(data['slices'])} slices, keys {''.join(sorted(data['keys']))}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "atm10")
