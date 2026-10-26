/* Bee planner. Expects BEES, T, LANG and STORE_KEY from the page (see templates/bees.html). */
const byId = Object.fromEntries(BEES.map(b => [b.id, b]));
const kids = {};
BEES.forEach(b => b.methods.forEach(m => m.parents.forEach(p => { (kids[p] ||= new Set()).add(b.id) })));

let done = new Set();
try { done = new Set(JSON.parse(localStorage.getItem(STORE_KEY) || '[]')) } catch (e) {}
const save = () => { try { localStorage.setItem(STORE_KEY, JSON.stringify([...done])) } catch (e) {} };

const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fmt = (s, v) => s.replace(/\{(\w+)\}/g, (_, k) => v[k]);
const nm = id => byId[id] ? byId[id].name : id;
const ready = m => m.parents.every(p => done.has(p));
const avail = b => !done.has(b.id) && (!!b.special || b.methods.some(ready));
const status = b => done.has(b.id) ? 'done' : avail(b) ? 'avail' : 'lock';
const qt = s => LANG === 'fr' ? `«\u00a0${s}\u00a0»` : `"${s}"`;
const itemText = i => (i.n.startsWith('tag ') ? `${T.tag} ${qt(i.n.slice(4))}` : i.n) + (i.m ? ` (${i.m})` : '');
const itemHtml = i => `<span class="item">${esc(i.n.startsWith('tag ') ? `${T.tag} ${qt(i.n.slice(4))}` : i.n)}${i.m ? ` <span class="m">${esc(i.m)}</span>` : ''}</span>`;
// Search matches the name in both languages (French players often know the English in-game name),
// the bee's mod, and the items its recipes use
const haystack = b => [b.name, b.alt, b.mod, b.flower && itemText(b.flower), ...b.methods.flatMap(m => m.items.map(itemText))].join('\n').toLowerCase();
const HAY = Object.fromEntries(BEES.map(b => [b.id, haystack(b)]));
const matches = (b, q) => HAY[b.id].includes(q);
let modFilter = '';

/* ---------- layout ---------- */
const S = 46, G = 14, PER = 18, ROWG = 16, BANDG = 46, LEFT = 90, TOPY = 120;
const tiers = {};
BEES.forEach(b => (tiers[b.tier] ||= []).push(b));
const tierKeys = Object.keys(tiers).map(Number).sort((a, b) => a - b);
const pos = {};
const W = LEFT + PER * (S + G) + 30;
let y = TOPY;
const bands = [];
tierKeys.forEach(t => {
  let list = tiers[t];
  // order by average x of parents (fewer crossings), then name
  const bx = b => { const xs = []; b.methods.forEach(m => m.parents.forEach(p => pos[p] && xs.push(pos[p].x))); return xs.length ? xs.reduce((a, c) => a + c, 0) / xs.length : W / 2 };
  list = list.map(b => [bx(b), b]).sort((a, c) => a[0] - c[0] || a[1].name.localeCompare(c[1].name, LANG)).map(e => e[1]);
  const rows = Math.ceil(list.length / PER);
  const y0 = y;
  for (let r = 0; r < rows; r++) {
    const row = list.slice(r * PER, (r + 1) * PER);
    const rowW = row.length * (S + G) - G;
    const x0 = LEFT + (PER * (S + G) - G - rowW) / 2;
    row.forEach((b, i) => { pos[b.id] = { x: x0 + i * (S + G) + S / 2, y: y + S / 2 } });
    y += S + ROWG;
  }
  bands.push({ t, y0, y1: y - ROWG, n: list.length });
  y += BANDG - ROWG;
});
const H = y + 20;

const svg = document.getElementById('svg');
let zoom = window.innerWidth < 700 ? 0.7 : 1;
function sizeSvg() { svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('width', W * zoom); svg.setAttribute('height', H * zoom) }

function beeIcon(b) {
  // tiny pixel bee in the bee's colours
  const c = b.color, c2 = b.color2 || '#222';
  return `<g class="ic" transform="translate(-13,-12)" shape-rendering="crispEdges">
    <rect x="9" y="1" width="7" height="5" fill="#eaf6ff" stroke="#2b1d0e" stroke-width="1"/>
    <rect x="3" y="7" width="20" height="13" fill="${c}" stroke="#2b1d0e" stroke-width="1.5"/>
    <rect x="9" y="7" width="3" height="13" fill="${c2}"/><rect x="15" y="7" width="3" height="13" fill="${c2}"/>
    <rect x="19" y="10" width="3" height="3" fill="#111"/><rect x="0" y="12" width="3" height="2" fill="#2b1d0e"/></g>`;
}

let linkMode = 'all'; // all | sel
let selected = null, hovered = null;

function draw() {
  sizeSvg();
  const parts = [];
  // bands
  bands.forEach(bd => parts.push(`<text class="band-label" x="10" y="${bd.y0 + 18}">${esc(fmt(T.tier, { t: bd.t }))}</text><text class="band-label" x="10" y="${bd.y0 + 36}" style="font-size:12px">${esc(fmt(T.n_bees, { n: bd.n }))}</text>`));
  // root box
  const rootW = 360, rootX = LEFT + (PER * (S + G) - G - rootW) / 2;
  parts.push(`<g class="root"><rect x="${rootX}" y="20" width="${rootW}" height="58"/><text x="${rootX + rootW / 2}" y="57" text-anchor="middle">${esc(T.root)}</text></g>`);
  // edges (with a mod filter on, only links touching that mod's bees stay visible)
  const keep = id => modFilter && byId[id] && byId[id].mod === modFilter;
  const edges = [];
  BEES.forEach(b => {
    const seen = new Set();
    if (b.tier === 0) {
      edges.push(`<line class="edge ${done.has(b.id) ? 'e-done' : 'e-avail'}${keep(b.id) ? ' keep' : ''}" data-c="${esc(b.id)}" x1="${rootX + rootW / 2}" y1="78" x2="${pos[b.id].x}" y2="${pos[b.id].y - S / 2}"/>`);
      return;
    }
    b.methods.forEach(m => m.parents.forEach(p => {
      if (seen.has(p) || !pos[p]) return; seen.add(p);
      const cls = done.has(b.id) ? 'e-done' : (done.has(p) ? 'e-avail' : 'e-lock');
      const a = pos[p], c = pos[b.id];
      const my = (a.y + S / 2 + c.y - S / 2) / 2;
      edges.push(`<path class="edge ${cls}${keep(b.id) || keep(p) ? ' keep' : ''}" data-p="${esc(p)}" data-c="${esc(b.id)}" d="M${a.x} ${a.y + S / 2} C${a.x} ${my} ${c.x} ${my} ${c.x} ${c.y - S / 2}"/>`);
    }));
  });
  parts.push(edges.join(''));
  // nodes
  const q = query.trim().toLowerCase();
  BEES.forEach(b => {
    const p = pos[b.id], st = status(b);
    const hit = q && matches(b, q);
    const dim = modFilter && b.mod !== modFilter;
    parts.push(`<g class="node ${st}${selected === b.id ? ' sel' : ''}${hit ? ' hit' : ''}${dim ? ' dim' : ''}" data-id="${esc(b.id)}" tabindex="0" role="button" aria-label="${esc(b.name)}" transform="translate(${p.x},${p.y})">
      <rect class="bg" x="${-S / 2}" y="${-S / 2}" width="${S}" height="${S}" rx="5"/>
      <rect class="bevel" x="${-S / 2 + 3}" y="${-S / 2 + 3}" width="${S - 6}" height="${S - 6}" rx="3"/>${beeIcon(b)}</g>`);
  });
  svg.innerHTML = parts.join('');
  svg.classList.toggle('selmode', linkMode === 'sel');
  svg.classList.toggle('filtering', !!modFilter);
  highlight();
  const n = BEES.filter(b => done.has(b.id)).length;
  document.getElementById('count').textContent = `${n} / ${BEES.length}`;
  document.getElementById('barfill').style.width = (n / BEES.length * 100) + '%';
}

/* ---------- text helpers ---------- */
const pct = c => LANG === 'fr' ? `${Math.round(c * 100)} %` : `${Math.round(c * 100)}%`;
const biomeText = s => s.split(',').map(x => x.trim()).map(x => T.biomes[x] || x.replace(/^#?minecraft:/, '').replace(/^#/, '').replace(/_/g, ' ')).join(', ');
function kindText(m) {
  if (m.kind === 'breeding') return T.k_breeding;
  if (m.kind === 'conversion') return T.k_conversion + (m.chance ? ` (${pct(m.chance)})` : '');
  if (m.kind === 'nest') return T.k_nest + m.items.map(i => i.n).join(', ');
  if (m.kind === 'fishing') return T.k_fishing + (m.chance ? ` ${pct(m.chance)}` : '');
  if (m.kind === 'item_conversion') return T.k_item_conversion;
  return T.machines[m.machine] || m.machine;
}

/* ---------- tooltip ---------- */
const tip = document.getElementById('tip');
function showTip(b, ev) {
  const lines = [`<div>${esc(b.name)}</div>`, `<div class="mod">${esc(b.mod)}</div>`];
  if (b.special) lines.push(`<div class="sub">${esc(b.special)}</div>`);
  const withParents = b.methods.filter(m => m.parents.length);
  if (!withParents.length && !b.special) b.methods.slice(0, 2).forEach(m => lines.push(`<div class="sub">${esc(kindText(m))}${m.biomes ? ' · ' + esc(biomeText(m.biomes)) : ''}</div>`));
  withParents.slice(0, 3).forEach((m, i) => {
    lines.push(`<div class="req">${i ? T.or : ''}${esc(T.requires)} ${m.parents.length > 1 ? esc(T.and) : ''}</div>`);
    m.parents.forEach(p => lines.push(`<div class="${done.has(p) ? 'ok' : 'req'}">- ${esc(nm(p))}</div>`));
    if (m.items.length) lines.push(`<div class="sub">+ ${esc(m.items.slice(0, 2).map(itemText).join(', '))}</div>`);
  });
  if (withParents.length > 3) lines.push(`<div class="sub">${esc(fmt(T.more_methods, { n: withParents.length - 3 }))}</div>`);
  tip.innerHTML = lines.join(''); tip.hidden = false; moveTip(ev);
}
function moveTip(ev) {
  const r = tip.getBoundingClientRect();
  let x = ev.clientX + 14, yy = ev.clientY + 14;
  if (x + r.width > innerWidth - 8) x = ev.clientX - r.width - 14;
  if (yy + r.height > innerHeight - 8) yy = ev.clientY - r.height - 14;
  tip.style.left = Math.max(8, x) + 'px'; tip.style.top = Math.max(8, yy) + 'px';
}

/* ---------- drawer ---------- */
let openId = null;
function chip(id) { return `<button type="button" class="chip ${done.has(id) ? 'done' : ''}" data-open="${esc(id)}">${esc(nm(id))}${done.has(id) ? ' ✓' : ''}</button>` }
function openDrawer(id) {
  const b = byId[id]; if (!b) return;
  openId = id; selected = id; draw();
  // Shareable link to this bee (e.g. to answer a question on Reddit or Discord)
  history.replaceState(null, '', '#' + encodeURIComponent(id));
  const st = status(b);
  const ch = [...(kids[id] || [])].map(k => byId[k]).filter(Boolean).sort((a, c) => a.tier - c.tier);
  const d = document.getElementById('drawer');
  d.innerHTML = `<div class="d-head"><svg width="48" height="48" viewBox="-24 -24 48 48" aria-hidden="true"><rect x="-23" y="-23" width="46" height="46" rx="5" fill="var(--${st === 'done' ? 'done-lo' : st === 'avail' ? 'avail-lo' : 'lock'})" stroke="#0c0d10" stroke-width="2"/>${beeIcon(b)}</svg>
    <h3 id="d-title">${esc(b.name)}${b.alt && b.alt !== b.name ? `<span class="alt">${esc(b.alt)}</span>` : ''}</h3><button class="close" type="button" aria-label="${esc(T.close)}">×</button></div>
    <div class="state"><span class="pill modname">${esc(T.mod)}${LANG === 'fr' ? '\u00a0: ' : ': '}${esc(b.mod)}</span><span class="pill">${esc(fmt(T.tier, { t: b.tier }))}</span><span class="pill">${esc(st === 'done' ? T.state_done : st === 'avail' ? T.state_avail : T.state_lock)}</span></div>
    <button type="button" class="primary ${st === 'done' ? 'undo' : ''}" data-toggle="${esc(id)}">${esc(st === 'done' ? T.untick : T.tick)}</button>
    ${b.desc ? `<p class="desc">${esc(b.desc)}</p>` : ''}
    <div class="sec"><h4>${esc(T.how_to_get)}</h4>
      ${b.special ? `<div class="method ready"><div class="kind">${esc(b.special)}</div></div>` : ''}
      ${b.methods.map((m, i) => `<div class="method ${m.parents.length && ready(m) ? 'ready' : ''}"><div class="kind">${i || b.special ? esc(T.or_method) : ''}${esc(kindText(m))}</div>
        ${m.parents.length ? `<div class="chips">${m.parents.map(chip).join(m.kind === 'breeding' ? '<span>×</span>' : '')}</div>` : ''}
        ${m.items.length && m.kind !== 'nest' ? `<div class="meta">${esc(T.with)}${m.items.map(itemHtml).join(', ')}</div>` : ''}
        ${m.biomes ? `<div class="meta">${esc(T.where)}${esc(biomeText(m.biomes))}</div>` : ''}</div>`).join('')}</div>
    ${b.flower ? `<div class="sec"><h4>${esc(T.flower)}</h4><div>${itemHtml(b.flower)}</div></div>` : ''}
    ${ch.length ? `<div class="sec"><h4>${esc(T.unlocks)}</h4><div class="chips">${ch.map(k => chip(k.id)).join('')}</div></div>` : ''}`;
  d.hidden = false; document.getElementById('scrim').hidden = false;
}
function closeDrawer() {
  openId = null; selected = null; document.getElementById('drawer').hidden = true; document.getElementById('scrim').hidden = true;
  history.replaceState(null, '', location.pathname + location.search); draw();
}

/* ---------- toggle + toast ---------- */
let toastTimer;
function toggle(id) {
  const before = new Set(BEES.filter(avail).map(b => b.id));
  if (done.has(id)) { done.delete(id); save(); hideToast() }
  else {
    done.add(id); save();
    const un = BEES.filter(b => avail(b) && !before.has(b.id));
    const t = document.getElementById('toast');
    t.innerHTML = `<button class="x" type="button" aria-label="${esc(T.close)}">×</button><div>${esc(fmt(T.toast_done, { name: nm(id) }))}</div>` +
      (un.length ? `<div>${esc(fmt(T.toast_unlocks, { n: un.length }))}</div><div class="chips">${un.map(b => `<button type="button" class="chip" data-open="${esc(b.id)}">${esc(b.name)}</button>`).join('')}</div>`
        : `<div style="font-size:13px">${esc(T.toast_nothing)}</div>`);
    t.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(hideToast, un.length ? 12000 : 4000);
  }
  if (openId) openDrawer(openId); else draw();
}
function hideToast() { document.getElementById('toast').hidden = true }

/* ---------- interactions ---------- */
let query = '';
const board = document.getElementById('board');
svg.addEventListener('mouseover', e => { const g = e.target.closest('.node'); if (!g) return; hovered = g.dataset.id; showTip(byId[hovered], e); highlight() });
svg.addEventListener('mousemove', e => { if (!tip.hidden) moveTip(e) });
svg.addEventListener('mouseout', e => { const g = e.target.closest('.node'); if (!g || (e.relatedTarget && g.contains(e.relatedTarget))) return; hovered = null; tip.hidden = true; highlight() });
function highlight() {
  const f = hovered || selected;
  svg.querySelectorAll('.edge').forEach(e => e.classList.toggle('hl', !!f && (e.dataset.p === f || e.dataset.c === f)));
}

let drag = null, moved = false;
board.addEventListener('pointerdown', e => { if (e.pointerType !== 'mouse' || e.button !== 0) return; drag = { x: e.clientX, y: e.clientY, l: board.scrollLeft, t: board.scrollTop }; moved = false });
addEventListener('pointermove', e => { if (!drag) return; const dx = e.clientX - drag.x, dy = e.clientY - drag.y; if (Math.abs(dx) + Math.abs(dy) > 4) { moved = true; board.classList.add('drag') } board.scrollLeft = drag.l - dx; board.scrollTop = drag.t - dy });
addEventListener('pointerup', () => { drag = null; board.classList.remove('drag') });

document.addEventListener('click', e => {
  const tg = e.target.closest('[data-toggle]'); if (tg) { toggle(tg.dataset.toggle); return }
  const op = e.target.closest('[data-open]'); if (op) { openDrawer(op.dataset.open); return }
  const nd = e.target.closest('.node'); if (nd && !moved) { tip.hidden = true; openDrawer(nd.dataset.id); return }
  if (e.target.closest('.close') || e.target.id === 'scrim') closeDrawer();
  if (e.target.closest('.toast .x')) hideToast();
});
svg.addEventListener('keydown', e => { const nd = e.target.closest('.node'); if (nd && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); openDrawer(nd.dataset.id) } });
document.addEventListener('keydown', e => { if (e.key === 'Escape' && openId) closeDrawer() });

function setZoom(z) {
  const cx = (board.scrollLeft + board.clientWidth / 2) / zoom, cy = (board.scrollTop + board.clientHeight / 2) / zoom;
  zoom = Math.min(2, Math.max(0.35, z)); sizeSvg();
  board.scrollLeft = cx * zoom - board.clientWidth / 2; board.scrollTop = cy * zoom - board.clientHeight / 2;
}
const scrollToBee = (b, behavior) => { const p = pos[b.id]; board.scrollTo({ left: p.x * zoom - board.clientWidth / 2, top: p.y * zoom - board.clientHeight / 2, behavior }) };
document.getElementById('zin').onclick = () => setZoom(zoom * 1.2);
document.getElementById('zout').onclick = () => setZoom(zoom / 1.2);
board.addEventListener('wheel', e => { if (!e.ctrlKey) return; e.preventDefault(); setZoom(zoom * (e.deltaY < 0 ? 1.1 : 1 / 1.1)) }, { passive: false });
const linksBtn = document.getElementById('links');
linksBtn.onclick = () => { linkMode = linkMode === 'all' ? 'sel' : 'all'; linksBtn.textContent = linkMode === 'all' ? T.links_all : T.links_sel; draw() };
document.getElementById('q').addEventListener('input', e => {
  query = e.target.value; draw();
  const q = query.trim().toLowerCase(); if (!q) return;
  const b = BEES.find(x => matches(x, q));
  if (b) scrollToBee(b, 'smooth');
});
const modSel = document.getElementById('mod');
const modCounts = {};
BEES.forEach(b => modCounts[b.mod] = (modCounts[b.mod] || 0) + 1);
Object.keys(modCounts).sort((a, c) => a.localeCompare(c, LANG)).forEach(m => modSel.add(new Option(`${m} (${modCounts[m]})`, m)));
modSel.addEventListener('change', () => {
  modFilter = modSel.value; draw();
  const b = modFilter && BEES.find(x => x.mod === modFilter);
  if (b) scrollToBee(b, 'smooth');
});
const resetBtn = document.getElementById('reset');
resetBtn.onclick = () => {
  if (resetBtn.dataset.c) { done.clear(); save(); draw(); resetBtn.textContent = T.reset; delete resetBtn.dataset.c; return }
  resetBtn.dataset.c = '1'; resetBtn.textContent = T.reset_confirm;
  setTimeout(() => { resetBtn.textContent = T.reset; delete resetBtn.dataset.c }, 4000);
};

draw();
board.scrollLeft = (W * zoom - board.clientWidth) / 2;
// Open the bee named in the URL (#productivebees:iron), carried over by the language switch too
const fromHash = byId[decodeURIComponent(location.hash.slice(1))];
if (fromHash) { scrollToBee(fromHash, 'auto'); openDrawer(fromHash.id) }
document.querySelector('.lang')?.addEventListener('click', e => { if (location.hash) e.currentTarget.href = e.currentTarget.href.split('#')[0] + location.hash });
