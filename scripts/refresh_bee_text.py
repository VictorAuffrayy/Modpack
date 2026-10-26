"""Refresh bee names and descriptions from Productive Bees' own lang files.

Each bee in packs/<pack>/bees.json stores the lang keys of its name and
description (langKeys). This script downloads the mod's lang files and
rewrites the text for every language, so translations always match the game.

    python3 scripts/refresh_bee_text.py atm10
"""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANGS = {"en": "en_us", "fr": "fr_fr"}


def fetch_lang(url_tpl, code):
    with urllib.request.urlopen(url_tpl.format(lang=code), timeout=30) as r:
        return json.load(r)


def main(slug):
    pack_dir = ROOT / "packs" / slug
    pack = json.loads((pack_dir / "pack.json").read_text())
    url = pack["sources"]["productivebees_lang"]
    lang = {short: fetch_lang(url, code) for short, code in LANGS.items()}

    bees = json.loads((pack_dir / "bees.json").read_text())
    changed = missing = 0
    for bee in bees:
        for field in ("name", "desc"):
            key = bee["langKeys"].get(field)
            if not key:
                continue
            if key not in lang["en"]:
                missing += 1
                print(f"  ! {bee['id']}: lang key {key} no longer exists")
                continue
            # A language without the key falls back to English, like the game does
            text = {short: lang[short].get(key, lang["en"][key]) for short in LANGS}
            if bee.get(field) != text:
                bee[field] = text
                changed += 1

    (pack_dir / "bees.json").write_text(json.dumps(bees, ensure_ascii=False, indent=1) + "\n")
    print(f"{slug}: {len(bees)} bees, {changed} texts updated, {missing} missing keys")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "atm10")
