"""The asset index: a JSON list of every usable image in the user's own folders.

The index stores paths, words and sizes only. It never copies or changes art.
"""
from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

import yaml

from . import naming
from .vocab import expand, LIGHT_WORDS, RUG_WORDS

PACK_MANIFEST = "mapwriter-pack.yaml"
DEFAULT_PPSQ = 200
SIZE_WORDS = {"big": 1, "large": 1, "long": 1, "huge": 1, "great": 1, "small": -1, "little": -1, "tiny": -1}
PART_WORDS = {"adornment", "part", "broken", "piece", "overlay", "top", "base", "covered", "arranged", "arrangement", "misc",
              "connector", "corner", "joint", "ending", "shadow", "lid", "sticker", "spray", "stump",
              "log", "branch", "trunk"}
# Words that put an item in a special setting or season. A plain 'tree' or 'bush' should
# not come back as a Christmas tree or a Feywild bush unless the scene asks for that.
THEME_WORDS = {"christmas", "christma", "holiday", "halloween", "feywild", "multicolor", "volcanic", "underdark", "astral",
               "horror", "ceremorph", "drow", "industrial", "fallen", "bare", "dead", "burnt", "ruined", "snow",
               "snowy", "frozen", "icy", "winter", "autumn", "grave", "burial", "ore", "pumpkin"}
COLOUR_WORDS = {"red", "blue", "green", "yellow", "orange", "purple", "pink", "white", "black", "grey", "gray",
                "brown", "gold", "silver", "violet", "teal", "cyan", "magenta", "multicolor"}
MIXED_COLOUR_HEADS = {"flower"}        # a flower bed may mix colours; trees and bushes keep one
# Plants come green unless the scene names a colour: red and orange trees are autumn ones.
FLORA_HEADS = {"tree", "bush", "plant", "shrub", "hedge", "fern", "grass", "leaf", "vine", "ivy"}
# Words a scene uses for a strip of ground. 'dirt path' wants dirt, not a file named *_Path.
ROUTE_WORDS = {"path", "road", "track", "trail", "lane", "footpath", "way"}          # Forgotten Adventures, 2-Minute Tabletop and most packs paint 200 px per 5 ft square


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
    look: dict | None = None      # what the picture looks like (assets/look.py), if measured
    guessed: list[str] = field(default_factory=list)   # words guessed from the picture, for vague names

    @property
    def seen_colours(self) -> set[str]:
        return set(self.look.get("colours", ())) if self.look else set()

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
    found = _best_resolution(found)
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


DPI_RE = re.compile(r"(\d{2,3})\s*dpi", re.I)


def folder_ppsq(rel: str) -> int | None:
    """Pixels per square from a folder such as 'Assets - 300 DPI' (2-Minute Tabletop and
    other packs that ship print and VTT copies: one inch, 300 px, is one square)."""
    m = DPI_RE.search(os.path.dirname(rel))
    return int(m.group(1)) if m else None


def _best_resolution(found: list[tuple[str, Path]]) -> list[tuple[str, Path]]:
    """Where a pack has the same picture in several DPI folders, keep the sharpest copy."""
    best: dict[tuple[str, str], tuple[int, str, Path]] = {}
    out = []
    for rel, full in found:
        dpi = folder_ppsq(rel)
        if dpi is None:
            out.append((rel, full))
            continue
        folder = re.sub(r"\([^)]*\)", "", DPI_RE.sub("", os.path.dirname(rel))).lower()
        key = (re.sub(r"[^a-z/]+", "", folder), os.path.basename(rel).lower())
        if key not in best or dpi > best[key][0]:
            best[key] = (dpi, rel, full)
    return out + [(rel, full) for _dpi, rel, full in best.values()]


def describe(rel: str, pack: str, root: str, ppsq: int = DEFAULT_PPSQ, overrides=None, kinds=None, full=None,
             px: list[int] | None = None) -> Asset:
    fp = naming.footprint(os.path.basename(rel))
    kind = naming.kind_for(rel)
    ppsq = folder_ppsq(rel) or ppsq
    if px is None and full is not None:
        px = _image_size(full)
    if fp is not None and set(naming.words(os.path.basename(rel))) & {"texture", "tile"}:
        # A texture that names its size, such as '8x8 dirt texture.jpg' or 'Water Tile 1 (8x8).jpg'
        kind = "floor"
        if px:
            ppsq = max(1, round(px[0] / fp[0]))
        fp = None
    elif kind == "floor" and fp is not None:
        kind = "prop"
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


# Words in file names that say nothing about what the picture shows.
GENERIC_WORDS = {"img", "image", "asset", "object", "item", "prop", "untitled", "sprite", "dsc", "final", "new",
                 "copy", "token", "file", "pic", "picture", "export", "layer", "render", "sheet", "scan", "photo"}
GUESS_MAX = 10.0         # likeness() distance within which a vague file takes a group's word
GUESS_MARGIN = 2.0       # ...and the next nearest group must be this much further off


def is_vague(a: Asset) -> bool:
    """True when the file name gives a search nothing to go on (IMG_0042.png, 17.webp) and
    no tags.yaml or pack manifest words were added."""
    return not a.extra_tags and not (set(naming.words(os.path.basename(a.rel))) - GENERIC_WORDS)


def _named_for(filename: str, name_list: list[str]) -> set[str]:
    """The words a file is named for: its first word, and with 2-Minute Tabletop style
    'Storage - Crate 1 - Dark.png' names also the first word after the category."""
    out = set(name_list[:1])
    parts = filename.split(" - ")
    if len(parts) > 1:
        out |= set(naming.words(parts[1])[:1])
    return out


def _drop_route_word(ws: list[str], kind: str | None) -> list[str]:
    if kind == "floor" and len(ws) > 1 and ws[-1] in ROUTE_WORDS:
        return ws[:-1]
    return ws


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
            name_list = naming.words(os.path.basename(a.rel))
            nw = set(name_list) | set(a.extra_tags)
            themes = {w.rstrip("0123456789") for w in aw} & THEME_WORDS
            if "arranged" in a.rel.lower():          # indexes made before 0.2 dropped the word
                aw = aw | {"arranged"}
            self._words[id(a)] = (aw, nw, _named_for(a.name, name_list), themes)
            by_kind = self._postings.setdefault(a.kind, {})
            for w in aw | set(a.guessed):
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

    # ---------- pictures ----------
    def add_looks(self, workers: int = 8, force: bool = False, progress=None) -> dict:
        """Measure the pictures (see assets/look.py), then use what they show: seamless
        textures filed among props become floors, and files with vague names get a word
        guessed from the named files they look most like."""
        from .look import look_all
        n = look_all(self.assets, workers=workers, force=force, progress=progress)
        floors = self._floors_from_looks()
        guesses = self.guess_words()
        self._reindex()
        return {"measured": n, "looked": sum(1 for a in self.assets if a.look), "floors": floors, "guessed": guesses}

    def _floors_from_looks(self) -> list[Asset]:
        out = []
        for a in self.assets:
            lk = a.look
            if (a.kind == "prop" and lk and lk.get("tile") and lk.get("fill", 0) > 0.99 and a.px
                    and naming.footprint(a.name) is None and min(a.px) >= 2 * a.ppsq):
                a.kind, a.footprint = "floor", None
                out.append(a)
        return out

    def guess_words(self) -> list[tuple[Asset, str, float]]:
        """Give each vague-named file the word of the group of named files it looks most
        like, when one group is clearly nearest. Groups are files of the same kind that
        share a first word (Barrel_*, Crate_*), with at least three measured pictures.
        Guessed words count for less than real ones and the plan says when one was used."""
        from .look import centre, likeness
        groups: dict[tuple[str, str], list[list[int]]] = {}
        vague = []
        for a in self.assets:
            if not a.look or not a.look.get("sig"):
                continue
            if is_vague(a):
                a.guessed = []
                vague.append(a)
                continue
            first = [w for w in naming.words(os.path.basename(a.rel)) if w not in GENERIC_WORDS][:1]
            if first and not (set(a.words) & PART_WORDS):
                groups.setdefault((a.kind, first[0]), []).append(a.look["sig"])
        mids: dict[str, list[tuple[str, list[int]]]] = {}
        for (kind, word), sigs in groups.items():
            if len(sigs) >= 3:
                mids.setdefault(kind, []).append((word, centre(sigs)))
        out = []
        for a in vague:
            near = sorted((likeness(a.look["sig"], mid), word) for word, mid in mids.get(a.kind, ()))
            if not near or near[0][0] > GUESS_MAX:
                continue
            if len(near) > 1 and near[1][0] - near[0][0] < GUESS_MARGIN:
                continue
            a.guessed = [near[0][1]]
            out.append((a, near[0][1], round(near[0][0], 1)))
        return out

    def look_alikes(self, asset: Asset, limit: int = 10, kind: str | None = None) -> list[tuple[float, Asset]]:
        """Assets whose pictures look most like ``asset``'s, nearest first."""
        from .look import likeness
        if not asset.look or not asset.look.get("sig"):
            return []
        sig = asset.look["sig"]
        kind = kind or asset.kind
        res = [(likeness(sig, a.look["sig"]), a) for a in self._by_kind.get(kind, ())
               if a is not asset and a.look and a.look.get("sig")]
        res.sort(key=lambda t: (t[0], t[1].id))
        return res[:limit]

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
        Other words add points. A footprint close to ``size`` adds points. Where pictures
        have been measured (``mapwriter look``), colours seen in the picture count too, and
        art that looks unlike the files named for the thing loses points.
        """
        return [(s, a) for s, a, _u in self._search(want, kind, size, limit)]

    def _search(self, want, kind, size, limit):
        """As search(), with a third value per result: True when the picture looks unlike
        the files named for the thing (a handcart that has 'apple' in its name)."""
        ws = [w for w in naming.words(want) if w not in SIZE_WORDS]
        size_word = next((SIZE_WORDS[w] for w in naming.words(want) if w in SIZE_WORDS), 0)
        ws = _drop_route_word(ws, kind)
        if not ws:
            return []
        head = ws[-1]
        head_opts = expand(head)
        mods = [(w, expand(w)) for w in ws[:-1]]
        asked = set(ws)
        scored = []
        asked_colours = {("grey" if w == "gray" else w) for w in asked} & COLOUR_WORDS
        for a in self._candidates(kind, head_opts):
            aw, name_words, first, themes = self._words[id(a)]
            seen = a.seen_colours
            if head in aw:
                s = 10.0
            elif head_opts & aw:
                s = 7.0
            else:
                s = 5.0                     # only a word guessed from the picture
            if head_opts & name_words:
                s += 3
            if head in first:               # named for the thing itself: Dirt_A_01, not Stone_Floor_Dirt
                s += 3
            elif first & head_opts:         # ...or for a near word: Box_* when asked for a crate
                s += 1
            if head in name_words and (name_words & head_opts) - {head} - asked:
                s -= 1.5                    # 'Chair - Armchair' is a kind of chair, not a plain one
            if themes and not themes & asked:     # a Christmas tree sits in Holidays: asking for one is enough
                s -= 3
            if head in FLORA_HEADS and ((name_words & COLOUR_WORDS) - {"green"} - asked):
                s -= 2
            if (head in FLORA_HEADS and not asked_colours and "green" not in seen
                    and seen & {"red", "orange", "yellow", "pink", "purple", "white"}):
                s -= 1.5                    # looks autumnal or in flower though the name is plain
            for w, opts in mods:
                cw = "grey" if w == "gray" else w
                if cw in COLOUR_WORDS and seen and cw not in aw:
                    s += 1.5 if cw in seen else -1.0       # 'red apple': the picture is red, or not
                    continue
                if w in aw:
                    s += 2.5 if w in name_words else 1.5
                    if w in name_words and w in THEME_WORDS | COLOUR_WORDS:
                        s += 1.5        # asked for 'christmas tree' or 'red tree': that beats a plain one
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
            scored.append([s, a, False, head in first and not junk])
        self._judge_looks(scored)
        scored.sort(key=lambda t: (-t[0], t[1].id))
        return [(s, a, u) for s, a, u, _e in scored[:limit]]

    LOOK_FAR = 24.0      # likeness() distance beyond which art looks unlike the named files
    LOOK_NEAR = 9.0

    def _judge_looks(self, scored):
        """Compare each candidate's picture with the middle look of the files named for the
        thing itself (Apple_Red_1x1, Apple_Green_1x1...). A file that only has the word
        somewhere else in its name and looks nothing like them is probably something else."""
        from .look import centre, likeness
        exemplars = [t for t in scored if t[3] and t[1].look and t[1].look.get("sig")]
        if not exemplars:
            return
        mid = centre([t[1].look["sig"] for t in exemplars])
        sure = len(exemplars) >= 2
        for t in scored:
            lk = t[1].look
            if not lk or not lk.get("sig"):
                continue
            d = likeness(lk["sig"], mid)
            if t[3]:
                if len(exemplars) >= 3 and d > self.LOOK_FAR:
                    t[0] -= 1.0             # an odd one out among the named files
            elif d > self.LOOK_FAR:
                t[0] -= 2.5 if sure else 1.5
                t[2] = True
            elif d < self.LOOK_NEAR and sure:
                t[0] += 0.5

    def loose(self, want: str, asset: "Asset", kind: str | None = "prop") -> bool:
        """True when ``asset`` matched ``want`` only through a synonym of its main noun,
        so the scene may get something rather different from what it asked for."""
        ws = _drop_route_word([w for w in naming.words(want) if w not in SIZE_WORDS], kind)
        if not ws:
            return False
        # Also loose: only a part of the thing, such as a tree stump for 'tree'.
        return ws[-1] not in asset.all_words or bool((asset.all_words & PART_WORDS) - set(ws))

    def by_look(self, want: str, asset: "Asset", kind: str | None = "prop") -> bool:
        """True when ``asset`` matched ``want`` only through a word guessed from its picture."""
        ws = _drop_route_word([w for w in naming.words(want) if w not in SIZE_WORDS], kind)
        return bool(ws) and not (expand(ws[-1]) & asset.all_words) and bool(expand(ws[-1]) & set(asset.guessed))

    # Packs such as Forgotten Adventures split some pieces into a base and a top
    # (Display_Case_Base_* and Display_Case_Top_*): the top is drawn above tokens.
    LAYER_PAIRS = (("Base", "Top"), ("Bottom", "Top"), ("Lower", "Upper"))

    def top_piece(self, asset: Asset, seed: int = 0) -> Asset | None:
        """The matching top piece for a base piece, from the same folder, or None."""
        if asset is None:
            return None
        folder, name = os.path.split(asset.rel)
        stem, ext = os.path.splitext(name)
        toks = stem.split("_")
        for low, high in self.LAYER_PAIRS:
            if low not in toks:
                continue
            i = toks.index(low)
            exact = "_".join(toks[:i] + [high] + toks[i + 1:]) + ext
            rel = f"{folder}/{exact}" if folder else exact
            hit = next((a for a in self.assets if a.pack == asset.pack and a.rel == rel), None)
            if hit is not None:
                return hit
            # Otherwise the best sibling that shares the name before the split and the footprint.
            head = toks[:i]
            best, score = [], -1
            for a in self.assets:
                if a.pack != asset.pack or os.path.dirname(a.rel) != folder or a is asset:
                    continue
                t = os.path.splitext(os.path.basename(a.rel))[0].split("_")
                if high not in t or t[:i] != head or (asset.footprint and a.footprint != asset.footprint):
                    continue
                shared = len(set(t) & set(toks))
                if shared > score:
                    best, score = [a], shared
                elif shared == score:
                    best.append(a)
            if best:
                best.sort(key=lambda a: a.rel)
                return random.Random(f"{seed}:{asset.rel}").choice(best)
        return None

    def pick(self, want: str, kind: str | None = "prop", size=None, seed: int = 0, family_seed: int | None = None,
             small: bool = False):
        """Choose one asset: a seeded pick among the near-best matches.

        With ``family_seed`` (used when each copy gets its own ``seed``), one family of art is
        chosen first, such as all of ``Tree_Green_*``, and the copies vary inside it. Then a
        wood is all green trees rather than a mix of summer and autumn ones. Flowers may mix colours.

        With ``small``, 1x1 art wins when there is any that is not only a loose match: 'apple'
        gets an apple rather than a handcart of apples from another pack.
        """
        found = self._search(want, kind, size, limit=None)
        if not found:
            return None
        unlike = {id(a) for _s, a, u in found if u}
        res = [(s, a) for s, a, _u in found]
        if small:
            ones = [(s, a) for s, a in res if a.footprint and a.footprint[0] * a.footprint[1] <= 1
                    and not self.loose(want, a, kind) and id(a) not in unlike]
            if ones:
                res = ones
        # The first pack listed that has the thing itself (not only something with a similar
        # name) supplies it, so a small fill-in pack listed later never wins on wording alone.
        rank = {p: i for i, p in enumerate(self.pack_order)}
        for pack in sorted({a.pack for _s, a in res}, key=lambda p: rank.get(p, 99)):
            mine = [(s, a) for s, a in res if a.pack == pack]
            if not self.loose(want, mine[0][1], kind) and id(mine[0][1]) not in unlike:
                res = mine
                break
        best = res[0][0]
        top = [a for s, a in res if s >= best - 0.75]      # all near-best, so scatter varies across the whole set
        # When packs tie, the pack listed first wins (the user's main pack goes first).
        first = min(rank.get(a.pack, 99) for a in top)
        top = [a for a in top if rank.get(a.pack, 99) == first]
        if family_seed is not None and len(top) > 1:
            ws = [w for w in naming.words(want) if w not in SIZE_WORDS]
            mixed = bool(ws) and ws[-1] in MIXED_COLOUR_HEADS
            def family(a):
                return (a.pack,) + tuple(w for w in naming.words(os.path.splitext(a.name)[0])
                                         if not (mixed and w.rstrip("0123456789") in COLOUR_WORDS))
            fams = sorted({family(a) for a in top})
            fam = random.Random(f"{family_seed}:{want}:{kind}:{size}:family").choice(fams)
            top = [a for a in top if family(a) == fam]
        rnd = random.Random(f"{seed}:{want}:{kind}:{size}")
        return rnd.choice(top)
