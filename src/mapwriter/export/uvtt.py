"""Universal VTT (.dd2vtt) export, read by Foundry's Universal Battlemap Importer.

Walls become line_of_sight polylines, doors become closed portals and windows
become open portals (light and sight pass through). All units are grid squares.

Notes from reading the importer's code (Universal Battlemap Importer 6.1, Foundry v14):
- It sets each light's colour strength to 0.05 x intensity, so an intensity of 0.8
  gives an almost invisible tint. We write intensity scaled up (LIGHT_SCALE) so the
  colour lands at about half our strength, close to Foundry's own default of 0.5.
- A portal becomes one door wall, so a double door is written as two portals that
  open on their own, as in Foundry.
- Secret doors are left as plain wall in the file. The format has no secret door,
  and a normal door would show players where it is. Make it a secret door in Foundry
  by hand (the check image marks it in purple).
- Windows come in as walls that block movement and let sight and light through
  only from close by (10 ft), unless "Openable Windows" is ticked in the importer's
  settings, which makes them doors.
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


LIGHT_SCALE = 10.0     # importer colour strength = 0.05 * intensity, so 10 x 0.8 -> 0.4


def _portal(a, b, closed):
    (ax, ay), (bx, by) = a, b
    return {"position": {"x": (ax + bx) / 2, "y": (ay + by) / 2},
            "bounds": [{"x": ax, "y": ay}, {"x": bx, "y": by}],
            "rotation": 0 if ay == by else math.pi / 2, "closed": closed, "freestanding": False}


def uvtt_data(plan: Plan, image: Image.Image | None, fmt="webp", quality=88, step=2.0, light_scale=LIGHT_SCALE,
              version: str | None = None):
    """version (day, night, sunset...) keeps only that version's lights and uses its ambient.
    Left out, every light is written with the night ambient."""
    sc = plan.scene
    # For sight, every opening is a gap; windows and doors come back as portals.
    gaps = [o for o, _ in plan.openings if o.kind != "secret"]
    glass = set(plan.see_through_walls)
    segs = merge_walls([w for w in plan.raw_walls if w not in glass], gaps)
    los = [_resample(*s, step=step) for s in segs]
    # Glass walls come in as windows: they stop movement but let sight and light through.
    portals = [_portal((x0, y0), (x1, y1), False) for x0, y0, x1, y1 in merge_walls(list(glass), gaps)]
    for o, _ in plan.openings:
        if o.kind in ("arch", "secret"):
            continue
        if o.kind == "double":
            (ax, ay), (bx, by) = o.a, o.b
            mid = ((ax + bx) / 2, (ay + by) / 2)
            portals += [_portal(o.a, mid, True), _portal(mid, o.b, True)]
        else:
            portals.append(_portal(o.a, o.b, o.kind != "window"))
    lights = [{"position": {"x": L.at[0], "y": L.at[1]}, "range": L.radius, "intensity": round(L.intensity * light_scale, 2),
               "color": "ff%02x%02x%02x" % tuple(L.colour), "shadows": True} for L in plan.lights
              if version is None or L.when in ("both", version)]
    ambient = sc.ambient.get(version or "night") or sc.ambient.get("night", (80, 86, 130))
    data = {"format": 0.3,
            "resolution": {"map_origin": {"x": 0, "y": 0}, "map_size": {"x": sc.width, "y": sc.height},
                           "pixels_per_grid": sc.px_per_square},
            "line_of_sight": los, "objects_line_of_sight": [], "portals": portals,
            "environment": {"baked_lighting": True, "ambient_light": "ff%02x%02x%02x" % tuple(ambient)},
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


def write_dd2vtt(plan: Plan, image: Image.Image, path, fmt="webp", quality=88, version: str | None = None):
    data = uvtt_data(plan, image, fmt, quality, version=version)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return {"walls": len(data["line_of_sight"]), "portals": len(data["portals"]), "lights": len(data["lights"])}
