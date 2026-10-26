"""Build the static site into docs/ (served by GitHub Pages).

Reads packs/<slug>/ (pack.json + tool data), i18n/<lang>.json and templates/,
and writes one page per language: docs/<lang>/, docs/<lang>/<pack>/,
docs/<lang>/<pack>/bees/. No network, no dependencies.

    python3 scripts/build_site.py
"""
import html
import json
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs"
LANGS = ["en", "fr"]
SITE_URL = os.environ.get("SITE_URL", "https://victorauffrayy.github.io/Modpack/")

TOOLS = [  # order shown on a pack page
    ("bees", "🐝"),
    ("quests", "📜"),
    ("howto", "🧭"),
]

I18N = {lang: json.loads((ROOT / "i18n" / f"{lang}.json").read_text()) for lang in LANGS}


def lookup(ctx, key):
    val = ctx
    for part in key.split("."):
        if not isinstance(val, dict) or part not in val:
            raise KeyError(f"template key not found: {key}")
        val = val[part]
    return val


def render(tpl, ctx):
    """{{key}} is HTML-escaped, {{{key}}} is inserted as is. Dotted keys reach into nested dicts."""
    tpl = re.sub(r"\{\{\{\s*([\w.]+)\s*\}\}\}", lambda m: str(lookup(ctx, m.group(1))), tpl)
    return re.sub(r"\{\{\s*([\w.]+)\s*\}\}", lambda m: html.escape(str(lookup(ctx, m.group(1)))), tpl)


def fmt(s, **kw):
    return re.sub(r"\{(\w+)\}", lambda m: str(kw[m.group(1)]), s)


def script_json(data):
    # Safe to inline in <script>: no "</script>" can close the tag early
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def template(name):
    return (ROOT / "templates" / f"{name}.html").read_text()


def write_page(path, lang, ctx, body_tpl, crumbs=()):
    """path is relative to the language folder, e.g. "atm10/bees/" ("" for the home page)."""
    t = I18N[lang]
    alt = "fr" if lang == "en" else "en"
    depth = 1 + path.count("/")
    root = "../" * depth
    crumb_html = " ".join(
        f'<span aria-hidden="true">›</span> <a href="{root}{lang}/{href}">{html.escape(label)}</a>' for label, href in crumbs
    )
    page_ctx = {
        **t,
        **ctx,
        "lang": lang,
        "alt_lang": alt,
        "root": root,
        "alt_href": f"{root}{alt}/{path}",
        "url_en": f"{SITE_URL}en/{path}",
        "url_fr": f"{SITE_URL}fr/{path}",
        "crumbs": crumb_html,
        "head_extra": ctx.get("head_extra", ""),
        "body_class": ctx.get("body_class", ""),
    }
    page_ctx["content"] = render(body_tpl, page_ctx)
    out = OUT / lang / path / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(template("layout"), page_ctx))
    return f"{lang}/{path}"


def load_packs():
    packs = []
    for pj in sorted((ROOT / "packs").glob("*/pack.json")):
        pack = json.loads(pj.read_text())
        pack["dir"] = pj.parent
        packs.append(pack)
    # Live packs first, then the ones still being prepared
    return sorted(packs, key=lambda p: (p.get("status") == "planned", p["slug"]))


def bees_for(pack, lang):
    """Flatten bee data to one language. Notes written by hand override nothing, they add a 'special' line."""
    bees = json.loads((pack["dir"] / "bees.json").read_text())
    notes_file = pack["dir"] / "bees_notes.json"
    notes = json.loads(notes_file.read_text()) if notes_file.exists() else {}
    alt = "fr" if lang == "en" else "en"
    out = []
    for b in bees:
        note = notes.get(b["id"])
        out.append({
            "id": b["id"], "cat": b["cat"], "tier": b["tier"], "color": b["color"], "color2": b["color2"],
            "name": b["name"][lang], "alt": b["name"][alt],
            "desc": b["desc"][lang] if b["desc"] else None,
            "special": note[lang] if note else None,
            "methods": b["methods"], "flower": b["flower"], "breedItem": b["breedItem"],
        })
    return out


def card(icon, title, desc, meta, href, status, t):
    label = t["status_" + status]
    go = f'<a class="go" href="{href}">{html.escape(label)} →</a>' if status == "live" else f'<span class="go">{html.escape(label)}</span>'
    return (f'<li class="card{"" if status == "live" else " off"}"><h3><span class="ico" aria-hidden="true">{icon}</span>{html.escape(title)}</h3>'
            f'<p>{html.escape(desc)}</p>{f"<span class=meta>{html.escape(meta)}</span>" if meta else ""}{go}</li>')


def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "static", OUT / "static")
    (OUT / ".nojekyll").write_text("")
    packs = load_packs()
    pages = []

    for lang in LANGS:
        t = I18N[lang]

        # Home: one card per modpack
        cards = []
        for p in packs:
            live = p.get("status") != "planned"
            n_live = sum(1 for s in p["tools"].values() if s == "live")
            meta = fmt(t["pack_mc"], mc=p["minecraft"], loader=p["loader"])
            desc = " · ".join(t[f"tool_{k}_name"] for k, _ in TOOLS if p["tools"].get(k) == "live") or t["status_planned"]
            cards.append(card("⛏️", p["name"], desc, meta, f"{p['slug']}/", "live" if live and n_live else "planned", t))
        pages.append(write_page("", lang, {
            "page_title": f"{t['site_name']} · {t['site_tagline']}",
            "page_desc": t["home_lead"],
            "pack_cards": "".join(cards),
        }, template("home")))

        for p in packs:
            if p.get("status") == "planned":
                continue
            slug, short = p["slug"], p["short"]

            # Pack page: one card per tool
            tool_cards = [
                card(icon, t[f"tool_{k}_name"], t[f"tool_{k}_desc"], None, f"{k}/", p["tools"].get(k, "planned"), t)
                for k, icon in TOOLS
            ]
            pages.append(write_page(f"{slug}/", lang, {
                "page_title": f"{p['name']} · {t['site_name']}",
                "page_desc": " ".join(t[f"tool_{k}_desc"] for k, _ in TOOLS),
                "pack_name": p["name"],
                "pack_mc_line": fmt(t["pack_mc"], mc=p["minecraft"], loader=p["loader"]),
                "tool_cards": "".join(tool_cards),
            }, template("pack"), crumbs=[(short, f"{slug}/")]))

            if p["tools"].get("bees") == "live":
                bees = bees_for(p, lang)
                pages.append(write_page(f"{slug}/bees/", lang, {
                    "page_title": fmt(t["bees_title"], pack=short) + f" · {t['site_name']}",
                    "page_desc": fmt(t["bees_meta"], pack=short, n=len(bees)),
                    "bees_heading": fmt(t["bees_heading"], pack=short),
                    "bees_json": script_json(bees),
                    "t_json": script_json(t["js"]),
                    # Same key in both languages: progress follows you when you switch
                    "store_key": f"{slug}-bees-v1",
                    "head_extra": f'<link rel="stylesheet" href="{"../" * 3}static/bees.css">',
                    "body_class": "app",
                }, template("bees"), crumbs=[(short, f"{slug}/"), (t["tool_bees_name"], f"{slug}/bees/")]))

    # Root: send visitors to their language (explicit choice first, then the browser's)
    (OUT / "index.html").write_text("""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Modpack Companion</title>
<link rel="alternate" hreflang="en" href="%(u)sen/"><link rel="alternate" hreflang="fr" href="%(u)sfr/">
<script>
var l; try { l = localStorage.getItem('lang') } catch (e) {}
if (!l) l = (navigator.language || 'en').toLowerCase().startsWith('fr') ? 'fr' : 'en';
location.replace(l + '/');
</script></head>
<body style="font-family:sans-serif;background:#e9d3a3;color:#2b1d0e;padding:24px">
<p><a href="en/">English</a> · <a href="fr/">Français</a></p></body></html>
""" % {"u": SITE_URL})
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n")
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{SITE_URL}{p}</loc></url>\n" for p in pages)
        + "</urlset>\n"
    )
    print(f"built {len(pages)} pages into {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    build()
