# Scene file format (v0.3)

A scene file is YAML. All positions and sizes are in grid squares (5 ft each). `x` runs right and `y` runs down; `[0, 0]` is the top-left corner of the map. Walls, doors and windows sit on grid lines, between squares.

## Top level

| Key | Meaning | Default |
|---|---|---|
| `name` | Map name, also used for file names | `Untitled map` |
| `grid` | `{ width, height, px_per_square }`. 140 px per square suits Foundry; FA art is drawn at 200 | `px_per_square: 140` |
| `seed` | Any whole number. Changes random choices (which variant of a chair, where auto-placed props go) | `1` |
| `ground` | Floor words for the whole map, e.g. `grass`, `cobblestone` | `stone floor` |
| `style` | `{ walls, doors, windows }`: words for the default wall, door and window art. Also `pack`: the pack whose look the map keeps to, and `match: true` to even out the colour and brightness of art from other packs (see [Mixing packs](asset-packs.md#mixing-packs)) | `stone wall`, `wood door`, `wood window`; the first pack listed; no matching |
| `areas` | Floors without walls (lawns, yards, mud, squares) | none |
| `paths` | Strips of floor along a line (roads, tracks, footpaths) | none |
| `water` | Ponds, lakes, rivers and streams, with banks | none |
| `scatter` | Many copies of something spread over a place (trees, rocks, flowers, a pile of crates) | none |
| `rooms` | Walled spaces with floors, doors and windows | none |
| `walls` | Extra free-standing walls | none |
| `doors`, `windows`, `arches` | Openings not tied to a room | none |
| `props` | Furniture and other things | none |
| `lights` | Light sources (candles and lanterns in `props` add their own) | none |
| `notes` | Numbered notes for the GM key | none |
| `lighting` | `{ versions: [day, night], day: { ambient }, night: { ambient } }` | day and night |

## Shapes

Rooms and areas take either:

- `box: [x0, y0, x1, y1]`: a rectangle from corner to corner, or
- `shape: [[x, y], [x, y], ...]`: an outline. For rooms its edges must go straight across or straight down (L-shapes, T-shapes and so on); for areas they can go at any angle.
- Areas can also take `circle: [x, y, radius]` (or `{ centre: [x, y], radius: r }`).

## Areas

```yaml
areas:
  - name: square
    circle: [13, 10, 6]
    floor: cobblestone
    rough: 0.3          # the edge wanders in and out by up to this many squares
    soft: 0.15          # edge feather, in squares
  - name: mud
    shape: [[2, 13], [7, 12], [8, 16], [4, 18], [1, 17]]
    floor: dirt
    smooth: true        # round off the corners first
    rough: 0.5
```

| Key | Meaning | Default |
|---|---|---|
| `floor` | Floor words (required) | |
| `soft` | How far the edge fades, in squares | `0.3` |
| `rough` | How far the edge wanders in and out, in squares. `0` keeps it exact | `0` |
| `smooth` | `true` rounds off the corners | `false` |

The rough edge is worked out from the scene's `seed` and the area's name, so it stays the same each time you render.

## Paths

```yaml
paths:
  - name: east road
    points: [[18.5, 9], [21, 8], [23.5, 9.5], [26, 9]]
    width: 2.5
    floor: dirt path
```

| Key | Meaning | Default |
|---|---|---|
| `points` | Two or more `[x, y]` points the path runs through. Points can lie off the map, so a road runs off the edge | |
| `floor` | Floor words (required) | |
| `width` | Width in squares | `2` |
| `curve` | `true` draws a smooth curve through the points, `false` straight legs between them | `true` |
| `rough` | How much the width wanders, in squares | `0.25` |
| `soft` | Edge feather, in squares | `0.3` |

Paths are painted first, then areas, then water, then rooms, so a road runs under the square or yard it leads into.

## Water

```yaml
water:
  - name: duck pond
    circle: [4, 6, 2]             # or box: / shape:, like an area
  - name: stream
    points: [[26, 15], [22, 17.5], [17, 17], [13, 19]]   # or a line, like a path
    width: 1.5
    bank: { floor: mud, width: 0.5 }
```

| Key | Meaning | Default |
|---|---|---|
| `circle`, `box`, `shape` | A pond or lake outline, as for areas | |
| `points`, `width`, `curve` | A river or stream along a line, as for paths | width `2`, curve `true` |
| `floor` | Words for the water texture | `water` |
| `bank` | `{ floor, width }` for the strip of ground round the water, just floor words, or `false` for no bank | `mud`, `0.6` squares |
| `rough` | How far the edge wanders, in squares | `0.3` |
| `smooth` | Round off the corners of a pond outline | `true` |
| `soft` | Edge feather, in squares | `0.15` |

Water is painted darker in the middle, with a pale line of shallows along the shore. It does not block movement or sight in the Foundry export.

## Rooms

```yaml
rooms:
  - name: Kitchen
    box: [16, 2, 22, 8]
    floor: warm stone tiles     # words, matched against floor textures
    walls: stone wall           # or "none" for an open area with a floor
    label: Kitchen (Pelbury's)  # optional text for the key and sketch
    doors:
      - { wall: west, at: 4 }                 # opening from (16,4) to (16,5)
      - { wall: south, at: 18, width: 2, kind: double }
    windows:
      - { wall: north, at: [18, 20] }         # two windows
    arches:
      - { wall: east, at: 3 }                 # an open doorway, no door
```

- `wall` is `north`, `south`, `east` or `west`. `at` is where the opening starts along that wall, as an absolute grid coordinate (an `x` for north and south walls, a `y` for east and west walls).
- `width` defaults to 1 (2 for `kind: double`).
- `kind` can be `door`, `double`, `secret`, `window` or `arch`. A secret door is painted as plain wall but is a door in the Foundry export.
- `want: iron door` picks particular art for one opening; `file:` pins an exact file.
- For a room drawn with `shape`, give openings as `{ from: [x, y], to: [x, y] }`.
- Rooms that touch share one wall. A door listed on either room cuts through it.
- `walls:` words pick the art for this room's walls only, for example `walls: wood fence` for a pen in a stone-walled yard. Without it the room uses `style: walls`.
- `see_through: true` makes the walls glass: they stop movement but let sight and light through (the Foundry export brings them in as windows). Walls whose words say `glass`, `fence` or `railing` are see-through anyway; `see_through: false` turns that off.
- `wall_thickness` draws the walls thicker or thinner, in squares.

## Free-standing walls

```yaml
walls:
  - { from: [0, 3], to: [0, 40] }                           # uses style: walls
  - { points: [[3, 29], [9, 29], [9, 35]], style: hedge, thickness: 1 }   # an L-shaped hedge
  - { from: [20, 5], to: [26, 5], style: iron railing }    # see-through: blocks movement only
```

| Key | Meaning | Default |
|---|---|---|
| `from`, `to` | The two ends, on straight lines across or down | |
| `points` | Instead of `from`/`to`: a run of straight legs through these points | |
| `style` | Words (or a file name) for the wall art. Strips such as Forgotten Adventures' hedge maze and fence `*_Path` files work | `style: walls` |
| `see_through` | `true` for glass, fences and railings: movement is blocked, sight and light are not | `true` if the words say glass, fence or railing |
| `thickness` | How thick it is drawn, in squares. `1` suits a hedge | the usual wall thickness |

Hedges drawn this way block sight in Foundry, so a hedge maze plays like one.

## Props

```yaml
props:
  - { want: counter, at: [11, 3], size: [4, 1], label: bar }
  - { want: chair, at: [7, 10], rot: 180 }
  - { want: round table, in: Common room, count: 2 }
  - { want: bookshelf, in: Kitchen, along: north, count: 1 }
  - { file: Table_Round_Wood_Ashen_A2_2x2.webp, centre: [8, 8] }
```

| Key | Meaning |
|---|---|
| `want` | Words describing the thing. The last word is the main noun (`round table`, `small oak tree`). Size words (`big`, `small`, `long`) prefer larger or smaller art. |
| `file` | An exact asset instead of words: its file name, path inside the pack, or full id |
| `at` | Top-left corner of the squares it covers |
| `centre` | Its centre point, instead of `at` |
| `size` | `[w, h]` in squares. If the art is long the other way, it is turned to fit |
| `rot` | Degrees clockwise. `0` means the back of the item faces north (chairs face south) |
| `in` | A room name: MapWriter finds free spots inside it, away from doors |
| `along` | With `in`: put it against that wall (`north`, `south`, `east`, `west`), facing into the room |
| `count` | How many, for `in` placement |
| `label` | Name on the sketch and key |
| `light` | `false` to stop a candle or lantern lighting itself, or `{ radius, colour, intensity }` |
| `vary` | `true` to pick different art for each copy |
| `layer` | Draw order: 0 rugs, 1 furniture, 2 small items on top. Worked out for you if left out |
| `scale`, `flip`, `shadow` | Fine adjustments. A `scale` below 1 with no `size` also means a small thing: 1x1 art is preferred, so `apple` gets an apple rather than a handcart of apples |
| `top` | `false` to leave off the pack's matching top piece (see below) |
| `overlap` | `ok` for pieces built to sit together, such as a counter in front of a tent or an awning over a counter: no overlap warning for them |

Furniture placed with `at` that covers squares another piece already covers gets a warning, since it is usually a mistake. Small items (layer 2) never warn, and nor do pieces marked `overlap: ok`.

Words that match a floor texture but no prop (for example `red rug`) are drawn as a rug of that texture, cut to `size`.

Some packs split a piece into a base and a top, for example Forgotten Adventures' `Display_Case_Base_*` and `Display_Case_Top_*`, or the starter pack's well and its roof. When the art chosen for a prop is a base piece, MapWriter adds the matching top from the same folder, drawn above the furniture layer and without a second shadow. Names with `Base`/`Top`, `Bottom`/`Top` or `Lower`/`Upper` are paired; an exact name match wins, otherwise the closest name with the same footprint.

## Scatter

```yaml
scatter:
  - { want: oak tree, count: 6, cluster: 3.5, spread: 3, gap: -0.6 }     # copses on open ground
  - { want: bush, density: 0.025, cluster: 3, spread: 1.2 }
  - { want: rock, in: duck pond bank, count: 3 }
  - { want: crate, in: Store room, count: 5, cluster: 5, spread: 0.8 }   # a pile of crates
```

| Key | Meaning | Default |
|---|---|---|
| `want` | Words for the thing to scatter (required) | |
| `in` | An area, path, water (or its bank, e.g. `duck pond bank`) or room name, or `map` | `map` |
| `count` | How many | |
| `density` | How many per square, used when `count` is not given | |
| `cluster` | Average number in each clump. `1` spreads them out evenly | `1` |
| `spread` | How far a clump reaches from its middle, in squares | `1.5` |
| `gap` | Space kept between items, in squares. Negative lets them overlap (tree canopies) | `0.1` |
| `turn` | `any` angle, `square` (quarter turns) or `none` | `any` |
| `scale` | `[min, max]` size change for each copy | `[0.9, 1.1]` |
| `size` | `[w, h]` in squares, if the art has no size in its name | |
| `vary` | Different art for each copy, where the pack has it | `true` |
| `avoid` | More names to keep off, or `none` to drop the defaults | |
| `layer`, `label` | As for props. Trees go on top of everything else | |

Scattered things keep off walled rooms, furniture, door squares and each other. On open ground (`in: map`) they also keep off every path, area and pond; inside a named place they keep off paths and water. The layout comes from the scene's `seed`, so it is the same every render. If there isn't room for them all, `mapwriter check` says how many fitted.

## Lights

```yaml
lights:
  - { at: [13, 3.5], radius: 5, colour: warm }
  - { at: [12, 22], radius: 8, colour: moon, when: night, intensity: 0.5 }
```

`at` is a point (use `.5` for the middle of a square). `colour` is a name (`warm`, `candle`, `fire`, `lantern`, `cool`, `moon`, `white`, `magic`, `green`, `blue`, `red`, `gold`), `#rrggbb` or `[r, g, b]`. `when` is `both`, `day` or `night`. Light is cast against the walls: walls and closed doors throw shadows, while windows, arches and open doors (`open: true` on a door) let light spill into the next room or outside. Add `room: Kitchen` to a light to keep it inside one room.

## Notes

```yaml
notes:
  - { at: [21.5, 13.5], text: "Strongbox (locked, DC 12)." }
```

Notes are numbered in order and drawn on the GM key and sketch only, never on the player map.
