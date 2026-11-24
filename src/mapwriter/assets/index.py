"""The asset index: a JSON list of every usable image in the user's own folders.

The index stores paths, words and sizes only. It never copies or changes art.
"""
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path

import yaml

from . import naming
from .vocab import expand, LIGHT_WORDS, RUG_WORDS

PACK_MANIFEST = "mapwriter-pack.yaml"
DEFAULT_PPSQ = 200
SIZE_WORDS = {"big": 1, "large": 1, "long": 1, "huge": 1, "great": 1, "small": -1, "little": -1, "tiny": -1}
PART_WORDS = {"adornment", "part", "broken", "piece", "overlay", "top", "base", "covered", "arranged", "arrangement", "misc",
              "connector", "corner", "joint", "ending", "shadow"}          # Forgotten Adventures, 2-Minute Tabletop and most packs paint 200 px per 5 ft square


@dataclass
class Asset:
    id: str                       # pack/relative/path
    pack: str
    root: str                     # absolute folder of the pack
    rel: str                      # path inside the pack
    kind: str                     # floor, wall, door, window, prop, overlay, roof, effect
    words: list[str]
    footprint: list[int] | None   # squares [w, h], if known
    px: list[int] | None = None   # image size in pixels
    ppsq: int = DEFAULT_PPSQ
    extra_tags: list[str] = field(default_factory=list)
    credit: str | None = None     # the pack's credit line, from mapwriter-pack.yaml

    @property
    def path(self) -> str:
        return os.path.join(self.root, self.rel)

    @property
    def all_words(self) -> set[str]:
        return set(self.words) | set(self.extra_tags)

    @property
    def name(self) -> str:
        return os.path.basename(self.rel)

    @property
    def emits_light(self) -> bool:
        return bool(self.all_words & LIGHT_WORDS)

    @property
    def is_rug(self) -> bool:
        return bool(self.all_words & RUG_WORDS)


def _read_manifest(root: Path) -> dict:
    p = root / PACK_MANIFEST
    if p.exists():
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {}


def _image_size(full) -> list[int] | None:
    try:
        from PIL import Image
        with Image.open(full) as im:
            return [im.width, im.height]
    except Exception:
        return None


def scan(root: str | os.PathLike, pack: str | None = None, read_sizes: bool = True,
         workers: int = 16) -> list[Asset]:
    """Walk one pack folder and describe every image in it.

    Reading each image's size means opening its header, which is slow on a cold
    disk (about 10 ms a file). Big packs have well over 100,000 images, so the
    headers are read on a pool of threads.
    """
    root = Path(root).resolve()
    man = _read_manifest(root)
    pack = pack or man.get("name") or root.name
    ppsq = int(man.get("px_per_square", DEFAULT_PPSQ))
    overrides = man.get("tags", {}) or {}
    kinds = man.get("kinds", {}) or {}
    found: list[tuple[str, Path]] = []
    for dirpath, _dirs, files in os.walk(root):
        for fn in sorted(files):
            ext = os.path.splitext(fn)[1].lower()
            if ext not in naming.IMAGE_EXTS:
                continue
            full = Path(dirpath) / fn
            found.append((full.relative_to(root).as_posix(), full))
    sizes: list[list[int] | None] = [None] * len(found)
    if read_sizes and found:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max(1, workers)) as ex:
            sizes = list(ex.map(_image_size, (full for _rel, full in found), chunksize=64))
    credit = man.get("credit")
    out = [describe(rel, pack, str(root), ppsq, overrides, kinds, px=px) for (rel, _full), px in zip(found, sizes)]
    for a in out:
        a.credit = credit
    return out


def describe(rel: str, pack: str, root: str, ppsq: int = DEFAULT_PPSQ, overrides=None, kinds=None, full=None,
             px: list[int] | None = None) -> Asset:
    fp = naming.footprint(os.path.basename(rel))
    kind = naming.kind_for(rel)
    if kind == "floor" and fp is not None:
        kind = "prop"
    if px is None and full is not None:
        px = _image_size(full)
    if fp is None and px and kind in ("prop", "door", "window"):
        fp = [max(1, round(px[0] / ppsq)), max(1, round(px[1] / ppsq))]
    extra = []
    for pattern, tags in (overrides or {}).items():
        if pattern.lower() in rel.lower():
            extra += [t.lower() for t in (tags if isinstance(tags, list) else [tags])]
    for pattern, k in (kinds or {}).items():
        if pattern.lower() in rel.lower():
            kind = k
    return Asset(id=f"{pack}/{rel}", pack=pack, root=root, rel=rel, kind=kind,
                 words=list(dict.fromkeys(naming.words(rel))), footprint=list(fp) if fp else None, px=px,
                 ppsq=ppsq, extra_tags=extra)


class Index:
    def __init__(self, assets: list[Asset] | None = None):
        self.assets = assets or []
        self.pack_order = list(dict.fromkeys(a.pack for a in self.assets))
        self._by_kind: dict[str, list[Asset]] = {}
        self._reindex()

    def _reindex(self):
        """Group assets by kind and build word lookups, so a search only scores assets
        that share its main noun (big packs have well over 100,000 images)."""
        self._by_kind = {}
        self._words: dict[int, tuple[set[str], set[str]]] = {}
        self._postings: dict[str | None, dict[str, list[Asset]]] = {None: {}}
        for a in self.assets:
            self._by_kind.setdefault(a.kind, []).append(a)
            aw = a.all_words
            nw = set(naming.words(os.path.basename(a.rel))) | set(a.extra_tags)
            self._words[id(a)] = (aw, nw)
            by_kind = self._postings.setdefault(a.kind, {})
            for w in aw:
                by_kind.setdefault(w, []).append(a)
                self._postings[None].setdefault(w, []).append(a)

    def _candidates(self, kind: str | None, head_opts: set[str]) -> list[Asset]:
        postings = self._postings.get(kind, {})
        seen: dict[int, Asset] = {}
        for w in head_opts:
            for a in postings.get(w, ()):
                seen[id(a)] = a
        return list(seen.values())

    # ---------- files ----------
    @classmethod
    def build(cls, folders: list[str], read_sizes: bool = True) -> "Index":
        assets = []
        for f in folders:
            assets += scan(f, read_sizes=read_sizes)
        return cls(assets)

    def save(self, path: str | os.PathLike):
        data = {"version": 1, "assets": [asdict(a) for a in self.assets]}
        Path(path).write_text(json.dumps(data, indent=0), encoding="utf-8")

    @classmethod
    def load(cls, *paths: str | os.PathLike) -> "Index":
        assets = []
        for p in paths:
            data = json.loads(Path(p).read_text(encoding="utf-8"))
            for d in data["assets"]:
                assets.append(Asset(**d))
        return cls(assets)

    def apply_tags(self, tags_file: str | os.PathLike):
        """Apply a user's tags.yaml: {pattern: [tags]} and optional kinds: {pattern: kind}."""
        data = yaml.safe_load(Path(tags_file).read_text(encoding="utf-8")) or {}
        kinds = data.pop("kinds", {}) or {}
        for a in self.assets:
            for pattern, tags in data.items():
                if pattern.lower() in a.rel.lower():
                    a.extra_tags += [t.lower() for t in (tags if isinstance(tags, list) else [tags])]
            for pattern, k in kinds.items():
                if pattern.lower() in a.rel.lower():
                    a.kind = k
        self._reindex()

    # ---------- search ----------
    def kinds(self) -> dict[str, int]:
        return {k: len(v) for k, v in sorted(self._by_kind.items())}

    def get(self, ident: str) -> Asset | None:
        for a in self.assets:
            if a.id == ident or a.rel == ident or a.name == ident or os.path.splitext(a.name)[0] == ident:
                return a
        return None

    def search(self, want: str, kind: str | None = "prop", size=None, limit: int = 10):
        """Rank assets for a plain description such as 'small round table' or 'warm wood planks'.

        The last word is the main noun and must match (directly or by synonym).
        Other words add points. A footprint close to ``size`` adds points.
        """
        ws = [w for w in naming.words(want) if w not in SIZE_WORDS]
        size_word = next((SIZE_WORDS[w] for w in naming.words(want) if w in SIZE_WORDS), 0)
        if not ws:
            return []
        head = ws[-1]
        head_opts = expand(head)
        mods = [(w, expand(w)) for w in ws[:-1]]
        asked = set(ws)
        scored = []
        for a in self._candidates(kind, head_opts):
            aw, name_words = self._words[id(a)]
            s = 10.0 if head in aw else 7.0
            if head_opts & name_words:
                s += 3
            for w, opts in mods:
                if w in aw:
                    s += 2.5 if w in name_words else 1.5
                elif opts & aw:
                    s += 1.0
            if size and a.footprint:
                w, h = size
                fw, fh = a.footprint
                if (fw, fh) == (w, h) or (fh, fw) == (w, h):
                    s += 3
                else:
                    ratio_a = max(fw, fh) / min(fw, fh)
                    ratio_t = max(w, h) / min(w, h)
                    s += max(0.0, 2 - abs(ratio_a - ratio_t))
                    s -= 0.15 * abs(fw * fh - w * h)
            elif size_word and a.footprint:
                area = a.footprint[0] * a.footprint[1]
                s += min(3.0, 0.5 * area) if size_word > 0 else (2.0 if area == 1 else -0.5 * area)
            # Whole, single items beat parts, covered furniture and pre-arranged sets.
            junk = (aw & PART_WORDS) - asked
            if junk:
                s -= 3
            if kind == "wall":
                if "path" in aw:
                    s += 6
                if aw & {"corner", "connector", "joint", "ending", "diag", "broken"}:
                    s -= 6
            if kind == "floor" and aw & {"floor", "flooring"}:
                s += 2
            s -= 0.01 * len(aw)
            scored.append((s, a))
        scored.sort(key=lambda t: (-t[0], t[1].id))
        return scored[:limit]

    def pick(self, want: str, kind: str | None = "prop", size=None, seed: int = 0):
        """Choose one asset: a seeded pick among the near-best matches."""
        res = self.search(want, kind, size, limit=12)
        if not res:
            return None
        best = res[0][0]
        top = [a for s, a in res if s >= best - 0.75]
        # When packs tie, the pack listed first wins (the user's main pack goes first).
        rank = {p: i for i, p in enumerate(self.pack_order)}
        first = min(rank.get(a.pack, 99) for a in top)
        top = [a for a in top if rank.get(a.pack, 99) == first]
        rnd = random.Random(f"{seed}:{want}:{kind}:{size}")
        return rnd.choice(top)
