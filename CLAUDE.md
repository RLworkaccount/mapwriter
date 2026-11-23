# MapWriter: notes for Claude

MapWriter turns a YAML scene file plus the user's own asset folders into painted battlemaps and Foundry `.dd2vtt` files. Python 3.10+, Pillow and PyYAML only. MIT licence. Owner: RLworkaccount (Robbie).

## Rules

- British spelling in prose, docs and user-facing messages. Code identifiers may stay as they are (`colour` is used in the scene format; `color` is accepted too).
- Never commit, bundle or upload third-party asset packs (Forgotten Adventures, 2-Minute Tabletop, etc.). The tool reads them in place. Test with the code-drawn starter pack (`mapwriter starter-pack`) or with lists of file names only (`tests/fa_names_sample.txt`).
- No AI-generated images anywhere in the project. Starter art is drawn in code (`src/mapwriter/testart.py`).
- Plain, concrete writing in docs and messages.
- Think big when proposing features (Robbie's standing rule), then cut a sensible next milestone. See ROADMAP.md.

## Layout

```
src/mapwriter/
  assets/naming.py   file path -> words, footprint (WxH), kind
  assets/vocab.py    synonyms, light-source and rug words
  assets/index.py    Asset, Index (scan, save/load, search, pick, tags.yaml)
  scene.py           YAML -> Scene dataclasses, with friendly SceneError messages
  geometry.py        merge walls, cut openings, reachability flood fill
  plan.py            Scene + Index -> Plan (chosen art, placed props, walls, lights, warnings)
  render/canvas.py   Pillow canvas in grid squares, tiling, shadows, radial lights
  render/painter.py  Plan -> day/night images
  render/sketch.py   block plan PNG
  export/uvtt.py     .dd2vtt (Universal Battlemap Importer)
  export/keymap.py   GM key and wall/door/light check images
  build.py           high-level steps used by the CLI
  cli.py             `mapwriter` command
  testart.py         starter pack drawn in code
examples/            tavern.yaml, chapel.yaml (must render with the starter pack alone)
docs/                scene format, asset packs, describing maps to an AI
tests/               pytest; fast (about 1 s)
```

Everything after `plan.build` reads only the Plan, so the sketch, painting and exports always agree. Add new features at the Plan level first.

## Working on it

```bash
pip install -e ".[dev]"
pytest -q
mapwriter starter-pack /tmp/starter && mapwriter index /tmp/starter -o /tmp/i.json
mapwriter render examples/tavern.yaml -i /tmp/i.json -o /tmp/out
```

Look at the rendered images (scale them down first) before saying a visual change works. Rendering a 24 x 18 map at 140 px per square takes a few seconds; avoid Pillow MinFilter/MaxFilter with large kernels on full-size canvases (that made renders 10 times slower once).

## Format facts worth keeping

- Coordinates are grid squares, x right, y down. Openings sit on grid lines. Prop `at` is the top-left square; `rot` is clockwise, 0 = back to the north.
- FA: 200 px per square, wall strips are `*_Straight_Path.webp`, doors and windows are 1x1 images with the door drawn as a band across the middle.
- `.dd2vtt`: format 0.3, units in squares, walls as `line_of_sight` polylines with points at least 0.4 squares apart (the importer thins closer points), doors are `closed: true` portals, windows `closed: false`, arches are plain gaps.
- `Image.radial_gradient` is about 181 (not 255) at the edge midpoints; the light sprite divides by the measured value.
