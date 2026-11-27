"""A painting surface measured in grid squares, built on Pillow."""
from __future__ import annotations

import hashlib
import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from ..assets.index import Asset


def ac(dst: Image.Image, src: Image.Image, pos):
    """alpha_composite that tolerates negative or overhanging positions."""
    x, y = int(pos[0]), int(pos[1])
    cx0, cy0 = max(0, -x), max(0, -y)
    cx1, cy1 = min(src.width, dst.width - x), min(src.height, dst.height - y)
    if cx1 <= cx0 or cy1 <= cy0:
        return
    dst.alpha_composite(src.crop((cx0, cy0, cx1, cy1)), (x + cx0, y + cy0))


def tint(im: Image.Image, colour, amount=0.5):
    g = ImageOps.grayscale(im.convert("RGB"))
    col = ImageOps.colorize(g, (0, 0, 0), colour, mid=tuple(int(c * 0.6) for c in colour))
    out = Image.blend(im.convert("RGB"), col, amount)
    if im.mode == "RGBA":
        out = out.convert("RGBA"); out.putalpha(im.getchannel("A"))
    return out


def seeded(*parts) -> int:
    return int(hashlib.md5(":".join(map(str, parts)).encode()).hexdigest()[:8], 16)


class Canvas:
    def __init__(self, w: int, h: int, R: int, bg=(58, 56, 54)):
        self.w, self.h, self.R = w, h, R
        self.img = Image.new("RGBA", (w * R, h * R), bg + (255,))
        self._cache: dict = {}

    # ---------- coordinates ----------
    def P(self, x, y):
        return int(round(x * self.R)), int(round(y * self.R))

    def poly_px(self, poly):
        return [self.P(x, y) for x, y in poly]

    def mask(self):
        return Image.new("L", self.img.size, 0)

    def poly_mask(self, poly, feather=0.0, grow=0.0):
        m = self.mask()
        d = ImageDraw.Draw(m)
        pts = self.poly_px(poly)
        d.polygon(pts, fill=255)
        if grow:
            w = max(1, int(2 * grow * self.R))
            d.line(pts + [pts[0]], fill=255, width=w, joint="curve")
        if feather:
            m = m.filter(ImageFilter.GaussianBlur(feather * self.R))
        return m

    def region_mask(self, region, feather=0.0):
        """Mask for a plan Region: an outline, or a strip drawn as overlapping discs."""
        if region.poly is not None:
            return self.poly_mask(region.poly, feather=feather)
        m = self.mask()
        d = ImageDraw.Draw(m)
        for (x, y), r in zip(region.line, region.radii):
            X, Y = self.P(x, y); rr = r * self.R
            d.ellipse([X - rr, Y - rr, X + rr, Y + rr], fill=255)
        if feather:
            m = m.filter(ImageFilter.GaussianBlur(feather * self.R))
        return m

    def rect_mask(self, x0, y0, x1, y1, radius=0.0):
        m = self.mask()
        ImageDraw.Draw(m).rounded_rectangle([*self.P(x0, y0), *self.P(x1, y1)], radius=int(radius * self.R), fill=255)
        return m

    # ---------- images ----------
    def load(self, asset: Asset, scale=1.0) -> Image.Image:
        """The asset's image, scaled from its own pixels-per-square to ours."""
        key = (asset.id, round(scale, 4))
        if key not in self._cache:
            im = Image.open(asset.path).convert("RGBA")
            k = self.R / asset.ppsq * scale
            im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
            self._cache[key] = im
        return self._cache[key]

    def raw(self, asset: Asset) -> Image.Image:
        key = ("raw", asset.id)
        if key not in self._cache:
            self._cache[key] = Image.open(asset.path).convert("RGBA")
        return self._cache[key]

    def graded(self, asset: Asset, grade) -> Image.Image:
        """The asset's image with colour strength and brightness moved towards the map's
        main style (see assets/style.py)."""
        key = ("graded", asset.id, tuple(grade))
        if key not in self._cache:
            from ..assets.style import apply_grade
            self._cache[key] = apply_grade(self.raw(asset), grade)
        return self._cache[key]

    def tile(self, tex: Image.Image, box_px) -> Image.Image:
        x0, y0, x1, y1 = box_px
        tw, th = tex.size
        out = Image.new("RGBA", (max(1, x1 - x0), max(1, y1 - y0)))
        sx = (x0 // tw) * tw - x0
        sy = (y0 // th) * th - y0
        for yy in range(sy, y1 - y0, th):
            for xx in range(sx, x1 - x0, tw):
                out.paste(tex, (xx, yy))
        return out

    def fill(self, tex: Image.Image, mask: Image.Image):
        bb = mask.getbbox()
        if not bb:
            return
        reg = self.tile(tex, bb)
        layer = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        layer.paste(reg, bb[:2])
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
        self.img = Image.alpha_composite(self.img, layer)

    def overlay(self, layer: Image.Image):
        self.img = Image.alpha_composite(self.img, layer)

    def shadow(self, im: Image.Image, pos, op=0.5, off=None, blur=None):
        off = off if off is not None else max(2, int(self.R * 0.05))
        blur = blur or max(2, int(self.R * 0.05))
        pad = blur * 3 + off
        sh = Image.new("L", (im.width + 2 * pad, im.height + 2 * pad), 0)
        sh.paste(im.getchannel("A"), (pad, pad))
        sh = sh.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * op))
        layer = Image.new("RGBA", sh.size, (12, 10, 18, 0)); layer.putalpha(sh)
        ac(self.img, layer, (pos[0] - pad + off, pos[1] - pad + off))

    def put(self, im: Image.Image, cx, cy, shadow=True, op=0.5):
        x, y = self.P(cx, cy)
        pos = (x - im.width // 2, y - im.height // 2)
        if shadow:
            self.shadow(im, pos, op=op)
        ac(self.img, im, pos)


def alpha_crop(im: Image.Image, threshold=8) -> Image.Image:
    a = im.getchannel("A").point(lambda v: 255 if v > threshold else 0)
    bb = a.getbbox()
    return im.crop(bb) if bb else im


def radial(r: int, col, inten: float) -> Image.Image:
    n = max(2, 2 * r)
    g = Image.radial_gradient("L")              # 0 at the centre, about 181 at the edge midpoints
    edge = g.getpixel((g.width // 2, 0)) or 181
    m = g.resize((n, n)).point(lambda v: int(255 * max(0.0, 1 - v / edge) ** 1.8 * inten))
    return Image.merge("RGB", [m.point(lambda v, c=c: int(v * c / 255)) for c in col])


def noise_texture(size, base, var=18, seed=0, grain=3):
    """A quiet mottled texture for floors with no art."""
    w, h = size
    n = Image.effect_noise((max(1, w // grain), max(1, h // grain)), 64).resize((w, h), Image.BICUBIC)
    n = n.filter(ImageFilter.GaussianBlur(1))
    out = Image.new("RGB", (w, h), base)
    shade = n.point(lambda v: int((v - 128) / 128 * var + 128))
    out = ImageChops.add(ImageChops.subtract(out, Image.merge("RGB", [shade.point(lambda v: max(0, 128 - v))] * 3)),
                         Image.merge("RGB", [shade.point(lambda v: max(0, v - 128))] * 3))
    return out.convert("RGBA")
