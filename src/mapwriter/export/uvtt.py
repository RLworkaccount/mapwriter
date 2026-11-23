"""Universal VTT (.dd2vtt) export, read by Foundry's Universal Battlemap Importer.

Walls become line_of_sight polylines, doors become closed portals and windows
become open portals (light and sight pass through). All units are grid squares.
"""
from __future__ import annotations

import base64
import io
import json
import math

from PIL import Image

from ..geometry import merge_walls
from ..plan import Plan


def _resample(x0, y0, x1, y1, step=0.5):
    # The importer drops points closer than about 0.3 squares, so keep them spaced.
    n = max(1, int(math.ceil(math.hypot(x1 - x0, y1 - y0) / max(step, 0.4))))
    return [{"x": round(x0 + (x1 - x0) * i / n, 4), "y": round(y0 + (y1 - y0) * i / n, 4)} for i in range(n + 1)]


def uvtt_data(plan: Plan, image: Image.Image | None, fmt="webp", quality=88, step=2.0):
    sc = plan.scene
    # For sight, every opening is a gap; windows and doors come back as portals.
    segs = merge_walls(plan.raw_walls, [o for o, _ in plan.openings if o.kind != "secret"])
    los = [_resample(*s, step=step) for s in segs]
    portals = []
    for o, _ in plan.openings:
        if o.kind == "arch":
            continue
        (ax, ay), (bx, by) = o.a, o.b
        portals.append({"position": {"x": (ax + bx) / 2, "y": (ay + by) / 2},
                        "bounds": [{"x": ax, "y": ay}, {"x": bx, "y": by}],
                        "rotation": 0 if o.horizontal else math.pi / 2,
                        "closed": o.kind != "window", "freestanding": False})
    lights = [{"position": {"x": L.at[0], "y": L.at[1]}, "range": L.radius, "intensity": round(L.intensity, 2),
               "color": "ff%02x%02x%02x" % tuple(L.colour), "shadows": True} for L in plan.lights]
    data = {"format": 0.3,
            "resolution": {"map_origin": {"x": 0, "y": 0}, "map_size": {"x": sc.width, "y": sc.height},
                           "pixels_per_grid": sc.px_per_square},
            "line_of_sight": los, "objects_line_of_sight": [], "portals": portals,
            "environment": {"baked_lighting": True, "ambient_light": "ff%02x%02x%02x" % tuple(sc.ambient.get("night", (80, 86, 130)))},
            "lights": lights}
    if image is not None:
        buf = io.BytesIO()
        if fmt == "webp":
            image.convert("RGB").save(buf, "WEBP", quality=quality, method=4)
        elif fmt == "png":
            image.convert("RGB").save(buf, "PNG")
        else:
            image.convert("RGB").save(buf, "JPEG", quality=quality)
        data["image"] = base64.b64encode(buf.getvalue()).decode()
    return data


def write_dd2vtt(plan: Plan, image: Image.Image, path, fmt="webp", quality=88):
    data = uvtt_data(plan, image, fmt, quality)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return {"walls": len(data["line_of_sight"]), "portals": len(data["portals"]), "lights": len(data["lights"])}
