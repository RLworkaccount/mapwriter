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
