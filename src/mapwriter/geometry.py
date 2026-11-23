"""Wall maths: merge wall lines, cut openings, check reachability."""
from __future__ import annotations

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
