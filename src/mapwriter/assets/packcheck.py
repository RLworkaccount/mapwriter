"""Look over a new asset pack before indexing it: guess its pixels per square,
find files whose names say too little, and write a starter mapwriter-pack.yaml.

Works for any pack. It is how MapWriter takes on packs such as 2-Minute Tabletop,
whose names and sizes differ from Forgotten Adventures: check the pack, look at
the guesses, then fix the few things it flags in the pack's yaml or a tags.yaml.
"""
from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

from . import naming
from . import index
from .index import PACK_MANIFEST, scan

COMMON_PPSQ = (70, 100, 128, 140, 150, 200, 256, 280, 300, 400)


def guess_ppsq(assets) -> tuple[int | None, str]:
    """Pixels per square, from files that name their size (Barrel_1x1.png at 200 x 200
    px means 200) or, failing that, from the commonest small prop size."""
    by_folder = Counter(a.ppsq for a in assets if index.folder_ppsq(a.rel))
    if by_folder and sum(by_folder.values()) * 2 > len(assets):
        v, n = by_folder.most_common(1)[0]
        return v, f"{n} files sit in folders named for {v} DPI (one inch, {v} px, per square)"
    named = Counter()
    for a in assets:
        if a.px and a.kind in ("prop", "door", "window"):
            fp = naming.footprint(os.path.basename(a.rel))
            if fp:
                named[round(max(a.px[0] / fp[0], a.px[1] / fp[1]))] += 1
    if named:
        v, n = named.most_common(1)[0]
        return v, f"{n} files with a size in their name agree on {v} px per square"
    sides = Counter()
    for a in assets:
        if a.px and a.kind == "prop":
            s = max(a.px)
            near = min(COMMON_PPSQ, key=lambda c: abs(c - s))
            if abs(near - s) <= 0.08 * near:
                sides[near] += 1
    if sides:
        v, n = sides.most_common(1)[0]
        return v, f"{n} props are about {v} px across (a guess: check a 1-square item such as a barrel)"
    return None, "no image sizes to go on"


def vague(assets, limit=20) -> list[str]:
    """Files whose words give a search almost nothing to match."""
    return [a.rel for a in assets if a.kind == "prop" and index.is_vague(a)][:limit]


def style(assets) -> dict | None:
    """The pack's look on average: how much black ink, how strongly coloured, how bright,
    how much soft shadow. Packs by different artists differ most in these."""
    looks = [a.look for a in assets if a.look and a.kind == "prop"]
    if not looks:
        return None
    return {k: round(sum(lk[k] for lk in looks) / len(looks), 2) for k in ("ink", "sat", "bright", "soft")}


def check_pack(folder, write=False, credit=None, look=True) -> dict:
    root = Path(folder)
    assets = scan(root, read_sizes=True)
    ppsq, why = guess_ppsq(assets)
    looked = {"floors": [], "guessed": []}
    if look:
        for a in assets:
            a.ppsq = a.ppsq if index.folder_ppsq(a.rel) or not ppsq else ppsq
        looked = index.Index(assets).add_looks()
    kinds = Counter(a.kind for a in assets)
    report = {"pack": root.resolve().name, "files": len(assets), "kinds": dict(kinds), "ppsq": ppsq, "why": ppsq and why or why,
              "vague": vague(assets), "manifest": None, "floors": [a.rel for a in looked["floors"]],
              "guessed": [(a.rel, w) for a, w, _d in looked["guessed"]], "style": style(assets)}
    man = root / PACK_MANIFEST
    if write and not man.exists():
        lines = [f"name: {report['pack']}"]
        if ppsq:
            lines.append(f"px_per_square: {ppsq}        # {why}")
        lines.append(f"credit: {credit!r}" if credit else "# credit: \"Art by ... (licence)\"   # written next to every map that uses this pack")
        lines += ["tags:                    # extra words for files whose path contains the key", "  # Stall_A: [market, stall]"]
        lines += [f"  # {os.path.basename(rel)!r}: [{w}]        # guessed from the picture: check, then remove the #"
                  for rel, w in report["guessed"][:200]]
        lines += ["kinds:                   # force a kind for matching paths", "  # Rug_Square: floor", ""]
        man.write_text("\n".join(lines), encoding="utf-8")
        report["manifest"] = str(man)
    return report
