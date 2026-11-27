"""Resolve a Scene against an asset Index into a concrete Plan.

The plan says exactly which image goes where, which wall lines exist after
doors are cut, and where every light sits. Sketch, painter and exporters all
read the plan, so they always agree.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .assets.index import Asset, Index
from .geometry import (Region, distance_to_segment, grown, path_strip, rough_outline, joint_shape, light_area, merge_walls, on_wall, reachable,
                       wall_junctions)
from .assets import naming
from .scene import Scene, Prop, Light, Opening, Room, SceneError, WallLook


# Walls made of these let sight and light through (they still stop movement).
SEE_THROUGH = {"glass", "fence", "railing"}


@dataclass
class WallSet:
    """Walls that share one look: the same art, thickness and see-through setting."""
    style: str
    asset: Asset | None
    raw: list = field(default_factory=list)       # before openings are cut
    segs: list = field(default_factory=list)      # after, as painted
    joints: list = field(default_factory=list)
    thickness: float | None = None                # squares; None is the painter's usual thickness
    see_through: bool = False


@dataclass
class Placed:
    want: str
    asset: Asset | None
    box: tuple[float, float, float, float]   # squares covered (x0, y0, x1, y1)
    rot: float                                # clockwise degrees applied to the image
    label: str | None = None
    layer: int = 1
    scale: float = 1.0
    shadow: bool = True
    flip: bool = False
    fit_rot: float = 0.0                      # extra rotation to make the image fit the box
    part: str = ""                            # "top" for the upper piece of a layered asset
    grade: tuple | None = None                # (colour strength, brightness, outline) to match the main style

    @property
    def centre(self):
        x0, y0, x1, y1 = self.box
        return (x0 + x1) / 2, (y0 + y1) / 2


@dataclass
class Floor:
    name: str
    poly: list
    want: str | None
    asset: Asset | None
    soft: float = 0.0
    is_room: bool = False
    region: Region | None = None              # the exact outline painted; set for every floor
    water: bool = False                       # painted with a deep middle and a light shoreline

    def __post_init__(self):
        if self.region is None:
            self.region = Region(poly=self.poly)


@dataclass
class Plan:
    scene: Scene
    floors: list[Floor] = field(default_factory=list)
    raw_walls: list = field(default_factory=list)          # before openings are cut
    walls: list = field(default_factory=list)              # after
    light_walls: list = field(default_factory=list)        # walls and closed doors: what stops light
    light_areas: list = field(default_factory=list)        # one polygon per light: where its light reaches
    wall_joints: list = field(default_factory=list)        # (x, y, asset, clockwise quarter turns)
    wall_asset: Asset | None = None
    wall_sets: list[WallSet] = field(default_factory=list)  # walls grouped by look, for painting
    see_through_walls: list = field(default_factory=list)  # raw glass walls: they stop movement only
    openings: list[tuple[Opening, Asset | None]] = field(default_factory=list)
    props: list[Placed] = field(default_factory=list)
    lights: list[Light] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


LIGHT_DEFAULTS = [  # (word, radius, colour, intensity)
    ({"fireplace", "hearth", "campfire", "bonfire", "brazier"}, 7, (255, 150, 70), 0.9),
    ({"chandelier"}, 8, (255, 205, 140), 0.85),
    ({"lantern", "lamp", "torch", "sconce"}, 6, (255, 196, 120), 0.8),
    ({"candle", "candelabra", "candlestick"}, 4, (255, 176, 96), 0.7),
]


def _auto_light(asset: Asset):
    w = asset.all_words
    for words, r, c, i in LIGHT_DEFAULTS:
        if w & words:
            return r, c, i
    return 5, (255, 190, 110), 0.75


def _layer(p: Prop, asset: Asset | None, size) -> int:
    if p.layer is not None:
        return int(p.layer)
    if asset is not None and asset.is_rug:
        return 0
    if asset is not None and asset.kind in ("overlay",):
        return 3
    area = size[0] * size[1]
    return 1 if area >= 2 else 2


def _fit(asset: Asset | None, size, rot):
    """Return (box size w,h in squares, extra image rotation) for a prop."""
    fp = tuple(asset.footprint) if asset is not None and asset.footprint else None
    if size is None:
        w, h = fp if fp else (1, 1)
        if int(round(rot)) % 180 == 90:
            w, h = h, w
        return (w, h), 0.0
    w, h = size
    if fp and fp[0] != fp[1]:
        want_long_x = w > h
        img_long_x = fp[0] > fp[1]
        r = int(round(rot)) % 180 == 90
        if (img_long_x != r) != want_long_x and w != h:
            return (w, h), 90.0
    return (w, h), 0.0


def build(scene: Scene, index: Index) -> Plan:
    """Choose art and place everything. The scene's ``style: pack`` (or the first pack
    listed) sets the style that art from other packs is matched to."""
    before = index.main_pack
    index.main_pack = scene.style_pack
    try:
        plan = _build(scene, index)
        _match_styles(plan, index)
        return plan
    finally:
        index.main_pack = before


def _match_styles(plan: Plan, index: Index):
    """Grade art from other packs towards the main pack's style (style: { match: true }),
    or say when the map mixes clearly different styles."""
    from .assets.style import CLASH, describe, grade_for
    sc = plan.scene
    if sc.style_pack and sc.style_pack not in index.styles:
        plan.warnings.append(f"style: pack '{sc.style_pack}' is not in the index; packs are: "
                             f"{', '.join(index.pack_order) or 'none'}.")
    main = index.main
    target = index.styles.get(main)
    if not target:
        return
    used = {p.asset.pack for p in plan.props if p.asset is not None}
    if sc.match_style:
        for p in plan.props:
            if p.asset is not None and p.asset.pack != main and p.asset.kind != "floor":
                p.grade = grade_for(index.styles.get(p.asset.pack), target)
        return
    clashes = [(pk, index.style_gap(pk)) for pk in sorted(used - {main})]
    clashes = [(pk, g) for pk, g in clashes if g is not None and g > CLASH]
    if clashes and main in used | {plan.wall_asset.pack if plan.wall_asset else None}:
        pk = clashes[0][0]
        plan.warnings.append(
            f"This map mixes art in clearly different styles: {main} ({describe(target)}) and {pk} "
            f"({describe(index.styles[pk])}). Add style: {{ match: true }} to even out colour and brightness.")


def _build(scene: Scene, index: Index) -> Plan:
    plan = Plan(scene)
    seed = scene.seed
    warn = plan.warnings.append
    loose_told: set[str] = set()

    def tell_if_loose(want, a, kind="prop"):
        """Say so when the art only matched through a similar word (a 'stall' that came back
        as a booth), so the user can check it or name a file."""
        if a is not None and want not in loose_told and index.loose(want, a, kind):
            loose_told.add(want)
            if index.by_look(want, a, kind):
                warn(f"No file is named for '{want}'; using {a.name}, which looks like the "
                     f"{a.guessed[0]} files. Check it, or add the word in tags.yaml.")
            else:
                warn(f"No close match for '{want}'; using {a.name}, found through a similar word.")

    # ---------- floors ----------
    def floor_asset(want):
        if not want:
            return None
        a = index.get(want)
        if a is None:
            # Roof textures (Roof_Thatch_*) index as kind roof. Asking for 'roof' words looks
            # there first; otherwise they are a fallback when no floor texture matches.
            order = ("roof", "floor") if "roof" in naming.words(want) else ("floor", "roof")
            a = index.pick(want, order[0], seed=seed) or index.pick(want, order[1], seed=seed)
        if a is None:
            warn(f"No floor texture matches '{want}'; using a plain colour.")
        return a

    W, H = scene.width, scene.height
    plan.floors.append(Floor("ground", [(0, 0), (W, 0), (W, H), (0, H)], scene.ground, floor_asset(scene.ground)))
    # Paths go down first, so a road runs under the square or yard it leads into.
    for p in scene.paths:
        strip = path_strip(p.points, p.width, p.rough, random.Random(f"{seed}:path:{p.name}"), p.curve)
        plan.floors.append(Floor(p.name, None, p.floor, floor_asset(p.floor), p.soft, region=strip))
    for a in scene.areas:
        rnd_edge = random.Random(f"{seed}:area:{a.name}")
        outline = rough_outline(a.poly, a.rough, rnd_edge, a.smooth)
        plan.floors.append(Floor(a.name, outline, a.floor, floor_asset(a.floor), a.soft))
    # Water after areas, with each bank first so it shows as a rim round the water.
    for wt in scene.water:
        rnd_w = random.Random(f"{seed}:water:{wt.name}")
        if wt.points:
            body = path_strip(wt.points, wt.width, wt.rough * 0.6, rnd_w, wt.curve)
        else:
            body = Region(poly=rough_outline(wt.poly, wt.rough, rnd_w, wt.smooth))
        if wt.bank and wt.bank_width > 0:
            bank = grown(body, wt.bank_width, wt.bank_width * 0.4, rnd_w)
            plan.floors.append(Floor(f"{wt.name} bank", bank.poly, wt.bank, floor_asset(wt.bank),
                                     max(wt.soft, wt.bank_width * 0.5), region=bank))
        plan.floors.append(Floor(wt.name, body.poly, wt.floor, floor_asset(wt.floor), wt.soft, region=body, water=True))
    for r in scene.rooms:
        if r.floor:
            plan.floors.append(Floor(r.name, r.poly, r.floor, floor_asset(r.floor), 0.0, True))

    # ---------- walls and openings ----------
    raw = []
    looks = []
    for r in scene.rooms:
        if r.walls is None:
            continue
        style = None if r.walls in ("default", True) else str(r.walls)
        for (ax, ay), (bx, by) in r.edges():
            raw.append((ax, ay, bx, by))
            looks.append(WallLook(style, r.see_through, r.wall_thickness))
    raw += list(scene.walls)
    looks += list(scene.wall_looks) + [WallLook()] * (len(scene.walls) - len(scene.wall_looks))
    plan.raw_walls = raw
    plan.wall_asset = index.get(scene.wall_style) or index.pick(scene.wall_style, "wall", seed=seed)
    if raw and plan.wall_asset is None:
        warn(f"No wall art matches '{scene.wall_style}'; walls are drawn as plain stone.")
    sets: dict = {}
    for seg, lk in zip(raw, looks):
        style = lk.style or scene.wall_style
        see = lk.see_through if lk.see_through is not None else bool(SEE_THROUGH & set(naming.words(style)))
        key = (style.lower(), see, lk.thickness)
        if key not in sets:
            if style.lower() == scene.wall_style.lower():
                asset = plan.wall_asset
            else:
                asset = index.get(style) or index.pick(style, "wall", seed=seed)
                if asset is None:
                    warn(f"No wall art matches '{style}'; those walls use the scene's wall style.")
                    asset = plan.wall_asset
            sets[key] = WallSet(style, asset, thickness=lk.thickness, see_through=see)
        sets[key].raw.append(seg)
    plan.wall_sets = list(sets.values())
    plan.see_through_walls = [w for ws in plan.wall_sets if ws.see_through for w in ws.raw]
    solid_raw = [w for ws in plan.wall_sets if not ws.see_through for w in ws.raw]

    openings = [o for r in scene.rooms for o in r.openings] + list(scene.openings)
    seen = set()
    for o in openings:
        key = (o.a, o.b) if o.a <= o.b else (o.b, o.a)
        if key in seen:
            continue                      # same door listed on both rooms
        seen.add(key)
        if not on_wall(o, raw):
            warn(f"The {o.kind} from {o.a} to {o.b} is not on any wall.")
        asset = None
        if o.kind in ("door", "double", "secret"):
            want = o.want or scene.door_style
            asset = (index.get(o.file) if o.file else None) or index.pick(want, "door", seed=seed)
        elif o.kind == "window":
            want = o.want or scene.window_style
            asset = (index.get(o.file) if o.file else None) or index.pick(want, "window", seed=seed)
        plan.openings.append((o, asset))
    cut = [o for o, _ in plan.openings if o.kind != "window"]
    plan.walls = merge_walls(raw, cut)
    # Light passes through windows, arches, open doors and glass, and is stopped by walls and closed doors.
    plan.light_walls = merge_walls(solid_raw, [o for o, _ in plan.openings
                                               if o.kind in ("window", "arch") or o.open])
    for ws in plan.wall_sets:
        ws.segs = merge_walls(ws.raw, cut)
        ws.joints = _wall_joints(ws.segs, ws.asset, index)
    plan.wall_joints = [j for ws in plan.wall_sets for j in ws.joints]

    # ---------- props ----------
    occupied: set[tuple[int, int]] = set()
    overlap_ok: set[tuple[int, int]] = set()       # squares of pieces marked overlap: ok
    door_squares: set[tuple[int, int]] = set()
    for o, _ in plan.openings:
        if o.kind == "window":
            continue
        (ax, ay), (bx, by) = o.a, o.b
        if o.horizontal:
            for x in range(int(min(ax, bx)), int(math.ceil(max(ax, bx)))):
                door_squares |= {(x, int(ay)), (x, int(ay) - 1)}
        else:
            for y in range(int(min(ay, by)), int(math.ceil(max(ay, by)))):
                door_squares |= {(int(ax), y), (int(ax) - 1, y)}

    def squares(box):
        x0, y0, x1, y1 = box
        return {(x, y) for x in range(int(math.floor(x0 + 0.01)), int(math.ceil(x1 - 0.01)))
                for y in range(int(math.floor(y0 + 0.01)), int(math.ceil(y1 - 0.01)))}

    rnd = random.Random(seed)
    chosen: dict[str, Asset | None] = {}

    def choose(p: Prop, i: int):
        if p.file:
            a = index.get(p.file)
            if a is None:
                warn(f"No asset file called '{p.file}'.")
            return a
        key = p.want if not p.vary else f"{p.want}#{i}"
        if key not in chosen:
            # A prop drawn smaller than its art with no size given is a small thing (an apple, a
            # loaf): prefer 1x1 art, so the word doesn't pull in a handcart or stall full of them.
            small = p.size is None and p.scale < 1
            a = index.pick(p.want, "prop", p.size, seed=seed + (i if p.vary else 0), family_seed=seed if p.vary else None,
                           small=small)
            if a is None:
                # rugs, mats and similar sometimes live with floor textures
                a = index.pick(p.want, "floor", seed=seed)
            if a is None:
                warn(f"No asset matches '{p.want}'; it is shown as a labelled box.")
            tell_if_loose(p.want, a)
            chosen[key] = a
        return chosen[key]

    for pi, p in enumerate(scene.props):
        name = p.want or p.file
        count = max(1, p.count)
        boxes: list[tuple[tuple, float]] = []
        if p.at is not None or p.centre is not None:
            a = choose(p, 0)
            (w, h), _ = _fit(a, p.size, p.rot)
            if p.at is not None:
                x, y = p.at
            else:
                x, y = p.centre[0] - w / 2, p.centre[1] - h / 2
            boxes.append(((x, y, x + w, y + h), p.rot))
        else:
            try:
                room = scene.room(p.room)
            except SceneError as e:
                warn(f"props[{pi}] ({name}): {e}")
                continue
            a = choose(p, 0)
            boxes += _auto_place(room, p, a, count, occupied, door_squares, rnd, warn, name)
        for bi, (box, rot) in enumerate(boxes):
            a = choose(p, bi)
            _, fit_rot = _fit(a, (box[2] - box[0], box[3] - box[1]), rot)
            x0, y0, x1, y1 = box
            if x0 < -0.01 or y0 < -0.01 or x1 > W + 0.01 or y1 > H + 0.01:
                warn(f"'{name}' at {box[:2]} runs off the map edge.")
            pl = Placed(name, a, box, rot, p.label, _layer(p, a, (x1 - x0, y1 - y0)), p.scale, p.shadow, p.flip, fit_rot)
            if pl.layer >= 1:
                sq = squares(box)
                # overlap: ok marks pieces built to sit together (a counter in front of a tent).
                if pl.layer == 1 and p.at is not None and not p.overlap and sq & (occupied - overlap_ok):
                    warn(f"'{name}' at {box[:2]} overlaps another piece of furniture.")
                if pl.layer == 1:
                    occupied |= sq
                    if p.overlap:
                        overlap_ok |= sq
            plan.props.append(pl)
            # Base pieces with a separate top (well roofs, glass display tops) get the top too.
            top = index.top_piece(a, seed + bi) if (a is not None and p.top) else None
            if top is not None:
                plan.props.append(Placed(name, top, box, rot, None, max(3, pl.layer + 1), p.scale, False, p.flip, fit_rot, part="top"))
            # automatic lights from candles, lanterns, fireplaces
            if a is not None and a.emits_light and p.light is not False:
                r, c, inten = _auto_light(a)
                if isinstance(p.light, dict):
                    r = float(p.light.get("radius", r)); inten = float(p.light.get("intensity", inten))
                    if "colour" in p.light or "color" in p.light:
                        from .scene import colour
                        c = colour(p.light.get("colour", p.light.get("color")))
                cx, cy = pl.centre
                plan.lights.append(Light((cx, cy), r, c, inten, "both"))

    # ---------- scatter ----------
    taken: list[tuple[float, float, float]] = []       # (x, y, radius) of scattered items so far
    for si, rule in enumerate(scene.scatter):
        plan.props += _scatter(plan, rule, si, index, occupied | door_squares, taken, warn, tell_if_loose)

    plan.lights = list(scene.lights) + plan.lights
    for L in plan.lights:
        plan.light_areas.append(_light_area(scene, L, plan.light_walls))

    # ---------- checks ----------
    for r in scene.rooms:
        x0, y0, x1, y1 = r.box
        if x0 < 0 or y0 < 0 or x1 > W or y1 > H:
            warn(f"Room '{r.name}' runs off the map ({r.box}; map is {W} x {H}).")
    if plan.walls and scene.rooms:
        # Every walled room should be reachable from outside or from the first room.
        start = None
        for y in range(H):
            for x in range(W):
                if scene.room_at(x + 0.5, y + 0.5) is None:
                    start = (x, y); break
            if start: break
        if start is None:
            r0 = scene.rooms[0]
            start = (int(r0.box[0]), int(r0.box[1]))
        reach = reachable(W, H, plan.walls, start)
        for r in scene.rooms:
            if r.walls is None:
                continue
            x0, y0, x1, y1 = r.box
            inside = [(x, y) for x in range(int(x0), int(math.ceil(x1))) for y in range(int(y0), int(math.ceil(y1)))
                      if r.contains(x + 0.5, y + 0.5)]
            if inside and not any(s in reach for s in inside):
                warn(f"Room '{r.name}' has no way in (no door or arch reaches it).")
    return plan


def _light_area(scene: Scene, L: Light, blockers) -> list:
    """Where a light reaches, cast against the walls. A light sitting on a wall line
    (a sconce, a fireplace against the wall) is nudged into its room first, so it
    does not shine through the wall it hangs on."""
    x, y = L.at
    if any(distance_to_segment(x, y, s) < 0.12 for s in blockers):
        rm = scene.room_at(x, y) or scene.room_at(x + 0.2, y + 0.2) or scene.room_at(x - 0.2, y - 0.2)
        if rm is not None:
            bx0, by0, bx1, by1 = rm.box if getattr(rm, "box", None) else (x, y, x, y)
            cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
            d = max(1e-6, ((cx - x) ** 2 + (cy - y) ** 2) ** 0.5)
            x, y = x + 0.15 * (cx - x) / d, y + 0.15 * (cy - y) / d
    return light_area((x, y), blockers, L.radius)
TALL_WORDS = {"tree", "oak", "pine", "willow", "canopy"}


def _region_named(plan: Plan, name: str):
    """A floor (area, path, water) or room by name, as a Region."""
    for f in plan.floors[1:]:
        if f.name.lower() == name.lower():
            return f.region
    for r in plan.scene.rooms:
        if r.name.lower() == name.lower():
            return Region(poly=r.poly)
    return None


def _scatter(plan: Plan, rule, si: int, index: Index, blocked_squares, taken, warn, tell=lambda *_: None) -> list:
    """Place copies of ``rule.want`` inside a region, in clumps if asked, keeping off
    paths, water, buildings, furniture and each other."""
    sc = plan.scene
    W, H = sc.width, sc.height
    rnd = random.Random(f"{sc.seed}:scatter:{si}:{rule.want}")
    name = rule.want
    if rule.within.lower() == "map":
        region = Region(poly=[(0, 0), (W, 0), (W, H), (0, H)])
    else:
        region = _region_named(plan, rule.within)
        if region is None:
            warn(f"scatter '{name}': nothing called '{rule.within}' to scatter in.")
            return []
    inside_room = any(r.name.lower() == rule.within.lower() for r in sc.rooms)
    # Keep off paths, water and walled rooms by default, plus anything named in avoid.
    avoid, solid = [], []          # solid: buildings, which a tree's canopy should not cover either
    if not (rule.avoid and any(str(a).lower() == "none" for a in rule.avoid)):
        # On open ground, keep off every path, area and pond; inside a named place, only off paths and water.
        on_map = rule.within.lower() == "map"
        avoid += [f.region for f in plan.floors[1:] if f.region is not region and not f.is_room
                  and (on_map or f.water or f.poly is None)]
        if not inside_room:
            # A bed or patch inside a walled room (a glasshouse border) scatters freely in it.
            bx0, by0, bx1, by1 = region.bbox()
            corners = [(bx0 + 0.01, by0 + 0.01), (bx1 - 0.01, by0 + 0.01), (bx0 + 0.01, by1 - 0.01), (bx1 - 0.01, by1 - 0.01)]
            solid += [Region(poly=r.poly) for r in sc.rooms
                      if r.walls is not None and not all(r.contains(x, y) for x, y in corners)]
    for a in rule.avoid or []:
        if str(a).lower() != "none":
            g = _region_named(plan, str(a))
            if g is None:
                warn(f"scatter '{name}': nothing called '{a}' to keep off.")
            else:
                avoid.append(g)

    x0, y0, x1, y1 = region.bbox()
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if rule.count is not None:
        n = max(0, rule.count)
    else:
        cells = sum(1 for i in range(int(x0 * 2), int(math.ceil(x1 * 2))) for j in range(int(y0 * 2), int(math.ceil(y1 * 2)))
                    if region.contains(i / 2 + 0.25, j / 2 + 0.25))
        n = int(round(rule.density * cells / 4))

    def choose(i):
        a = index.pick(name, "prop", rule.size, seed=sc.seed + (i if rule.vary else 0), family_seed=sc.seed if rule.vary else None)
        if a is None:
            a = index.pick(name, "prop", rule.size, seed=sc.seed)
        tell(name, a)
        return a

    def free(x, y, r):
        if not (0 <= x <= W and 0 <= y <= H) or not region.contains(x, y):
            return False
        dirs = ((1, 0), (-1, 0), (0, 1), (0, -1), (0.7, 0.7), (-0.7, 0.7), (0.7, -0.7), (-0.7, -0.7))
        edge = [(x, y)] + [(x + r * 0.7 * dx, y + r * 0.7 * dy) for dx, dy in dirs]
        if any(g.contains(px, py) for g in avoid for px, py in edge):
            return False
        rim = [(x + r * dx, y + r * dy) for dx, dy in dirs]
        if any(g.contains(px, py) for g in solid for px, py in edge + rim):
            return False
        # Big pieces (tree canopies) keep their whole spread off furniture so it stays in view;
        # small ones (a pile of crates) may sit snug against it.
        if any((int(px), int(py)) in blocked_squares for px, py in (edge if r > 0.75 else edge[:1])):
            return False
        return all(math.hypot(x - tx, y - ty) >= r + tr + rule.gap for tx, ty, tr in taken)

    centres = []
    if rule.cluster > 1:
        k = max(1, int(math.ceil(n / rule.cluster)))
        for _ in range(k * 40):
            if len(centres) >= k:
                break
            cx, cy = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
            if free(cx, cy, 0) and all(math.hypot(cx - a, cy - b) > rule.spread * 1.5 for a, b in centres):
                centres.append((cx, cy))
        if not centres:
            warn(f"scatter '{name}': no free spot in '{rule.within}'.")
            return []

    out, art = [], None
    for i in range(n):
        a = choose(i) if (rule.vary or art is None) else art
        art = art or a
        k = rnd.uniform(*rule.scale)
        placed = False
        for _size_try in range(4):
            fw, fh = rule.size or (tuple(a.footprint) if a is not None and a.footprint else (1, 1))
            r = 0.5 * min(fw, fh) * k * 0.9
            for t in range(80):
                if centres:
                    cx, cy = centres[(i + t // 12) % len(centres)]     # a full clump hands on to the next
                    x, y = rnd.gauss(cx, rule.spread / 2), rnd.gauss(cy, rule.spread / 2)
                else:
                    x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
                if free(x, y, r):
                    placed = True
                    break
            if placed or rule.size or a is None:
                break
            # No room for art this big: try the next size down from the same pack (a smaller tree).
            a = index.smaller(name, a, "prop", seed=sc.seed + i)
            if a is None:
                break
        if not placed:
            continue
        taken.append((x, y, r))
        rot = {"any": rnd.uniform(0, 360), "square": rnd.choice([0, 90, 180, 270]), "none": 0.0}[rule.turn]
        if a is not None:
            layer = int(rule.layer) if rule.layer is not None else (4 if a.all_words & TALL_WORDS else 1)
        else:
            layer = int(rule.layer or 1)
        out.append(Placed(name, a, (x - fw / 2, y - fh / 2, x + fw / 2, y + fh / 2), rot, rule.label, layer, k))
    # A count is a promise; a density is a rough aim, so only a big shortfall is worth a warning.
    if len(out) < n and (rule.count is not None or len(out) < n / 2):
        warn(f"Only room for {len(out)} of {n} '{name}' in {rule.within}.")
    if out and all(p.asset is None for p in out):
        warn(f"No asset matches '{name}'; it is shown as a labelled box.")
    return out


# Forgotten Adventures sets ship joint pieces next to each *_Straight_Path strip.
JOINT_NAMES = {"corner": "Corner_A_1x1", "tee": "Joint_B_1x1", "cross": "Joint_A_1x1"}


def _wall_joints(walls, wall_asset: Asset | None, index: Index) -> list:
    """Corner, T and cross pieces from the wall's own set, where the pack has them."""
    if wall_asset is None or "Straight_Path" not in wall_asset.rel:
        return []
    pieces = {}
    for kind, name in JOINT_NAMES.items():
        rel = wall_asset.rel.replace("Straight_Path", name)
        pieces[kind] = next((a for a in index.assets if a.pack == wall_asset.pack and a.rel == rel), None)
    out = []
    for (x, y), arms in sorted(wall_junctions(walls).items()):
        kind, turns = joint_shape(arms)
        if kind and pieces.get(kind) is not None:
            out.append((x, y, pieces[kind], turns))
    return out


def _auto_place(room: Room, p: Prop, a, count, occupied, door_squares, rnd, warn, name):
    """Find spots inside a room: along a wall if asked, otherwise anywhere free."""
    (w, h), _ = _fit(a, p.size, p.rot)
    x0, y0, x1, y1 = room.box
    out = []
    side = str(p.along).lower() if p.along else None
    if side:
        rot = {"north": 0, "south": 180, "west": 270, "east": 90}[side] + p.rot
        if side in ("east", "west"):
            w, h = (h, w) if (a is None or not a.footprint or a.footprint[0] >= a.footprint[1]) and p.size is None else (w, h)
        if side in ("north", "south"):
            span = (x0, x1); length = w
        else:
            span = (y0, y1); length = h
        free = [t for t in range(int(span[0]), int(span[1] - length) + 1)]
        def spot(t):
            if side == "north": return (t, y0, t + w, y0 + h)
            if side == "south": return (t, y1 - h, t + w, y1)
            if side == "west": return (x0, t, x0 + w, t + h)
            return (x1 - w, t, x1, t + h)
        def ok(box):
            sq = {(x, y) for x in range(int(box[0]), int(math.ceil(box[2]))) for y in range(int(box[1]), int(math.ceil(box[3])))}
            return all(room.contains(x + 0.5, y + 0.5) for x, y in sq) and not (sq & occupied) and not (sq & door_squares)
        cands = [t for t in free if ok(spot(t))]
        if count > len(cands):
            warn(f"Only room for {len(cands)} of {count} '{name}' along the {side} wall of {room.name}.")
        # spread evenly
        picks = []
        if cands:
            n = min(count, len(cands))
            for k in range(n):
                idx = round((k + 0.5) * len(cands) / n - 0.5)
                t = cands[min(idx, len(cands) - 1)]
                box = spot(t)
                if ok(box):
                    picks.append(box)
                    occupied |= {(x, y) for x in range(int(box[0]), int(math.ceil(box[2]))) for y in range(int(box[1]), int(math.ceil(box[3])))}
        return [(b, rot) for b in picks]
    # anywhere free inside, kept off the walls where possible
    spots = []
    for y in range(int(y0), int(math.ceil(y1 - h)) + 1):
        for x in range(int(x0), int(math.ceil(x1 - w)) + 1):
            box = (x, y, x + w, y + h)
            sq = {(i, j) for i in range(x, int(math.ceil(x + w))) for j in range(y, int(math.ceil(y + h)))}
            if all(room.contains(i + 0.5, j + 0.5) for i, j in sq) and not (sq & occupied) and not (sq & door_squares):
                inner = x > x0 and y > y0 and x + w < x1 and y + h < y1
                spots.append((0 if inner else 1, rnd.random(), box, sq))
    spots.sort()
    for _, _, box, sq in spots:
        if len(out) >= count:
            break
        if sq & occupied:
            continue
        out.append((box, p.rot + (rnd.choice([0, 90, 180, 270]) if p.rot == 0 and w == h else 0)))
        occupied |= sq
    if len(out) < count:
        warn(f"Only room for {len(out)} of {count} '{name}' in {room.name}.")
    return out
