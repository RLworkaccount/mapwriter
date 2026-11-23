"""Wall maths: merge wall lines, cut openings, check reachability."""
from __future__ import annotations

import math
from collections import deque

EPS = 1e-6


def _union(iv):
    iv = sorted(iv)
    out = []
    for a, b in iv:
        if out and a <= out[-1][1] + EPS:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _cut(iv, gaps):
    for g0, g1 in gaps:
        nv = []
        for a, b in iv:
            if g1 <= a + EPS or g0 >= b - EPS:
                nv.append((a, b))
            else:
                if g0 > a + EPS:
                    nv.append((a, g0))
                if g1 < b - EPS:
                    nv.append((g1, b))
        iv = nv
    return iv


def merge_walls(segments, openings=()):
    """Union collinear axis-aligned wall segments, then cut gaps for openings.

    segments: iterable of (x0, y0, x1, y1). openings: objects with .a and .b.
    Returns a list of (x0, y0, x1, y1).
    """
    H, V = {}, {}
    for x0, y0, x1, y1 in segments:
        if abs(y0 - y1) < EPS:
            H.setdefault(round(y0, 4), []).append((min(x0, x1), max(x0, x1)))
        elif abs(x0 - x1) < EPS:
            V.setdefault(round(x0, 4), []).append((min(y0, y1), max(y0, y1)))
    out = []
    for y, iv in H.items():
        gaps = [(min(o.a[0], o.b[0]), max(o.a[0], o.b[0])) for o in openings
                if abs(o.a[1] - y) < EPS and abs(o.b[1] - y) < EPS]
        out += [(a, y, b, y) for a, b in _cut(_union(iv), gaps)]
    for x, iv in V.items():
        gaps = [(min(o.a[1], o.b[1]), max(o.a[1], o.b[1])) for o in openings
                if abs(o.a[0] - x) < EPS and abs(o.b[0] - x) < EPS]
        out += [(x, a, x, b) for a, b in _cut(_union(iv), gaps)]
    return out


def on_wall(opening, segments) -> bool:
    """True if the opening lies along some (unmerged) wall segment."""
    (ax, ay), (bx, by) = opening.a, opening.b
    for x0, y0, x1, y1 in segments:
        if abs(ay - by) < EPS and abs(y0 - y1) < EPS and abs(y0 - ay) < EPS:
            if min(ax, bx) >= min(x0, x1) - EPS and max(ax, bx) <= max(x0, x1) + EPS:
                return True
        if abs(ax - bx) < EPS and abs(x0 - x1) < EPS and abs(x0 - ax) < EPS:
            if min(ay, by) >= min(y0, y1) - EPS and max(ay, by) <= max(y0, y1) + EPS:
                return True
    return False


def blocked_edges(walls):
    """Set of unit grid edges covered by walls: ('h', x, y) is the edge from (x,y) to (x+1,y)."""
    out = set()
    for x0, y0, x1, y1 in walls:
        if abs(y0 - y1) < EPS:
            a, b = sorted((x0, x1))
            # cover every unit edge the wall overlaps by more than half
            for xi in range(int(a // 1), int(-(-b // 1))):
                if min(b, xi + 1) - max(a, xi) > 0.5:
                    out.add(("h", xi, round(y0)))
        else:
            a, b = sorted((y0, y1))
            for yi in range(int(a // 1), int(-(-b // 1))):
                if min(b, yi + 1) - max(a, yi) > 0.5:
                    out.add(("v", round(x0), yi))
    return out


def reachable(width, height, walls, start):
    """Flood fill squares from start (sx, sy) without crossing walls."""
    block = blocked_edges(walls)
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy, edge in ((1, 0, ("v", x + 1, y)), (-1, 0, ("v", x, y)),
                             (0, 1, ("h", x, y + 1)), (0, -1, ("h", x, y))):
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in seen and edge not in block:
                seen.add((nx, ny))
                q.append((nx, ny))
    return seen


def _ray_hit(ox, oy, dx, dy, seg):
    """Distance along the ray (ox, oy) + t (dx, dy) to the segment, or None."""
    x0, y0, x1, y1 = seg
    ex, ey = x1 - x0, y1 - y0
    den = dx * ey - dy * ex
    if abs(den) < 1e-12:
        return None
    t = ((x0 - ox) * ey - (y0 - oy) * ex) / den
    u = ((x0 - ox) * dy - (y0 - oy) * dx) / den
    if t > 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return t
    return None


def light_area(origin, blockers, radius, steps=96):
    """The part of a circle of ``radius`` round ``origin`` that light reaches.

    ``blockers`` are wall lines (x0, y0, x1, y1) that stop light. Rays are cast at
    even angles and just either side of every nearby wall end, so shadow edges are
    sharp. Returns a polygon as a list of (x, y) points in grid squares.
    """
    ox, oy = origin
    near = [s for s in blockers
            if min(s[0], s[2]) - radius <= ox <= max(s[0], s[2]) + radius
            and min(s[1], s[3]) - radius <= oy <= max(s[1], s[3]) + radius]
    angles = [2 * math.pi * i / steps for i in range(steps)]
    for x0, y0, x1, y1 in near:
        for x, y in ((x0, y0), (x1, y1)):
            if math.hypot(x - ox, y - oy) <= radius + 1e-6:
                a = math.atan2(y - oy, x - ox)
                angles += [a - 1e-4, a, a + 1e-4]
    pts = []
    for a in sorted(x % (2 * math.pi) for x in angles):
        dx, dy = math.cos(a), math.sin(a)
        t = radius
        for seg in near:
            h = _ray_hit(ox, oy, dx, dy, seg)
            if h is not None and h < t:
                t = h
        pts.append((ox + dx * t, oy + dy * t))
    return pts


def distance_to_segment(px, py, seg) -> float:
    x0, y0, x1, y1 = seg
    ex, ey = x1 - x0, y1 - y0
    L = ex * ex + ey * ey
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - x0) * ex + (py - y0) * ey) / L))
    return math.hypot(px - (x0 + t * ex), py - (y0 + t * ey))
