"""mapwriter command line.

    mapwriter starter-pack OUT_DIR          draw the free starter pack
    mapwriter index FOLDER... -o index.json scan asset folders
    mapwriter search "round table"          find assets by words
    mapwriter check scene.yaml              list problems with a scene
    mapwriter sketch scene.yaml             quick block plan (PNG)
    mapwriter render scene.yaml             painted maps, key, check, .dd2vtt
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
    p = write_sketch(plan, args.out, args.px)
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


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mapwriter", description="Battlemaps from your own asset packs and a plain scene file.")
    ap.add_argument("--version", action="version", version=f"mapwriter {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("starter-pack", help="draw the free starter asset pack"); p.add_argument("out"); p.set_defaults(fn=cmd_starter)

    p = sub.add_parser("index", help="scan asset folders into an index file")
    p.add_argument("folders", nargs="+"); p.add_argument("-o", "--output", default=DEFAULT_INDEX)
    p.add_argument("--fast", action="store_true", help="skip reading image sizes")
    p.set_defaults(fn=cmd_index)

    p = sub.add_parser("search", help="find assets by words"); p.add_argument("words")
    p.add_argument("-k", "--kind", default="prop", choices=["prop", "floor", "wall", "door", "window", "overlay", "roof", "effect", "any"])
    p.add_argument("-s", "--size", help="wanted footprint, e.g. 2x1"); p.add_argument("-n", "--limit", type=int, default=12)
    _index_args(p); p.set_defaults(fn=cmd_search)

    p = sub.add_parser("check", help="check a scene file for problems"); p.add_argument("scene")
    p.add_argument("-v", "--verbose", action="store_true"); _index_args(p); p.set_defaults(fn=cmd_check)

    p = sub.add_parser("sketch", help="draw a quick block plan"); p.add_argument("scene")
    p.add_argument("-o", "--out", default="out"); p.add_argument("--px", type=int, default=48)
    _index_args(p); p.set_defaults(fn=cmd_sketch)

    p = sub.add_parser("render", help="paint the map and write all exports"); p.add_argument("scene")
    p.add_argument("-o", "--out", default="out"); p.add_argument("-f", "--format", default="webp", choices=["webp", "png", "jpg"])
    p.add_argument("-q", "--quality", type=int, default=88); p.add_argument("--no-foundry", action="store_true")
    _index_args(p); p.set_defaults(fn=cmd_render)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
