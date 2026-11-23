"""High-level steps used by the command line and by other programs."""
from __future__ import annotations

from pathlib import Path

from .assets.index import Index
from .export import check_overlay, gm_key, write_dd2vtt
from .plan import build as build_plan, Plan
from .render.painter import Painter
from .render.sketch import sketch
from .scene import load as load_scene


def load_index(paths, tags=None) -> Index:
    idx = Index.load(*paths)
    for t in tags or []:
        idx.apply_tags(t)
    return idx


def plan_for(scene_path, index: Index) -> Plan:
    return build_plan(load_scene(scene_path), index)


def slug(name: str) -> str:
    s = "".join(c.lower() if c.isalnum() else "-" for c in name)
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-") or "map"


def write_sketch(plan: Plan, out_dir, px=48) -> Path:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    p = out / f"{slug(plan.scene.name)}-sketch.png"
    sketch(plan, px).save(p)
    return p


def render_all(plan: Plan, out_dir, image_format="webp", quality=88, uvtt=True) -> dict:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    name = slug(plan.scene.name)
    images = Painter(plan).paint()
    written = {}
    for version, im in images.items():
        p = out / f"{name}-{version}.{image_format}"
        if image_format == "webp":
            im.save(p, "WEBP", quality=quality, method=4)
        elif image_format == "png":
            im.save(p)
        else:
            im.save(p, "JPEG", quality=quality)
        written[f"{version} image"] = p
        if uvtt:
            q = out / f"{name}-{version}.dd2vtt"
            counts = write_dd2vtt(plan, im, q)
            written[f"{version} foundry"] = q
            written["counts"] = counts
    first = images[plan.scene.versions[0]]
    k = out / f"{name}-key.jpg"; gm_key(plan, first).save(k, quality=88); written["key"] = k
    c = out / f"{name}-check.jpg"; check_overlay(plan, first).save(c, quality=85); written["check"] = c
    return written
