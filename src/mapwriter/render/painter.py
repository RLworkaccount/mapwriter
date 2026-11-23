"""Paint a Plan into finished battlemap images (one per lighting version)."""
from __future__ import annotations

import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from ..plan import Plan, Placed
from .canvas import Canvas, ac, alpha_crop, noise_texture, radial, seeded

FALLBACK_COLOURS = [  # words -> plain floor colour when no texture matches
    ({"grass", "lawn", "meadow"}, (92, 128, 64)),
    ({"water", "pond", "river", "lake"}, (62, 108, 140)),
    ({"dirt", "earth", "soil", "mud", "path"}, (122, 96, 66)),
    ({"sand"}, (196, 172, 120)),
    ({"marble"}, (214, 210, 204)),
    ({"wood", "plank", "wooden", "timber"}, (128, 88, 56)),
    ({"cobble", "cobblestone", "cobbles"}, (112, 108, 102)),
    ({"stone", "flagstone", "tile", "slate"}, (120, 118, 116)),
    ({"carpet", "rug"}, (128, 52, 52)),
]


def _fallback_colour(want: str | None):
    ws = set((want or "").lower().replace(",", " ").split())
    for words, col in FALLBACK_COLOURS:
        if ws & words:
            return col
    return (110, 106, 100)


class Painter:
    def __init__(self, plan: Plan, wall_thickness: float = 0.3):
        self.plan = plan
        sc = plan.scene
        self.cv = Canvas(sc.width, sc.height, sc.px_per_square)
        self.t = max(4, int(wall_thickness * sc.px_per_square))
        self.rnd = random.Random(sc.seed)

    # ------------------------------------------------------------ floors
    def floors(self):
        cv = self.cv
        for f in self.plan.floors:
            if f.asset is not None:
                tex = cv.load(f.asset)
                if f.asset.kind != "floor":
                    tex = alpha_crop(tex)
            else:
                tex = noise_texture((cv.R * 2, cv.R * 2), _fallback_colour(f.want), seed=seeded(f.name))
            m = cv.poly_mask(f.poly, feather=f.soft)
            cv.fill(tex, m)
            if f.is_room:
                # soft darkening into the corners of each room
                edge = cv.poly_mask(f.poly)
                ring = ImageChops.invert(edge).filter(ImageFilter.GaussianBlur(cv.R * 0.22))
                ring = ImageChops.multiply(ring, edge).point(lambda v: int(min(255, v * 1.6) * 0.5))
                l = Image.new("RGBA", cv.img.size, (18, 14, 20, 0)); l.putalpha(ring)
                cv.overlay(l)

    # ------------------------------------------------------------ props
    def _prop_image(self, p: Placed) -> Image.Image | None:
        cv = self.cv
        x0, y0, x1, y1 = p.box
        bw, bh = (x1 - x0) * cv.R, (y1 - y0) * cv.R
        a = p.asset
        if a is None:
            return None
        if a.kind == "floor":                       # a texture used as a rug
            tex = cv.load(a)
            im = cv.tile(tex, (0, 0, int(bw), int(bh)))
            m = Image.new("L", im.size, 0)
            r = int(min(bw, bh) * 0.08)
            ImageDraw.Draw(m).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=r, fill=255)
            im.putalpha(m)
            d = ImageDraw.Draw(im)
            d.rounded_rectangle([2, 2, im.width - 3, im.height - 3], radius=r, outline=(50, 40, 40, 200), width=max(2, int(cv.R * 0.05)))
            return im
        im = cv.raw(a)
        rot = (p.rot + p.fit_rot) % 360
        if p.flip:
            from PIL import ImageOps
            im = ImageOps.mirror(im)
        if rot:
            im = im.rotate(-rot, expand=True, resample=Image.BICUBIC)
        # Scale so the asset's own footprint matches the box it was given.
        if a.footprint:
            fw, fh = a.footprint
            if int(round(rot)) % 180 == 90:
                fw, fh = fh, fw
            if rot % 90:
                k = cv.R / a.ppsq * p.scale
                k *= min(bw / (fw * cv.R), bh / (fh * cv.R))
            else:
                k = min(bw / (fw * a.ppsq), bh / (fh * a.ppsq)) * p.scale
        else:
            k = min(bw / im.width, bh / im.height) * p.scale
        return im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)

    def props(self, layers):
        cv = self.cv
        for p in sorted(self.plan.props, key=lambda p: p.layer):
            if p.layer not in layers:
                continue
            im = self._prop_image(p)
            cx, cy = p.centre
            if im is None:
                continue        # missing art is only shown on the sketch
            cv.put(im, cx, cy, shadow=p.shadow and p.layer > 0, op=0.5 if p.layer > 0 else 0.3)

    # ------------------------------------------------------------ walls
    def _wall_strip(self):
        a = self.plan.wall_asset
        if a is None:
            return None
        im = alpha_crop(self.cv.raw(a))
        if im.height > im.width:
            im = im.rotate(90, expand=True)
        self._wall_band = im.height
        k = self.t / im.height
        return im.resize((max(1, round(im.width * k)), self.t), Image.LANCZOS)

    def _plain_strip(self, length):
        t = self.t
        s = Image.new("RGBA", (length, t), (86, 82, 80, 255))
        d = ImageDraw.Draw(s)
        rnd = random.Random(length)
        x = 0
        while x < length:
            w = rnd.randint(int(t * 0.9), int(t * 1.8))
            c = rnd.randint(-10, 10)
            d.rectangle([x, 1, x + w - 2, t - 2], fill=(98 + c, 94 + c, 90 + c, 255))
            x += w
        d.rectangle([0, 0, length - 1, t - 1], outline=(40, 38, 40, 255), width=max(1, t // 10))
        return s

    def walls(self):
        cv = self.cv
        t = self.t
        strip = self._wall_strip()
        layer = Image.new("RGBA", cv.img.size, (0, 0, 0, 0))
        for i, (x0, y0, x1, y1) in enumerate(self.plan.walls):
            X0, Y0 = cv.P(x0, y0); X1, Y1 = cv.P(x1, y1)
            L = abs(X1 - X0) + abs(Y1 - Y0) + t
            if strip is not None:
                s = Image.new("RGBA", (L, t))
                xx = -random.Random(i).randrange(0, max(1, strip.width - 10))
                while xx < L:
                    ac(s, strip, (xx, 0)); xx += strip.width
            else:
                s = self._plain_strip(L)
            if Y0 == Y1:
                ac(layer, s, (min(X0, X1) - t // 2, Y0 - t // 2))
            else:
                ac(layer, s.rotate(90, expand=True), (X0 - t // 2, min(Y0, Y1) - t // 2))
        if strip is not None:
            # Joint pieces share the strip's band thickness; scale them the same way.
            k = t / self._wall_band
            for x, y, asset, turns in self.plan.wall_joints:
                im = self.cv.raw(asset)
                im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
                if turns:
                    im = im.rotate(-90 * turns, expand=True)
                X, Y = cv.P(x, y)
                ac(layer, im, (X - im.width // 2, Y - im.height // 2))
        a = layer.getchannel("A")
        ao = a.filter(ImageFilter.GaussianBlur(cv.R * 0.22)).point(lambda v: int(min(255, v * 1.4) * 0.55))
        aol = Image.new("RGBA", cv.img.size, (15, 12, 20, 0)); aol.putalpha(ao)
        cv.overlay(aol)
        cv.overlay(layer)

    def openings(self):
        cv = self.cv
        t = self.t
        for o, asset in self.plan.openings:
            X0, Y0 = cv.P(*o.a); X1, Y1 = cv.P(*o.b)
            L = abs(X1 - X0) + abs(Y1 - Y0)
            if o.kind == "arch":
                im = Image.new("RGBA", (L + t, t), (0, 0, 0, 0))
                d = ImageDraw.Draw(im)
                d.rectangle([t // 2, t // 4, L + t // 2, t - t // 4], fill=(110, 104, 96, 80))
                for cx in (0, L):
                    d.rectangle([cx, 0, cx + t, t - 1], fill=(84, 80, 84, 255), outline=(40, 38, 44, 255), width=2)
            elif o.kind == "secret":
                continue              # drawn as plain wall; the export still has the door
            else:
                if asset is not None:
                    im = alpha_crop(cv.raw(asset))
                    if im.height > im.width:
                        im = im.rotate(90, expand=True)
                    th = max(int(t * (1.0 if o.kind == "window" else 0.8)), int(im.height * (L + t // 2) / im.width))
                    th = min(th, int(t * 1.6))
                    im = im.resize((L + t // 2, th), Image.LANCZOS)
                else:
                    th = int(t * (0.9 if o.kind == "window" else 0.7))
                    im = Image.new("RGBA", (L + t // 2, th), (0, 0, 0, 0))
                    d = ImageDraw.Draw(im)
                    if o.kind == "window":
                        d.rectangle([0, 0, im.width - 1, th - 1], fill=(170, 200, 220, 230), outline=(60, 50, 44, 255), width=max(2, th // 5))
                    else:
                        d.rectangle([0, 0, im.width - 1, th - 1], fill=(120, 80, 48, 255), outline=(52, 34, 22, 255), width=max(2, th // 6))
                        n = max(2, L // max(1, int(cv.R * 0.25)))
                        for k in range(1, n):
                            x = k * im.width // n
                            d.line([x, 2, x, th - 3], fill=(84, 56, 34, 255), width=2)
            if o.open and o.kind in ("door", "double"):
                self._open_door(o, im)
                continue
            if not o.horizontal:
                im = im.rotate(90, expand=True)
            cx, cy = (X0 + X1) // 2, (Y0 + Y1) // 2
            pos = (cx - im.width // 2, cy - im.height // 2)
            if o.kind in ("door", "double"):
                cv.shadow(im, pos, op=0.55)
            ac(cv.img, im, pos)

    def _open_door(self, o, im: Image.Image):
        """Draw a door swung open: each leaf turned square to the wall at its hinge,
        on the side where a room is (inside, for an outside door)."""
        cv, sc = self.cv, self.plan.scene
        (ax, ay), (bx, by) = sorted([o.a, o.b])
        mx, my = (ax + bx) / 2, (ay + by) / 2
        def inside(s):
            return sc.room_at(mx + (0 if o.horizontal else 0.5 * s), my + (0.5 * s if o.horizontal else 0)) is not None
        side = 1 if inside(1) or not inside(-1) else -1
        hinges = [((ax, ay), 1)] if o.kind == "door" else [((ax, ay), 1), ((bx, by), -1)]
        span = (bx - ax) + (by - ay)
        leaf_len = max(2, int(cv.R * span / len(hinges)))
        th = im.height
        leaf = im.resize((leaf_len, th), Image.LANCZOS).rotate(90, expand=True)   # now th wide, leaf_len tall
        for (hx, hy), along in hinges:
            HX, HY = cv.P(hx, hy)
            if o.horizontal:
                x = HX if along > 0 else HX - th
                y = HY if side > 0 else HY - leaf_len
                piece = leaf
            else:
                piece = leaf.rotate(90, expand=True)                                # leaf_len wide, th tall
                y = HY if along > 0 else HY - th
                x = HX if side > 0 else HX - leaf_len
            cv.shadow(piece, (x, y), op=0.55)
            ac(cv.img, piece, (x, y))

    # ------------------------------------------------------------ lighting
    def lit(self, base: Image.Image, version: str) -> Image.Image:
        sc = self.plan.scene
        cv = self.cv
        ambient = sc.ambient.get(version, (200, 200, 200))
        strength = 0.35 if version == "day" else 1.0
        glow = 0.08 if version == "day" else 0.22
        lm = Image.new("RGB", base.size, ambient)
        add = Image.new("RGB", base.size, (0, 0, 0))
        masks = {}
        areas = self.plan.light_areas or [None] * len(self.plan.lights)
        for L, area in zip(self.plan.lights, areas):
            if L.when not in ("both", version):
                continue
            rr = max(2, int(L.radius * cv.R))
            spr = radial(rr, L.colour, L.intensity * strength)
            x, y = cv.P(*L.at)
            if area:
                # Shadow mask, drawn on the sprite's own small square: walls and closed
                # doors cast shadows; open doors, arches and windows let light through.
                n = spr.width
                m = Image.new("L", (n, n), 0)
                pts = [(px - (x - rr), py - (y - rr)) for px, py in cv.poly_px(area)]
                d = ImageDraw.Draw(m)
                d.polygon(pts, fill=255)
                d.line(pts + [pts[0]], fill=255, width=max(1, int(0.24 * cv.R)), joint="curve")
                m = m.filter(ImageFilter.GaussianBlur(0.08 * cv.R))
                spr = ImageChops.multiply(spr, Image.merge("RGB", [m] * 3))
            piece = Image.new("RGB", base.size, (0, 0, 0))
            piece.paste(spr, (x - rr, y - rr))
            if L.room:                     # set in the scene file: keep this light in one room
                if L.room not in masks:
                    room = sc.room(L.room)
                    masks[L.room] = cv.poly_mask(room.poly, grow=0.15, feather=0.08)
                piece = ImageChops.multiply(piece, Image.merge("RGB", [masks[L.room]] * 3))
            add = ImageChops.add(add, piece)
        lm = ImageChops.add(lm, add)
        out = ImageChops.multiply(base.convert("RGB"), lm)
        return ImageChops.add(out, add.point(lambda v: int(v * glow)))

    # ------------------------------------------------------------ all
    def paint(self) -> dict[str, Image.Image]:
        self.floors()
        self.props({0})
        self.props({1})
        self.walls()
        self.openings()
        self.props({2, 3, 4, 5})
        base = self.cv.img
        return {v: self.lit(base, v) for v in self.plan.scene.versions}
