"""Turn asset file paths into words, kinds and footprints.

Most battlemap packs name files in a readable way, for example
``Furniture/Tables/Table_Wood_Walnut_A1_2x3.webp``. We split the path into
lower-case words, drop variant codes (``A1``, ``03``) and read a ``WxH``
footprint when one is present.
"""
from __future__ import annotations

import re

FOOTPRINT_RE = re.compile(r"(?:^|[_\-\s])(\d{1,2})x(\d{1,2})(?=$|[_\-\s.])", re.I)
VARIANT_RE = re.compile(r"^(?:[a-z]{1,2}\d{0,2}|\d{1,3}|v\d+(?:\.\d+)*)$", re.I)
CAMEL_RE = re.compile(r"(?<=[a-z])(?=[A-Z])")
SPLIT_RE = re.compile(r"[\\/_\-\s.()\[\]!,]+")

IMAGE_EXTS = {".png", ".webp", ".jpg", ".jpeg"}

# Words that are noise in folder names.
STOP = {"assets", "asset", "webp", "png", "jpg", "pack", "core", "fa", "the", "and", "of",
        "misc", "arranged", "base", "settlements", "settlement", "mapmaking", "v1", "free"}

# Kind rules: first match wins. Each rule is (kind, words that must appear).
KIND_RULES = [
    ("overlay", {"overlay"}),
    ("overlay", {"shadow", "path"}),
    ("roof", {"roof"}),
    ("wall", {"wall", "path"}),
    ("wall", {"walls"}),
    ("door", {"door"}),
    ("door", {"doors"}),
    ("window", {"window"}),
    ("window", {"windows"}),
    ("floor", {"textures"}),
    ("floor", {"texture"}),
    ("floor", {"flooring"}),
    ("floor", {"floors"}),
    ("floor", {"tiles"}),
    ("effect", {"effects"}),
]

# Simple plural folding so "chairs" finds "chair".
IRREGULAR = {"shelves": "shelf", "benches": "bench", "boxes": "box", "glasses": "glass",
             "torches": "torch", "brushes": "brush", "dishes": "dish", "cases": "case",
             "leaves": "leaf", "knives": "knife", "wolves": "wolf", "mice": "mouse",
             "geese": "goose", "cacti": "cactus", "fungi": "fungus", "stairs": "stairs",
             "glass": "glass", "moss": "moss", "grass": "grass", "dress": "dress"}


def singular(w: str) -> str:
    if w in IRREGULAR:
        return IRREGULAR[w]
    if len(w) > 5 and w.endswith(("ches", "shes", "xes")):
        return w[:-2]                       # bushes, benches, boxes
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
        return w[:-1]
    return w


def words(text: str) -> list[str]:
    """Lower-case content words, variant codes removed, plurals folded."""
    text = CAMEL_RE.sub(" ", text)
    out = []
    for raw in SPLIT_RE.split(text):
        if not raw:
            continue
        w = raw.lower()
        if FOOTPRINT_RE.fullmatch("_" + w):
            continue
        if VARIANT_RE.match(w) and not w.isalpha() or (len(w) <= 1):
            continue
        if re.fullmatch(r"[a-z]\d+|\d+[a-z]?", w):
            continue
        w = singular(w)
        if w in STOP:
            continue
        out.append(w)
    return out


def footprint(name: str):
    """Return (w, h) in squares from a ``_WxH`` token, or None."""
    stem = name.rsplit(".", 1)[0]
    m = None
    for m in FOOTPRINT_RE.finditer(stem):
        pass
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def kind_for(rel_path: str) -> str:
    toks = set(words(rel_path))
    raw = set(re.split(r"[\\/_\-\s.]+", rel_path.lower()))
    toks |= raw
    for kind, need in KIND_RULES:
        if need <= toks:
            return kind
    return "prop"
