"""Talk to it: make and change scene files with the AI assistant you already use.

MapWriter never calls an AI service itself and never needs an API key. Instead:

1. ``mapwriter describe "a riverside mill with a waterwheel"`` writes a *brief*: the
   request, the scene format, the words your asset packs actually use, and a
   starting layout from a template. You give the brief to any assistant (a chat
   on claude.ai, Claude Code, or anything else) and save its reply.
2. ``mapwriter apply reply.md`` reads the scene files out of the reply, checks each
   one against your packs, and draws their sketches side by side. If anything is
   wrong it writes a short follow-up brief listing the problems, to paste back.
3. ``mapwriter edit scene.yaml "make the kitchen two squares wider"`` writes a brief
   for a change to an existing scene; ``mapwriter apply reply.md --edit scene.yaml``
   saves the new version and keeps the old one next to it.

An assistant that can run commands itself (Claude Code, for example) can do the
whole loop on its own: run ``describe --print``, write the files, run ``apply``.
"""
from __future__ import annotations

import collections
import difflib
import re
from pathlib import Path

import yaml

from . import templates
from .assets.index import Index
from .scene import SceneError, parse
from .yamlout import dump

LETTERS = "ABCDEFGH"
DOCS_URL = "https://github.com/RLworkaccount/mapwriter/blob/main/docs/scene-format.md"

CHEAT_SHEET = """\
Scene files are YAML in 5 ft grid squares; x runs right, y runs down, [0, 0] is the top-left corner.
Walls, doors and windows sit on grid lines. A prop's `at` is the top-left square it covers.

name: ...                       grid: { width: 24, height: 18, px_per_square: 140 }
seed: 1                         ground: grass          style: { walls: stone wall, doors: wood door, windows: wood window }
rooms:   - { name, box: [x0, y0, x1, y1] or shape: [[x, y], ...] (straight edges only), floor: words,
             doors: [{ wall: south, at: 6 }], windows: [{ wall: north, at: [3, 8] }], arches: [...] }
           door kinds: door, double (2 wide), secret; add open: true for an open door. walls: none for no walls.
areas:   - { name, box/shape/circle: [x, y, r], floor: words, rough: 0.3, soft: 0.3, smooth: false }
paths:   - { name, points: [[x, y], ...], width: 2, floor: dirt path, rough: 0.25, curve: true }
water:   - { name, circle/box/shape (a pond) or points + width (a river), bank: { floor: mud, width: 0.6 } }
props:   - { want: words, at: [x, y] or centre: [x, y], size: [w, h], rot: 0/90/180/270 (clockwise, 0 = back to the north),
             label: text }    or   { want: words, in: Room name, along: north/south/east/west, count: 2 }
scatter: - { want: oak tree, in: map/area/room name, count: 6 or density: 0.05 (per square), cluster: 3, spread: 2, gap: 0.1,
             avoid: [names] }
lights:  - { at: [x, y], radius: 6, colour: warm/candle/fire/cool/moon/magic or #rrggbb }   (candles, lanterns, fires light themselves)
notes:   - { at: [x, y], text: "for the GM key" }
"""

RULES = """\
- Grid squares are 5 ft. Keep rooms a believable size: a bedroom about 3 x 4 squares, a tavern common room 10 x 8 or more.
- Every walled room needs a door or arch, and doors should not open straight into furniture.
- Put furniture where people would use it: chairs by tables, beds and shelves against walls (`along:`).
- Use `want:` words from the word list below where you can; they are what the user's packs contain.
- Add `notes:` for anything the GM needs to know, and `label:` for important props.
- Keep everything inside the grid. Openings must sit on a room's wall.
"""


# ------------------------------------------------------------------ vocabulary
def vocabulary(index: Index, per_kind: int = 60) -> dict[str, list[str]]:
    """The most common words in the user's packs, by kind: what `want:` should say."""
    noise = {"wood", "stone", "metal", "dark", "light", "red", "blue", "green", "gray", "grey", "brown", "white", "black",
             "furniture", "clutter", "structure", "nature", "texture", "prop", "object", "item", "decor", "small", "large", "medium"}
    import os
    from .assets.index import PART_WORDS
    from .assets.naming import words
    noise |= PART_WORDS
    out = {}
    for kind in ("prop", "floor", "wall", "door", "window"):
        c = collections.Counter()
        for a in index.assets:
            if a.kind == kind:
                # File names only: folder names ("Seating", "Containers") are not things to ask for.
                ws = set(words(os.path.basename(a.rel))) | set(a.extra_tags)
                c.update(w for w in ws if w.isalpha() and len(w) > 2 and w not in noise)
        if c:
            out[kind] = [w for w, _ in c.most_common(per_kind)]
    return out


def _format_reference() -> str:
    here = Path(__file__).resolve()
    for p in (here.parents[2] / "docs" / "scene-format.md", here.parent / "scene-format.md"):
        if p.exists():
            return p.read_text(encoding="utf-8")
    return CHEAT_SHEET + f"\nFull reference: {DOCS_URL}\n"


def guess_template(text: str) -> str | None:
    t = text.lower()
    for word, kind in [("tavern", "tavern"), ("inn", "tavern"), ("pub", "tavern"), ("alehouse", "tavern"),
                       ("shop", "shop"), ("store", "shop"), ("smith", "shop"), ("apothecary", "shop"),
                       ("market", "market"), ("square", "market"), ("fair", "market"),
                       ("clearing", "clearing"), ("forest", "clearing"), ("wood", "clearing"), ("camp", "clearing"), ("glade", "clearing"),
                       ("house", "house"), ("cottage", "house"), ("home", "house"), ("farm", "house"), ("hut", "house")]:
        if re.search(rf"\b{word}", t):
            return kind
    return None


def _words_block(index: Index | None) -> str:
    if index is None:
        return "(No asset index given, so no word list. Plain words such as table, chair, barrel and oak tree usually match.)\n"
    voc = vocabulary(index)
    return "\n".join(f"- {kind}: {', '.join(ws)}" for kind, ws in voc.items()) + "\n"


def _answer_format(n: int) -> str:
    if n == 1:
        return "Reply with the scene file in one ```yaml block. You can add a sentence or two before it about your choices.\n"
    letters = ", ".join(LETTERS[:n])
    return (f"Reply with {n} different layouts ({letters}), each a complete scene file in its own ```yaml block, "
            "with a line before each block saying in a sentence what makes it different. Make them genuinely different "
            "(where the rooms go, where the way in is, how the space is used), not the same plan with furniture moved.\n")


def describe_brief(request: str, index: Index | None = None, options: int = 3, template: str | None = None) -> str:
    kind = template or guess_template(request)
    parts = ["# MapWriter brief: new map", "",
             "You are writing scene files for MapWriter, a battlemap maker. MapWriter turns the YAML into a painted map "
             "using the user's own asset packs, and exports it for Foundry VTT.", "",
             "## What the user wants", "", request.strip(), "",
             "## How to answer", "", _answer_format(options),
             "## Rules", "", RULES,
             "## Words the user's asset packs use", "", _words_block(index)]
    if kind:
        start = dump(templates.make(kind, 0))
        parts += [f"## A starting point (the '{kind}' template)", "",
                  "Use it as a guide to the format and to sensible sizes. Change anything that does not fit the request.", "",
                  "```yaml", start.rstrip(), "```", ""]
    parts += ["## Scene format", "", _format_reference()]
    return "\n".join(parts)


def edit_brief(scene_path: str | Path, request: str, index: Index | None = None) -> str:
    text = Path(scene_path).read_text(encoding="utf-8")
    problems = []
    if index is not None:
        try:
            from .plan import build
            problems = build(parse(yaml.safe_load(text)), index).warnings
        except SceneError as e:
            problems = [f"Scene problem: {e}"]
    parts = ["# MapWriter brief: change a map", "",
             "You are editing a scene file for MapWriter, a battlemap maker. Change only what the user asks for, "
             "keep everything else as it is (names, seed, layout), and keep the comments.", "",
             "## The change", "", request.strip(), "",
             "## How to answer", "", "Reply with the whole new scene file in one ```yaml block, and a line before it "
             "listing what you changed.", "",
             "## The scene file now", "", "```yaml", text.rstrip(), "```", ""]
    if problems:
        parts += ["## Problems MapWriter found in it now (fix these too if the change touches them)", ""]
        parts += [f"- {p}" for p in problems] + [""]
    parts += ["## Rules", "", RULES, "## Words the user's asset packs use", "", _words_block(index),
              "## Scene format", "", _format_reference()]
    return "\n".join(parts)


# ------------------------------------------------------------------ reading replies
YAML_BLOCK = re.compile(r"```(?:ya?ml)?[ \t]*\n(.*?)```", re.S | re.I)


def scenes_in_reply(text: str) -> list[tuple[str, dict | None, str | None]]:
    """Every scene in an assistant's reply: (yaml text, data or None, error or None).

    Takes fenced ```yaml blocks; a reply that is just a scene file works too."""
    blocks = YAML_BLOCK.findall(text)
    if not blocks and re.search(r"^grid:", text, re.M):
        blocks = [text]
    out = []
    for b in blocks:
        try:
            data = yaml.safe_load(b)
        except yaml.YAMLError as e:
            out.append((b, None, f"not valid YAML: {str(e).splitlines()[0]}"))
            continue
        if not isinstance(data, dict) or "grid" not in data:
            continue                    # an example snippet, not a scene
        out.append((b, data, None))
    return out


def check(data: dict, index: Index):
    """(plan or None, list of problems) for one scene."""
    from .plan import build
    try:
        plan = build(parse(data), index)
    except SceneError as e:
        return None, [f"Scene problem: {e}"]
    return plan, list(plan.warnings)


def sheet(plans: list, titles: list[str], px: int = 22):
    """Sketches side by side with a title over each, to choose between layouts."""
    from PIL import Image, ImageDraw
    from .render.sketch import sketch, font
    ims = [sketch(p, px, rings=False) for p in plans]
    band = int(px * 1.6)
    gap = px
    W = sum(i.width for i in ims) + gap * (len(ims) + 1)
    H = max(i.height for i in ims) + band + gap
    out = Image.new("RGB", (W, H), (250, 250, 247))
    d = ImageDraw.Draw(out)
    x = gap
    f = font(max(14, int(px * 0.8)))
    for im, t in zip(ims, titles):
        d.text((x, band // 2 + gap // 2), t, fill=(20, 20, 30), font=f, anchor="lm")
        out.paste(im, (x, band))
        x += im.width + gap
    return out


def _slug(s: str) -> str:
    from .build import slug
    return slug(s)


def write_options(scenes: list[tuple[str, dict]], index: Index, out_dir, stem: str, header: str | None = None,
                  keep_text: bool = False) -> dict:
    """Write each scene as stem-a.yaml, stem-b.yaml ..., check them, and draw the sheet.
    Returns {"files": [...], "problems": {file: [...]}, "sheet": path}."""
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    files, problems, plans, titles = [], {}, [], []
    for i, (text, data) in enumerate(scenes):
        letter = LETTERS[i] if len(scenes) > 1 else ""
        p = out / (f"{stem}-{letter.lower()}.yaml" if letter else f"{stem}.yaml")
        body = text if keep_text else dump(data, header)
        p.write_text(body, encoding="utf-8")
        files.append(p)
        if index is None:
            continue                     # no asset index: write the files, skip checking and sketching
        plan, probs = check(data, index)
        problems[str(p)] = probs
        if plan is not None:
            plans.append(plan)
            n = len(probs)
            titles.append(f"{letter + ': ' if letter else ''}{plan.scene.name}  ({'no problems' if not n else f'{n} to look at'})")
    sheet_path = None
    if plans:
        sheet_path = out / f"{stem}-options.png"
        sheet(plans, titles).save(sheet_path)
    return {"files": files, "problems": problems, "sheet": sheet_path}


def fix_brief(problems: dict) -> str | None:
    bad = {f: ps for f, ps in problems.items() if ps}
    if not bad:
        return None
    lines = ["# MapWriter found some problems", "",
             "Please fix these and send back the corrected scene files, each complete in its own ```yaml block, "
             "in the same order.", ""]
    for f, ps in bad.items():
        lines.append(f"## {Path(f).name}")
        lines += [f"- {p}" for p in ps] + [""]
    return "\n".join(lines)


def apply_edit(reply: str, scene_path: str | Path, index: Index, out_dir) -> dict:
    """Save the scene in a reply as the new version of ``scene_path``; keep the old one."""
    found = [(t, d) for t, d, e in scenes_in_reply(reply) if d is not None]
    if not found:
        errs = [e for _, d, e in scenes_in_reply(reply) if e]
        raise SceneError("No scene file found in the reply" + (f" ({errs[0]})" if errs else "") + ".")
    text, data = found[-1]
    scene_path = Path(scene_path)
    old_text = scene_path.read_text(encoding="utf-8")
    prev = scene_path.with_name(scene_path.stem + ".prev" + scene_path.suffix)
    prev.write_text(old_text, encoding="utf-8")
    new_text = text if text.endswith("\n") else text + "\n"
    scene_path.write_text(new_text, encoding="utf-8")
    old_plan, _ = check(yaml.safe_load(old_text), index)
    new_plan, problems = check(data, index)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    sheet_path = None
    if old_plan is not None and new_plan is not None:
        sheet_path = out / f"{_slug(new_plan.scene.name)}-before-after.png"
        sheet([old_plan, new_plan], ["Before", "After"]).save(sheet_path)
    diff = list(difflib.unified_diff(old_text.splitlines(), new_text.splitlines(), "before", "after", lineterm="", n=0))
    changed = [l for l in diff if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    return {"scene": scene_path, "previous": prev, "problems": problems, "sheet": sheet_path, "changed_lines": changed}
