"""Ready-made layouts: a tavern, shop, house, market square or woodland clearing.

Each template is a small function that lays out a scene from a size and a random
seed. Different seeds give different layouts (which side the kitchen is on, where
the road comes in), so ``mapwriter new tavern --options 3`` gives three to choose
from. The result is an ordinary scene file to edit by hand or by asking an AI.

Templates only ask for plain words (table, barrel, oak tree) so they work with any
pack, including the starter art.
"""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class Box:
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def w(self):
        return self.x1 - self.x0

    @property
    def h(self):
        return self.y1 - self.y0

    def list(self):
        return [self.x0, self.y0, self.x1, self.y1]


def _split(b: Box, side: str, depth: int) -> tuple[Box, Box]:
    """Cut a strip ``depth`` squares deep off one side of a box: (strip, rest)."""
    if side == "west":
        return Box(b.x0, b.y0, b.x0 + depth, b.y1), Box(b.x0 + depth, b.y0, b.x1, b.y1)
    if side == "east":
        return Box(b.x1 - depth, b.y0, b.x1, b.y1), Box(b.x0, b.y0, b.x1 - depth, b.y1)
    if side == "north":
        return Box(b.x0, b.y0, b.x1, b.y0 + depth), Box(b.x0, b.y0 + depth, b.x1, b.y1)
    return Box(b.x0, b.y1 - depth, b.x1, b.y1), Box(b.x0, b.y0, b.x1, b.y1 - depth)


def _halves(b: Box, rnd, along_x: bool, lo=0.4, hi=0.6) -> tuple[Box, Box]:
    """Split a box in two, across x (side by side) or across y (one above the other)."""
    if along_x:
        cut = b.x0 + max(2, min(b.w - 2, round(b.w * rnd.uniform(lo, hi))))
        return Box(b.x0, b.y0, cut, b.y1), Box(cut, b.y0, b.x1, b.y1)
    cut = b.y0 + max(2, min(b.h - 2, round(b.h * rnd.uniform(lo, hi))))
    return Box(b.x0, b.y0, b.x1, cut), Box(b.x0, cut, b.x1, b.y1)


def _shared(a: Box, b: Box):
    """The side of ``a`` that touches ``b`` and the span they share, or None."""
    if a.x1 == b.x0 or a.x0 == b.x1:
        lo, hi = max(a.y0, b.y0), min(a.y1, b.y1)
        if hi - lo >= 1:
            return ("east" if a.x1 == b.x0 else "west"), lo, hi
    if a.y1 == b.y0 or a.y0 == b.y1:
        lo, hi = max(a.x0, b.x0), min(a.x1, b.x1)
        if hi - lo >= 1:
            return ("south" if a.y1 == b.y0 else "north"), lo, hi
    return None


def _door_between(rooms: dict, a: str, b: str, rnd, kind="doors"):
    """Put a door on the wall two rooms share (listed on the first room)."""
    s = _shared(rooms[a]["_box"], rooms[b]["_box"])
    if s is None:
        return
    side, lo, hi = s
    at = rnd.randint(int(lo) + (1 if hi - lo > 2 else 0), int(hi) - (2 if hi - lo > 2 else 1))
    rooms[a].setdefault(kind, []).append({"wall": side, "at": at})


def _span(b: Box, side: str):
    return (b.x0, b.x1) if side in ("north", "south") else (b.y0, b.y1)


def _windows(b: Box, side: str, rnd, every=4, avoid=()):
    lo, hi = _span(b, side)
    spots = [t for t in range(int(lo) + 1, int(hi) - 1, every) if all(abs(t - a) > 1 for a in avoid)]
    rnd.shuffle(spots)
    return sorted(spots[:max(1, (hi - lo) // every)])


OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}


def _outside_door(b: Box, side: str, rnd):
    lo, hi = _span(b, side)
    return rnd.randint(int(lo) + 1, max(int(lo) + 1, int(hi) - 2))


def _road_from(b: Box, side: str, at: float, W: int, H: int, width=2):
    """A path from a door on side ``side`` of ``b`` out to the map edge."""
    if side == "south":
        return [[at + 0.5, b.y1], [at + 0.5, H]]
    if side == "north":
        return [[at + 0.5, b.y0], [at + 0.5, 0]]
    if side == "west":
        return [[b.x0, at + 0.5], [0, at + 0.5]]
    return [[b.x1, at + 0.5], [W, at + 0.5]]


def _finish(rooms: dict) -> list:
    out = []
    for name, r in rooms.items():
        r = dict(r)
        box = r.pop("_box").list()
        out.append({"name": name, "box": box, **r})
    return out


def _door_squares(rooms: dict) -> set:
    """Squares on both sides of every door and arch, to keep furniture out of doorways."""
    sq = set()
    for r in rooms.values():
        b = r["_box"]
        for key in ("doors", "arches"):
            for o in r.get(key, []):
                w = int(o.get("width", 2 if o.get("kind") == "double" else 1))
                for t in range(int(o["at"]), int(o["at"]) + w):
                    if o["wall"] == "north":
                        sq |= {(t, b.y0), (t, b.y0 - 1)}
                    elif o["wall"] == "south":
                        sq |= {(t, b.y1 - 1), (t, b.y1)}
                    elif o["wall"] == "west":
                        sq |= {(b.x0, t), (b.x0 - 1, t)}
                    else:
                        sq |= {(b.x1 - 1, t), (b.x1, t)}
    return sq


def _seating(b: Box, rnd, blocked: set, clear: dict | None = None, limit: int = 99) -> list:
    """Round tables with a chair either side, set out in rows inside a room.

    ``clear`` keeps a band free along some walls, e.g. {"east": 2} in front of a bar."""
    clear = clear or {}
    x0 = b.x0 + 1 + clear.get("west", 0); x1 = b.x1 - 1 - clear.get("east", 0)
    y0 = b.y0 + 1 + clear.get("north", 0); y1 = b.y1 - 1 - clear.get("south", 0)
    cols = max(0, (x1 - x0 + 1) // 4); rows = max(0, (y1 - y0 + 1) // 3)
    if not cols or not rows:
        return []
    # Centre the grid in the free space.
    ox = x0 + ((x1 - x0) - (cols * 4 - 1)) // 2
    oy = y0 + ((y1 - y0) - (rows * 3 - 2)) // 2
    out = []
    cells = [(c, r) for r in range(rows) for c in range(cols)]
    for c, r in cells:
        tx, ty = ox + c * 4 + 1, oy + r * 3
        group = {(tx - 1, ty), (tx, ty), (tx + 1, ty)}
        if group & blocked or not (b.x0 <= tx - 1 and tx + 1 < b.x1 and b.y0 <= ty < b.y1):
            continue
        if len(out) // 3 >= limit:
            break
        blocked |= group
        out += [{"want": "round table", "at": [tx, ty], "size": [1, 1]},
                {"want": "chair", "at": [tx - 1, ty], "rot": 270},
                {"want": "chair", "at": [tx + 1, ty], "rot": 90}]
    return out


def _bar(b: Box, side: str, length: int, blocked: set):
    """A counter along one inside wall, clear of doors, with stools in front."""
    lo, hi = _span(b, side)
    spots = [t for t in range(int(lo) + 1, int(hi) - length) ]
    spots.sort(key=lambda t: abs(t + length / 2 - (lo + hi) / 2))
    for t in spots:
        if side in ("north", "south"):
            y = b.y0 if side == "north" else b.y1 - 1
            front = y + 1 if side == "north" else y - 1
            sq = {(x, y) for x in range(t, t + length)} | {(x, front) for x in range(t, t + length)}
            if sq & blocked:
                continue
            blocked |= sq
            return ([{"want": "counter", "at": [t, y], "size": [length, 1], "label": "bar"}] +
                    [{"want": "stool", "at": [x, front]} for x in range(t, t + length, 2)])
        x = b.x0 if side == "west" else b.x1 - 1
        front = x + 1 if side == "west" else x - 1
        sq = {(x, y) for y in range(t, t + length)} | {(front, y) for y in range(t, t + length)}
        if sq & blocked:
            continue
        blocked |= sq
        return ([{"want": "counter", "at": [x, t], "size": [1, length], "label": "bar"}] +
                [{"want": "stool", "at": [front, y]} for y in range(t, t + length, 2)])
    return []


# ------------------------------------------------------------------ tavern
def tavern(rnd: random.Random, width=24, height=18, name="The Wayside Inn", option=0):
    W, H = width, height
    street = ["south", "west", "east"][option % 3]
    m = 2
    bld = Box(m, m, W - m, H - m)
    # The service strip (kitchen and store room) sits on the far side or one end.
    strip_side = rnd.choice([s for s in ("north", "east", "west") if s != street])
    depth = max(4, round((bld.w if strip_side in ("east", "west") else bld.h) * rnd.uniform(0.3, 0.38)))
    strip, common = _split(bld, strip_side, depth)
    kitchen, store = _halves(strip, rnd, along_x=strip_side in ("north", "south"))
    if rnd.random() < 0.5:
        kitchen, store = store, kitchen
    rooms = {
        "Common room": {"_box": common, "floor": "walnut wood planks"},
        "Kitchen": {"_box": kitchen, "floor": "warm stone tiles"},
        "Store room": {"_box": store, "floor": "grey flagstones"},
    }
    _door_between(rooms, "Common room", "Kitchen", rnd)
    _door_between(rooms, "Kitchen", "Store room", rnd)
    front_side = street                       # the strip is never on the street side
    front = _outside_door(common, front_side, rnd)
    rooms["Common room"]["doors"] = [{"wall": front_side, "at": front, "width": 2, "kind": "double"}] + rooms["Common room"].get("doors", [])
    win_sides = [s for s in ("north", "south", "east", "west") if s not in (strip_side, front_side)]
    rnd.shuffle(win_sides)
    rooms["Common room"]["windows"] = [{"wall": s, "at": _windows(common, s, rnd, 4)} for s in win_sides[:2]]
    blocked = _door_squares(rooms)
    props = _bar(common, strip_side, 4 if (common.w if strip_side in ("north", "south") else common.h) >= 9 else 3, blocked)
    props += [{"want": "fireplace", "in": "Common room", "along": OPPOSITE[strip_side], "count": 1}]
    # Keep the bar side and the fireplace side clear, then fill the floor with tables.
    props += _seating(common, rnd, blocked, {strip_side: 2, OPPOSITE[strip_side]: 1})
    props += [
        {"want": "red rug", "in": "Common room", "count": 1, "size": [3, 2]},
        {"want": "armchair", "in": "Common room", "count": 2},
        {"want": "bench", "in": "Common room", "along": front_side, "count": 1},
        {"want": "plant", "in": "Common room", "count": 2},
        {"want": "lantern", "in": "Common room", "count": 2},
        {"want": "cauldron", "in": "Kitchen", "count": 1},
        {"want": "table", "in": "Kitchen", "count": 1, "size": [2, 1]},
        {"want": "shelf", "in": "Kitchen", "along": strip_side, "count": 1},
        {"want": "barrel", "in": "Kitchen", "count": 1},
        {"want": "chest", "in": "Store room", "count": 1, "label": "strongbox"},
    ]
    scatter = [
        {"want": "barrel", "in": "Store room", "count": 3, "cluster": 3, "spread": 1.6, "turn": "any", "gap": 0},
        {"want": "crate", "in": "Store room", "count": 3, "cluster": 3, "spread": 1.6, "turn": "square", "gap": 0},
        {"want": "sack", "in": "Store room", "count": 2, "cluster": 2, "spread": 1.6},
        {"want": "oak tree", "in": "map", "count": 3, "cluster": 1, "gap": -0.4},
        {"want": "bush", "in": "map", "density": 0.03, "cluster": 3, "spread": 1.2},
        {"want": "flowers", "in": "map", "density": 0.015, "cluster": 4, "spread": 1},
    ]
    return {
        "name": name, "grid": {"width": W, "height": H, "px_per_square": 140}, "ground": "grass",
        "style": {"walls": "stone wall", "doors": "wood door", "windows": "wood window"},
        "paths": [{"name": "road", "points": _road_from(common, front_side, front + 0.5, W, H), "width": 3, "floor": "dirt path"}],
        "rooms": _finish(rooms), "props": props, "scatter": scatter,
        "notes": [{"at": [store.x0 + 0.5, store.y0 + 0.5], "text": "Store room. Locked at night; the innkeeper has the key."}],
    }


# ------------------------------------------------------------------ shop
def shop(rnd: random.Random, width=14, height=11, name="Pelbury's Goods", option=0):
    W, H = width, height
    bld = Box(1, 1, W - 1, H - 2)
    back_side = ["north", "east", "west"][option % 3]
    depth = max(3, round((bld.h if back_side == "north" else bld.w) * rnd.uniform(0.33, 0.42)))
    back, front = _split(bld, back_side, depth)
    rooms = {"Shop": {"_box": front, "floor": "walnut wood planks"},
             "Back room": {"_box": back, "floor": "grey flagstones"}}
    if option % 3 == 0 and back.w >= 8:
        work, living = _halves(back, rnd, along_x=True)
        rooms.pop("Back room")
        rooms["Workshop"] = {"_box": work, "floor": "grey flagstones"}
        rooms["Bedroom"] = {"_box": living, "floor": "light wood planks"}
        _door_between(rooms, "Shop", "Workshop", rnd)
        _door_between(rooms, "Workshop", "Bedroom", rnd)
    else:
        _door_between(rooms, "Shop", "Back room", rnd)
    door_at = _outside_door(front, "south", rnd)
    rooms["Shop"]["doors"] = [{"wall": "south", "at": door_at}] + rooms["Shop"].get("doors", [])
    rooms["Shop"]["windows"] = [{"wall": "south", "at": _windows(front, "south", rnd, 3, (door_at,))}]
    counter_y = front.y0 + max(1, front.h // 3)
    props = [
        {"want": "counter", "at": [front.x0 + max(1, front.w // 2 - 2), counter_y], "size": [3, 1], "label": "counter"},
        {"want": "shelf", "in": "Shop", "along": "east" if back_side != "east" else "west", "count": 2},
        {"want": "bookshelf", "in": "Shop", "along": back_side if back_side != "north" else "west", "count": 1},
        {"want": "barrel", "in": "Shop", "count": 2},
        {"want": "crate", "in": "Shop", "count": 2},
        {"want": "plant", "in": "Shop", "count": 1},
        {"want": "lantern", "at": [front.x0 + front.w // 2, front.y0 + front.h // 2 + 1]},
        {"want": "chest", "in": list(rooms)[1], "count": 1, "label": "strongbox"},
    ]
    if "Bedroom" in rooms:
        props += [{"want": "bed", "in": "Bedroom", "along": "north", "count": 1}, {"want": "candle", "in": "Bedroom", "count": 1}]
        props += [{"want": "table", "in": "Workshop", "count": 1, "size": [2, 1]}]
    else:
        props += [{"want": "table", "in": "Back room", "count": 1, "size": [2, 1]}, {"want": "candle", "in": "Back room", "count": 1}]
    return {
        "name": name, "grid": {"width": W, "height": H, "px_per_square": 140}, "ground": "cobblestone",
        "rooms": _finish(rooms), "props": props,
        "scatter": [{"want": "crate", "in": list(rooms)[1], "count": 2, "cluster": 2, "spread": 1, "turn": "square", "gap": 0}],
        "notes": [{"at": [front.x0 + front.w / 2, counter_y + 0.5], "text": "The shopkeeper keeps a cudgel and a bell under the counter."}],
    }


# ------------------------------------------------------------------ house
def house(rnd: random.Random, width=16, height=12, name="Miller's Cottage", option=0):
    W, H = width, height
    bld = Box(2, 2, W - 2, H - 2)
    bed_side = ["east", "west", "north"][option % 3]
    depth = max(3, round((bld.w if bed_side in ("east", "west") else bld.h) * rnd.uniform(0.35, 0.42)))
    beds, main = _split(bld, bed_side, depth)
    b1, b2 = _halves(beds, rnd, along_x=bed_side == "north")
    rooms = {"Main room": {"_box": main, "floor": "light wood planks"},
             "Bedroom": {"_box": b1, "floor": "walnut wood planks"},
             "Pantry": {"_box": b2, "floor": "grey flagstones"}}
    if rnd.random() < 0.5:
        rooms["Bedroom"]["_box"], rooms["Pantry"]["_box"] = b2, b1
    _door_between(rooms, "Main room", "Bedroom", rnd)
    _door_between(rooms, "Main room", "Pantry", rnd)
    door_side = "south" if bed_side != "north" else rnd.choice(["south", "west"])
    door_at = _outside_door(main, door_side, rnd)
    rooms["Main room"]["doors"] = [{"wall": door_side, "at": door_at}] + rooms["Main room"].get("doors", [])
    outer = [x for x in (OPPOSITE[bed_side], "east", "west", "north", "south") if x not in (bed_side, door_side)]
    fire_side = outer[0]
    shelf_side = outer[1] if len(outer) > 1 else door_side
    # Windows on the front, beside the door, and on the side wall without the shelf.
    rooms["Main room"]["windows"] = [{"wall": door_side, "at": _windows(main, door_side, rnd, 4, (door_at,))}]
    blocked = _door_squares(rooms)
    meal = _seating(main, rnd, blocked, {fire_side: 1}, limit=1)
    props = meal + [
        {"want": "fireplace", "in": "Main room", "along": fire_side, "count": 1},
        {"want": "armchair", "in": "Main room", "count": 1},
        {"want": "rug", "in": "Main room", "count": 1, "size": [2, 2]},
        {"want": "shelf", "in": "Main room", "along": shelf_side, "count": 1},
        {"want": "bed", "in": "Bedroom", "count": 1},
        {"want": "chest", "in": "Bedroom", "count": 1},
        {"want": "candle", "in": "Bedroom", "count": 1},
        {"want": "barrel", "in": "Pantry", "count": 1},
        {"want": "sack", "in": "Pantry", "count": 2},
        {"want": "lantern", "in": "Main room", "count": 1},
    ]
    return {
        "name": name, "grid": {"width": W, "height": H, "px_per_square": 140}, "ground": "grass",
        "style": {"walls": "wood wall"},
        "paths": [{"name": "path", "points": _road_from(main, door_side, door_at + 0.5, W, H), "width": 1.5, "floor": "dirt path"}],
        "rooms": _finish(rooms), "props": props,
        "scatter": [{"want": "bush", "in": "map", "density": 0.04, "cluster": 3, "spread": 1},
                    {"want": "flowers", "in": "map", "density": 0.03, "cluster": 4, "spread": 1},
                    {"want": "oak tree", "in": "map", "count": 2, "gap": 0}],
    }


# ------------------------------------------------------------------ market square
def market(rnd: random.Random, width=26, height=20, name="Market Square", option=0):
    W, H = width, height
    cx, cy = W / 2 + rnd.uniform(-1.5, 1.5), H / 2 + rnd.uniform(-1, 1)
    r = min(W, H) * rnd.uniform(0.26, 0.32)
    roads = {0: ["north", "south", "east", "west"], 1: ["west", "east", "south"], 2: ["north", "east"]}[option % 3]
    import math
    paths = []
    for side in roads:
        wob = rnd.uniform(-1.5, 1.5)
        end = {"north": [cx + wob, 0], "south": [cx + wob, H], "west": [0, cy + wob], "east": [W, cy + wob]}[side]
        mid = [(cx + end[0]) / 2 + rnd.uniform(-1, 1), (cy + end[1]) / 2 + rnd.uniform(-1, 1)]
        sx, sy = cx + (end[0] - cx) * r * 0.75 / max(1e-6, math.hypot(end[0] - cx, end[1] - cy)), cy + (end[1] - cy) * r * 0.75 / max(1e-6, math.hypot(end[0] - cx, end[1] - cy))
        paths.append({"name": f"{side} road", "points": [[round(sx, 1), round(sy, 1)], [round(mid[0], 1), round(mid[1], 1)], end],
                      "width": 2.5, "floor": "dirt path"})
    # Stalls round the edge of the square, facing in.
    stalls, props = rnd.randint(4, 6), []
    import math
    for k in range(stalls):
        a = 2 * math.pi * (k + rnd.uniform(-0.15, 0.15)) / stalls + (math.pi / stalls)
        sx, sy = cx + math.cos(a) * (r - 1.8), cy + math.sin(a) * (r - 1.8)
        rot = (round(math.degrees(a) / 90) * 90 + 90) % 360
        props.append({"want": rnd.choice(["market stall", "red market stall", "blue market stall"]),
                      "centre": [round(sx, 1), round(sy, 1)], "rot": rot, "label": f"stall {k + 1}"})
    props.append({"want": "well", "centre": [round(cx, 1), round(cy, 1)], "label": "well"})
    props.append({"want": "lantern", "centre": [round(cx + 1.5, 1), round(cy, 1)]})
    data = {
        "name": name, "grid": {"width": W, "height": H, "px_per_square": 140}, "ground": "grass",
        "paths": paths,
        "areas": [{"name": "square", "circle": [round(cx, 1), round(cy, 1), round(r, 1)], "floor": "cobblestone", "rough": 0.3, "soft": 0.15}],
        "props": props,
        "scatter": [
            {"want": "crate", "in": "square", "count": 4, "cluster": 2, "spread": 1.2, "gap": -0.05, "label": "crates"},
            {"want": "barrel", "in": "square", "count": 2, "gap": 0},
            {"want": "oak tree", "in": "map", "count": 6, "cluster": 3, "spread": 3, "gap": -0.6},
            {"want": "bush", "in": "map", "density": 0.025, "cluster": 3, "spread": 1.2},
            {"want": "flowers", "in": "map", "density": 0.015, "cluster": 4, "spread": 1},
        ],
    }
    if option % 3 == 2:
        data["water"] = [{"name": "pond", "circle": [round(W * 0.2, 1), round(H * 0.75, 1), 2.2], "rough": 0.4}]
    return data


# ------------------------------------------------------------------ woodland clearing
def clearing(rnd: random.Random, width=24, height=18, name="Woodland Clearing", option=0):
    W, H = width, height
    cx, cy = W / 2 + rnd.uniform(-2, 2), H / 2 + rnd.uniform(-1.5, 1.5)
    r = min(W, H) * rnd.uniform(0.28, 0.34)
    side = rnd.choice(["south", "west", "east", "north"])
    end = {"north": [cx + rnd.uniform(-3, 3), 0], "south": [cx + rnd.uniform(-3, 3), H], "west": [0, cy + rnd.uniform(-3, 3)],
           "east": [W, cy + rnd.uniform(-3, 3)]}[side]
    feature = ["camp", "pond", "stones"][option % 3]
    props, water, notes = [], [], []
    if feature == "camp":
        props += [{"want": "campfire", "centre": [round(cx, 1), round(cy, 1)], "label": "campfire"},
                  {"want": "log", "centre": [round(cx, 1), round(cy - 1.6, 1)]},
                  {"want": "log", "centre": [round(cx - 1.6, 1), round(cy + 0.6, 1)], "rot": 90},
                  {"want": "sack", "centre": [round(cx + 1.6, 1), round(cy + 1, 1)]},
                  {"want": "chest", "centre": [round(cx + 2.2, 1), round(cy - 1.5, 1)], "label": "bandit loot"}]
        notes.append({"at": [round(cx, 1), round(cy, 1)], "text": "The fire is still warm. Whoever camped here left in a hurry."})
    elif feature == "pond":
        water.append({"name": "pool", "circle": [round(cx + 1, 1), round(cy, 1), round(r * 0.45, 1)], "rough": 0.5})
        notes.append({"at": [round(cx + 1, 1), round(cy, 1)], "text": "Clear, cold water. Something glints at the bottom."})
    else:
        import math
        for k in range(7):
            a = 2 * math.pi * k / 7
            props.append({"want": "big rock", "centre": [round(cx + math.cos(a) * r * 0.55, 1), round(cy + math.sin(a) * r * 0.55, 1)]})
        props.append({"want": "altar", "centre": [round(cx, 1), round(cy, 1)], "label": "altar stone"})
        notes.append({"at": [round(cx, 1), round(cy, 1)], "text": "Standing stones. At midnight the altar hums."})
    return {
        "name": name, "grid": {"width": W, "height": H, "px_per_square": 140}, "ground": "grass", "seed": rnd.randint(1, 999),
        "areas": [{"name": "clearing", "circle": [round(cx, 1), round(cy, 1), round(r, 1)], "floor": "grass", "rough": 0.8, "soft": 0.4}],
        "paths": [{"name": "track", "points": [[round(cx, 1), round(cy, 1)], [round((cx + end[0]) / 2 + rnd.uniform(-2, 2), 1),
                                                                             round((cy + end[1]) / 2 + rnd.uniform(-2, 2), 1)], [round(end[0], 1), round(end[1], 1)]],
                   "width": 1.5, "floor": "dirt path", "rough": 0.2}],
        "water": water,
        "props": props,
        "scatter": [
            {"want": "rock", "in": "map", "count": 2, "gap": 0},
            {"want": "flowers", "in": "clearing", "density": 0.06, "cluster": 2, "spread": 1.5},
            {"want": "oak tree", "in": "map", "density": 0.11, "cluster": 4, "spread": 3, "gap": -0.7, "avoid": ["clearing"]},
            {"want": "bush", "in": "map", "density": 0.05, "cluster": 3, "spread": 1.5},
        ],
        "notes": notes,
    }


TEMPLATES = {"tavern": tavern, "shop": shop, "house": house, "market": market, "clearing": clearing}
ALIASES = {"inn": "tavern", "pub": "tavern", "store": "shop", "cottage": "house", "home": "house",
           "market square": "market", "square": "market", "forest": "clearing", "woods": "clearing", "camp": "clearing"}


def names() -> list[str]:
    return list(TEMPLATES)


def make(kind: str, option: int = 0, seed: int = 1, width: int | None = None, height: int | None = None,
         name: str | None = None) -> dict:
    """One layout as scene data. ``option`` picks the layout family, ``seed`` the details."""
    k = ALIASES.get(kind.lower(), kind.lower())
    if k not in TEMPLATES:
        raise ValueError(f"No template called '{kind}'. Templates: {', '.join(TEMPLATES)}.")
    fn = TEMPLATES[k]
    kw = {"option": option}
    if width:
        kw["width"] = width
    if height:
        kw["height"] = height
    if name:
        kw["name"] = name
    data = fn(random.Random(f"{k}:{seed}:{option}"), **kw)
    data.setdefault("seed", seed + option)
    # Put the usual keys first, so files read the same way every time.
    order = ["name", "grid", "seed", "ground", "style", "areas", "paths", "water", "rooms", "props", "scatter", "lights", "notes"]
    return {key: data[key] for key in order if key in data and data[key] not in (None, [], {})}
