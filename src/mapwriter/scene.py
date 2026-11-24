"""The scene file: a plain YAML description of a battlemap, in grid squares.

Coordinates: x runs right, y runs down, (0, 0) is the top-left corner of the map.
Walls, doors and windows sit on grid lines. ``at`` for a prop is the top-left
corner of the squares it covers.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SIDES = ("north", "south", "east", "west")

COLOURS = {
    "warm": (255, 196, 120), "candle": (255, 176, 96), "fire": (255, 140, 60),
    "lantern": (255, 200, 130), "cool": (180, 205, 255), "moon": (150, 170, 255),
    "white": (255, 250, 240), "magic": (195, 150, 255), "green": (150, 255, 170),
    "blue": (120, 170, 255), "red": (255, 90, 70), "gold": (255, 215, 120),
}


class SceneError(ValueError):
    pass


def colour(value, default=(255, 196, 120)):
    if value is None:
        return default
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return tuple(int(v) for v in value)
    s = str(value).strip().lower()
    if s in COLOURS:
        return COLOURS[s]
    if s.startswith("#") and len(s) == 7:
        return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))
    raise SceneError(f"Unknown colour '{value}'. Use a name ({', '.join(COLOURS)}), #rrggbb or [r, g, b].")


@dataclass
class Opening:
    a: tuple[float, float]
    b: tuple[float, float]
    kind: str = "door"            # door, double, arch, window, secret
    want: str | None = None       # e.g. "iron door"
    file: str | None = None
    open: bool = False

    @property
    def horizontal(self) -> bool:
        return self.a[1] == self.b[1]


@dataclass
class Room:
    name: str
    poly: list[tuple[float, float]]   # rectilinear outline, clockwise or not
    floor: str | None = None
    walls: str | None = "default"     # material word, or None for no walls
    label: str | None = None
    openings: list[Opening] = field(default_factory=list)
    light: bool = True                # whether lights inside are clipped to this room

    @property
    def box(self):
        xs = [p[0] for p in self.poly]; ys = [p[1] for p in self.poly]
        return min(xs), min(ys), max(xs), max(ys)

    def edges(self):
        n = len(self.poly)
        for i in range(n):
            yield self.poly[i], self.poly[(i + 1) % n]

    def contains(self, x: float, y: float) -> bool:
        """Point in polygon (even-odd), for points not on the outline."""
        inside = False
        n = len(self.poly)
        for i in range(n):
            (x0, y0), (x1, y1) = self.poly[i], self.poly[(i + 1) % n]
            if (y0 > y) != (y1 > y):
                xc = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                if x < xc:
                    inside = not inside
        return inside


@dataclass
class Area:
    name: str
    poly: list[tuple[float, float]]
    floor: str
    soft: float = 0.3      # edge feather, squares
    rough: float = 0.0     # how far the edge wanders in and out, squares
    smooth: bool = False   # round off the corners


@dataclass
class ScenePath:
    """A strip of floor along a line: a road, a track, a stream bed."""
    name: str
    points: list[tuple[float, float]]
    floor: str
    width: float = 2.0     # squares
    soft: float = 0.3
    rough: float = 0.25    # how much the width wanders, squares
    curve: bool = True     # smooth curve through the points, or straight legs


@dataclass
class Prop:
    want: str | None = None
    file: str | None = None
    at: tuple[float, float] | None = None
    centre: tuple[float, float] | None = None
    size: tuple[float, float] | None = None
    rot: float = 0.0              # degrees clockwise
    room: str | None = None       # "in": place somewhere inside this room
    along: str | None = None      # with room: north/south/east/west wall
    count: int = 1
    label: str | None = None
    light: object = None          # None = automatic, False = off, dict = custom
    scale: float = 1.0
    layer: int | None = None
    vary: bool = False
    shadow: bool = True
    flip: bool = False


@dataclass
class Water:
    """A pond or lake (an outline) or a river or stream (points along a line), with a bank."""
    name: str
    floor: str = "water"
    poly: list[tuple[float, float]] | None = None
    points: list[tuple[float, float]] | None = None
    width: float = 2.0
    rough: float = 0.3
    smooth: bool = True
    curve: bool = True
    bank: str | None = "mud"   # floor words for the bank, or None for no bank
    bank_width: float = 0.6
    soft: float = 0.15


@dataclass
class Scatter:
    """Many copies of something spread over a place: trees in a wood, rocks on a slope,
    a pile of crates in a store room."""
    want: str
    within: str = "map"            # an area, path, water or room name, or "map"
    count: int | None = None
    density: float | None = None   # items per square, used when count is not given
    cluster: float = 1.0           # average items per clump (1 = spread out evenly)
    spread: float = 1.5            # how far a clump reaches from its middle, squares
    gap: float = 0.1               # space kept between items, squares (negative lets them overlap)
    turn: str = "any"              # any, square (quarter turns) or none
    scale: tuple[float, float] = (0.9, 1.1)
    size: tuple[float, float] | None = None
    vary: bool = True              # different art for each copy, where the pack has it
    avoid: list[str] | None = None # extra names to keep off; "none" clears the defaults
    layer: int | None = None
    label: str | None = None


@dataclass
class Light:
    at: tuple[float, float]
    radius: float = 6.0
    colour: tuple[int, int, int] = (255, 196, 120)
    intensity: float = 0.8
    when: str = "both"            # both, day, night
    room: str | None = None       # clip to this room (auto when inside one)


@dataclass
class Note:
    at: tuple[float, float]
    text: str


@dataclass
class Scene:
    name: str
    width: int
    height: int
    px_per_square: int = 140
    seed: int = 1
    ground: str | None = "stone floor"
    wall_style: str = "stone wall"
    door_style: str = "wood door"
    window_style: str = "wood window"
    rooms: list[Room] = field(default_factory=list)
    areas: list[Area] = field(default_factory=list)
    paths: list[ScenePath] = field(default_factory=list)
    water: list[Water] = field(default_factory=list)
    scatter: list[Scatter] = field(default_factory=list)
    walls: list[tuple[float, float, float, float]] = field(default_factory=list)
    openings: list[Opening] = field(default_factory=list)
    props: list[Prop] = field(default_factory=list)
    lights: list[Light] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    versions: list[str] = field(default_factory=lambda: ["day", "night"])
    ambient: dict = field(default_factory=lambda: {"day": (246, 240, 228), "night": (74, 82, 128)})
    source: str | None = None

    def room(self, name: str) -> Room:
        for r in self.rooms:
            if r.name.lower() == str(name).lower():
                return r
        raise SceneError(f"No room called '{name}'. Rooms are: {', '.join(r.name for r in self.rooms) or 'none'}.")

    def room_at(self, x: float, y: float) -> Room | None:
        for r in self.rooms:
            if r.contains(x, y):
                return r
        return None


# ---------------------------------------------------------------- parsing
def _pt(v, what):
    if not (isinstance(v, (list, tuple)) and len(v) == 2):
        raise SceneError(f"{what} should be [x, y], got {v!r}")
    return float(v[0]), float(v[1])


def _circle(c, what, steps=48):
    if isinstance(c, dict):
        (cx, cy), r = _pt(c.get("centre", c.get("center")), what), c.get("radius")
    elif isinstance(c, (list, tuple)) and len(c) == 3:
        cx, cy, r = c
    else:
        raise SceneError(f"{what}: circle should be [x, y, radius] or {{centre: [x, y], radius: r}}, got {c!r}")
    try:
        cx, cy, r = float(cx), float(cy), float(r)
    except (TypeError, ValueError):
        raise SceneError(f"{what}: circle needs numbers, got {c!r}")
    if r <= 0:
        raise SceneError(f"{what}: circle radius must be more than 0")
    return [(cx + r * math.cos(2 * math.pi * i / steps), cy + r * math.sin(2 * math.pi * i / steps)) for i in range(steps)]


def _poly(d, what, any_angle=False):
    if any_angle and "circle" in d:
        return _circle(d["circle"], what)
    if "box" in d:
        b = d["box"]
        if not (isinstance(b, (list, tuple)) and len(b) == 4):
            raise SceneError(f"{what}: box should be [x0, y0, x1, y1], got {b!r}")
        x0, y0, x1, y1 = map(float, b)
        if x1 <= x0 or y1 <= y0:
            raise SceneError(f"{what}: box {b} has no size (x1 must be > x0 and y1 > y0)")
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if "shape" in d:
        pts = [_pt(p, what) for p in d["shape"]]
        if len(pts) < 3:
            raise SceneError(f"{what}: shape needs at least 3 points")
        for i in range(len(pts) if not any_angle else 0):
            (ax, ay), (bx, by) = pts[i], pts[(i + 1) % len(pts)]
            if ax != bx and ay != by:
                raise SceneError(f"{what}: shape edges must be straight across or down; {pts[i]} to {pts[(i + 1) % len(pts)]} is diagonal")
        return pts
    extra = ", a circle [x, y, radius]" if any_angle else ""
    raise SceneError(f"{what} needs a box [x0, y0, x1, y1]{extra} or a shape [[x, y], ...]")


def _side_opening(room_poly, spec, kind, what):
    """Opening given as {wall: south, at: 6, width: 1} on a box room."""
    xs = [p[0] for p in room_poly]; ys = [p[1] for p in room_poly]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    side = str(spec["wall"]).lower()
    if side not in SIDES:
        raise SceneError(f"{what}: wall should be one of {', '.join(SIDES)}, got '{side}'")
    width = float(spec.get("width", 2 if kind == "double" else 1))
    ats = spec.get("at")
    if ats is None:
        mid = (x0 + x1) / 2 if side in ("north", "south") else (y0 + y1) / 2
        ats = [mid - width / 2]
    if not isinstance(ats, list):
        ats = [ats]
    out = []
    for at in ats:
        at = float(at)
        if side == "north":
            a, b = (at, y0), (at + width, y0)
        elif side == "south":
            a, b = (at, y1), (at + width, y1)
        elif side == "west":
            a, b = (x0, at), (x0, at + width)
        else:
            a, b = (x1, at), (x1, at + width)
        lo, hi = (x0, x1) if side in ("north", "south") else (y0, y1)
        if at < lo or at + width > hi:
            raise SceneError(f"{what}: {kind} at {at} (width {width}) does not fit on the {side} wall, which runs {lo} to {hi}")
        out.append(Opening(a, b, kind, spec.get("want"), spec.get("file"), bool(spec.get("open", False))))
    return out


def _free_opening(spec, kind, what):
    a = _pt(spec["from"], what); b = _pt(spec["to"], what)
    if a[0] != b[0] and a[1] != b[1]:
        raise SceneError(f"{what}: openings must be straight across or down")
    return Opening(a, b, kind, spec.get("want"), spec.get("file"), bool(spec.get("open", False)))


def parse(data: dict, source: str | None = None) -> Scene:
    if not isinstance(data, dict):
        raise SceneError("The scene file should be a YAML mapping (name:, grid:, rooms: ...)")
    grid = data.get("grid") or {}
    try:
        w, h = int(grid["width"]), int(grid["height"])
    except (KeyError, TypeError, ValueError):
        raise SceneError("grid: needs width and height in squares, e.g. grid: { width: 20, height: 14 }")
    style = data.get("style") or {}
    sc = Scene(name=str(data.get("name", "Untitled map")), width=w, height=h,
               px_per_square=int(grid.get("px_per_square", 140)), seed=int(data.get("seed", 1)),
               ground=data.get("ground", "stone floor"),
               wall_style=style.get("walls", "stone wall"), door_style=style.get("doors", "wood door"),
               window_style=style.get("windows", "wood window"), source=source)

    for i, a in enumerate(data.get("areas") or []):
        what = f"areas[{i}] ({a.get('name', '?')})"
        if "floor" not in a:
            raise SceneError(f"{what} needs a floor")
        sc.areas.append(Area(str(a.get("name", f"area {i + 1}")), _poly(a, what, any_angle=True), str(a["floor"]),
                             float(a.get("soft", 0.3)), float(a.get("rough", 0.0)), bool(a.get("smooth", False))))

    for i, p in enumerate(data.get("paths") or []):
        what = f"paths[{i}] ({p.get('name', '?') if isinstance(p, dict) else '?'})"
        if not isinstance(p, dict) or "floor" not in p:
            raise SceneError(f"{what} needs a floor, e.g. floor: dirt path")
        pts = [_pt(q, what) for q in (p.get("points") or [])]
        if len(pts) < 2:
            raise SceneError(f"{what} needs points: [[x, y], [x, y], ...] with at least two points")
        width = float(p.get("width", 2))
        if width <= 0:
            raise SceneError(f"{what}: width must be more than 0")
        sc.paths.append(ScenePath(str(p.get("name", f"path {i + 1}")), pts, str(p["floor"]), width,
                             float(p.get("soft", 0.3)), float(p.get("rough", 0.25)), bool(p.get("curve", True))))

    for i, wt in enumerate(data.get("water") or []):
        what = f"water[{i}] ({wt.get('name', '?') if isinstance(wt, dict) else '?'})"
        if not isinstance(wt, dict):
            raise SceneError(f"{what}: give a pond as circle/box/shape, or a river as points: [[x, y], ...]")
        bank = wt.get("bank", {})
        if bank in (False, None, "none", "no"):
            bank_floor, bank_w = None, 0.0
        elif isinstance(bank, dict):
            bank_floor, bank_w = str(bank.get("floor", "mud")), float(bank.get("width", 0.6))
        else:
            bank_floor, bank_w = str(bank), 0.6
        w = Water(str(wt.get("name", f"water {i + 1}")), str(wt.get("floor", "water")),
                  rough=float(wt.get("rough", 0.3)), smooth=bool(wt.get("smooth", True)),
                  curve=bool(wt.get("curve", True)), bank=bank_floor, bank_width=bank_w,
                  soft=float(wt.get("soft", 0.15)))
        if "points" in wt:
            w.points = [_pt(q, what) for q in wt["points"] or []]
            if len(w.points) < 2:
                raise SceneError(f"{what} needs points: [[x, y], [x, y], ...] with at least two points")
            w.width = float(wt.get("width", 2))
            if w.width <= 0:
                raise SceneError(f"{what}: width must be more than 0")
        else:
            w.poly = _poly(wt, what, any_angle=True)
        sc.water.append(w)

    for i, r in enumerate(data.get("rooms") or []):
        what = f"rooms[{i}] ({r.get('name', '?')})"
        poly = _poly(r, what)
        walls = r.get("walls", "default")
        if walls in (False, "none", "no", None):
            walls = None
        room = Room(str(r.get("name", f"room {i + 1}")), poly, r.get("floor"), walls, r.get("label"))
        for key, kind in (("doors", "door"), ("windows", "window"), ("arches", "arch")):
            for j, o in enumerate(r.get(key) or []):
                w2 = f"{what} {key}[{j}]"
                if isinstance(o, dict) and "from" in o:
                    room.openings.append(_free_opening(o, o.get("kind", kind), w2))
                elif isinstance(o, dict) and "wall" in o:
                    room.openings += _side_opening(poly, o, o.get("kind", kind), w2)
                else:
                    raise SceneError(f"{w2}: give {{wall: south, at: 4}} or {{from: [x, y], to: [x, y]}}")
        sc.rooms.append(room)

    for i, wl in enumerate(data.get("walls") or []):
        what = f"walls[{i}]"
        if isinstance(wl, dict):
            a = _pt(wl["from"], what); b = _pt(wl["to"], what)
            wl = [a[0], a[1], b[0], b[1]]
        if len(wl) != 4:
            raise SceneError(f"{what}: give {{from: [x, y], to: [x, y]}}")
        x0, y0, x1, y1 = map(float, wl)
        if x0 != x1 and y0 != y1:
            raise SceneError(f"{what}: walls must be straight across or down")
        sc.walls.append((x0, y0, x1, y1))

    for key, kind in (("doors", "door"), ("windows", "window"), ("arches", "arch")):
        for j, o in enumerate(data.get(key) or []):
            sc.openings.append(_free_opening(o, o.get("kind", kind), f"{key}[{j}]"))

    for i, p in enumerate(data.get("props") or []):
        what = f"props[{i}]"
        if not isinstance(p, dict) or not (p.get("want") or p.get("file")):
            raise SceneError(f"{what}: each prop needs want: (words) or file: (an exact asset)")
        size = p.get("size")
        if size is not None:
            size = _pt(size, what + " size")
        sc.props.append(Prop(
            want=p.get("want"), file=p.get("file"),
            at=_pt(p["at"], what) if "at" in p else None,
            centre=_pt(p["centre"], what) if "centre" in p else None,
            size=size, rot=float(p.get("rot", 0)), room=p.get("in"), along=p.get("along"),
            count=int(p.get("count", 1)), label=p.get("label"), light=p.get("light"),
            scale=float(p.get("scale", 1.0)), layer=p.get("layer"), vary=bool(p.get("vary", False)),
            shadow=bool(p.get("shadow", True)), flip=bool(p.get("flip", False))))
        pr = sc.props[-1]
        if pr.at is None and pr.centre is None and pr.room is None:
            raise SceneError(f"{what} ({pr.want or pr.file}): give at: [x, y], centre: [x, y], or in: <room>")
        if pr.along and str(pr.along).lower() not in SIDES:
            raise SceneError(f"{what}: along should be one of {', '.join(SIDES)}")

    for i, sp in enumerate(data.get("scatter") or []):
        what = f"scatter[{i}]"
        if not isinstance(sp, dict) or not sp.get("want"):
            raise SceneError(f"{what}: each scatter rule needs want: (words), e.g. want: oak tree")
        what += f" ({sp['want']})"
        sc_ = sp.get("scale", (0.9, 1.1))
        if isinstance(sc_, (int, float)):
            sc_ = (float(sc_), float(sc_))
        turn = str(sp.get("turn", "any")).lower()
        if turn not in ("any", "square", "none"):
            raise SceneError(f"{what}: turn should be any, square or none")
        avoid = sp.get("avoid")
        if isinstance(avoid, str):
            avoid = [avoid]
        rule = Scatter(str(sp["want"]), str(sp.get("in", "map")),
                       int(sp["count"]) if "count" in sp else None,
                       float(sp["density"]) if "density" in sp else None,
                       float(sp.get("cluster", 1)), float(sp.get("spread", 1.5)), float(sp.get("gap", 0.1)),
                       turn, (float(sc_[0]), float(sc_[1])),
                       _pt(sp["size"], what + " size") if "size" in sp else None,
                       bool(sp.get("vary", True)), avoid, sp.get("layer"), sp.get("label"))
        if rule.count is None and rule.density is None:
            raise SceneError(f"{what}: give count: (how many) or density: (how many per square)")
        sc.scatter.append(rule)

    for i, l in enumerate(data.get("lights") or []):
        what = f"lights[{i}]"
        sc.lights.append(Light(_pt(l["at"], what), float(l.get("radius", 6)), colour(l.get("colour", l.get("color"))),
                               float(l.get("intensity", 0.8)), str(l.get("when", "both")), l.get("room")))

    for i, n in enumerate(data.get("notes") or []):
        sc.notes.append(Note(_pt(n["at"], f"notes[{i}]"), str(n["text"])))

    lt = data.get("lighting") or {}
    if "versions" in lt:
        sc.versions = list(lt["versions"])
    for v in ("day", "night"):
        if v in lt and isinstance(lt[v], dict) and "ambient" in lt[v]:
            sc.ambient[v] = colour(lt[v]["ambient"])
    for v in sc.versions:
        sc.ambient.setdefault(v, (200, 200, 200))
    return sc


def load(path: str | Path) -> Scene:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise SceneError(f"{path.name} is not valid YAML: {e}")
    return parse(data, str(path))
