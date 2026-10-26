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


def card(icon, title, desc, meta, href, status, t):
    label = t["status_" + status]
    go = f'<a class="go" href="{href}">{html.escape(label)} →</a>' if status == "live" and href else f'<span class="go">{html.escape(label)}</span>'
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


def mod_href(m, guides, pack):
    """Where a mod's card leads, relative to the pack page, and which badge it carries."""
    if m["id"] == "productivebees" and pack["tools"].get("bees") == "live":
        return f"mods/{m['id']}/", "badge_tool"
    if m["id"] in guides:
        return f"mods/{m['id']}/", "badge_guide"
    return f"mods/{m['id']}/", "badge_planned" if m["wanted"] else None


def render_mod_cards(mods, guides, pack, lang):
    t = I18N[lang]
    order = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    # Guides first, then mods waiting for one, then the rest; within each, by category then name
    def rank(m):
        badge = mod_href(m, guides, pack)[1]
        return (badge not in ("badge_guide", "badge_tool"), badge != "badge_planned", order[m["cat"]], m["name"].lower())
    out = []
    for m in sorted(mods, key=rank):
        href, badge = mod_href(m, guides, pack)
        keys = html.escape(f"{m['name']} {m['id']} {t['cat'][m['cat']]}".lower())
        badge_html = f'<span class="badge {badge}">{html.escape(t[badge])}</span>' if badge else ""
        out.append(
            f'<li data-k="{keys}" data-c="{m["cat"]}"{" data-g=1" if badge in ("badge_guide", "badge_tool") else ""}>'
            f'<a href="{href}"><span class="mc-name">{html.escape(m["name"])}</span>{badge_html}'
            f'<span class="mc-cat">{html.escape(t["cat"][m["cat"]])}</span><span class="mc-ver">{html.escape(m["version"])}</span></a></li>'
        )
    return "".join(out)


def render_cat_chips(mods, lang):
    t = I18N[lang]
    counts = {c: sum(1 for m in mods if m["cat"] == c) for c in CATEGORY_ORDER}
    chips = [f'<button type="button" data-c="" aria-pressed="true">{html.escape(t["pack_all"])} <span>{len(mods)}</span></button>']
    chips += [f'<button type="button" data-c="{c}" aria-pressed="false">{html.escape(t["cat"][c])} <span>{n}</span></button>'
              for c, n in counts.items() if n]
    return "".join(chips)


def chat_html(slug, mod_id, mod, lang, root):
    t = I18N[lang]
    strings = {k: t[k] for k in ("chat_open", "chat_placeholder", "chat_send", "chat_reset", "chat_close",
                                 "chat_disclaimer", "chat_error", "chat_busy")}
    strings["chat_title"] = fmt(t["chat_title"], mod=mod)
    return (f'<div id="mod-chat" data-pack="{slug}" data-mod="{html.escape(mod_id)}" data-lang="{lang}"></div>'
            f'<script>window.CHAT_T = {script_json(strings)};</script>'
            f'<script src="{root}static/chat.js" defer></script>')


def schematic_text(name):
    """A schematic as plain text layers + legend, so the chat can answer build questions from the same data."""
    built = schematics.SCHEMATICS[name]()
    blocks = schematics.BLOCKS
    if isinstance(built, dict):
        blocks = {**blocks, **built["blocks"]}
        built = built["layers"]
    used = sorted({c for layer in built for row in layer for c in row})
    lines = []
    for i, layer in enumerate(built):
        lines.append(f"Layer {i + 1} (bottom = 1, seen from above):")
        lines += ["  " + row for row in layer]
    lines.append("Legend: " + "; ".join(f"{c} = {blocks[c][1]['en']}" for c in used if c in blocks))
    return "\n".join(lines)


def guide_context(guide):
    """The guide as English plain text for the chat's system prompt."""
    parts = [guide["intro"]["en"], f"Checked against: {guide['checked']}"]
    for sec in guide["sections"]:
        parts.append(f"\n## {sec['title']['en']}")
        parts += sec.get("text", {}).get("en", [])
        for i, st in enumerate(sec.get("chain", []), 1):
            parts.append(f"{i}. {st['machine']['en']}: {st['in']['en']} -> {st['out']['en']}")
        parts += [f"- {r['en']}" for r in sec.get("rules", [])]
        if sec.get("schematic"):
            parts.append("Minimal valid schematic:\n" + schematic_text(sec["schematic"]))
        if sec.get("sources"):
            parts.append("Sources: " + "; ".join(f"{x['label']} ({x['url']})" for x in sec["sources"]))
    return "\n".join(parts)


def write_chat_context(pack, mods, guides):
    """api/_data/<pack>.json: what the chat function puts in Claude's system prompt for each mod of the pack."""
    cat_names = I18N["en"]["cat"]
    data = {
        "pack": {"name": pack["name"], "short": pack["short"], "minecraft": pack["minecraft"], "loader": pack["loader"],
                 "mods": "\n".join(f"{m['name']} ({m['id']}) {m['version']} [{cat_names[m['cat']]}]" for m in mods)},
        "mods": {},
    }
    for m in mods:
        g = guides.get(m["id"])
        if g and "redirect" in g:
            g = guides[g["redirect"]]
        data["mods"][m["id"]] = {
            "name": m["name"], "version": m["version"], "category": cat_names[m["cat"]],
            "guide": guide_context(g) if g else None,
        }
    out = ROOT / "api" / "_data"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{pack['slug']}.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")


def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "static", OUT / "static")
    (OUT / ".nojekyll").write_text("")
    packs = load_packs()
    pages = []
    loaded_packs = {p["slug"]: load_mods(p) for p in packs if p.get("status") != "planned"}
    total_mods = sum(len(l[0]) for l in loaded_packs.values() if l)
    total_guides = sum(sum(1 for g in l[1].values() if "redirect" not in g) for l in loaded_packs.values() if l)
    for p in packs:
        if loaded_packs.get(p["slug"]):
            write_chat_context(p, *loaded_packs[p["slug"]])

    for lang in LANGS:
        t = I18N[lang]

        # Home: one card per modpack
        cards = []
        for p in packs:
            loaded = loaded_packs.get(p["slug"])
            meta = fmt(t["pack_mc"], mc=p["minecraft"], loader=p["loader"])
            if loaded:
                n_guides = sum(1 for g in loaded[1].values() if "redirect" not in g)
                desc = fmt(t["home_stats"], mods=len(loaded[0]), guides=n_guides)
                cards.append(card("⛏️", p["name"], desc, meta, f"{p['slug']}/", "live", t))
            else:
                cards.append(card("⛏️", p["name"], t["status_planned"], meta, None, "planned", t))
        pages.append(write_page("", lang, {
            "page_title": f"{t['site_name']} · {t['site_tagline']}",
            "page_desc": t["home_lead"],
            "home_stats_line": fmt(t["home_stats"], mods=total_mods, guides=total_guides),
            "pack_cards": "".join(cards),
        }, template("home")))

        for p in packs:
            loaded = loaded_packs.get(p["slug"])
            if not loaded:
                continue
            mods, guides = loaded
            slug, short = p["slug"], p["short"]

            # Pack page: every mod as a card, plus a strip of the pack's tools
            tool_links = []
            for k, icon in TOOLS:
                if k == "mods":
                    continue
                status = p["tools"].get(k, "planned")
                label = f'{icon} {html.escape(t[f"tool_{k}_name"])}'
                tool_links.append(f'<a class="tool-pill" href="{k}/">{label}</a>' if status == "live"
                                  else f'<span class="tool-pill off">{label} · {html.escape(t["status_" + status])}</span>')
            pages.append(write_page(f"{slug}/", lang, {
                "page_title": fmt(t["mods_title"], pack=short) + f" · {t['site_name']}",
                "page_desc": fmt(t["mods_meta"], pack=short, n=len(mods)),
                "pack_name": p["name"],
                "pack_lead_text": fmt(t["pack_lead"], n=len(mods)),
                "pack_mc_line": fmt(t["pack_mc"], mc=p["minecraft"], loader=p["loader"]),
                "pack_search_text": fmt(t["pack_search"], n=len(mods)),
                "tool_links": "".join(tool_links),
                "cat_chips": render_cat_chips(mods, lang),
                "mod_cards": render_mod_cards(mods, guides, p, lang),
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

            # The old list page now lives on the pack page
            redirect = OUT / lang / slug / "mods" / "index.html"
            redirect.parent.mkdir(parents=True, exist_ok=True)
            redirect.write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=../">'
                                '<link rel="canonical" href="../"><a href="../">…</a>\n')

            # One page per mod: its guide if it has one, otherwise its facts; always the chat
            names = {m["id"]: m["name"] for m in mods}
            for m in mods:
                mod_id, mod = m["id"], m["name"]
                path = f"{slug}/mods/{mod_id}/"
                root = "../" * (1 + path.count("/"))
                crumbs = [(short, f"{slug}/"), (mod, path)]
                common = {"pack_short": short, "chat": chat_html(slug, mod_id, mod, lang, root),
                          "head_extra": f'<link rel="stylesheet" href="{root}static/chat.css">'}
                guide = guides.get(mod_id)
                if guide and "redirect" not in guide:
                    toc, sections = render_guide_sections(guide, lang)
                    pages.append(write_page(path, lang, {
                        **common,
                        "page_title": fmt(t["guide_title"], mod=mod, pack=short) + f" · {t['site_name']}",
                        "page_desc": fmt(t["guide_meta"], mod=mod, pack=short),
                        "guide_kicker": f"{short} · {t['badge_guide']}",
                        "guide_heading": mod,
                        "guide_intro": guide["intro"][lang],
                        "guide_checked_line": fmt(t["guide_checked"], what=guide["checked"]),
                        "guide_toc_items": toc,
                        "guide_sections": sections,
                    }, template("guide"), crumbs=crumbs))
                    continue
                if mod_id == "productivebees" and p["tools"].get("bees") == "live":
                    body = f'<p><a class="go-link" href="../../bees/">🐝 {html.escape(t["mod_see_tool"])} →</a></p>'
                elif guide:
                    parent = guide["redirect"]
                    body = (f'<p>{html.escape(fmt(t["mod_see_guide"], guide=names.get(parent, parent)))} '
                            f'<a class="go-link" href="../{parent}/">{html.escape(names.get(parent, parent))} →</a></p>')
                else:
                    body = f'<p class="note">{html.escape(t["mod_no_guide"])}</p>'
                    if m["wanted"]:
                        body += f'<p class="note">{html.escape(t["mod_guide_planned"])}</p>'
                pages.append(write_page(path, lang, {
                    **common,
                    "page_title": f"{mod} · {p['name']} · {t['site_name']}",
                    "page_desc": fmt(t["mod_meta"], mod=mod, pack=short, version=m["version"]),
                    "mod_kicker": f"{short} · {t['cat'][m['cat']]}",
                    "mod_heading": mod,
                    "mod_version_label": fmt(t["mod_version"], pack=short),
                    "mod_version_value": m["version"],
                    "mod_category_value": t["cat"][m["cat"]],
                    "mod_body": body,
                }, template("mod"), crumbs=crumbs))

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
