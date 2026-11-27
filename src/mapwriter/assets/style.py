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

# How far grading may push a picture: gentle, so art never looks washed out or garish.
COLOUR_RANGE = (0.7, 1.35)
BRIGHT_RANGE = (0.8, 1.2)


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


def grade_for(src: dict | None, target: dict | None) -> tuple[float, float] | None:
    """(colour strength, brightness) factors that move art in style ``src`` towards
    ``target``, or None when they are already close."""
    if not src or not target:
        return None
    colour = _clamp(target["sat"] / src["sat"], COLOUR_RANGE) if src["sat"] > 0.02 else 1.0
    bright = _clamp(target["bright"] / src["bright"], BRIGHT_RANGE) if src["bright"] > 0.02 else 1.0
    if abs(colour - 1) < 0.05 and abs(bright - 1) < 0.04:
        return None
    return round(colour, 2), round(bright, 2)


def apply_grade(im, grade):
    """The RGBA image with its colour strength and brightness scaled; transparency kept."""
    from PIL import ImageEnhance
    colour, bright = grade
    rgba = im.convert("RGBA")
    alpha = rgba.getchannel("A")
    rgb = rgba.convert("RGB")
    if colour != 1:
        rgb = ImageEnhance.Color(rgb).enhance(colour)
    if bright != 1:
        rgb = ImageEnhance.Brightness(rgb).enhance(bright)
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


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
