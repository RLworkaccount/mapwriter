"""The asset browser: one local HTML page for looking through every pack in an index.

`mapwriter browse` writes a folder with ``index.html`` and small thumbnails of your
own art. It stays on your computer: the page reads nothing from the internet and
sends nothing anywhere. Open it in any browser to search by words, kind, pack and
colour, see the art that looks most alike, and mark corrections (extra words, a
different kind) that download as a ``tags.yaml``.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

THUMB_PX = 96


def thumb_name(asset) -> str:
    return hashlib.sha1(asset.id.encode("utf-8")).hexdigest()[:20] + ".webp"


def _make_thumb(asset, out: Path) -> bool:
    if out.exists() and out.stat().st_mtime >= os.path.getmtime(asset.path):
        return True
    try:
        from PIL import Image
        with Image.open(asset.path) as im:
            if im.format == "JPEG":
                im.draft("RGB", (THUMB_PX * 2, THUMB_PX * 2))
            im = im.convert("RGBA")
            im.thumbnail((THUMB_PX, THUMB_PX))
            im.save(out, "WEBP", quality=80)
        return True
    except Exception:
        return False


def entry(asset, thumb: str | None) -> dict:
    lk = asset.look or {}
    return {
        "id": asset.id, "pack": asset.pack, "rel": asset.rel, "kind": asset.kind,
        "words": asset.words, "tags": asset.extra_tags, "guessed": asset.guessed,
        "fp": asset.footprint, "colours": lk.get("colours", []), "sig": lk.get("sig"),
        "ink": lk.get("ink"), "sat": lk.get("sat"), "bright": lk.get("bright"), "tile": lk.get("tile"),
        "thumb": thumb, "src": Path(asset.path).resolve().as_uri() if asset.root else None,
    }


def write_browser(index, out_dir, thumbs: bool = True, workers: int = 8, packs=None, progress=None) -> Path:
    """Write the page and thumbnails to ``out_dir``. Returns the page's path."""
    out = Path(out_dir)
    (out / "thumbs").mkdir(parents=True, exist_ok=True)
    assets = [a for a in index.assets if not packs or a.pack in packs]
    names = [thumb_name(a) for a in assets]
    ok = [False] * len(assets)
    if thumbs and assets:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max(1, workers)) as ex:
            done = 0
            for i, good in enumerate(ex.map(lambda t: _make_thumb(t[0], out / "thumbs" / t[1]),
                                            zip(assets, names), chunksize=32)):
                ok[i] = good
                done += 1
                if progress and done % 2000 == 0:
                    progress(done, len(assets))
    data = [entry(a, f"thumbs/{n}" if good else None) for a, n, good in zip(assets, names, ok)]
    from .assets.style import describe
    styles = {p: {"text": describe(st), **st} for p, st in index.styles.items() if st}
    meta = {"packs": index.pack_order, "styles": styles, "count": len(data)}
    page = PAGE.replace("/*DATA*/", "const ASSETS = " + json.dumps(data, separators=(",", ":")) + ";\n"
                        + "const META = " + json.dumps(meta, separators=(",", ":")) + ";")
    p = out / "index.html"
    p.write_text(page, encoding="utf-8")
    return p


PAGE = r"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MapWriter asset browser</title>
<style>
:root { --bg:#f6f4ef; --panel:#fffdf8; --ink:#24211c; --muted:#6d665b; --line:#ddd6c8; --accent:#8a4b1f; --chip:#efe8da; --check:#e9e4da; }
@media (prefers-color-scheme: dark) { :root { --bg:#1b1a18; --panel:#252320; --ink:#ece6da; --muted:#a59d8f; --line:#3a3631; --accent:#e09a5c; --chip:#34302b; --check:#2d2a26; } }
* { box-sizing: border-box; }
body { margin:0; font:14px/1.45 system-ui, sans-serif; background:var(--bg); color:var(--ink); }
header { position:sticky; top:0; z-index:2; background:var(--panel); border-bottom:1px solid var(--line); padding:10px 16px; display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
header h1 { font-size:16px; margin:0 12px 0 0; }
input, select, button { font:inherit; color:inherit; background:var(--bg); border:1px solid var(--line); border-radius:6px; padding:6px 8px; }
input[type=search] { flex:1 1 220px; min-width:0; }
button { cursor:pointer; } button.primary { background:var(--accent); color:#fff; border-color:var(--accent); }
label.tog { display:flex; gap:4px; align-items:center; color:var(--muted); }
main { display:grid; grid-template-columns: 1fr minmax(0, 360px); gap:0; }
#grid { padding:12px 16px; display:grid; grid-template-columns:repeat(auto-fill, minmax(112px, 1fr)); gap:10px; align-content:start; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:6px; cursor:pointer; min-width:0; }
.card.sel { outline:2px solid var(--accent); }
.card.fixed { border-color:var(--accent); }
.pic { aspect-ratio:1; display:flex; align-items:center; justify-content:center; border-radius:4px;
  background: repeating-conic-gradient(var(--check) 0 25%, transparent 0 50%) 0 0/16px 16px; overflow:hidden; }
.pic img { max-width:100%; max-height:100%; }
.name { font-size:11px; color:var(--muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-top:4px; }
aside { border-left:1px solid var(--line); background:var(--panel); padding:14px 16px; position:sticky; top:57px; height:calc(100vh - 57px); overflow:auto; }
aside h2 { font-size:15px; margin:0 0 6px; word-break:break-all; }
aside .big { aspect-ratio:1; max-height:260px; margin-bottom:10px; }
.chips { display:flex; flex-wrap:wrap; gap:4px; margin:4px 0 8px; }
.chip { background:var(--chip); border-radius:10px; padding:1px 8px; font-size:12px; }
.chip.g { border:1px dashed var(--muted); background:none; }
dl { display:grid; grid-template-columns:auto 1fr; gap:2px 10px; margin:8px 0; font-size:13px; } dt { color:var(--muted); }
.alikes { display:grid; grid-template-columns:repeat(4, 1fr); gap:6px; }
.alikes .card { padding:3px; }
.status { padding:8px 16px 0; color:var(--muted); }
.more { grid-column:1/-1; justify-self:center; }
.fix { border-top:1px solid var(--line); margin-top:12px; padding-top:10px; display:grid; gap:6px; }
.empty { color:var(--muted); }
@media (max-width: 760px) { header { position:static; } main { grid-template-columns:1fr; } aside { position:static; height:auto; border-left:0; border-top:1px solid var(--line); } }
</style>
</head>
<body>
<header>
  <h1>Asset browser</h1>
  <input type="search" id="q" placeholder="Words, e.g. round table" aria-label="Search words">
  <select id="kind" aria-label="Kind"><option value="">All kinds</option></select>
  <select id="pack" aria-label="Pack"><option value="">All packs</option></select>
  <select id="colour" aria-label="Colour"><option value="">Any colour</option></select>
  <label class="tog"><input type="checkbox" id="vague"> Guessed words only</label>
  <button id="dl" class="primary" title="Download your corrections as tags.yaml">Download tags.yaml (<span id="nfix">0</span>)</button>
</header>
<div class="status" id="status"></div>
<main>
  <div id="grid"></div>
  <aside id="side"><p class="empty">Click a picture to see what MapWriter knows about it, the art that looks most like it, and to correct its words or kind.</p></aside>
</main>
<script>
/*DATA*/
const KINDS = ["prop","floor","wall","door","window","overlay","roof","effect"];
const COLOURS = ["red","orange","yellow","green","teal","blue","purple","pink","brown","grey","white","black"];
const PAGE = 240;
let shown = PAGE, results = [], current = null;
let fixes = {};
try { fixes = JSON.parse(localStorage.getItem("mapwriter-fixes") || "{}"); } catch (e) { fixes = {}; }
const byId = new Map(ASSETS.map(a => [a.id, a]));
const $ = id => document.getElementById(id);
function fill(sel, vals) { for (const v of vals) { const o = document.createElement("option"); o.value = o.textContent = v; sel.appendChild(o); } }
fill($("kind"), KINDS.filter(k => ASSETS.some(a => a.kind === k)));
fill($("pack"), META.packs);
fill($("colour"), COLOURS);
function saveFixes() { try { localStorage.setItem("mapwriter-fixes", JSON.stringify(fixes)); } catch (e) {} $("nfix").textContent = Object.keys(fixes).length; }
function stem(w) { w = w.toLowerCase(); if (w.length > 4 && w.endsWith("ies")) return w.slice(0, -3) + "y"; if (w.length > 5 && /(ches|shes|xes)$/.test(w)) return w.slice(0, -2); if (w.length > 3 && w.endsWith("s") && !/(ss|us)$/.test(w)) return w.slice(0, -1); return w; }
function wordsOf(a) { const f = fixes[a.id]; return new Set([...a.words, ...a.tags, ...a.guessed, ...a.colours, ...(f && f.words ? f.words : [])]); }
function kindOf(a) { const f = fixes[a.id]; return f && f.kind ? f.kind : a.kind; }
function score(a, qs) {
  const ws = wordsOf(a); let s = 0;
  for (const q of qs) { if (!ws.has(q)) return -1; s += a.words.includes(q) ? 2 : 1; }
  const name = a.rel.split("/").pop().toLowerCase();
  if (qs.length && name.startsWith(qs[qs.length - 1])) s += 2;
  return s;
}
function search() {
  const qs = $("q").value.split(/[^A-Za-z]+/).filter(Boolean).map(stem);
  const k = $("kind").value, p = $("pack").value, c = $("colour").value, g = $("vague").checked;
  const out = [];
  for (const a of ASSETS) {
    if (k && kindOf(a) !== k) continue; if (p && a.pack !== p) continue;
    if (c && !a.colours.includes(c)) continue; if (g && !a.guessed.length) continue;
    const s = qs.length ? score(a, qs) : 0; if (s < 0) continue;
    out.push([s, a]);
  }
  if (qs.length) out.sort((x, y) => y[0] - x[0] || x[1].id.localeCompare(y[1].id));
  results = out.map(t => t[1]); shown = PAGE; draw();
}
function card(a, small) {
  const d = document.createElement("div"); d.className = "card" + (fixes[a.id] ? " fixed" : "") + (current === a ? " sel" : "");
  const pic = document.createElement("div"); pic.className = "pic";
  const src = a.thumb || a.src;
  if (src) { const im = document.createElement("img"); im.loading = "lazy"; im.alt = ""; im.src = src; pic.appendChild(im); }
  d.appendChild(pic);
  if (!small) { const n = document.createElement("div"); n.className = "name"; n.textContent = a.rel.split("/").pop(); n.title = a.id; d.appendChild(n); }
  else d.title = a.rel.split("/").pop();
  d.onclick = () => show(a);
  return d;
}
function draw() {
  const grid = $("grid"); grid.textContent = "";
  for (const a of results.slice(0, shown)) grid.appendChild(card(a));
  if (results.length > shown) { const b = document.createElement("button"); b.className = "more"; b.textContent = `Show more (${results.length - shown} left)`; b.onclick = () => { shown += PAGE; draw(); }; grid.appendChild(b); }
  $("status").textContent = `${results.length} of ${ASSETS.length} pictures` + (results.length ? "" : ": nothing matches");
}
function dist(x, y) { const W = [1,1,1,1,1,1,1,1,1,1,1,1,0.6,0.5,0.5,0.4,0.4,0.2]; let s = 0, t = 0; for (let i = 0; i < W.length; i++) { s += W[i] * Math.abs(x[i] - y[i]); t += W[i]; } return s / t * 2; }
function alikes(a, n) {
  if (!a.sig) return [];
  return ASSETS.filter(b => b !== a && b.sig && b.kind === a.kind).map(b => [dist(a.sig, b.sig), b]).sort((x, y) => x[0] - y[0]).slice(0, n).map(t => t[1]);
}
function chips(list, cls) { const d = document.createElement("div"); d.className = "chips"; for (const w of list) { const c = document.createElement("span"); c.className = "chip " + (cls || ""); c.textContent = w; d.appendChild(c); } return d; }
function row(dl, k, v) { const t = document.createElement("dt"); t.textContent = k; const d = document.createElement("dd"); d.style.margin = 0; d.textContent = v; dl.append(t, d); }
function show(a) {
  current = a; draw();
  const s = $("side"); s.textContent = "";
  const h = document.createElement("h2"); h.textContent = a.rel.split("/").pop(); s.appendChild(h);
  const big = document.createElement("div"); big.className = "pic big";
  const im = document.createElement("img"); im.alt = ""; im.src = a.src || a.thumb; im.onerror = () => { if (a.thumb && im.src !== a.thumb) im.src = a.thumb; }; big.appendChild(im); s.appendChild(big);
  s.appendChild(chips(a.words));
  if (a.tags.length) s.appendChild(chips(a.tags));
  if (a.guessed.length) { const p = document.createElement("div"); p.className = "empty"; p.textContent = "Guessed from the picture:"; s.appendChild(p); s.appendChild(chips(a.guessed, "g")); }
  const dl = document.createElement("dl");
  row(dl, "Pack", a.pack + (META.styles[a.pack] ? ` (${META.styles[a.pack].text})` : ""));
  row(dl, "Kind", kindOf(a)); row(dl, "Footprint", a.fp ? a.fp.join(" x ") + " squares" : "none (tiles)");
  if (a.sig) { row(dl, "Colours", a.colours.join(", ") || "mixed"); row(dl, "Outline ink", Math.round(a.ink * 100) + "%"); row(dl, "Colour strength", Math.round(a.sat * 100) + "%"); row(dl, "Brightness", Math.round(a.bright * 100) + "%"); if (a.tile) row(dl, "Tiles", "seamlessly"); }
  else row(dl, "Picture", "not measured yet (run mapwriter look)");
  row(dl, "Path", a.rel); s.appendChild(dl);
  const al = alikes(a, 12);
  if (al.length) { const p = document.createElement("div"); p.className = "empty"; p.textContent = "Looks most like:"; s.appendChild(p); const g = document.createElement("div"); g.className = "alikes"; for (const b of al) g.appendChild(card(b, true)); s.appendChild(g); }
  const fx = document.createElement("div"); fx.className = "fix";
  const f = fixes[a.id] || {};
  const lab = document.createElement("label"); lab.textContent = "Extra words (comma separated)";
  const inp = document.createElement("input"); inp.value = (f.words || []).join(", "); inp.placeholder = "e.g. market, stall";
  const ks = document.createElement("select"); fill(ks, ["(kind unchanged)", ...KINDS]); ks.value = f.kind || "(kind unchanged)";
  const btns = document.createElement("div"); btns.style.display = "flex"; btns.style.gap = "6px";
  const save = document.createElement("button"); save.className = "primary"; save.textContent = "Keep correction";
  const clear = document.createElement("button"); clear.textContent = "Clear";
  save.onclick = () => { const ws = inp.value.split(",").map(x => x.trim().toLowerCase()).filter(Boolean); const k = ks.value.startsWith("(") ? null : ks.value; if (ws.length || k) fixes[a.id] = { rel: a.rel, words: ws, kind: k }; else delete fixes[a.id]; saveFixes(); show(a); };
  clear.onclick = () => { delete fixes[a.id]; saveFixes(); show(a); };
  btns.append(save, clear); fx.append(lab, inp, ks, btns); s.appendChild(fx);
}
function yamlKey(s) { return JSON.stringify(s); }
$("dl").onclick = () => {
  const ids = Object.keys(fixes); if (!ids.length) { alertless("No corrections yet: click a picture and add words or a kind."); return; }
  const lines = ["# Corrections made in the MapWriter asset browser.", "# Use as tags.yaml (or copy the lines into yours): mapwriter render scene.yaml -t tags.yaml", ""];
  for (const id of ids) { const f = fixes[id]; if (f.words && f.words.length) lines.push(`${yamlKey(f.rel)}: [${f.words.map(yamlKey).join(", ")}]`); }
  const ks = ids.filter(id => fixes[id].kind); if (ks.length) { lines.push("kinds:"); for (const id of ks) lines.push(`  ${yamlKey(fixes[id].rel)}: ${fixes[id].kind}`); }
  const blob = new Blob([lines.join("\n") + "\n"], { type: "text/yaml" });
  const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = "tags.yaml"; link.click();
};
function alertless(msg) { $("status").textContent = msg; }
let timer = null;
for (const id of ["q", "kind", "pack", "colour", "vague"]) $(id).addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(search, 120); });
saveFixes(); search();
</script>
</body>
</html>
"""
