"""Draw a small starter asset pack in code, so MapWriter works with no downloads.

The art is simple on purpose. It exists for tests, examples and trying the tool
out; real maps should use real asset packs. Everything here is drawn by this
file and is MIT licensed with the rest of MapWriter.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

S = 200          # pixels per square, like most commercial packs
SS = 2           # supersampling


def _new(w, h):
    return Image.new("RGBA", (w * S * SS, h * S * SS), (0, 0, 0, 0))


def _done(im):
    return im.resize((im.width // SS, im.height // SS), Image.LANCZOS)


def _shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3]) + ((c[3],) if len(c) == 4 else ())


def _grain(d, box, col, n, rnd, horizontal=True, width=2):
    x0, y0, x1, y1 = box
    for _ in range(n):
        if horizontal:
            y = rnd.uniform(y0, y1); d.line([x0, y, x1, y + rnd.uniform(-6, 6)], fill=col, width=width)
        else:
            x = rnd.uniform(x0, x1); d.line([x, y0, x + rnd.uniform(-6, 6), y1], fill=col, width=width)


# ------------------------------------------------------------------ floors
def planks(colour, seed=0, size=2):
    rnd = random.Random(seed)
    W = H = size * S
    im = Image.new("RGB", (W, H), colour)
    d = ImageDraw.Draw(im)
    ph = S // 4
    for row in range(H // ph):
        y = row * ph
        x = -rnd.randint(0, S)
        while x < W:
            L = rnd.randint(S, int(S * 2.2))
            k = rnd.uniform(0.86, 1.12)
            c = _shade(colour, k)
            d.rectangle([x, y, x + L, y + ph], fill=c)
            for _ in range(5):
                yy = y + rnd.uniform(3, ph - 3)
                d.line([x + 3, yy, x + L - 3, yy + rnd.uniform(-2, 2)], fill=_shade(c, 0.9), width=1)
            d.line([x, y, x, y + ph], fill=_shade(colour, 0.6), width=2)
            x += L
        d.line([0, y, W, y], fill=_shade(colour, 0.55), width=2)
    # wrap seams so the texture tiles
    return im


def flagstones(colour, seed=0, size=2, cobble=False):
    rnd = random.Random(seed)
    W = H = size * S
    im = Image.new("RGB", (W, H), _shade(colour, 0.55))
    d = ImageDraw.Draw(im)
    step = S // 4 if cobble else S // 2
    for gy in range(0, H, step):
        off = (step // 2) if (gy // step) % 2 else 0
        for gx in range(-step, W + step, step):
            x = gx + off
            k = rnd.uniform(0.85, 1.12)
            g = 4 if cobble else 3
            if cobble:
                d.rounded_rectangle([x + g, gy + g, x + step - g, gy + step - g], radius=step // 3, fill=_shade(colour, k))
            else:
                d.rectangle([x + g, gy + g, x + step - g, gy + step - g], fill=_shade(colour, k))
    im = im.filter(ImageFilter.SMOOTH)
    return im


def grass(colour=(96, 132, 66), seed=0, size=2):
    rnd = random.Random(seed)
    W = H = size * S
    im = Image.new("RGB", (W, H), colour)
    d = ImageDraw.Draw(im)
    for _ in range(2600):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        L = rnd.uniform(6, 16); a = rnd.uniform(-0.6, 0.6) - math.pi / 2
        c = _shade(colour, rnd.uniform(0.75, 1.25))
        for ox in (0, -W, W):
            for oy in (0, -H, H):
                d.line([x + ox, y + oy, x + ox + L * math.cos(a), y + oy + L * math.sin(a)], fill=c, width=2)
    return im


def water(colour=(58, 104, 128), seed=0, size=2):
    rnd = random.Random(seed)
    W = H = size * S
    im = Image.new("RGB", (W, H), colour)
    d = ImageDraw.Draw(im)
    for _ in range(160):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        L = rnd.uniform(20, 60); c = _shade(colour, rnd.uniform(0.9, 1.25))
        for ox in (0, -W, W):
            for oy in (0, -H, H):
                d.arc([x + ox - L, y + oy - L / 4, x + ox + L, y + oy + L / 4], 200, 340, fill=c, width=2)
    return im.filter(ImageFilter.SMOOTH)


def mud(colour=(104, 84, 60), seed=0, size=2):
    rnd = random.Random(seed)
    W = H = size * S
    im = Image.new("RGB", (W, H), colour)
    d = ImageDraw.Draw(im)
    for _ in range(500):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H); r = rnd.uniform(4, 18)
        c = _shade(colour, rnd.uniform(0.8, 1.15))
        for ox in (0, -W, W):
            for oy in (0, -H, H):
                d.ellipse([x + ox - r, y + oy - r * .7, x + ox + r, y + oy + r * .7], fill=c)
    return im.filter(ImageFilter.GaussianBlur(2))


def rug_texture(base, trim, seed=0):
    W = H = S
    im = Image.new("RGB", (W, H), base)
    d = ImageDraw.Draw(im)
    for i in range(0, W, 25):
        d.line([i, 0, i, H], fill=_shade(base, 0.92), width=3)
    d.polygon([(W / 2, 30), (W - 30, H / 2), (W / 2, H - 30), (30, H / 2)], outline=trim, width=6)
    d.ellipse([W / 2 - 18, H / 2 - 18, W / 2 + 18, H / 2 + 18], fill=trim)
    return im


# ------------------------------------------------------------------ structure
def wall_strip(colour=(118, 112, 106), length=8, seed=0):
    rnd = random.Random(seed)
    t = int(S * 0.34)
    im = Image.new("RGBA", (length * S, t), _shade(colour, 0.45) + (255,))
    d = ImageDraw.Draw(im)
    x = 0
    while x < im.width:
        w = rnd.randint(int(t * 0.9), int(t * 1.7))
        for row in (0, 1):
            ox = 0 if row == 0 else -w // 2
            c = _shade(colour, rnd.uniform(0.85, 1.12))
            d.rounded_rectangle([x + ox + 2, row * t // 2 + 2, x + ox + w - 2, (row + 1) * t // 2 - 2], radius=4, fill=c)
        x += w
    d.rectangle([0, 0, im.width - 1, t - 1], outline=_shade(colour, 0.35) + (255,), width=4)
    return im


def door(wood=(132, 86, 50)):
    im = _new(1, 1); d = ImageDraw.Draw(im); s = S * SS
    y0, y1 = int(s * 0.4), int(s * 0.6)
    d.rectangle([0, y0, s - 1, y1], fill=wood + (255,), outline=_shade(wood, 0.45) + (255,), width=6)
    for k in range(1, 4):
        x = k * s // 4; d.line([x, y0 + 6, x, y1 - 6], fill=_shade(wood, 0.7) + (255,), width=4)
    d.ellipse([s * 0.78, s * 0.47, s * 0.84, s * 0.53], fill=(60, 52, 40, 255))
    return _done(im)


def window(frame=(110, 76, 48)):
    im = _new(1, 1); d = ImageDraw.Draw(im); s = S * SS
    y0, y1 = int(s * 0.42), int(s * 0.58)
    d.rectangle([0, y0, s - 1, y1], fill=(176, 208, 226, 235), outline=frame + (255,), width=10)
    d.line([s / 2, y0, s / 2, y1], fill=frame + (255,), width=8)
    return _done(im)


# ------------------------------------------------------------------ props
def table(w, h, wood=(150, 100, 60), round_=False, seed=0):
    rnd = random.Random(seed)
    im = _new(w, h); d = ImageDraw.Draw(im); s = S * SS
    box = [s * 0.08, s * 0.08, w * s - s * 0.08, h * s - s * 0.08]
    if round_:
        d.ellipse(box, fill=wood + (255,), outline=_shade(wood, 0.5) + (255,), width=10)
    else:
        d.rounded_rectangle(box, radius=s * 0.06, fill=wood + (255,), outline=_shade(wood, 0.5) + (255,), width=10)
        _grain(d, [box[0] + 12, box[1] + 12, box[2] - 12, box[3] - 12], _shade(wood, 0.85) + (255,), 14 * max(w, h), rnd, w >= h, 3)
    return _done(im)


def chair(wood=(140, 92, 54), cushion=(160, 60, 60)):
    im = _new(1, 1); d = ImageDraw.Draw(im); s = S * SS
    d.rounded_rectangle([s * .22, s * .28, s * .78, s * .82], radius=20, fill=wood + (255,), outline=_shade(wood, .5) + (255,), width=8)
    d.rounded_rectangle([s * .3, s * .38, s * .7, s * .74], radius=16, fill=cushion + (255,))
    d.rounded_rectangle([s * .18, s * .16, s * .82, s * .3], radius=14, fill=_shade(wood, .8) + (255,), outline=_shade(wood, .45) + (255,), width=8)
    return _done(im)


def stool(wood=(150, 104, 62)):
    im = _new(1, 1); d = ImageDraw.Draw(im); s = S * SS
    d.ellipse([s * .28, s * .28, s * .72, s * .72], fill=wood + (255,), outline=_shade(wood, .5) + (255,), width=8)
    return _done(im)


def bench(n=3, wood=(136, 90, 52)):
    im = _new(n, 1); d = ImageDraw.Draw(im); s = S * SS
    d.rounded_rectangle([s * .06, s * .3, n * s - s * .06, s * .7], radius=12, fill=wood + (255,), outline=_shade(wood, .5) + (255,), width=8)
    d.line([s * .1, s * .5, n * s - s * .1, s * .5], fill=_shade(wood, .7) + (255,), width=5)
    return _done(im)


def barrel(wood=(146, 96, 54)):
    im = _new(1, 1); d = ImageDraw.Draw(im); s = S * SS
    d.ellipse([s * .1, s * .1, s * .9, s * .9], fill=wood + (255,), outline=(70, 60, 54, 255), width=14)
    d.ellipse([s * .22, s * .22, s * .78, s * .78], outline=(80, 70, 60, 255), width=8)
    for k in range(6):
        a = k * math.pi / 3
        d.line([s / 2, s / 2, s / 2 + math.cos(a) * s * .28, s / 2 + math.sin(a) * s * .28], fill=_shade(wood, .7) + (255,), width=4)
    return _done(im)


def crate(wood=(170, 128, 76)):
    im = _new(1, 1); d = ImageDraw.Draw(im); s = S * SS
    d.rectangle([s * .1, s * .1, s * .9, s * .9], fill=wood + (255,), outline=_shade(wood, .45) + (255,), width=12)
    d.line([s * .14, s * .14, s * .86, s * .86], fill=_shade(wood, .7) + (255,), width=16)
    d.line([s * .86, s * .14, s * .14, s * .86], fill=_shade(wood, .7) + (255,), width=16)
    return _done(im)


def chest(wood=(120, 76, 44)):
    im = _new(1, 1); d = ImageDraw.Draw(im); s = S * SS
    d.rounded_rectangle([s * .12, s * .26, s * .88, s * .74], radius=14, fill=wood + (255,), outline=(60, 44, 30, 255), width=10)
    for x in (.3, .7):
        d.line([s * x, s * .26, s * x, s * .74], fill=(196, 160, 70, 255), width=12)
    d.rectangle([s * .46, s * .42, s * .54, s * .56], fill=(220, 184, 80, 255))
    return _done(im)


def bed(blanket=(90, 110, 160), wood=(130, 84, 50)):
    im = _new(1, 2); d = ImageDraw.Draw(im); s = S * SS
    d.rounded_rectangle([s * .06, s * .06, s * .94, 2 * s - s * .06], radius=16, fill=wood + (255,), outline=_shade(wood, .5) + (255,), width=8)
    d.rounded_rectangle([s * .14, s * .14, s * .86, s * .5], radius=26, fill=(238, 234, 226, 255))
    d.rounded_rectangle([s * .12, s * .6, s * .88, 2 * s - s * .14], radius=18, fill=blanket + (255,))
    d.line([s * .12, s * .76, s * .88, s * .76], fill=_shade(blanket, .8) + (255,), width=10)
    return _done(im)


def shelf(n=2, wood=(124, 82, 48), seed=0):
    rnd = random.Random(seed)
    im = _new(n, 1); d = ImageDraw.Draw(im); s = S * SS
    d.rectangle([s * .04, s * .1, n * s - s * .04, s * .5], fill=wood + (255,), outline=_shade(wood, .45) + (255,), width=8)
    x = s * .08
    while x < n * s - s * .12:
        bw = rnd.uniform(s * .05, s * .1)
        c = rnd.choice([(150, 50, 50), (60, 90, 140), (70, 120, 70), (170, 140, 60), (110, 70, 120)])
        d.rectangle([x, s * .14, x + bw, s * .46], fill=c + (255,))
        x += bw + 4
    return _done(im)


def counter(n=3, wood=(140, 96, 58)):
    im = _new(n, 1); d = ImageDraw.Draw(im); s = S * SS
    d.rectangle([s * .02, s * .12, n * s - s * .02, s * .88], fill=wood + (255,), outline=_shade(wood, .45) + (255,), width=10)
    d.rectangle([s * .02, s * .12, n * s - s * .02, s * .3], fill=_shade(wood, 1.12) + (255,))
    for k in range(1, n * 2):
        d.line([k * s / 2, s * .32, k * s / 2, s * .86], fill=_shade(wood, .75) + (255,), width=5)
    return _done(im)


def plant(leaf=(70, 130, 64), pot=(176, 96, 64), seed=0):
    rnd = random.Random(seed)
    im = _new(1, 1); d = ImageDraw.Draw(im); s = S * SS
    d.ellipse([s * .26, s * .26, s * .74, s * .74], fill=pot + (255,), outline=_shade(pot, .5) + (255,), width=8)
    for k in range(11):
        a = k * 2 * math.pi / 11 + rnd.uniform(-.2, .2); r = s * rnd.uniform(.18, .32)
        x, y = s / 2 + math.cos(a) * r, s / 2 + math.sin(a) * r
        d.ellipse([x - s * .1, y - s * .1, x + s * .1, y + s * .1], fill=_shade(leaf, rnd.uniform(.8, 1.2)) + (255,))
    return _done(im)


def tree(leaf=(64, 112, 58), size=2, seed=0):
    rnd = random.Random(seed)
    im = _new(size, size); d = ImageDraw.Draw(im); s = S * SS * size
    for k in range(26):
        a = rnd.uniform(0, 2 * math.pi); r = s * rnd.uniform(0, .3)
        x, y = s / 2 + math.cos(a) * r, s / 2 + math.sin(a) * r; rr = s * rnd.uniform(.12, .2)
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=_shade(leaf, rnd.uniform(.75, 1.2)) + (255,))
    return _done(im)


def rock(size=1, colour=(128, 124, 118), seed=0):
    rnd = random.Random(seed)
    im = _new(size, size); d = ImageDraw.Draw(im); s = S * SS * size
    n = 9
    pts = [(s / 2 + math.cos(2 * math.pi * k / n) * s * rnd.uniform(.28, .42),
            s / 2 + math.sin(2 * math.pi * k / n) * s * rnd.uniform(.28, .42)) for k in range(n)]
    d.polygon(pts, fill=colour + (255,), outline=_shade(colour, .5) + (255,), width=8 * size)
    d.polygon([(x * .55 + s * .2, y * .55 + s * .16) for x, y in pts], fill=_shade(colour, 1.18) + (255,))
    return _done(im)


def bush(leaf=(74, 120, 60), seed=0, flowers=None):
    rnd = random.Random(seed)
    im = _new(1, 1); d = ImageDraw.Draw(im); s = S * SS
    for k in range(16):
        a = rnd.uniform(0, 2 * math.pi); r = s * rnd.uniform(0, .22)
        x, y = s / 2 + math.cos(a) * r, s / 2 + math.sin(a) * r; rr = s * rnd.uniform(.1, .16)
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=_shade(leaf, rnd.uniform(.75, 1.2)) + (255,))
    for _ in range(14 if flowers else 0):
        x, y = rnd.uniform(s * .25, s * .75), rnd.uniform(s * .25, s * .75); rr = s * .035
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=flowers + (255,))
    return _done(im)


def candle():
    im = _new(1, 1); d = ImageDraw.Draw(im); s = S * SS
    d.ellipse([s * .38, s * .38, s * .62, s * .62], fill=(238, 228, 200, 255), outline=(150, 130, 100, 255), width=6)
    d.ellipse([s * .46, s * .46, s * .54, s * .54], fill=(255, 190, 60, 255))
    return _done(im)


def lantern():
    im = _new(1, 1); d = ImageDraw.Draw(im); s = S * SS
    d.rounded_rectangle([s * .34, s * .34, s * .66, s * .66], radius=10, fill=(60, 54, 50, 255))
    d.rounded_rectangle([s * .4, s * .4, s * .6, s * .6], radius=8, fill=(255, 210, 110, 255))
    return _done(im)


def fireplace(stone=(120, 114, 108)):
    im = _new(2, 1); d = ImageDraw.Draw(im); s = S * SS
    d.rectangle([s * .04, s * .04, 2 * s - s * .04, s * .62], fill=stone + (255,), outline=_shade(stone, .45) + (255,), width=10)
    d.rectangle([s * .4, s * .1, 2 * s - s * .4, s * .56], fill=(40, 30, 26, 255))
    for k, c in enumerate([(255, 120, 40), (255, 180, 60), (255, 230, 120)]):
        r = s * (.2 - k * .05)
        d.ellipse([s - r, s * .36 - r * .7, s + r, s * .36 + r * .7], fill=c + (255,))
    return _done(im)


def cauldron():
    im = _new(1, 1); d = ImageDraw.Draw(im); s = S * SS
    d.ellipse([s * .14, s * .14, s * .86, s * .86], fill=(44, 44, 48, 255), outline=(20, 20, 24, 255), width=10)
    d.ellipse([s * .24, s * .24, s * .76, s * .76], fill=(110, 170, 90, 255))
    return _done(im)


def sack(c=(186, 160, 112)):
    im = _new(1, 1); d = ImageDraw.Draw(im); s = S * SS
    d.ellipse([s * .2, s * .24, s * .8, s * .84], fill=c + (255,), outline=_shade(c, .55) + (255,), width=8)
    d.ellipse([s * .42, s * .18, s * .58, s * .34], fill=_shade(c, .8) + (255,))
    return _done(im)


def altar(stone=(170, 166, 160), cloth=(70, 80, 150)):
    im = _new(2, 1); d = ImageDraw.Draw(im); s = S * SS
    d.rounded_rectangle([s * .06, s * .16, 2 * s - s * .06, s * .84], radius=14, fill=stone + (255,), outline=_shade(stone, .5) + (255,), width=10)
    d.rectangle([s * .7, s * .16, 2 * s - s * .7, s * .84], fill=cloth + (255,))
    d.line([s * .7, s * .78, 2 * s - s * .7, s * .78], fill=(220, 190, 90, 255), width=8)
    return _done(im)


def pew(n=3):
    return bench(n, (110, 72, 44))


def cage(n=1, metal=(150, 150, 160)):
    im = _new(n, 1); d = ImageDraw.Draw(im); s = S * SS
    d.rounded_rectangle([s * .1, s * .1, n * s - s * .1, s * .9], radius=20, fill=(70, 60, 50, 90), outline=metal + (255,), width=10)
    x = s * .2
    while x < n * s - s * .15:
        d.line([x, s * .12, x, s * .88], fill=metal + (255,), width=5); x += s * .12
    return _done(im)


def stall(w=3, cloth=(190, 70, 70)):
    im = _new(w, 2); d = ImageDraw.Draw(im); s = S * SS
    d.rectangle([s * .1, s * .9, w * s - s * .1, 2 * s - s * .2], fill=(140, 96, 58, 255), outline=(70, 46, 28, 255), width=8)
    stripes = w * 4
    for k in range(stripes):
        c = cloth if k % 2 == 0 else (240, 230, 210)
        d.rectangle([k * w * s / stripes, s * .05, (k + 1) * w * s / stripes, s * .85], fill=c + (255,))
    d.rectangle([0, s * .05, w * s - 1, s * .85], outline=_shade(cloth, .5) + (255,), width=8)
    return _done(im)


# ------------------------------------------------------------------ pack
def build_pack(out_dir: str | Path) -> int:
    out = Path(out_dir)
    def save(rel, im, q=92):
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix == ".jpg":
            im.convert("RGB").save(p, quality=q)
        else:
            im.save(p)
    (out).mkdir(parents=True, exist_ok=True)
    (out / "mapwriter-pack.yaml").write_text(
        "name: MapWriter Starter\npx_per_square: 200\n"
        "# Simple art drawn by code (mapwriter/testart.py). MIT licensed, free to share.\n", encoding="utf-8")
    woods = {"Walnut": (110, 72, 44), "Light": (176, 132, 84), "Red": (150, 82, 56), "Ashen": (150, 140, 126)}
    for name, c in woods.items():
        save(f"Textures/Wooden_Floors/Wooden_Flooring_{name}.jpg", planks(c, seed=len(name)))
    save("Textures/Stone_Floors/Stone_Flagstones_Gray.jpg", flagstones((134, 130, 124), 1))
    save("Textures/Stone_Floors/Stone_Tiles_Warm.jpg", flagstones((160, 138, 112), 2))
    save("Textures/Stone_Floors/Cobblestone_Gray.jpg", flagstones((122, 118, 112), 3, cobble=True))
    save("Textures/Grass/Grass_Green.jpg", grass())
    save("Textures/Water/Water_Pond_Blue.jpg", water())
    save("Textures/Dirt/Mud_Brown.jpg", mud())
    save("Textures/Dirt/Dirt_Path.jpg", flagstones((126, 100, 70), 4, cobble=True))
    save("Textures/Rugs/Rug_Texture_Red.jpg", rug_texture((140, 44, 48), (220, 180, 90)))
    save("Textures/Rugs/Rug_Texture_Blue.jpg", rug_texture((52, 70, 130), (220, 200, 140)))
    save("Structures/Walls/Wall_Stone_Gray_Path.png", wall_strip())
    save("Structures/Walls/Wall_Wood_Walnut_Path.png", wall_strip((116, 80, 50), seed=2))
    save("Structures/Doors/Door_Wood_Walnut_1x1.png", door())
    save("Structures/Doors/Door_Metal_Iron_1x1.png", door((96, 96, 104)))
    save("Structures/Windows/Window_Wood_Walnut_1x1.png", window())
    F = "Furniture"
    save(f"{F}/Tables/Table_Wood_Walnut_2x1.png", table(2, 1, seed=1))
    save(f"{F}/Tables/Table_Wood_Walnut_3x2.png", table(3, 2, seed=2))
    save(f"{F}/Tables/Table_Round_Wood_Light_1x1.png", table(1, 1, (176, 130, 82), True))
    save(f"{F}/Tables/Table_Round_Wood_Light_2x2.png", table(2, 2, (176, 130, 82), True))
    save(f"{F}/Seating/Chair_Wood_Walnut_1x1.png", chair())
    save(f"{F}/Seating/Armchair_Cushioned_Green_1x1.png", chair((110, 72, 44), (70, 120, 80)))
    save(f"{F}/Seating/Stool_Wood_Light_1x1.png", stool())
    save(f"{F}/Seating/Bench_Wood_Walnut_3x1.png", bench(3))
    save(f"{F}/Seating/Pew_Wood_Dark_3x1.png", pew(3))
    save(f"{F}/Beds/Bed_Single_Blue_1x2.png", bed())
    save(f"{F}/Beds/Bed_Single_Green_1x2.png", bed((80, 130, 90)))
    save(f"{F}/Shelves/Bookshelf_Wood_Walnut_2x1.png", shelf(2, seed=1))
    save(f"{F}/Shelves/Shelf_Wood_Light_3x1.png", shelf(3, (160, 120, 76), seed=2))
    save(f"{F}/Counters/Counter_Wood_Walnut_3x1.png", counter(3))
    save(f"{F}/Counters/Counter_Wood_Walnut_4x1.png", counter(4))
    save(f"{F}/Altars/Altar_Stone_Gray_2x1.png", altar())
    save(f"{F}/Hearths/Fireplace_Stone_Gray_2x1.png", fireplace())
    save(f"{F}/Kitchen/Cauldron_Iron_1x1.png", cauldron())
    C = "Clutter"
    save(f"{C}/Containers/Barrel_Wood_1x1.png", barrel())
    save(f"{C}/Containers/Crate_Wood_1x1.png", crate())
    save(f"{C}/Containers/Chest_Wood_Gold_1x1.png", chest())
    save(f"{C}/Containers/Sack_Cloth_1x1.png", sack())
    save(f"{C}/Lightsources/Candle_Wax_1x1.png", candle())
    save(f"{C}/Lightsources/Lantern_Iron_1x1.png", lantern())
    save(f"{C}/Cages/Cage_Metal_1x1.png", cage(1))
    save(f"{C}/Cages/Cage_Metal_2x1.png", cage(2))
    N = "Nature"
    save(f"{N}/Plants/Plant_Potted_Green_1x1.png", plant(seed=1))
    save(f"{N}/Plants/Plant_Potted_Flowering_1x1.png", plant((150, 90, 150), seed=2))
    save(f"{N}/Rocks/Rock_Gray_1x1.png", rock(1, seed=1))
    save(f"{N}/Rocks/Rock_Gray_2x2.png", rock(2, seed=2))
    save(f"{N}/Rocks/Rock_Mossy_1x1.png", rock(1, (110, 122, 96), seed=3))
    save(f"{N}/Bushes/Bush_Green_1x1.png", bush(seed=1))
    save(f"{N}/Bushes/Bush_Green_Dark_1x1.png", bush((56, 96, 52), seed=2))
    save(f"{N}/Flowers/Flowers_Red_1x1.png", bush((96, 140, 70), seed=3, flowers=(210, 60, 60)))
    save(f"{N}/Flowers/Flowers_Yellow_1x1.png", bush((96, 140, 70), seed=4, flowers=(240, 210, 70)))
    save(f"{N}/Trees/Tree_Oak_Green_2x2.png", tree(seed=1))
    save(f"{N}/Trees/Tree_Oak_Green_3x3.png", tree(size=3, seed=2))
    save("Market/Stalls/Market_Stall_Red_3x2.png", stall(3))
    save("Market/Stalls/Market_Stall_Blue_3x2.png", stall(3, (60, 90, 160)))
    return sum(1 for p in out.rglob("*") if p.suffix in (".png", ".jpg"))
