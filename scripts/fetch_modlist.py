"""Fetch the official mod list of a pack and write packs/<pack>/modlist.json.

The All the Mods repos ship config/crash_assistant/modlist.json: every jar in
the pack with its mod id, display name and version. We keep one entry per mod
id, skip libraries the player never sees, and sort by name.

    python3 scripts/fetch_modlist.py atm10
"""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Loader and pure-library jars: no blocks, no items, nothing to explain
SKIP_IDS = {"neoforge", "minecraft"}


def main(slug):
    pack_dir = ROOT / "packs" / slug
    pack = json.loads((pack_dir / "pack.json").read_text())
    with urllib.request.urlopen(pack["sources"]["modlist"], timeout=30) as r:
        raw = json.loads(r.read().decode("utf-8-sig"))

    mods = {}
    for jar in raw.values():
        mod_id = jar.get("modId")
        if not mod_id or mod_id in SKIP_IDS:
            continue
        mods.setdefault(mod_id, {"id": mod_id, "name": jar["name"], "version": jar.get("version", "")})

    out = sorted(mods.values(), key=lambda m: m["name"].lower())
    (pack_dir / "modlist.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(f"{slug}: {len(out)} mods")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "atm10")
