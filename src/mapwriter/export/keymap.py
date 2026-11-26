"""GM key (labelled copy) and wall check overlay."""
from __future__ import annotations

from PIL import Image, ImageDraw

from ..geometry import merge_walls
from ..plan import Plan
from ..render.sketch import font


def _scaled(image: Image.Image, plan: Plan, width: int):
    k = min(1.0, width / image.width)
    im = image.convert("RGB").resize((int(image.width * k), int(image.height * k)), Image.LANCZOS)
    return im, plan.scene.px_per_square * k


def gm_key(plan: Plan, image: Image.Image, width: int = 2000) -> Image.Image:
    im, R = _scaled(image, plan, width)
    d = ImageDraw.Draw(im, "RGBA")
    fb = font(max(14, int(R * 0.42))); f = font(max(12, int(R * 0.32)))
    for r in plan.scene.rooms:
        x0, y0, x1, y1 = r.box
        cx, cy = (x0 + x1) / 2 * R, y0 * R + R * 0.55
        text = r.label or r.name
        bb = d.textbbox((cx, cy), text, font=fb, anchor="mm")
        d.rounded_rectangle([bb[0] - 8, bb[1] - 5, bb[2] + 8, bb[3] + 5], radius=6, fill=(250, 246, 236, 225))
        d.text((cx, cy), text, fill=(30, 26, 24), font=fb, anchor="mm")
    lines = []
    for i, n in enumerate(plan.scene.notes, 1):
        x, y = n.at[0] * R, n.at[1] * R; r = R * 0.32
        d.ellipse([x - r, y - r, x + r, y + r], fill=(150, 34, 34, 240), outline=(255, 255, 255, 255), width=2)
        d.text((x, y), str(i), fill=(255, 255, 255), font=f, anchor="mm")
        lines.append(f"{i}. {n.text}")
    if lines:
        pad = 16
        lh = int(R * 0.42)
        h = pad * 2 + lh * len(lines)
        out = Image.new("RGB", (im.width, im.height + h), (250, 246, 236))
        out.paste(im, (0, 0))
        dd = ImageDraw.Draw(out)
        for k, line in enumerate(lines):
            dd.text((pad, im.height + pad + k * lh), line, fill=(30, 26, 24), font=f)
        im = out
    return im


def check_overlay(plan: Plan, image: Image.Image, width: int = 1600) -> Image.Image:
    """Walls red, doors green, windows and glass walls yellow, arches blue, light ranges as rings."""
    im, R = _scaled(image, plan, width)
    d = ImageDraw.Draw(im)
    for x in range(plan.scene.width + 1):
        d.line([x * R, 0, x * R, im.height], fill=(0, 0, 0), width=1)
    for y in range(plan.scene.height + 1):
        d.line([0, y * R, im.width, y * R], fill=(0, 0, 0), width=1)
    gaps = [o for o, _ in plan.openings if o.kind != "secret"]
    glass = set(plan.see_through_walls)
    for x0, y0, x1, y1 in merge_walls([w for w in plan.raw_walls if w not in glass], gaps):
        d.line([x0 * R, y0 * R, x1 * R, y1 * R], fill=(255, 30, 30), width=max(3, int(R * 0.08)))
    for x0, y0, x1, y1 in merge_walls(list(glass), gaps):          # glass: like a long window
        d.line([x0 * R, y0 * R, x1 * R, y1 * R], fill=(255, 230, 0), width=max(3, int(R * 0.08)))
    for o, _ in plan.openings:
        col = {"door": (30, 230, 60), "double": (30, 230, 60), "secret": (200, 60, 230),
               "window": (255, 230, 0), "arch": (60, 160, 255)}[o.kind]
        d.line([o.a[0] * R, o.a[1] * R, o.b[0] * R, o.b[1] * R], fill=col, width=max(5, int(R * 0.14)))
    for L in plan.lights:
        x, y = L.at[0] * R, L.at[1] * R; r = L.radius * R
        d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 200, 0), width=2)
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(255, 200, 0))
    return im
