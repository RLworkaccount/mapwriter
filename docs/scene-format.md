# Scene file format (v0.2)

A scene file is YAML. All positions and sizes are in grid squares (5 ft each). `x` runs right and `y` runs down; `[0, 0]` is the top-left corner of the map. Walls, doors and windows sit on grid lines, between squares.

## Top level

| Key | Meaning | Default |
|---|---|---|
| `name` | Map name, also used for file names | `Untitled map` |
| `grid` | `{ width, height, px_per_square }`. 140 px per square suits Foundry; FA art is drawn at 200 | `px_per_square: 140` |
| `seed` | Any whole number. Changes random choices (which variant of a chair, where auto-placed props go) | `1` |
| `ground` | Floor words for the whole map, e.g. `grass`, `cobblestone` | `stone floor` |
| `style` | `{ walls, doors, windows }`: words for the default wall, door and window art | `stone wall`, `wood door`, `wood window` |
| `areas` | Floors without walls (lawns, yards, mud, squares) | none |
| `paths` | Strips of floor along a line (roads, tracks, footpaths) | none |
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

Paths are painted first, then areas, then rooms, so a road runs under the square or yard it leads into.

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
| `scale`, `flip`, `shadow` | Fine adjustments |

Words that match a floor texture but no prop (for example `red rug`) are drawn as a rug of that texture, cut to `size`.

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
