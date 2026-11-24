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
