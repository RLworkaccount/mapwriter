"""What a picture looks like, read from its pixels on this computer.

File names only say so much. Two packs can both have a file with 'apple' in its
name, one an apple and the other a handcart full of them. This module opens each
image, shrinks it to a small thumbnail and measures plain things about it:

- shape: how much of the square it fills, the box round the drawn part, how solid it is
- colours: which colour words cover the drawn part (red, green, brown, grey...)
- style: how much black ink outlines it, how bright and how strongly coloured it is,
  how much soft shadow sits round it
- whether it tiles seamlessly, as floor textures do
- a short fingerprint for spotting near copies

Nothing leaves the computer and no model or online service is used: it is
arithmetic on pixels with Pillow. The results are small numbers stored in the
asset index, so they are worked out once per file.
"""
from __future__ import annotations

import colorsys
import os

LOOK_VERSION = 1
THUMB = 48

# Colour words, in the order their shares are stored in a look's signature.
COLOURS = ["red", "orange", "yellow", "green", "teal", "blue", "purple", "pink", "brown", "grey", "white", "black"]
COLOUR_MIN_SHARE = 0.22          # a colour word needs this share of the drawn part


def colour_word(r: int, g: int, b: int) -> str:
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    h *= 360
    if v < 0.16:
        return "black"
    if s < 0.16 or (s < 0.24 and v < 0.5):
        return "white" if v > 0.82 else "grey"
    if 12 <= h < 55 and (v < 0.6 or s < 0.45):
        return "brown"            # dull orange and yellow: wood, leather, earth
    if h < 12 or h >= 345:
        return "brown" if v < 0.42 else "red"
    if h < 40:
        return "orange"
    if h < 68:
        return "yellow"
    if h < 165:
        return "green"
    if h < 195:
        return "teal"
    if h < 255:
        return "blue"
    if h < 290:
        return "purple"
    return "pink"


def _open_small(path: str):
    from PIL import Image
    im = Image.open(path)
    if im.format == "JPEG":
        im.draft("RGB", (THUMB * 2, THUMB * 2))       # decode at a fraction of full size
    im = im.convert("RGBA")
    im.thumbnail((THUMB, THUMB))
    return im


def _seam(grey, w: int, h: int) -> bool:
    """True when the left edge runs on into the right and the top into the bottom about as
    smoothly as neighbouring columns and rows do: the picture tiles."""
    px = grey.load()
    if w < 8 or h < 8:
        return False

    def col_diff(a, b):
        return sum(abs(px[a, y] - px[b, y]) for y in range(h)) / h

    def row_diff(a, b):
        return sum(abs(px[x, a] - px[x, b]) for x in range(w)) / w

    inner_c = sum(col_diff(x, x + 1) for x in range(1, w - 2)) / (w - 3)
    inner_r = sum(row_diff(y, y + 1) for y in range(1, h - 2)) / (h - 3)
    return col_diff(0, w - 1) <= 1.8 * inner_c + 3 and row_diff(0, h - 1) <= 1.8 * inner_r + 3


def _dhash(grey) -> str:
    from PIL import Image
    g = grey.resize((9, 8), Image.BILINEAR)
    px = g.load()
    bits = 0
    for y in range(8):
        for x in range(8):
            bits = (bits << 1) | (px[x, y] > px[x + 1, y])
    return f"{bits:016x}"


def measure(im) -> dict:
    """The look of an RGBA image (any size; it is shrunk first)."""
    from PIL import Image
    im = im.convert("RGBA")
    if max(im.size) > THUMB:
        im = im.copy()
        im.thumbnail((THUMB, THUMB))
    w, h = im.size
    raw = im.tobytes()
    data = [tuple(raw[i:i + 4]) for i in range(0, len(raw), 4)]
    n = len(data)
    solid = [(r, g, b) for r, g, b, a in data if a >= 128]
    soft = sum(1 for *_c, a in data if 10 <= a < 128)
    fill = len(solid) / n
    alpha = im.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
    bbox = alpha.getbbox() or (0, 0, w, h)
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    shares = dict.fromkeys(COLOURS, 0)
    sat = val = 0.0
    for r, g, b in solid:
        shares[colour_word(r, g, b)] += 1
        _h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        sat += s
        val += v
    k = max(1, len(solid))
    mix = {c: round(shares[c] / k, 2) for c in COLOURS}
    named = sorted((c for c in COLOURS if mix[c] >= COLOUR_MIN_SHARE), key=lambda c: -mix[c])[:2]
    if not named and solid:
        top = max(COLOURS, key=lambda c: mix[c])
        if mix[top] >= 0.15:
            named = [top]               # a spread of shades: name the main one
    flat = Image.new("RGBA", im.size, (128, 128, 128, 255))
    flat.alpha_composite(im)
    grey = flat.convert("L")
    look = {
        "v": LOOK_VERSION,
        "fill": round(fill, 2),                                  # share of the canvas drawn on
        "box": [round(bbox[0] / w, 2), round(bbox[1] / h, 2), round(bbox[2] / w, 2), round(bbox[3] / h, 2)],
        "solid": round(len(solid) / max(1, bw * bh), 2),         # share of that box drawn on
        "colours": named,
        "mix": mix,
        "ink": mix["black"],                                     # black outlines and shading
        "sat": round(sat / k, 2),
        "bright": round(val / k, 2),
        "soft": round(soft / n, 2),                              # soft edges and baked shadow
        "tile": fill > 0.99 and _seam(grey, w, h),
        "hash": _dhash(grey),
    }
    look["sig"] = signature(look)
    return look


def signature(look: dict) -> list[int]:
    """The numbers likeness() compares, each 0 to 100."""
    mix = look["mix"]
    x0, y0, x1, y1 = look["box"]
    bw, bh = max(0.01, x1 - x0), max(0.01, y1 - y0)
    aspect = min(bw, bh) / max(bw, bh)
    return [round(100 * mix[c]) for c in COLOURS] + [
        round(100 * look["fill"]), round(100 * look["solid"]), round(100 * aspect),
        round(100 * look["sat"]), round(100 * look["bright"]), round(100 * min(1.0, 4 * look["soft"]))]


# How much each part of the signature counts: colours most, then shape, then style.
WEIGHTS = [1.0] * len(COLOURS) + [0.6, 0.5, 0.5, 0.4, 0.4, 0.2]
_WSUM = sum(WEIGHTS)


def likeness(a: list[int], b: list[int]) -> float:
    """Distance between two signatures: 0 for the same look; above about 12 they look
    clearly different."""
    return sum(w * abs(x - y) for w, x, y in zip(WEIGHTS, a, b)) / _WSUM * 2


def centre(sigs: list[list[int]]) -> list[int]:
    """The middle look of a group (the median of each number), so one odd file does not
    pull the group's look towards it."""
    out = []
    for vals in zip(*sigs):
        s = sorted(vals)
        out.append(s[len(s) // 2])
    return out


def stamp(path: str) -> list[int] | None:
    try:
        st = os.stat(path)
    except OSError:
        return None
    return [st.st_size, int(st.st_mtime)]


def look_at(path: str) -> dict | None:
    try:
        im = _open_small(path)
    except Exception:
        return None
    look = measure(im)
    look["at"] = stamp(path)
    return look


def up_to_date(asset) -> bool:
    lk = asset.look
    return bool(lk) and lk.get("v") == LOOK_VERSION and lk.get("at") == stamp(asset.path)


def look_all(assets, workers: int = 8, force: bool = False, progress=None) -> int:
    """Measure every asset whose look is missing or older than its file. Returns how many
    were measured. Big packs take a few minutes the first time; later runs only look at
    new or changed files."""
    todo = [a for a in assets if force or not up_to_date(a)]
    if not todo:
        return 0
    from concurrent.futures import ThreadPoolExecutor
    done = 0
    with ThreadPoolExecutor(max(1, workers)) as ex:
        for a, lk in zip(todo, ex.map(lambda a: look_at(a.path), todo, chunksize=32)):
            a.look = lk
            done += 1
            if progress and done % 2000 == 0:
                progress(done, len(todo))
    return len(todo)
