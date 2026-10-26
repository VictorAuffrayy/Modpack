"""Build the static site into docs/ (served by GitHub Pages).

Reads packs/<slug>/ (pack.json + tool data), i18n/<lang>.json and templates/,
and writes one page per language: docs/<lang>/, docs/<lang>/<pack>/,
docs/<lang>/<pack>/bees/, docs/<lang>/<pack>/mods/[<mod>/]. No network, no dependencies.

    python3 scripts/build_site.py
"""
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schematics  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs"
LANGS = ["en", "fr"]
SITE_URL = os.environ.get("SITE_URL", "https://victorauffrayy.github.io/Modpack/")

TOOLS = [  # order shown on a pack page
    ("bees", "🐝"),
    ("quests", "📜"),
    ("howto", "🧭"),
    ("mods", "📚"),
]
CATEGORY_ORDER = ["progression", "tech", "logistics", "storage", "magic", "exploration", "food", "building", "utility", "library"]

I18N = {lang: json.loads((ROOT / "i18n" / f"{lang}.json").read_text()) for lang in LANGS}
MODS = json.loads((ROOT / "packs" / "mods.json").read_text())


def mod_name(ns):
    return MODS.get(ns, ns.replace("_", " ").title())


def item(s):
    """'lithium bucket (mekanism)' -> {'n': 'Lithium bucket', 'm': 'Mekanism'}. No namespace = vanilla Minecraft."""
    m = re.fullmatch(r"(.*) \((\w+)\)", s)
    name, ns = (m.group(1), m.group(2)) if m else (s, None)
    return {"n": name[:1].upper() + name[1:], "m": mod_name(ns) if ns else None}


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
    cats = I18N[lang]["js"]["cats"]
    out = []
    for b in bees:
        note = notes.get(b["id"])
        methods = [{**m, "items": [item(i) for i in m.get("items", [])]} for m in b["methods"]]
        out.append({
            "id": b["id"], "tier": b["tier"], "color": b["color"], "color2": b["color2"],
            # The category is either a mod id (mekanism) or a Productive Bees group (dusts, gems...)
            "mod": cats.get(b["cat"], mod_name(b["cat"])),
            "name": b["name"][lang], "alt": b["name"][alt],
            "desc": b["desc"][lang] if b["desc"] else None,
            "special": note[lang] if note else None,
            "methods": methods,
            "flower": item(b["flower"]) if b["flower"] else None,
        })
    return out


def pack_stats(pack):
    bees = json.loads((pack["dir"] / "bees.json").read_text())
    mods = {mod_name(b["cat"]) for b in bees if b["cat"] in MODS}
    for b in bees:
        for s in [b["flower"] or ""] + [i for m in b["methods"] for i in m.get("items", [])]:
            if item(s)["m"]:
                mods.add(item(s)["m"])
    return {"bees": len(bees), "tiers": len({b["tier"] for b in bees}), "mods": len(mods)}


def card(icon, title, desc, meta, href, status, t):
    label = t["status_" + status]
    go = f'<a class="go" href="{href}">{html.escape(label)} →</a>' if status == "live" else f'<span class="go">{html.escape(label)}</span>'
    return (f'<li class="card{"" if status == "live" else " off"}"><h3><span class="ico" aria-hidden="true">{icon}</span>{html.escape(title)}</h3>'
            f'<p>{html.escape(desc)}</p>{f"<span class=meta>{html.escape(meta)}</span>" if meta else ""}{go}</li>')


def load_mods(pack):
    """The pack's mod list with a category, plus which mods have a guide (or a dedicated tool) and which deserve one."""
    modlist_file = pack["dir"] / "modlist.json"
    if not modlist_file.exists():
        return None
    mods = json.loads(modlist_file.read_text())
    cats = json.loads((pack["dir"] / "mod_categories.json").read_text())
    cat_of = {mid: c for c, ids in cats["categories"].items() for mid in ids}
    guides = {}
    for gf in sorted((pack["dir"] / "guides").glob("*.json")):
        g = json.loads(gf.read_text())
        guides[g["mod"]] = g
        for other in g.get("also", []):
            guides.setdefault(other, {"redirect": g["mod"]})
    for m in mods:
        m["cat"] = cat_of.get(m["id"], "library")
        m["wanted"] = m["id"] in cats["guide"]
    return mods, guides


def mod_link(m, guides, pack, lang):
    """(href, badge key) for a mod row: its guide, the bee planner for Productive Bees, or nothing."""
    if m["id"] == "productivebees" and pack["tools"].get("bees") == "live":
        return "../bees/", "badge_tool"
    g = guides.get(m["id"])
    if g:
        return f"{g.get('redirect', m['id'])}/", "badge_guide"
    return None, "badge_planned" if m["wanted"] else None


def render_mod_groups(mods, guides, pack, lang):
    t = I18N[lang]
    out = []
    for cat in CATEGORY_ORDER:
        group = [m for m in mods if m["cat"] == cat]
        if not group:
            continue
        # Mods with a guide first, then the ones waiting for one, then the rest, each alphabetically
        group.sort(key=lambda m: (mod_link(m, guides, pack, lang)[1] not in ("badge_guide", "badge_tool"), not m["wanted"], m["name"].lower()))
        items = []
        for m in group:
            href, badge = mod_link(m, guides, pack, lang)
            name = html.escape(m["name"])
            label = f'<a href="{href}">{name}</a>' if href else name
            badge_html = f'<span class="badge {badge}">{html.escape(t[badge])}</span>' if badge else ""
            keys = html.escape(f"{m['name']} {m['id']}".lower())
            items.append(f'<li data-k="{keys}"{" data-g=1" if href else ""}>{label}{badge_html}<span class="ver">{html.escape(m["version"])}</span></li>')
        out.append(f'<section class="mod-group"><h2>{html.escape(t["cat"][cat])} <span class="n">{len(group)}</span></h2><ul class="mod-list">{"".join(items)}</ul></section>')
    return "".join(out)


def render_guide_sections(guide, lang):
    t = I18N[lang]
    toc, out = [], []
    for sec in guide["sections"]:
        title = html.escape(sec["title"][lang])
        toc.append(f'<li><a href="#{sec["id"]}">{title}</a></li>')
        parts = [f'<section class="g-sec" id="{sec["id"]}"><h2>{title}</h2>']
        for para in sec.get("text", {}).get(lang, []):
            parts.append(f"<p>{html.escape(para)}</p>")
        if sec.get("chain"):
            steps = "".join(
                f'<li><span class="mach">{html.escape(st["machine"][lang])}</span>'
                f'<span class="io">{html.escape(st["in"][lang])} <b aria-hidden="true">→</b> {html.escape(st["out"][lang])}</span></li>'
                for st in sec["chain"]
            )
            parts.append(f'<h3>{html.escape(t["guide_chain"])}</h3><ol class="chain">{steps}</ol>')
        if sec.get("rules"):
            rules = "".join(f"<li>{html.escape(r[lang])}</li>" for r in sec["rules"])
            parts.append(f'<h3>{html.escape(t["guide_rules"])}</h3><ul class="rules">{rules}</ul>')
        if sec.get("schematic"):
            parts.append(f'<h3>{html.escape(t["guide_schematic"])}</h3>{schematics.render(sec["schematic"], lang)}')
        if sec.get("sources"):
            src = " · ".join(f'<a href="{html.escape(s["url"])}" rel="nofollow">{html.escape(s["label"])}</a>' for s in sec["sources"])
            colon = "\u00a0: " if lang == "fr" else ": "
            parts.append(f'<p class="sources">{html.escape(t["guide_sources"])}{colon}{src}</p>')
        parts.append("</section>")
        out.append("".join(parts))
    return "".join(toc), "".join(out)


def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "static", OUT / "static")
    (OUT / ".nojekyll").write_text("")
    packs = load_packs()
    pages = []
    # Home page numbers come from the first live pack's data, so they never drift from the planner
    stats_pack = next(p for p in packs if p["tools"].get("bees") == "live")
    stats = pack_stats(stats_pack)

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
            "home_stats_line": stats_pack["short"] + " · " + fmt(t["home_stats"], **stats),
            "pack_cards": "".join(cards),
        }, template("home")))

        for p in packs:
            if p.get("status") == "planned":
                continue
            slug, short = p["slug"], p["short"]

            # Pack page: one card per tool
            loaded = load_mods(p)
            n_mods = len(loaded[0]) if loaded else 0
            tool_cards = [
                card(icon, t[f"tool_{k}_name"], fmt(t[f"tool_{k}_desc"], n=n_mods), None, f"{k}/", p["tools"].get(k, "planned"), t)
                for k, icon in TOOLS
            ]
            pages.append(write_page(f"{slug}/", lang, {
                "page_title": f"{p['name']} · {t['site_name']}",
                "page_desc": " ".join(fmt(t[f"tool_{k}_desc"], n=n_mods) for k, _ in TOOLS),
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

            if p["tools"].get("mods") == "live" and loaded:
                mods, guides = loaded
                pages.append(write_page(f"{slug}/mods/", lang, {
                    "page_title": fmt(t["mods_title"], pack=short) + f" · {t['site_name']}",
                    "page_desc": fmt(t["mods_meta"], pack=short, n=len(mods)),
                    "mods_heading_text": fmt(t["mods_heading"], pack=short, n=len(mods)),
                    "mod_groups": render_mod_groups(mods, guides, p, lang),
                }, template("mods"), crumbs=[(short, f"{slug}/"), (t["tool_mods_name"], f"{slug}/mods/")]))
                names = {m["id"]: m["name"] for m in mods}
                for mod_id, guide in guides.items():
                    if "redirect" in guide:
                        continue
                    mod = names.get(mod_id, mod_name(mod_id))
                    toc, sections = render_guide_sections(guide, lang)
                    pages.append(write_page(f"{slug}/mods/{mod_id}/", lang, {
                        "page_title": fmt(t["guide_title"], mod=mod, pack=short) + f" · {t['site_name']}",
                        "page_desc": fmt(t["guide_meta"], mod=mod, pack=short),
                        "guide_kicker": f"{short} · {t['badge_guide']}",
                        "guide_heading": mod,
                        "guide_intro": guide["intro"][lang],
                        "guide_checked_line": fmt(t["guide_checked"], what=guide["checked"]),
                        "guide_toc_items": toc,
                        "guide_sections": sections,
                    }, template("guide"), crumbs=[(short, f"{slug}/"), (t["tool_mods_name"], f"{slug}/mods/"), (mod, f"{slug}/mods/{mod_id}/")]))

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
