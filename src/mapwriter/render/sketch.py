"""A quick block plan for checking a layout before painting it."""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from ..plan import Plan

ROOM_COLOURS = [(236, 222, 196), (206, 226, 214), (214, 214, 236), (238, 210, 210),
                (222, 234, 198), (232, 222, 238), (208, 230, 236), (240, 228, 206)]


def font(size: int):
    for name in ("DejaVuSans.ttf", "Arial.ttf", "arial.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def sketch(plan: Plan, px: int = 48) -> Image.Image:
    sc = plan.scene
    m = int(px * 0.9)       # margin for grid numbers
    top = int(px * 0.8)     # title band
    W, H = sc.width * px, sc.height * px
    im = Image.new("RGB", (W + 2 * m, H + 2 * m + top), (250, 250, 247))
    d = ImageDraw.Draw(im)
    d.text((m, top // 2), f"{sc.name}  ·  {sc.width} x {sc.height} squares  ·  sketch", fill=(30, 30, 30), font=font(max(12, px // 3)), anchor="lm")
    im2 = Image.new("RGB", (W + 2 * m, H + 2 * m), (250, 250, 247))
    full, im = im, im2
    d = ImageDraw.Draw(im)
    f = font(max(10, px // 3)); fs = font(max(9, px // 4)); fb = font(max(12, int(px * 0.42)))

    def P(x, y):
        return m + x * px, m + y * px

    d.rectangle([*P(0, 0), *P(sc.width, sc.height)], fill=(238, 236, 230))
    for a in sc.areas:
        d.polygon([P(*p) for p in a.poly], fill=(214, 228, 200))
    for i, r in enumerate(sc.rooms):
        d.polygon([P(*p) for p in r.poly], fill=ROOM_COLOURS[i % len(ROOM_COLOURS)])
    for x in range(sc.width + 1):
        d.line([P(x, 0), P(x, sc.height)], fill=(205, 205, 200), width=1)
        if x < sc.width and (x % 2 == 0 or px >= 40):
            d.text((m + x * px + px // 2, m // 2), str(x), fill=(120, 120, 120), font=fs, anchor="mm")
            d.text((m + x * px + px // 2, m + H + m // 2), str(x), fill=(120, 120, 120), font=fs, anchor="mm")
    for y in range(sc.height + 1):
        d.line([P(0, y), P(sc.width, y)], fill=(205, 205, 200), width=1)
        if y < sc.height and (y % 2 == 0 or px >= 40):
            d.text((m // 2, m + y * px + px // 2), str(y), fill=(120, 120, 120), font=fs, anchor="mm")
            d.text((m + W + m // 2, m + y * px + px // 2), str(y), fill=(120, 120, 120), font=fs, anchor="mm")

    # props
    for p in sorted(plan.props, key=lambda p: p.layer):
        x0, y0, x1, y1 = p.box
        missing = p.asset is None
        fill = (250, 214, 214) if missing else ((226, 210, 236) if p.layer == 0 else (255, 255, 255))
        out = (200, 40, 40) if missing else (90, 90, 110)
        inset = 0.06 * px
        d.rounded_rectangle([P(x0, y0)[0] + inset, P(x0, y0)[1] + inset, P(x1, y1)[0] - inset, P(x1, y1)[1] - inset],
                            radius=int(px * 0.12), fill=fill, outline=out, width=2)
        # facing tick: the side the back of the prop is on
        rot = int(round(p.rot)) % 360
        cx, cy = P(*p.centre)
        bx, by = {0: (0, -1), 90: (1, 0), 180: (0, 1), 270: (-1, 0)}.get(rot, (0, 0))
        if p.layer > 0 and (bx or by):
            hw, hh = (x1 - x0) * px / 2 - inset * 2, (y1 - y0) * px / 2 - inset * 2
            ex, ey = cx + bx * hw, cy + by * hh
            d.line([ex - abs(by) * hw * 0.6, ey - abs(bx) * hh * 0.6, ex + abs(by) * hw * 0.6, ey + abs(bx) * hh * 0.6], fill=out, width=3)
        text = p.label or p.want
        if len(text) > 18:
            text = text[:17] + "…"
        d.text((cx, cy), text, fill=(150, 30, 30) if missing else (40, 40, 60), font=fs, anchor="mm")

    # walls
    for x0, y0, x1, y1 in plan.walls:
        d.line([P(x0, y0), P(x1, y1)], fill=(30, 30, 34), width=max(4, px // 7))
    for o, _ in plan.openings:
        col = {"door": (40, 160, 60), "double": (40, 160, 60), "secret": (150, 60, 170),
               "window": (230, 190, 20), "arch": (60, 140, 220)}.get(o.kind, (0, 0, 0))
        d.line([P(*o.a), P(*o.b)], fill=col, width=max(6, px // 5))

    # lights
    for L in plan.lights:
        x, y = P(*L.at); r = max(4, px // 7)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 200, 40), outline=(160, 110, 0), width=2)
        rr = L.radius * px
        d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=(240, 190, 60), width=1)

    # room names and notes
    for r in sc.rooms:
        x0, y0, x1, y1 = r.box
        d.text(P((x0 + x1) / 2, y0 + 0.45), (r.label or r.name), fill=(20, 20, 30), font=fb, anchor="mm")
    for i, n in enumerate(sc.notes, 1):
        x, y = P(*n.at); r = px * 0.3
        d.ellipse([x - r, y - r, x + r, y + r], fill=(160, 40, 40))
        d.text((x, y), str(i), fill=(255, 255, 255), font=f, anchor="mm")

    full.paste(im, (0, top))
    return full
