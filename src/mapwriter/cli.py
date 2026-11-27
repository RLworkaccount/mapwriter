"""mapwriter command line.

    mapwriter starter-pack OUT_DIR          draw the free starter pack
    mapwriter pack-check FOLDER --write     look over a new pack, write mapwriter-pack.yaml
    mapwriter index FOLDER... -o index.json scan asset folders
    mapwriter search "round table"          find assets by words
    mapwriter check scene.yaml              list problems with a scene
    mapwriter sketch scene.yaml             quick block plan (PNG)
    mapwriter render scene.yaml             painted maps, key, check, .dd2vtt
    mapwriter new tavern --options 3        layouts from a template, with a sheet to choose from
    mapwriter describe "a riverside mill"   write a brief for your AI assistant (no API key needed)
    mapwriter edit scene.yaml "wider hall"  write a brief for a change
    mapwriter apply reply.md                read the assistant's reply, check it, draw the options
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__

DEFAULT_INDEX = "mapwriter-index.json"


def _index_args(p):
    p.add_argument("-i", "--index", action="append", help=f"asset index file (default: {DEFAULT_INDEX}); repeat for several")
    p.add_argument("-t", "--tags", action="append", help="tags.yaml with your own tag corrections")


def _load(args):
    from .build import load_index
    paths = args.index or [DEFAULT_INDEX]
    for p in paths:
        if not os.path.exists(p):
            sys.exit(f"No asset index at {p}. Make one first: mapwriter index <asset folder> -o {p}")
    tags = list(args.tags or [])
    if not tags and os.path.exists("tags.yaml"):
        tags = ["tags.yaml"]
    return load_index(paths, tags)


def cmd_starter(args):
    from .testart import build_pack
    n = build_pack(args.out)
    print(f"Drew {n} starter assets in {args.out}")


def cmd_index(args):
    from .assets.index import Index
    idx = Index.build(args.folders, read_sizes=not args.fast)
    idx.save(args.output)
    kinds = ", ".join(f"{v} {k}" for k, v in idx.kinds().items())
    print(f"Indexed {len(idx.assets)} assets ({kinds}) -> {args.output}")


def cmd_pack_check(args):
    from .assets.packcheck import check_pack
    r = check_pack(args.folder, write=args.write, credit=args.credit)
    print(f"{r['pack']}: {r['files']} images ({', '.join(f'{v} {k}' for k, v in sorted(r['kinds'].items()))})")
    print(f"Pixels per square: {r['ppsq'] or 'unknown'} ({r['why']})")
    if r["vague"]:
        print(f"{len(r['vague'])} file(s) with names that say too little; give them words in tags.yaml:")
        for v in r["vague"]:
            print(f"  - {v}")
    if r["manifest"]:
        print(f"Wrote {r['manifest']}. Check it, then run: mapwriter index \"{args.folder}\"")
    elif args.write:
        print("The pack already has a mapwriter-pack.yaml; left it alone.")


def cmd_search(args):
    idx = _load(args)
    kind = None if args.kind == "any" else args.kind
    size = tuple(map(float, args.size.lower().split("x"))) if args.size else None
    res = idx.search(args.words, kind, size, limit=args.limit)
    if not res:
        print(f"Nothing matches '{args.words}' (kind: {args.kind}).")
        return
    for s, a in res:
        fp = "x".join(map(str, a.footprint)) if a.footprint else "?"
        print(f"{s:5.1f}  {fp:>5}  {a.kind:7} {a.id}")


def _plan(args):
    from .build import plan_for
    from .scene import SceneError
    try:
        return plan_for(args.scene, _load(args))
    except SceneError as e:
        sys.exit(f"Scene problem: {e}")


def _report(plan):
    if plan.warnings:
        print(f"{len(plan.warnings)} thing(s) to look at:")
        for w in plan.warnings:
            print(f"  - {w}")
    else:
        print("No problems found.")


def cmd_check(args):
    plan = _plan(args)
    sc = plan.scene
    found = sum(1 for p in plan.props if p.asset is not None)
    print(f"{sc.name}: {sc.width} x {sc.height} squares, {len(sc.rooms)} rooms, {len(plan.openings)} openings, "
          f"{len(plan.props)} props ({found} with art), {len(plan.lights)} lights")
    if args.verbose:
        for p in plan.props:
            print(f"  {p.want:24} {str(p.box):28} {p.asset.id if p.asset else '(no art)'}")
    _report(plan)


def cmd_sketch(args):
    from .build import write_sketch
    plan = _plan(args)
    p = write_sketch(plan, args.out, args.px, rings=not args.no_light_rings)
    print(f"Sketch: {p}")
    _report(plan)


def cmd_render(args):
    from .build import render_all, write_sketch
    plan = _plan(args)
    out = render_all(plan, args.out, args.format, args.quality, not args.no_foundry)
    write_sketch(plan, args.out)
    for k, v in out.items():
        if k != "counts":
            print(f"{k:16} {v}")
    if "counts" in out:
        c = out["counts"]
        print(f"Foundry export: {c['walls']} walls, {c['portals']} doors/windows, {c['lights']} lights")
    _report(plan)


def _maybe_index(args):
    paths = args.index or [DEFAULT_INDEX]
    if all(os.path.exists(p) for p in paths):
        return _load(args)
    print(f"(No asset index at {paths[0]}: carrying on without one. Make one with: mapwriter index <asset folder>)", file=sys.stderr)
    return None


def _say_problems(problems: dict):
    for f, ps in problems.items():
        print(f"{f}: {'no problems' if not ps else f'{len(ps)} thing(s) to look at'}")
        for w in ps:
            print(f"  - {w}")


def cmd_new(args):
    from . import templates
    from .build import slug
    from .talk import write_options
    w = h = None
    if args.size:
        try:
            w, h = (int(v) for v in args.size.lower().split("x"))
        except ValueError:
            sys.exit("--size should look like 24x18")
    try:
        datas = [templates.make(args.template, i, args.seed, w, h, args.name) for i in range(args.options)]
    except ValueError as e:
        sys.exit(str(e))
    stem = args.stem or slug(args.template)
    header = (f"Made by: mapwriter new {args.template} (layout {{}} of {args.options}, seed {args.seed}).\n"
              "Edit freely: change sizes, move props, add notes. Check with: mapwriter check <this file>")
    scenes = [("", d) for d in datas]
    idx = _maybe_index(args)
    res = write_options(scenes, idx, args.out, stem, None)
    for i, (p, d) in enumerate(zip(res["files"], datas)):
        from .yamlout import dump
        p.write_text(dump(d, header.replace("{}", "ABCDEFGH"[i] if args.options > 1 else "1")), encoding="utf-8")
        print(f"Layout {'ABCDEFGH'[i]}: {p}")
    if res["sheet"]:
        print(f"Side by side: {res['sheet']}")
    _say_problems(res["problems"])


def _write_brief(text, args, default_name):
    if args.print:
        print(text)
        return
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    p = out / default_name
    p.write_text(text, encoding="utf-8")
    print(f"Brief: {p}")
    print("Give it to your AI assistant (paste it into a chat, or attach the file).")
    print(f"Save its whole reply as a text file, then run: mapwriter apply <reply file> -o {args.out}"
          + (f" --edit {args.scene}" if getattr(args, "scene", None) else ""))


def cmd_describe(args):
    from .talk import describe_brief
    text = describe_brief(args.request, _maybe_index(args), args.options, args.template)
    _write_brief(text, args, "brief.md")


def cmd_edit(args):
    from .talk import edit_brief
    if not os.path.exists(args.scene):
        sys.exit(f"No scene file at {args.scene}")
    text = edit_brief(args.scene, args.request, _maybe_index(args))
    _write_brief(text, args, "edit-brief.md")


def cmd_apply(args):
    from .build import slug
    from .scene import SceneError
    from .talk import scenes_in_reply, write_options, fix_brief, apply_edit
    reply = Path(args.reply).read_text(encoding="utf-8")
    idx = _load(args)
    if args.edit:
        try:
            r = apply_edit(reply, args.edit, idx, args.out)
        except SceneError as e:
            sys.exit(str(e))
        print(f"Saved the new version to {r['scene']} (the old one is {r['previous']}).")
        print(f"{len(r['changed_lines'])} line(s) changed.")
        if r["sheet"]:
            print(f"Before and after: {r['sheet']}")
        _say_problems({str(r["scene"]): r["problems"]})
        return
    found = scenes_in_reply(reply)
    for text, data, err in found:
        if err:
            print(f"Skipped a block that is {err}")
    scenes = [(t, d) for t, d, e in found if d is not None]
    if not scenes:
        sys.exit("No scene files found in the reply. They should be in ```yaml blocks.")
    stem = args.stem or slug(str(scenes[0][1].get("name", "map")))
    res = write_options(scenes, idx, args.out, stem, keep_text=True)
    for p in res["files"]:
        print(f"Scene: {p}")
    if res["sheet"]:
        print(f"Side by side: {res['sheet']}")
    _say_problems(res["problems"])
    fb = fix_brief(res["problems"])
    if fb:
        q = Path(args.out) / "fix-brief.md"
        q.write_text(fb, encoding="utf-8")
        print(f"To have the assistant fix them, give it {q}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mapwriter", description="Battlemaps from your own asset packs and a plain scene file.")
    ap.add_argument("--version", action="version", version=f"mapwriter {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("starter-pack", help="draw the free starter asset pack"); p.add_argument("out"); p.set_defaults(fn=cmd_starter)

    p = sub.add_parser("index", help="scan asset folders into an index file")
    p.add_argument("folders", nargs="+"); p.add_argument("-o", "--output", default=DEFAULT_INDEX)
    p.add_argument("--fast", action="store_true", help="skip reading image sizes")
    p.set_defaults(fn=cmd_index)

    p = sub.add_parser("pack-check", help="look over a new asset pack and guess its settings")
    p.add_argument("folder"); p.add_argument("-w", "--write", action="store_true", help="write a starter mapwriter-pack.yaml")
    p.add_argument("--credit", help="credit line to put in the pack's yaml, e.g. \"2-Minute Tabletop, CC BY-NC 4.0\"")
    p.set_defaults(fn=cmd_pack_check)

    p = sub.add_parser("search", help="find assets by words"); p.add_argument("words")
    p.add_argument("-k", "--kind", default="prop", choices=["prop", "floor", "wall", "door", "window", "overlay", "roof", "effect", "any"])
    p.add_argument("-s", "--size", help="wanted footprint, e.g. 2x1"); p.add_argument("-n", "--limit", type=int, default=12)
    _index_args(p); p.set_defaults(fn=cmd_search)

    p = sub.add_parser("check", help="check a scene file for problems"); p.add_argument("scene")
    p.add_argument("-v", "--verbose", action="store_true"); _index_args(p); p.set_defaults(fn=cmd_check)

    p = sub.add_parser("sketch", help="draw a quick block plan"); p.add_argument("scene")
    p.add_argument("-o", "--out", default="out"); p.add_argument("--px", type=int, default=48)
    p.add_argument("--no-light-rings", action="store_true", help="leave out the circles showing how far lights reach")
    _index_args(p); p.set_defaults(fn=cmd_sketch)

    p = sub.add_parser("render", help="paint the map and write all exports"); p.add_argument("scene")
    p.add_argument("-o", "--out", default="out"); p.add_argument("-f", "--format", default="webp", choices=["webp", "png", "jpg"])
    p.add_argument("-q", "--quality", type=int, default=88); p.add_argument("--no-foundry", action="store_true")
    _index_args(p); p.set_defaults(fn=cmd_render)

    p = sub.add_parser("new", help="make layouts from a template (tavern, shop, house, market, clearing)")
    p.add_argument("template"); p.add_argument("-o", "--out", default="scenes")
    p.add_argument("-n", "--options", type=int, default=3, choices=range(1, 9), metavar="N", help="how many layouts (default 3)")
    p.add_argument("--seed", type=int, default=1, help="change for different details")
    p.add_argument("--size", help="map size in squares, e.g. 24x18"); p.add_argument("--name", help="map name")
    p.add_argument("--stem", help="file name start (default: the template name)")
    _index_args(p); p.set_defaults(fn=cmd_new)

    p = sub.add_parser("describe", help="write a brief for your AI assistant to turn a description into scene files")
    p.add_argument("request", help="the map in your own words")
    p.add_argument("-o", "--out", default="scenes"); p.add_argument("-n", "--options", type=int, default=3)
    p.add_argument("--template", help="start from this template (default: guessed from the words)")
    p.add_argument("--print", action="store_true", help="print the brief instead of writing brief.md")
    _index_args(p); p.set_defaults(fn=cmd_describe)

    p = sub.add_parser("edit", help="write a brief for your AI assistant to change a scene file")
    p.add_argument("scene"); p.add_argument("request", help="the change in your own words")
    p.add_argument("-o", "--out", default="scenes"); p.add_argument("--print", action="store_true")
    _index_args(p); p.set_defaults(fn=cmd_edit)

    p = sub.add_parser("apply", help="read an assistant's reply: save, check and sketch the scenes in it")
    p.add_argument("reply"); p.add_argument("-o", "--out", default="scenes")
    p.add_argument("--edit", metavar="SCENE", help="the reply is a change to this scene file: save it as the new version")
    p.add_argument("--stem", help="file name start (default: from the map name)")
    _index_args(p); p.set_defaults(fn=cmd_apply)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
