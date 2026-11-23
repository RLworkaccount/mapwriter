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


# Directions as (dx, dy); clockwise order starting east (y runs down).
DIRS = {"E": (1, 0), "S": (0, 1), "W": (-1, 0), "N": (0, -1)}
CW = "ESWN"


def wall_junctions(walls):
    """Find where axis-aligned walls meet. Returns {(x, y): set of arm directions},
    for points with two or more arms that are not a straight run."""
    arms: dict[tuple[float, float], set[str]] = {}
    ends = set()
    for x0, y0, x1, y1 in walls:
        ends.add((round(x0, 4), round(y0, 4))); ends.add((round(x1, 4), round(y1, 4)))
    for x0, y0, x1, y1 in walls:
        horiz = abs(y0 - y1) < EPS
        lo, hi = ((x0, y0), (x1, y1)) if (x0, y0) <= (x1, y1) else ((x1, y1), (x0, y0))
        for v in ends:
            if horiz and abs(v[1] - lo[1]) < EPS and lo[0] - EPS <= v[0] <= hi[0] + EPS:
                pos, a, b = v[0], lo[0], hi[0]
                fwd, back = "E", "W"
            elif not horiz and abs(v[0] - lo[0]) < EPS and lo[1] - EPS <= v[1] <= hi[1] + EPS:
                pos, a, b = v[1], lo[1], hi[1]
                fwd, back = "S", "N"
            else:
                continue
            s = arms.setdefault(v, set())
            if pos < b - EPS:
                s.add(fwd)
            if pos > a + EPS:
                s.add(back)
    return {v: a for v, a in arms.items() if len(a) >= 2 and a not in ({"E", "W"}, {"N", "S"})}


def joint_shape(arms: set[str]):
    """Name the joint piece and its clockwise turns (0-3) for a set of arms.

    Base pieces: corner has arms E and S, tee has W, E and S, cross has all four.
    """
    if len(arms) == 4:
        return "cross", 0
    base = {"corner": {"E", "S"}, "tee": {"W", "E", "S"}}["corner" if len(arms) == 2 else "tee"]
    kind = "corner" if len(arms) == 2 else "tee"
    for k in range(4):
        if {CW[(CW.index(d) + k) % 4] for d in base} == arms:
            return kind, k
    return None, 0
