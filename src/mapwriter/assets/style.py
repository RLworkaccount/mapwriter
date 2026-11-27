"""Pack styles: how one artist's art differs from another's, so a map that mixes packs
can keep to one look.

A style profile is the average look (assets/look.py) of a pack's props: how much
black ink outlines them, how strongly coloured and how bright they are, and how
much soft shadow is baked in. Profiles are worked out from measured pictures only.
"""
from __future__ import annotations

KEYS = ("ink", "sat", "bright", "soft")
WEIGHTS = {"ink": 2.0, "sat": 1.0, "bright": 1.0, "soft": 1.0}
MIN_LOOKS = 3            # a pack needs this many measured props for a profile
CLASH = 18.0             # gap() above this: the styles are clearly different

# How far grading may push a picture, so art never looks washed out or garish.
COLOUR_RANGE = (0.55, 1.6)
BRIGHT_RANGE = (0.7, 1.3)
INK_STEP = 0.06          # the main style has this much more black ink: draw a dark outline


def profile(assets) -> dict | None:
    looks = [a.look for a in assets if a.look and a.kind == "prop" and all(k in a.look for k in KEYS)]
    if len(looks) < MIN_LOOKS:
        return None
    out = {k: round(sum(lk[k] for lk in looks) / len(looks), 3) for k in KEYS}
    out["n"] = len(looks)
    return out


def gap(a: dict | None, b: dict | None) -> float | None:
    """How different two styles are: 0 for the same, above about 18 clearly different."""
    if not a or not b:
        return None
    return sum(WEIGHTS[k] * abs(a[k] - b[k]) for k in KEYS) / sum(WEIGHTS.values()) * 100 * 2


def _clamp(v, lo_hi):
    lo, hi = lo_hi
    return max(lo, min(hi, v))


def grade_for(src: dict | None, target: dict | None) -> tuple[float, float, float] | None:
    """(colour strength, brightness, outline) that move art in style ``src`` towards
    ``target``, or None when they are already close. Outline is 0 to 1: how dark an
    edge to draw round art from a pack with little black ink, when the main pack has a lot."""
    if not src or not target:
        return None
    colour = _clamp(target["sat"] / src["sat"], COLOUR_RANGE) if src["sat"] > 0.02 else 1.0
    bright = _clamp(target["bright"] / src["bright"], BRIGHT_RANGE) if src["bright"] > 0.02 else 1.0
    more_ink = target["ink"] - src["ink"]
    outline = round(min(1.0, more_ink / 0.2), 2) if more_ink >= INK_STEP else 0.0
    if abs(colour - 1) < 0.05 and abs(bright - 1) < 0.04 and not outline:
        return None
    return round(colour, 2), round(bright, 2), outline


def apply_grade(im, grade):
    """The RGBA image with its colour strength and brightness scaled; transparency kept."""
    from PIL import Image, ImageChops, ImageEnhance, ImageFilter
    colour, bright = grade[0], grade[1]
    outline = grade[2] if len(grade) > 2 else 0.0
    rgba = im.convert("RGBA")
    alpha = rgba.getchannel("A")
    rgb = rgba.convert("RGB")
    if colour != 1:
        rgb = ImageEnhance.Color(rgb).enhance(colour)
    if bright != 1:
        rgb = ImageEnhance.Brightness(rgb).enhance(bright)
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    if outline:
        # A dark band just inside the edge of the drawn part, about 2% of its size across.
        # Worked out on a copy about 250 px across, so big art stays quick (a wide MinFilter
        # on a full-size picture is slow).
        solid = alpha.point(lambda v: 255 if v >= 128 else 0)
        small = solid.resize((max(8, im.width * 250 // max(1, min(im.size))),
                              max(8, im.height * 250 // max(1, min(im.size)))), Image.BILINEAR)
        ring = ImageChops.subtract(small, small.filter(ImageFilter.MinFilter(9)))
        ring = ring.filter(ImageFilter.GaussianBlur(1.2)).resize(im.size, Image.BILINEAR)
        ring = ring.point(lambda v: int(v * 0.95 * outline))
        ink = Image.new("RGBA", im.size, (20, 16, 14, 0))
        ink.putalpha(ImageChops.multiply(ring, alpha))
        out = Image.alpha_composite(out, ink)
        out.putalpha(alpha)
    return out


def mixed_packs(index, min_props: int = 20):
    """Packs whose top-level folders differ clearly in style, which usually means several
    packs were indexed as one. Yields (pack, folder, its style, folder, its style)."""
    by: dict[str, dict[str, list]] = {}
    for a in index.assets:
        if "/" in a.rel:
            by.setdefault(a.pack, {}).setdefault(a.rel.split("/", 1)[0], []).append(a)
    for pack, folders in by.items():
        profs = [(f, profile(v)) for f, v in folders.items()
                 if sum(1 for a in v if a.look and a.kind == "prop") >= min_props]
        profs = [(f, p) for f, p in profs if p]
        worst = None
        for i, (fa, pa) in enumerate(profs):
            for fb, pb in profs[i + 1:]:
                g = gap(pa, pb)
                if g > 1.5 * CLASH and (worst is None or g > worst[0]):
                    worst = (g, fa, pa, fb, pb)
        if worst:
            yield (pack,) + worst[1:]


def describe(p: dict) -> str:
    """A plain description of a style, for messages."""
    bits = []
    if p["ink"] >= 0.12:
        bits.append("heavy black outlines")
    elif p["ink"] <= 0.03:
        bits.append("hardly any black outline")
    bits.append("strong colour" if p["sat"] >= 0.5 else "soft colour" if p["sat"] <= 0.3 else "medium colour")
    bits.append("bright" if p["bright"] >= 0.65 else "dark" if p["bright"] <= 0.4 else "mid brightness")
    if p["soft"] >= 0.08:
        bits.append("baked-in shadows")
    return ", ".join(bits)
