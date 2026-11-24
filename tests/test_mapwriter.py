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
