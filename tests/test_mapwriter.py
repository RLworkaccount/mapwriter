import json
from pathlib import Path

import pytest

from mapwriter.assets import naming
from mapwriter.assets.index import Index, describe
from mapwriter.geometry import merge_walls
from mapwriter.plan import build
from mapwriter.scene import Opening, SceneError, parse

HERE = Path(__file__).parent


@pytest.fixture(scope="session")
def starter(tmp_path_factory):
    from mapwriter.testart import build_pack
    d = tmp_path_factory.mktemp("starter")
    build_pack(d)
    return Index.build([str(d)])


@pytest.fixture(scope="session")
def fa_names():
    return [l for l in (HERE / "fa_names_sample.txt").read_text().splitlines() if l]


# ------------------------------------------------------------------ naming
def test_footprint_and_words():
    assert naming.footprint("Table_Wood_Walnut_A1_2x3.webp") == (2, 3)
    assert naming.footprint("Wooden_Flooring_G_Walnut.jpg") is None
    w = naming.words("Furniture/Tables/Table_Round_Wood_Ashen_A2_2x2.webp")
    assert "table" in w and "round" in w and "ashen" in w
    assert "a2" not in w and "2x2" not in w


def test_kinds():
    assert naming.kind_for("Structures/Building/Doors/Door_Wood_Walnut_D_1x1.webp") == "door"
    assert naming.kind_for("Structures/Building/Windows/Window_Wood_Ashen_K_1x1.webp") == "window"
    assert naming.kind_for("Walls_and_Curbs/Wall_Stone_A/Wall_Stone_Slate_A_Straight_Path.webp") == "wall"
    assert naming.kind_for("Textures/Wooden_Floors/Wooden_Flooring_J_Walnut.jpg") == "floor"
    assert naming.kind_for("Furniture/Seating/Chairs/Chair_Wood_Ashen_A_1x1.webp") == "prop"


def test_fa_sample_indexes(fa_names):
    idx = Index([describe(n, "FA", "/fa") for n in fa_names])
    kinds = idx.kinds()
    assert kinds.get("prop", 0) > 100
    for a in idx.assets:
        assert a.words, a.rel


def test_wall_search_prefers_straight_paths():
    names = ["W/Wall_Stone_Slate_A_Corner_A_1x1.webp", "W/Wall_Stone_Slate_A_Straight_Path.webp",
             "W/Wall_Brick_Slate_A_Straight_Path.webp", "W/Wall_Stone_Slate_A_Connector_A_1x1.webp"]
    idx = Index([describe(n, "FA", "/fa") for n in names])
    assert idx.search("stone wall", "wall")[0][1].rel.endswith("Wall_Stone_Slate_A_Straight_Path.webp")


def test_search_synonyms_and_size(starter):
    assert starter.pick("counter", size=(4, 1)).footprint == [4, 1]
    assert "shel" in starter.pick("bookcase").rel.lower()
    assert starter.pick("big table").footprint == [3, 2]
    assert starter.pick("dragon hoard") is None


def test_pack_order_breaks_ties(tmp_path):
    a = [describe("Chair_Wood_1x1.png", "First", "/a"), describe("Chair_Wood_1x1.png", "Second", "/b")]
    assert Index(a).pick("chair").pack == "First"
    assert Index(list(reversed(a))).pick("chair").pack == "Second"


def test_scan_reads_sizes_in_threads(tmp_path):
    from PIL import Image
    from mapwriter.assets.index import scan
    for i in range(40):
        Image.new("RGBA", (200 + i, 400)).save(tmp_path / f"Crate_{i:02d}.png")
    (tmp_path / "broken.png").write_bytes(b"not an image")
    assets = {a.rel: a for a in scan(tmp_path, workers=4)}
    assert assets["Crate_07.png"].px == [207, 400]
    assert assets["Crate_07.png"].footprint == [1, 2]
    assert assets["broken.png"].px is None
    assert all(a.px is None for a in scan(tmp_path, read_sizes=False))
def test_plain_furniture_beats_arrangements():
    names = ["Clutter/Table_Arrangements/Table_Arrangement_A89_3x2.webp",
             "Furniture/Tables/Table_Rectangle_Wood_Dark_B_3x2.webp"]
    idx = Index([describe(n, "FA", "/fa") for n in names])
    assert "Rectangle" in idx.pick("big table", size=(3, 2)).rel
    assert "Arrangement" in idx.pick("table arrangement").rel
    assert idx.pick("sofa") is None


# ------------------------------------------------------------------ scene
ROOMS = {
    "name": "Test", "grid": {"width": 12, "height": 8},
    "rooms": [
        {"name": "A", "box": [1, 1, 6, 7], "floor": "wood planks", "doors": [{"wall": "south", "at": 3}, {"wall": "east", "at": 3}]},
        {"name": "B", "box": [6, 1, 11, 7], "floor": "stone"},
    ],
    "props": [{"want": "chair", "at": [2, 2]}, {"want": "barrel", "in": "B", "count": 3}],
}


def test_parse_errors():
    with pytest.raises(SceneError, match="grid"):
        parse({"name": "x"})
    with pytest.raises(SceneError, match="does not fit"):
        parse({"grid": {"width": 5, "height": 5}, "rooms": [{"box": [0, 0, 4, 4], "doors": [{"wall": "north", "at": 4}]}]})
    with pytest.raises(SceneError, match="diagonal"):
        parse({"grid": {"width": 5, "height": 5}, "rooms": [{"shape": [[0, 0], [4, 0], [3, 4]]}]})
    with pytest.raises(SceneError, match="want"):
        parse({"grid": {"width": 5, "height": 5}, "props": [{"at": [1, 1]}]})


def test_shared_wall_door_cut(starter):
    plan = build(parse(ROOMS), starter)
    # the shared wall x=6 runs 1..7 with a door 3..4 cut out of it
    x6 = sorted((y0, y1) for x0, y0, x1, y1 in plan.walls if x0 == x1 == 6)
    assert x6 == [(1, 3), (4, 7)]
    assert not plan.warnings, plan.warnings
    assert sum(1 for p in plan.props if p.want == "barrel") == 3


def test_unreachable_room_is_reported(starter):
    data = json.loads(json.dumps(ROOMS))
    data["rooms"][0]["doors"] = [{"wall": "south", "at": 3}]
    plan = build(parse(data), starter)
    assert any("'B' has no way in" in w for w in plan.warnings)


def test_merge_walls_windows_stay_for_painting():
    raw = [(0, 0, 5, 0)]
    win = Opening((2, 0), (3, 0), "window")
    assert merge_walls(raw, []) == [(0, 0, 5, 0)]
    assert merge_walls(raw, [win]) == [(0, 0, 2, 0), (3, 0, 5, 0)]


def test_auto_lights_from_props(starter):
    data = json.loads(json.dumps(ROOMS))
    data["props"].append({"want": "lantern", "at": [3, 4]})
    plan = build(parse(data), starter)
    assert any(abs(L.at[0] - 3.5) < 1e-6 for L in plan.lights)


# ------------------------------------------------------------------ export and render
def test_uvtt_structure(starter):
    from mapwriter.export.uvtt import uvtt_data
    data = json.loads(json.dumps(ROOMS))
    data["rooms"][1]["windows"] = [{"wall": "north", "at": 8}]
    plan = build(parse(data), starter)
    d = uvtt_data(plan, None)
    assert d["format"] == 0.3
    assert d["resolution"]["map_size"] == {"x": 12, "y": 8}
    closed = [p["closed"] for p in d["portals"]]
    assert closed.count(True) == 2 and closed.count(False) == 1
    for line in d["line_of_sight"]:
        for a, b in zip(line, line[1:]):
            assert abs(a["x"] - b["x"]) + abs(a["y"] - b["y"]) >= 0.4


def test_render_end_to_end(starter, tmp_path):
    from mapwriter.build import render_all, write_sketch
    data = json.loads(json.dumps(ROOMS))
    data["grid"]["px_per_square"] = 40
    plan = build(parse(data), starter)
    out = render_all(plan, tmp_path)
    write_sketch(plan, tmp_path, px=24)
    assert out["day image"].exists() and out["night image"].exists() and out["key"].exists()
    from PIL import Image
    assert Image.open(out["day image"]).size == (12 * 40, 8 * 40)


def test_examples_parse_and_plan(starter):
    from mapwriter.scene import load
    for ex in (HERE.parent / "examples").glob("*.yaml"):
        plan = build(load(ex), starter)
        missing = [p.want for p in plan.props if p.asset is None]
        assert not missing, f"{ex.name}: starter pack lacks {missing}"


def test_cli_smoke(tmp_path, capsys):
    from mapwriter.cli import main
    main(["starter-pack", str(tmp_path / "pack")])
    main(["index", str(tmp_path / "pack"), "-o", str(tmp_path / "i.json")])
    main(["search", "round table", "-i", str(tmp_path / "i.json")])
    assert "Table_Round" in capsys.readouterr().out


def test_light_is_cast_against_walls():
    from mapwriter.geometry import light_area
    from PIL import Image, ImageDraw

    def lit(area, x, y):
        m = Image.new("L", (200, 200), 0)
        ImageDraw.Draw(m).polygon([(px * 10, py * 10) for px, py in area], fill=255)
        return m.getpixel((int(x * 10), int(y * 10))) > 0

    wall = [(10, 0, 10, 20)]
    area = light_area((5, 10), wall, 8)
    assert lit(area, 8, 10) and not lit(area, 12, 10)
    # a one-square gap in the wall lets light through in a narrow beam
    gap = [(10, 0, 10, 9.5), (10, 10.5, 10, 20)]
    area = light_area((5, 10), gap, 8)
    assert lit(area, 12, 10) and not lit(area, 12, 14)


def test_open_doors_and_windows_let_light_out(starter):
    scene = parse({
        "name": "Spill", "grid": {"width": 12, "height": 8},
        "rooms": [{"name": "A", "box": [1, 1, 6, 7], "floor": "wood planks",
                   "doors": [{"wall": "east", "at": 3, "open": True}, {"wall": "south", "at": 3}],
                   "windows": [{"wall": "north", "at": 3}]}],
        "lights": [{"at": [3.5, 3.5], "radius": 6}],
    })
    plan = build(scene, starter)
    xs = [p[0] for p in plan.light_areas[0]]
    ys = [p[1] for p in plan.light_areas[0]]
    assert max(xs) > 7          # through the open east door
    assert min(ys) < 0.5        # through the north window
    assert max(ys) <= 7.01      # the closed south door blocks
def test_wall_junctions_and_joint_pieces():
    from mapwriter.geometry import joint_shape, wall_junctions
    # a box split by an inner wall: four corners and two T-joints
    walls = [(0, 0, 10, 0), (0, 6, 10, 6), (0, 0, 0, 6), (10, 0, 10, 6), (5, 0, 5, 6)]
    j = wall_junctions(walls)
    assert joint_shape(j[(0, 0)]) == ("corner", 0)      # arms east and south
    assert joint_shape(j[(10, 0)]) == ("corner", 1)     # south and west
    assert joint_shape(j[(10, 6)]) == ("corner", 2)
    assert joint_shape(j[(0, 6)]) == ("corner", 3)
    assert joint_shape(j[(5, 0)]) == ("tee", 0)         # west, east and south
    assert joint_shape(j[(5, 6)]) == ("tee", 2)         # west, east and north
    assert joint_shape({"N", "E", "S", "W"}) == ("cross", 0)
    assert len(j) == 6


def test_fa_wall_set_gives_joint_pieces():
    from mapwriter.plan import _wall_joints
    base = "Walls/Wall_Stone_A/Wall_Stone_Slate_A_"
    idx = Index([describe(base + n + ".webp", "FA", "/fa")
                 for n in ("Straight_Path", "Corner_A_1x1", "Joint_A_1x1", "Joint_B_1x1")])
    strip = idx.assets[0]
    joints = _wall_joints([(0, 0, 4, 0), (0, 0, 0, 4)], strip, idx)
    assert [(x, y, a.name, k) for x, y, a, k in joints] == [(0, 0, "Wall_Stone_Slate_A_Corner_A_1x1.webp", 0)]
    assert _wall_joints([(0, 0, 4, 0), (0, 0, 0, 4)], None, idx) == []


# ------------------------------------------------------------------ outdoors (v0.2)
OUTDOOR = {"name": "Green", "grid": {"width": 16, "height": 12, "px_per_square": 40}, "ground": "grass",
           "areas": [{"name": "pond lawn", "circle": [8, 6, 3], "floor": "cobblestone", "rough": 0.4},
                     {"name": "slope", "shape": [[0, 0], [5, 0], [1, 4]], "floor": "dirt", "smooth": True}],
           "paths": [{"name": "lane", "points": [[0, 10], [6, 9], [16, 11]], "width": 2, "floor": "dirt path"}]}


def test_outdoor_areas_and_paths_parse():
    sc = parse(OUTDOOR)
    assert len(sc.areas[0].poly) == 48                   # circle outline
    assert sc.areas[1].poly[2] == (1.0, 4.0)             # diagonal edges are fine for areas
    assert sc.paths[0].width == 2 and sc.paths[0].curve
    bad = json.loads(json.dumps(OUTDOOR))
    bad["paths"][0]["points"] = [[1, 1]]
    with pytest.raises(SceneError, match="at least two points"):
        parse(bad)
    bad = json.loads(json.dumps(OUTDOOR)); bad["areas"][0]["circle"] = [1, 2]
    with pytest.raises(SceneError, match="circle"):
        parse(bad)
    bad = {"name": "x", "grid": {"width": 4, "height": 4}, "rooms": [{"name": "r", "shape": [[0, 0], [3, 0], [0, 3]]}]}
    with pytest.raises(SceneError, match="diagonal"):
        parse(bad)                                       # rooms still need square walls


def test_rough_edges_and_path_strips_in_plan(starter):
    plan = build(parse(OUTDOOR), starter)
    names = [f.name for f in plan.floors]
    assert names == ["ground", "lane", "pond lawn", "slope"]   # paths go under areas
    lawn = plan.floors[2].region
    radii = [((x - 8) ** 2 + (y - 6) ** 2) ** 0.5 for x, y in lawn.poly]
    assert 2.5 < min(radii) < 3 < max(radii) < 3.5             # the edge wanders, but not far
    assert lawn.contains(8, 6) and not lawn.contains(8, 1)
    lane = plan.floors[1].region
    assert lane.poly is None and lane.contains(6, 9) and not lane.contains(6, 5)
    assert all(0.5 < r < 1.5 for r in lane.radii)
    again = build(parse(OUTDOOR), starter)                     # same seed, same edges
    assert again.floors[2].region.poly == lawn.poly


def test_outdoor_render(starter, tmp_path):
    from mapwriter.build import render_all, write_sketch
    plan = build(parse(OUTDOOR), starter)
    out = render_all(plan, tmp_path, uvtt=False)
    write_sketch(plan, tmp_path, px=20)
    from PIL import Image
    im = Image.open(out["day image"]).convert("RGB")
    lane, lawn = im.getpixel((6 * 40, 9 * 40 + 20)), im.getpixel((8 * 40, 6 * 40))
    grass = im.getpixel((14 * 40, 2 * 40))
    assert lane != grass and lawn != grass


def test_water_with_banks(starter):
    data = json.loads(json.dumps(OUTDOOR))
    data["water"] = [{"name": "pond", "circle": [4, 4, 2]},
                     {"name": "brook", "points": [[0, 7], [16, 7]], "width": 1, "bank": False},
                     {"name": "moat", "box": [10, 1, 14, 3], "bank": {"floor": "dirt", "width": 1}, "rough": 0}]
    plan = build(parse(data), starter)
    by = {f.name: f for f in plan.floors}
    assert [f.name for f in plan.floors if f.water] == ["pond", "brook", "moat"]
    assert "brook bank" not in by and by["moat bank"].want == "dirt"
    pond, bank = by["pond"].region, by["pond bank"].region
    assert pond.contains(4, 4) and bank.contains(4, 4)
    # The bank reaches past the water all the way round, and the water stays near its circle.
    edge = [((x - 4) ** 2 + (y - 4) ** 2) ** 0.5 for x, y in bank.poly]
    water = [((x - 4) ** 2 + (y - 4) ** 2) ** 0.5 for x, y in pond.poly]
    assert min(edge) > 2.0 and 1.5 < min(water) and max(water) < 2.5
    assert by["moat bank"].region.contains(12, 0.3) and not by["moat"].region.contains(12, 0.3)
    with pytest.raises(SceneError, match="at least two points"):
        parse({**data, "water": [{"name": "x", "points": [[1, 1]]}]})


def test_resample_spacing():
    from mapwriter.geometry import resample
    pts = resample([(0, 0), (0.01, 0), (0.02, 0), (4, 0)], 0.5, False)
    gaps = [b[0] - a[0] for a, b in zip(pts, pts[1:])]
    assert len(pts) == 9 and max(gaps) - min(gaps) < 1e-9


def test_scatter_and_clumps(starter):
    data = json.loads(json.dumps(OUTDOOR))
    data["rooms"] = [{"name": "Store", "box": [11, 0, 16, 4], "doors": [{"wall": "south", "at": 13}]}]
    data["scatter"] = [{"want": "bush", "count": 12, "cluster": 4, "spread": 1.5},
                       {"want": "crate", "in": "Store", "count": 5, "cluster": 5, "spread": 0.8, "gap": -0.05},
                       {"want": "rock", "in": "pond lawn", "density": 0.3, "turn": "square"}]
    plan = build(parse(data), starter)
    by = {}
    for p in plan.props:
        by.setdefault(p.want, []).append(p)
    lane = next(f.region for f in plan.floors if f.name == "lane")
    store = parse(data).rooms[0]
    lawn = next(f.region for f in plan.floors if f.name == "pond lawn")
    assert len(by["bush"]) == 12
    for p in by["bush"]:                     # open ground: off the lane, the lawn and the store
        assert not lane.contains(*p.centre) and not lawn.contains(*p.centre) and not store.contains(*p.centre)
    assert len(by["crate"]) == 5 and all(store.contains(*p.centre) for p in by["crate"])
    xs = [p.centre[0] for p in by["crate"]]
    assert max(xs) - min(xs) < 4             # one pile, not spread round the room
    assert by["rock"] and all(lawn.contains(*p.centre) and p.rot % 90 == 0 for p in by["rock"])
    again = build(parse(data), starter)
    assert [p.box for p in again.props] == [p.box for p in plan.props]
    with pytest.raises(SceneError, match="count"):
        parse({**data, "scatter": [{"want": "rock"}]})
    plan = build(parse({**data, "scatter": [{"want": "rock", "in": "nowhere", "count": 2}]}), starter)
    assert any("nowhere" in w for w in plan.warnings)


def test_pack_check_and_credits(tmp_path, starter):
    from PIL import Image
    from mapwriter.assets.packcheck import check_pack
    from mapwriter.build import credits
    pack = tmp_path / "2MT Garden"
    (pack / "Props").mkdir(parents=True)
    for name, size in (("Barrel 1.png", (256, 256)), ("Crate (Small) 2.png", (250, 262)),
                       ("Cart 3x2.png", (768, 512)), ("01.png", (256, 256))):
        Image.new("RGBA", size).save(pack / "Props" / name)
    r = check_pack(pack, write=True, credit="2-Minute Tabletop, CC BY-NC 4.0")
    assert r["ppsq"] == 256 and "Props/01.png" in r["vague"]
    text = (pack / "mapwriter-pack.yaml").read_text()
    assert "px_per_square: 256" in text and "CC BY-NC" in text
    idx = Index.build([str(pack)])
    cart = idx.get("Cart 3x2.png")
    assert cart.footprint == [3, 2] and cart.credit == "2-Minute Tabletop, CC BY-NC 4.0"
    assert idx.get("Barrel 1.png").footprint == [1, 1]
    scene = parse({"name": "x", "grid": {"width": 6, "height": 6}, "ground": "grass",
                   "props": [{"want": "cart", "at": [1, 1]}]})
    mixed = Index(starter.assets + idx.assets)
    assert credits(build(scene, mixed)) == ["2-Minute Tabletop, CC BY-NC 4.0"]


# ------------------------------------------------------------------ outdoor picks in big packs
FA_OUTDOOR = [
    "Woodlands/!Wilderness/Textures/Dirt/Dirt_A_01.jpg",
    "!Core_Settlements/Textures/Stone_Floors/Flat_Stone_Floor_A_Dirt.jpg",
    "!Core_Settlements/Structures/Building/Wooden_Walkway_Tiles/Paths/Walkway_Small_Wood_Ashen_A1_Path.webp",
    "!Core_Settlements/Decor/Holidays/Christmas/Christmas_Trees/Christmas_Tree_01_A1_3x3.webp",
    "Woodlands/!Wilderness/Flora/Trees/Tree_Green_A1_6x6.webp",
    "Woodlands/!Wilderness/Flora/Trees/Tree_Green_B1_5x5.webp",
    "Woodlands/!Wilderness/Flora/Trees/Tree_Red_A1_6x6.webp",
    "Woodlands/!Wilderness/Flora/Trees/Tree_Red_B1_5x5.webp",
    "Feywilds/!Wilderness/Flora/Bushes/Bush_Multicolor2_A1_1x1.webp",
    "Woodlands/!Wilderness/Flora/Bushes/Bush_Green_A1_1x1.webp",
    "Volcanic/!Wilderness/Decor/Rocks/Rock_Stone_Volcanic_B10_1x1.webp",
    "Mountain/!Wilderness/Decor/Rocks/Rock_Stone_Earthy_A10_1x1.webp",
    "!Core_Settlements/Decor/Storage/Boxes_and_Crates/Crates/Crate_Lid_Wood_Ashen_A_2x1.webp",
    "!Core_Settlements/Decor/Storage/Boxes_and_Crates/Crates/Crate_Wood_Ashen_A_1x1.webp",
    "!Core_Settlements/Decor/Storage/Boxes_and_Crates/Luggage/Box_Luggage_Base_Leather_Blue_A10_1x1.webp",
    "!Core_Settlements/Combat/Armor/Armor_Stands/Armor_Stand_Wood_Ashen_A1_1x1.webp",
    "Woodlands/!Wilderness/Flora/Flowers/Flowers_Rose_Red_A1_1x1.webp",
    "Woodlands/!Wilderness/Flora/Flowers/Flowers_Rose_Blue_A1_1x1.webp",
    "!Core_Settlements/Clutter/!Arranged_Clutter/Flowers/Arranged_Flowers_A1_1x1.webp",
]


def test_outdoor_words_find_plain_outdoor_art():
    idx = Index([describe(n, "FA", "/fa") for n in FA_OUTDOOR])
    assert idx.pick("dirt path", "floor").name == "Dirt_A_01.jpg"        # not a wooden *_Path strip or a dirty floor
    assert idx.pick("dirt road", "floor").name == "Dirt_A_01.jpg"
    assert "Tree_Green" in idx.pick("oak tree").name                      # not a Christmas tree or autumn red
    assert "Christmas" in idx.pick("christmas tree").name
    assert "Tree_Red" in idx.pick("red tree").name
    assert "Bush_Green" in idx.pick("bush").name
    assert "Earthy" in idx.pick("rock").name
    assert idx.pick("crate").name == "Crate_Wood_Ashen_A_1x1.webp"        # not a lid or a suitcase
    assert idx.pick("market stall") is None                               # an armour stand is not a stall
    assert "Arranged" not in idx.pick("flowers").name


def test_first_pack_with_the_real_thing_wins(tmp_path):
    fa = [describe(n, "FA", "/fa") for n in FA_OUTDOOR]
    fill = [describe(n, "Starter", "/s") for n in ("Oak_Tree_3x3.png", "Market_Stall_Red_3x2.png", "Booth_2x2.png")]
    idx = Index(fa + fill)
    assert idx.pick("oak tree").pack == "FA"              # 'oak' is only in the fill-in pack's name, but FA has trees
    assert idx.pick("market stall").pack == "Starter"     # FA has none, so the fill-in pack supplies it
    booth = Index(fill[2:]).pick("stall")
    assert booth.name == "Booth_2x2.png" and Index(fill[2:]).loose("stall", booth)
    assert not idx.loose("market stall", idx.pick("market stall"))


def test_scatter_keeps_one_family_and_mixes_flower_colours():
    idx = Index([describe(n, "FA", "/fa") for n in FA_OUTDOOR])
    trees = {idx.pick("tree", seed=s, family_seed=3).name.split("_")[1] for s in range(12)}
    assert trees == {"Green"}
    roses = {idx.pick("flowers", seed=s, family_seed=3).name for s in range(30)}
    assert any("Red" in r for r in roses) and any("Blue" in r for r in roses)


def test_scatter_keeps_canopies_off_buildings_and_furniture(starter):
    data = json.loads(json.dumps(OUTDOOR))
    data["rooms"] = [{"name": "Hut", "box": [8, 4, 14, 10], "doors": [{"wall": "south", "at": 10}]}]
    data["props"] = [{"want": "big table", "at": [2, 2], "size": [3, 2]}]
    data["scatter"] = [{"want": "oak tree", "count": 8, "size": [3, 3], "gap": -0.5}]
    plan = build(parse(data), starter)
    hut = parse(data).rooms[0]
    for p in plan.props:
        if p.want != "oak tree":
            continue
        x0, y0, x1, y1 = p.box
        assert x1 <= 8 or x0 >= 14 or y1 <= 4 or y0 >= 10 or not any(
            hut.contains(x, y) for x in (x0 + 0.3, x1 - 0.3) for y in (y0 + 0.3, y1 - 0.3))
        assert not (x0 < 4.5 and y0 < 3.5 and x1 > 2.5 and y1 > 2.5)     # the table stays in view


# ------------------------------------------------------------------ 2-Minute Tabletop style packs
def test_2mt_names_dpi_folders_and_sized_textures(tmp_path):
    from PIL import Image
    from mapwriter.assets.index import scan
    files = {"Assets - 300 DPI/Bush 2 - Green 1.png": (300, 300), "Assets - 70 DPI (Roll20)/Bush 2 - Green 1.png": (70, 70),
             "Assets - 300 DPI/Storage - Crate 1 - Dark.png": (300, 300), "Assets - 300 DPI/Chair - Armchair 1.a.png": (300, 300),
             "Assets - 300 DPI/Chair - Simple 1 - Dark.png": (300, 300), "Assets/8x8 dirt texture.jpg": (800, 800),
             "Assets/Water Tile 1 (8x8).jpg": (800, 800), "Assets/Rapids 1 (5x3).png": (500, 300),
             "Assets - 300 DPI/Tree Stump 1 - Tree.png": (300, 300)}
    for rel, size in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", size).save(tmp_path / rel)
    assets = scan(tmp_path, pack="2MT")
    by = {a.rel: a for a in assets}
    assert "Assets - 70 DPI (Roll20)/Bush 2 - Green 1.png" not in by           # the sharper copy is kept
    assert by["Assets - 300 DPI/Bush 2 - Green 1.png"].ppsq == 300
    assert by["Assets - 300 DPI/Bush 2 - Green 1.png"].footprint == [1, 1]
    dirt, water = by["Assets/8x8 dirt texture.jpg"], by["Assets/Water Tile 1 (8x8).jpg"]
    assert dirt.kind == water.kind == "floor" and dirt.ppsq == water.ppsq == 100
    assert by["Assets/Rapids 1 (5x3).png"].footprint == [5, 3]
    idx = Index(assets)
    assert idx.pick("crate").name == "Storage - Crate 1 - Dark.png"
    assert idx.pick("chair").name == "Chair - Simple 1 - Dark.png"             # a plain chair before an armchair
    assert idx.pick("dirt path", "floor") is dirt and idx.pick("water", "floor") is water
    stump = idx.pick("oak tree")
    assert idx.loose("oak tree", stump)                                         # a stump is only part of a tree
    fill = Index(assets + [describe("Oak_Tree_3x3.png", "Starter", "/s")])
    assert fill.pick("oak tree").pack == "Starter"


# ------------------------------------------------------------------ v0.3: templates, briefs, replies
def test_templates_make_clean_scenes(starter):
    from mapwriter import templates
    from mapwriter.yamlout import dump
    import yaml
    for kind in templates.names():
        seen = set()
        for option in range(3):
            data = templates.make(kind, option, seed=1)
            text = dump(data)
            assert yaml.safe_load(text) == data
            plan = build(parse(data), starter)
            assert not plan.warnings, (kind, option, plan.warnings)
            seen.add(text)
        assert len(seen) == 3, f"{kind}: the three options should differ"
    with pytest.raises(ValueError):
        templates.make("spaceship")
    assert templates.make("inn")["rooms"]       # aliases work


def test_tavern_template_seats_chairs_at_tables():
    from mapwriter import templates
    props = templates.make("tavern", 0)["props"]
    tables = {tuple(p["at"]) for p in props if p["want"] == "round table"}
    chairs = [p for p in props if p["want"] == "chair" and "at" in p]
    assert tables and chairs
    for c in chairs:
        x, y = c["at"]
        assert (x + 1, y) in tables or (x - 1, y) in tables
        assert c["rot"] == (270 if (x + 1, y) in tables else 90)     # facing the table


def test_new_writes_options_and_sheet(tmp_path, starter):
    from mapwriter import templates
    from mapwriter.talk import write_options
    scenes = [("", templates.make("shop", i)) for i in range(3)]
    res = write_options(scenes, starter, tmp_path, "shop")
    assert [p.name for p in res["files"]] == ["shop-a.yaml", "shop-b.yaml", "shop-c.yaml"]
    assert res["sheet"].exists()


def test_describe_brief_has_words_and_template(starter):
    from mapwriter.talk import describe_brief, guess_template
    assert guess_template("a smoky old inn on the moor") == "tavern"
    assert guess_template("a mossy glade") == "clearing"
    b = describe_brief("a smoky old inn on the moor", starter, options=3)
    assert "3 different layouts" in b and "The Wayside Inn" in b
    assert "barrel" in b and "Scene format" in b
    assert "seating" not in b.split("## Words")[1].split("##")[0]     # folder names left out


def test_reply_parsing_and_fix_brief(tmp_path, starter):
    from mapwriter import templates
    from mapwriter.talk import scenes_in_reply, write_options, fix_brief
    from mapwriter.yamlout import dump
    good = dump(templates.make("house", 0))
    bad = good.replace("grid: { width: 16", "grid: { width: x16")
    reply = (f"Two layouts.\n\nA:\n```yaml\n{good}```\nB:\n```yaml\n{bad}```\n"
             "A snippet:\n```yaml\nprops: [{want: chair}]\n```\nBroken:\n```yaml\ngrid: [\n```\n")
    found = scenes_in_reply(reply)
    assert len(found) == 3                                 # the snippet is skipped
    assert found[2][1] is None and "YAML" in found[2][2]
    res = write_options([(t, d) for t, d, e in found if d], starter, tmp_path, "home", keep_text=True)
    assert res["files"][0].read_text() == good
    fb = fix_brief(res["problems"])
    assert fb and "home-b.yaml" in fb and "home-a.yaml" not in fb


def test_apply_edit_keeps_previous(tmp_path, starter):
    from mapwriter import templates
    from mapwriter.talk import apply_edit, edit_brief
    from mapwriter.yamlout import dump
    p = tmp_path / "house.yaml"
    p.write_text(dump(templates.make("house", 1)))
    brief = edit_brief(p, "a bigger bedroom", starter)
    assert "a bigger bedroom" in brief and "Miller's Cottage" in brief
    new = p.read_text().replace("seed: 2", "seed: 9")
    r = apply_edit(f"Changed the seed.\n```yaml\n{new}```", p, starter, tmp_path)
    assert p.read_text() == new and r["previous"].exists()
    assert any("seed: 9" in l for l in r["changed_lines"]) and r["sheet"].exists()
    with pytest.raises(SceneError):
        apply_edit("no yaml here", p, starter, tmp_path)


def test_cli_new_describe_apply(tmp_path, capsys, starter):
    from mapwriter.cli import main
    idx = tmp_path / "i.json"; starter.save(idx)
    main(["new", "clearing", "-o", str(tmp_path / "s"), "-n", "2", "-i", str(idx)])
    assert (tmp_path / "s" / "clearing-b.yaml").exists() and (tmp_path / "s" / "clearing-options.png").exists()
    main(["describe", "a fishing village market", "-o", str(tmp_path / "s"), "-i", str(idx)])
    assert "market" in (tmp_path / "s" / "brief.md").read_text()
    reply = tmp_path / "reply.md"
    reply.write_text("```yaml\n" + (tmp_path / "s" / "clearing-a.yaml").read_text() + "```\n")
    main(["apply", str(reply), "-o", str(tmp_path / "r"), "-i", str(idx)])
    out = capsys.readouterr().out
    assert "no problems" in out


def test_layered_base_gets_its_top(starter):
    a = starter.pick("well")
    assert a is not None and "Base" in a.rel
    top = starter.top_piece(a)
    assert top is not None and "Top" in top.rel
    sc = parse({"name": "w", "grid": {"width": 6, "height": 6}, "props": [{"want": "well", "at": [2, 2]}]})
    plan = build(sc, starter)
    assert [p.part for p in plan.props] == ["", "top"]
    assert plan.props[1].layer > plan.props[0].layer and not plan.props[1].shadow
    sc = parse({"name": "w", "grid": {"width": 6, "height": 6}, "props": [{"want": "well", "at": [2, 2], "top": False}]})
    assert len(build(sc, starter).props) == 1


def test_top_piece_matches_fa_names(fa_names):
    idx = Index([describe(n, "FA", "/fa") for n in fa_names])
    base = next(a for a in idx.assets if "Display_Case_Base_Wood_Dark_C_2x2" in a.rel)
    top = idx.top_piece(base)
    assert top is not None and "Display_Case_Top" in top.rel and top.footprint == [2, 2]


def test_uvtt_foundry_fixes(starter):
    from mapwriter.export.uvtt import uvtt_data, LIGHT_SCALE
    sc = parse({"name": "d", "grid": {"width": 10, "height": 8},
                "rooms": [{"name": "Hall", "box": [1, 1, 9, 7],
                           "doors": [{"wall": "south", "at": 3, "kind": "double"}, {"wall": "north", "at": 4, "kind": "secret"}],
                           "windows": [{"wall": "east", "at": 3}]}],
                "lights": [{"at": [5, 4], "intensity": 0.8}]})
    d = uvtt_data(build(sc, starter), None)
    doors = [p for p in d["portals"] if p["closed"]]
    assert len(doors) == 2                                  # the double door is two leaves; the secret door is not a portal
    assert {(p["bounds"][0]["x"], p["bounds"][1]["x"]) for p in doors} == {(3, 4), (4, 5)}
    assert len([p for p in d["portals"] if not p["closed"]]) == 1
    assert d["lights"][0]["intensity"] == pytest.approx(0.8 * LIGHT_SCALE)


def test_uvtt_per_version_lights_and_ambient(starter):
    from mapwriter.export.uvtt import uvtt_data
    sc = parse({"name": "d", "grid": {"width": 10, "height": 8},
                "lighting": {"versions": ["day", "night"], "day": {"ambient": [250, 240, 220]}, "night": {"ambient": [60, 70, 120]}},
                "lights": [{"at": [2, 2]}, {"at": [5, 5], "when": "night", "colour": "moon"}]})
    plan = build(sc, starter)
    day, night = uvtt_data(plan, None, version="day"), uvtt_data(plan, None, version="night")
    assert len(day["lights"]) == 1 and len(night["lights"]) == 2      # the night-only moon stays out of the day file
    assert day["environment"]["ambient_light"] == "fffaf0dc"
    assert night["environment"]["ambient_light"] == "ff3c4678"


def test_sketch_light_rings_optional(starter):
    from mapwriter.render.sketch import sketch
    sc = parse({"name": "l", "grid": {"width": 8, "height": 8}, "lights": [{"at": [4, 4], "radius": 3}]})
    plan = build(sc, starter)
    with_rings, without = sketch(plan, 24), sketch(plan, 24, rings=False)
    assert with_rings.size == without.size and with_rings.tobytes() != without.tobytes()


def test_plural_folding():
    assert naming.singular("bushes") == "bush" and naming.singular("benches") == "bench" and naming.singular("boxes") == "box"


# ------------------------------------------------------------------ wall looks: glass, hedges, fences
def test_wall_looks_glass_hedges_and_fences(starter):
    from mapwriter.export.uvtt import uvtt_data
    from mapwriter.render.painter import Painter
    data = {"name": "Looks", "grid": {"width": 14, "height": 10, "px_per_square": 20}, "ground": "grass",
            "rooms": [{"name": "Glasshouse", "box": [1, 1, 6, 6], "see_through": True,
                       "doors": [{"wall": "south", "at": 3}]},
                      {"name": "Pen", "box": [8, 1, 12, 5], "walls": "wood fence"}],
            "walls": [{"points": [[1, 8], [6, 8], [6, 9]], "style": "hedge", "thickness": 1}],
            "lights": [{"at": [3.5, 3.5], "radius": 6}]}
    sc = parse(data)
    assert len(sc.walls) == 2 and sc.wall_looks[0].thickness == 1.0     # a polyline becomes two walls
    plan = build(sc, starter)
    glass = set(plan.see_through_walls)
    assert len(glass) == 8                                              # the glasshouse, plus the fence (by its words)
    assert any(ws.thickness == 1.0 and not ws.see_through for ws in plan.wall_sets)
    # Light passes the glass: the light reaches well past the glasshouse walls.
    xs = [x for x, _ in plan.light_areas[0]]
    assert max(xs) > 7 and min(xs) < 0.5
    d = uvtt_data(plan, None)
    windows = [p for p in d["portals"] if not p["closed"]]
    assert len(windows) >= 8                                            # glass and fence sides, door gap cut out
    los_points = [pt for line in d["line_of_sight"] for pt in line]
    assert not any(pt["x"] == 1 and 1 < pt["y"] < 6 for pt in los_points)  # glass is not a sight-blocking wall
    Painter(plan).walls()                                                # paints each set at its own thickness


def test_scatter_inside_an_area_within_a_walled_room(starter):
    data = {"name": "Beds", "grid": {"width": 12, "height": 10, "px_per_square": 20}, "ground": "grass",
            "rooms": [{"name": "Glasshouse", "box": [1, 1, 11, 9], "doors": [{"wall": "south", "at": 5}]}],
            "areas": [{"name": "bed", "box": [2, 2, 6, 5], "floor": "dirt"}],
            "scatter": [{"want": "bush", "in": "bed", "count": 4}]}
    plan = build(parse(data), starter)
    assert sum(p.want == "bush" for p in plan.props) == 4, plan.warnings


def test_wall_look_errors():
    base = {"name": "x", "grid": {"width": 6, "height": 6}}
    with pytest.raises(SceneError):
        parse({**base, "walls": [{"points": [[0, 0], [2, 2]]}]})
    with pytest.raises(SceneError):
        parse({**base, "walls": [{"from": [0, 0], "to": [2, 0], "thickness": "thick"}]})
    with pytest.raises(SceneError):
        parse({**base, "rooms": [{"name": "r", "box": [0, 0, 3, 3], "see_through": "yes"}]})


# ------------------------------------------------------------------ fixes from map-making sessions
def test_small_scale_prefers_single_square_art():
    names = ["Props/Carts/Handcart_Apples_3x2.webp", "Food/Fruit/Apple_Red_1x1.webp",
             "Market/Stalls/Stall_Bread_3x2.webp", "Food/Bread/Bread_Loaf_1x1.webp"]
    idx = Index([describe(n, "FA", "/fa") for n in names])
    assert idx.pick("apple", small=True).footprint == [1, 1]
    assert idx.pick("bread", small=True).footprint == [1, 1]
    sc = parse({"name": "s", "grid": {"width": 8, "height": 8},
                "props": [{"want": "apple", "at": [1, 1], "scale": 0.5}, {"want": "bread", "at": [3, 3], "scale": 0.6}]})
    plan = build(sc, idx)
    assert all(pl.asset.footprint == [1, 1] for pl in plan.props)


def test_small_scale_keeps_big_art_when_no_small_match():
    idx = Index([describe("Props/Carts/Handcart_Apples_3x2.webp", "FA", "/fa")])
    assert idx.pick("apple", small=True).footprint == [3, 2]


def test_roof_textures_work_as_floors():
    names = ["Textures/Roof_Thatch_A.webp", "Textures/Wooden_Flooring_Oak.webp"]
    idx = Index([describe(n, "FA", "/fa") for n in names])
    assert idx.assets[0].kind == "roof"
    for want in ("thatch roof", "thatch"):
        sc = parse({"name": "r", "grid": {"width": 6, "height": 6},
                    "rooms": [{"name": "loft", "box": [1, 1, 4, 4], "floor": want, "walls": "none"}]})
        plan = build(sc, idx)
        loft = next(f for f in plan.floors if f.name == "loft")
        assert loft.asset is not None and "Roof_Thatch" in loft.asset.rel, want
        assert not any(f"'{want}'" in w for w in plan.warnings), plan.warnings


def test_overlap_ok_silences_overlap_warning(starter):
    def warnings(extra):
        sc = parse({"name": "o", "grid": {"width": 10, "height": 8},
                    "props": [{"want": "market stall", "at": [2, 2]}, dict({"want": "counter", "at": [2, 3], "size": [3, 1]}, **extra)]})
        return [w for w in build(sc, starter).warnings if "overlaps" in w]
    assert warnings({})
    assert not warnings({"overlap": "ok"})
    assert not warnings({"layer": 2})


# ------------------------------------------------------------------ v0.4: picking by the pictures
def _pack(root, files):
    """Draw simple test pictures: name -> (size in px, function drawing on an RGBA image)."""
    from PIL import Image, ImageDraw
    for rel, (size, draw) in files.items():
        p = Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        im = Image.new("RGBA", size, (0, 0, 0, 0))
        draw(ImageDraw.Draw(im), im)
        im.save(p)
    return str(root)


def _blob(colour, r=0.35):
    def draw(d, im):
        w, h = im.size
        d.ellipse([w * (0.5 - r), h * (0.5 - r), w * (0.5 + r), h * (0.5 + r)], fill=colour)
    return draw


def _cart(d, im):
    w, h = im.size
    d.rectangle([w * 0.05, h * 0.1, w * 0.95, h * 0.9], fill=(120, 80, 45))
    for i in range(4):
        d.ellipse([w * (0.2 + 0.15 * i), h * 0.4, w * (0.26 + 0.15 * i), h * 0.5], fill=(200, 30, 30))


def _noise(d, im):
    import random
    rnd = random.Random(3)
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            g = rnd.randint(70, 150)
            px[x, y] = (g // 2, g, g // 3, 255)


def _index(*folders):
    idx = Index.build(list(folders))
    idx.add_looks(workers=2)
    return idx


def test_look_measures_shape_colour_and_tiles(tmp_path):
    from mapwriter.assets.look import look_at
    root = _pack(tmp_path, {"a/Apple_Red_1x1.png": ((200, 200), _blob((200, 30, 30))),
                            "a/Grass_01.png": ((400, 400), _noise)})
    apple = look_at(str(tmp_path / "a/Apple_Red_1x1.png"))
    assert apple["colours"] == ["red"] and 0.3 < apple["fill"] < 0.5 and not apple["tile"]
    grass = look_at(str(tmp_path / "a/Grass_01.png"))
    assert grass["fill"] == 1.0 and grass["tile"] and "green" in grass["colours"]
    assert len(apple["sig"]) == len(grass["sig"]) and apple["at"]


def test_handcart_named_for_apples_loses_to_real_apples(tmp_path):
    big = _pack(tmp_path / "Big", {"Props/Handcart_Apples_3x2.png": ((600, 400), _cart)})
    small = _pack(tmp_path / "Fill", {"Food/Apple_Red_1x1.png": ((200, 200), _blob((200, 30, 30))),
                                      "Food/Apple_Red_B_1x1.png": ((200, 200), _blob((180, 40, 35), 0.3)),
                                      "Food/Apple_Pile_1x1.png": ((200, 200), _blob((190, 35, 40), 0.4))})
    words_only = Index.build([big, small])
    assert words_only.pick("apple").name.startswith("Handcart")      # the first pack wins on its name alone
    idx = _index(big, small)
    assert idx.pick("apple").name.startswith("Apple")
    assert idx.pick("handcart").name.startswith("Handcart")          # still found when asked for


def test_colour_words_come_from_the_picture(tmp_path):
    root = _pack(tmp_path, {"f/Apple_A_1x1.png": ((200, 200), _blob((200, 30, 30))),
                            "f/Apple_B_1x1.png": ((200, 200), _blob((60, 170, 50))),
                            "t/Tree_Oak_A_2x2.png": ((400, 400), _blob((200, 110, 30), 0.45)),
                            "t/Tree_Oak_B_2x2.png": ((400, 400), _blob((60, 130, 50), 0.45))})
    idx = _index(root)
    assert idx.pick("green apple").name == "Apple_B_1x1.png"
    assert idx.pick("red apple").name == "Apple_A_1x1.png"
    assert idx.pick("tree").name == "Tree_Oak_B_2x2.png"            # a plain tree is a green one
    assert idx.pick("orange tree").name == "Tree_Oak_A_2x2.png"


def test_vague_names_get_a_word_from_look_alikes_and_seamless_props_become_floors(tmp_path):
    files = {f"p/Barrel_{i}_1x1.png": ((200, 200), _blob((125 + 5 * i, 82, 45), 0.4)) for i in range(3)}
    files.update({f"p/Rock_{i}_1x1.png": ((200, 200), _blob((128 + 4 * i, 126, 122), 0.3)) for i in range(3)})
    files["p/IMG_0042.png"] = ((200, 200), _blob((131, 128, 124), 0.32))
    files["p/Meadow_01.png"] = ((400, 400), _noise)
    idx = _index(_pack(tmp_path, files))
    vague = idx.get("IMG_0042.png")
    assert vague.guessed == ["rock"]
    a = idx.pick("rock", seed=1)
    assert a is not None
    hits = [x.name for _s, x in idx.search("rock", limit=None)]
    assert hits[-1] == "IMG_0042.png"                               # named rocks come first
    assert idx.get("Meadow_01.png").kind == "floor"
    plan = build(parse({"name": "s", "grid": {"width": 6, "height": 6},
                        "props": [{"want": "rock", "file": "IMG_0042.png", "at": [1, 1]}]}), idx)
    assert plan.props[0].asset is vague


def test_guessed_word_alone_warns_in_plan(tmp_path):
    files = {f"p/Rock_{i}_1x1.png": ((200, 200), _blob((128 + 4 * i, 126, 122), 0.3)) for i in range(3)}
    files["q/IMG_7.png"] = ((200, 200), _blob((130, 127, 123), 0.31))
    root = _pack(tmp_path, files)
    idx = _index(root)
    idx.assets = [a for a in idx.assets if a.name == "IMG_7.png"]
    idx._reindex()
    plan = build(parse({"name": "s", "grid": {"width": 6, "height": 6},
                        "props": [{"want": "rock", "at": [1, 1]}]}), idx)
    assert plan.props[0].asset.name == "IMG_7.png"
    assert any("looks like the rock files" in w for w in plan.warnings)


def test_looks_survive_save_and_load(tmp_path):
    root = _pack(tmp_path / "pk", {"a/Apple_Red_1x1.png": ((200, 200), _blob((200, 30, 30)))})
    idx = _index(root)
    idx.save(tmp_path / "i.json")
    back = Index.load(tmp_path / "i.json")
    assert back.assets[0].look["colours"] == ["red"]
    from mapwriter.assets.look import look_all
    assert look_all(back.assets) == 0                                # nothing changed, nothing re-read


def test_look_and_like_commands_and_pack_check(tmp_path, capsys):
    from mapwriter.cli import main
    from mapwriter.assets.packcheck import check_pack
    files = {f"p/Rock_{i}_1x1.png": ((200, 200), _blob((128 + 4 * i, 126, 122), 0.3)) for i in range(3)}
    files["p/IMG_9.png"] = ((200, 200), _blob((130, 127, 123), 0.31))
    root = _pack(tmp_path / "pk", files)
    ix = str(tmp_path / "i.json")
    main(["index", root, "-o", ix])
    main(["look", "-i", ix, "--suggest", str(tmp_path / "s.yaml")])
    assert '"p/IMG_9.png": [rock]' in (tmp_path / "s.yaml").read_text()
    main(["search", "Rock_0_1x1", "--like", "-i", ix])
    out = capsys.readouterr().out
    assert "IMG_9.png" in out and "grey" in out
    r = check_pack(root, write=True)
    assert ("p/IMG_9.png", "rock") in r["guessed"] and r["style"]["ink"] < 0.1
    assert "'IMG_9.png': [rock]" in (Path(root) / "mapwriter-pack.yaml").read_text()


# ------------------------------------------------------------------ v0.4: style matching
def _inked(colour):
    def draw(d, im):
        w, h = im.size
        d.ellipse([w * 0.12, h * 0.12, w * 0.88, h * 0.88], fill=colour, outline=(0, 0, 0), width=max(2, w // 7))
    return draw


def _style_packs(tmp_path):
    muted = lambda i: _blob((120 + 4 * i, 100, 80), 0.38)
    main = _pack(tmp_path / "Main", {f"p/{n}_{i}_1x1.png": ((200, 200), muted(i))
                                     for n in ("Chair", "Stool", "Table") for i in range(2)})
    ink = _pack(tmp_path / "Inky", {**{f"p/Barrel_{i}_1x1.png": ((200, 200), _inked((230, 120, 20))) for i in range(2)},
                                    "p/Sign_1x1.png": ((200, 200), _inked((20, 200, 60)))})
    soft = _pack(tmp_path / "Softy", {**{f"p/Barrel_{i}_1x1.png": ((200, 200), muted(i + 1)) for i in range(2)},
                                      "p/Pot_1x1.png": ((200, 200), muted(3))})
    return main, ink, soft


def test_style_profiles_and_nearest_style_supplies_missing_art(tmp_path):
    from mapwriter.assets.style import gap
    main, ink, soft = _style_packs(tmp_path)
    assert Index.build([main, ink, soft]).pick("barrel").pack == "Inky"      # by words: list order
    idx = _index(main, ink, soft)
    st = idx.styles
    assert st["Inky"]["ink"] > st["Main"]["ink"] + 0.1
    assert gap(st["Softy"], st["Main"]) < gap(st["Inky"], st["Main"])
    assert idx.pick("barrel").pack == "Softy"                                  # nearest style to Main
    idx.main_pack = "Inky"
    assert idx.pick("barrel").pack == "Inky"


def test_scene_style_pack_match_and_clash_warning(tmp_path):
    main, ink, soft = _style_packs(tmp_path)
    idx = _index(main, ink, soft)
    base = {"name": "s", "grid": {"width": 6, "height": 6}, "ground": None,
            "props": [{"want": "chair", "at": [0, 0]}, {"want": "sign", "at": [2, 2]}]}
    plan = build(parse(base), idx)
    assert any("clearly different styles" in w and "Inky" in w for w in plan.warnings)
    assert all(p.grade is None for p in plan.props)
    plan = build(parse({**base, "style": {"match": True}}), idx)
    sign = next(p for p in plan.props if p.want == "sign")
    assert sign.grade is not None and sign.grade[0] < 1                       # colour toned down
    assert not any("clearly different styles" in w for w in plan.warnings)
    assert next(p for p in plan.props if p.want == "chair").grade is None
    assert idx.main_pack is None                                               # build leaves the index as it was
    plan = build(parse({**base, "style": {"pack": "Nowhere"}}), idx)
    assert any("'Nowhere' is not in the index" in w for w in plan.warnings)


def test_grading_changes_colour_and_keeps_transparency(tmp_path):
    from PIL import Image
    from mapwriter.assets.style import apply_grade
    from mapwriter.assets.look import measure
    im = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    from PIL import ImageDraw
    ImageDraw.Draw(im).ellipse([5, 5, 35, 35], fill=(230, 120, 20, 255))
    out = apply_grade(im, (0.7, 0.9))
    assert out.getchannel("A").tobytes() == im.getchannel("A").tobytes()
    assert measure(out)["sat"] < measure(im)["sat"] and measure(out)["bright"] < measure(im)["bright"]


# ------------------------------------------------------------------ v0.4: asset browser
def test_browser_page_and_its_tags_file_format(tmp_path):
    import yaml as _yaml
    from mapwriter.browse import write_browser
    files = {f"p/Rock_{i}_1x1.png": ((200, 200), _blob((128 + 4 * i, 126, 122), 0.3)) for i in range(3)}
    files["p/IMG_9.png"] = ((200, 200), _blob((130, 127, 123), 0.31))
    idx = _index(_pack(tmp_path / "pk", files))
    page = write_browser(idx, tmp_path / "br", workers=2)
    html = page.read_text(encoding="utf-8")
    assert "const ASSETS = [" in html and '"guessed":["rock"]' in html
    assert len(list((tmp_path / "br" / "thumbs").glob("*.webp"))) == 4
    # The page downloads corrections in this shape; tags.yaml must read it.
    (tmp_path / "tags.yaml").write_text('"p/IMG_9.png": ["boulder", "stone"]\nkinds:\n  "p/IMG_9.png": prop\n')
    idx.apply_tags(tmp_path / "tags.yaml")
    assert idx.pick("boulder").name == "IMG_9.png"


# ------------------------------------------------------------------ outdoor placement fixes
def test_chairs_without_rot_face_the_nearest_table(starter):
    data = {"name": "Seats", "grid": {"width": 10, "height": 10}, "ground": "grass", "props": [
        {"want": "round table", "at": [4, 4], "size": [2, 2]},
        {"want": "chair", "at": [3, 4]}, {"want": "chair", "at": [6, 5]}, {"want": "chair", "at": [4, 3]},
        {"want": "chair", "at": [5, 6]}, {"want": "chair", "at": [3, 3]},
        {"want": "chair", "at": [8, 8]}, {"want": "chair", "at": [6, 4], "rot": 180}]}
    chairs = [p for p in build(parse(data), starter).props if p.want == "chair"]
    # rot 0 has the back to the north, so the seat faces south.
    assert [c.rot for c in chairs] == [270, 90, 0, 180, 315, 0, 180]


def test_rocks_in_water_lose_on_dry_ground_and_win_in_ponds():
    names = ["Nature/Rocks/Rock_Gray_A_1x1.png", "Nature/Rocks/Rock_Gray_B_1x1.png",
             "River and Water Assets/Rocks/Rock_River_Foam_A_1x1.png"]
    idx = Index([describe(n, "P", "/p") for n in names])
    assert {idx.pick("rock", seed=s).name for s in range(10)} <= {"Rock_Gray_A_1x1.png", "Rock_Gray_B_1x1.png"}
    assert idx.pick("water rock").name == "Rock_River_Foam_A_1x1.png"
    assert idx.pick("river rock").name == "Rock_River_Foam_A_1x1.png"
    # A rock whose picture is mostly white (snow, chalk, foam) loses to a grey one when no colour is asked.
    from mapwriter.assets.look import COLOURS
    grey, white = (describe(n, "P", "/p") for n in ("Rock_A_1x1.png", "Rock_B_1x1.png"))
    grey.look = {"sig": [100 if c == "grey" else 0 for c in COLOURS] + [40] * 6, "colours": ["grey"]}
    white.look = {"sig": [70 if c == "white" else 30 if c == "grey" else 0 for c in COLOURS] + [40] * 6,
                  "colours": ["white", "grey"]}
    idx = Index([white, grey])
    assert all(idx.pick("rock", seed=s) is grey for s in range(6))
    assert idx.pick("white rock") is white


def test_rocks_scattered_in_a_pond_ask_for_water_art(tmp_path):
    from mapwriter.testart import build_pack
    from PIL import Image
    build_pack(tmp_path)
    (tmp_path / "Water").mkdir()
    Image.new("RGBA", (200, 200), (200, 220, 230, 255)).save(tmp_path / "Water" / "Rock_River_Foam_1x1.png")
    idx = Index.build([str(tmp_path)])
    data = {"name": "Pond", "grid": {"width": 12, "height": 10}, "ground": "grass",
            "water": [{"name": "pond", "circle": [6, 5, 3], "bank": {"floor": "cobblestone", "width": 0.6}}],
            "scatter": [{"want": "rock", "in": "pond", "count": 3}, {"want": "rock", "in": "pond bank", "count": 3}]}
    plan = build(parse(data), idx)
    rocks = [p for p in plan.props if p.want == "rock"]
    assert len(rocks) == 6
    assert all("River" in p.asset.name for p in rocks[:3])
    assert not any("River" in p.asset.name for p in rocks[3:])


def test_cover_fills_a_bed_evenly_with_small_art(starter):
    data = {"name": "Bed", "grid": {"width": 10, "height": 8}, "ground": "grass",
            "areas": [{"name": "bed", "box": [1, 1, 9, 7], "floor": "dirt"}],
            "scatter": [{"want": "flowers", "in": "bed", "cover": 0.8, "gap": -0.2}]}
    plan = build(parse(data), starter)
    flowers = [p for p in plan.props if p.want == "flowers"]
    # Starter flowers draw on about 60% of their square each way, so 0.8 of 48 squares needs about 100.
    assert len(flowers) > 70 and not plan.warnings
    # Even: every square of the bed has a flower within reach.
    for x in range(1, 9):
        for y in range(1, 7):
            assert min((p.centre[0] - x - 0.5) ** 2 + (p.centre[1] - y - 0.5) ** 2 for p in flowers) < 0.8 ** 2
    with pytest.raises(SceneError, match="cover"):
        parse({**data, "scatter": [{"want": "flowers", "in": "bed", "cover": 3}]})
