# Roadmap

The aim: a map studio you talk to. Describe a place, pick from a few layouts, edit it in words, and get maps that are ready to play in Foundry, drawn from whatever asset packs you own.

| Version | Theme | What it adds |
|---|---|---|
| **v0.1** | Foundations (done) | Asset index with FA and generic naming, scene files, checks, sketch, painter with day and night lighting, GM key, check image, `.dd2vtt` export, starter art, tests |
| **v0.2** | Outdoors (in progress) | Areas with soft edges, paths along a line, water with banks, scatter rules (trees, rocks, flowers, clutter by density), 2-Minute Tabletop adapter, market and garden scenes |
| v0.3 | Talk to it | `mapwriter describe "..."` and `mapwriter edit scene.yaml "..."` using the user's own AI key, three layout options to choose from, templates (tavern, shop, market square, clearing, house) |
| v0.4 | Any pack | Picture-based tagging for packs with vague names, style matching so mixed packs look consistent, an asset browser page |
| v0.5 | Whole places | Generators for buildings with sensible room layouts, multi-storey houses with aligned stairs, dungeons, caves, villages |
| v0.6 | Ready to play | Full Foundry scenes: levels, map notes linked to journal entries, ambient sounds, starting tokens; story-aware GM keys made from an adventure document |
| v0.7 | Everywhere | Local web editor with drag and drop, MCP server so any assistant can drive MapWriter, Dungeondraft export, Owlbear Rodeo and print-ready PDF |
| Stretch | Animated maps | Flickering lights, moving water and drifting particles as short loops |

## v0.2 plan: Outdoors

The long view for outdoor maps: organic ground with rough soft edges, roads and tracks along a line, rivers and ponds with banks, woods and markets filled by scatter rules, then hills and cliffs, bridges and fords, trees that block sight in Foundry, season and weather versions of one map (summer, autumn, snow), and buildings dropped into an outdoor scene.

v0.2 cuts that to the parts every outdoor map needs, in this order. Each lands at the Plan level first, so the sketch, painting and exports agree.

1. **Areas with soft, rough edges** (done): any-angle outlines, circles, `rough` and `smooth` edges.
2. **Paths along a line** (done): `paths:` with points, width, curves and wandering edges.
3. **Water with banks** (done): ponds and rivers as areas or paths, a bank strip round them, deeper colour in the middle and a light shoreline.
4. **Scatter rules with clustering** (first slice done): `scatter:` fills an area, a room or the whole map with trees, rocks, flowers or clutter by density or count, in clumps, keeping off paths, water and furniture. The same code gives "a pile of crates" in a room.
5. **2-Minute Tabletop adapter** (done, to be tried on a real pack): `mapwriter pack-check` guesses any pack's pixels per square, flags vague names and writes its `mapwriter-pack.yaml`; a pack's `credit:` line is written next to every map that uses its art.
6. **Outdoor starter art and test scenes** (done): rocks, bushes, flowers, water, a well and a cart, plus a market and a garden-party scene that render with the starter pack alone.

Later: hills and cliffs, bridges and fords, sight-blocking trees, seasons.

## Known gaps in v0.1

- Indoor scenes only: no scatter, no curved or diagonal walls.
- Wall corners are plain overlaps; FA corner pieces aren't used yet.
- Lights are clipped to their room's outline, not traced against walls, so a light only spills through a door in Foundry, not in the baked image.
- Props are placed on whole squares when auto-placed; no clustering ("a pile of crates") yet.
- Layered assets (FA fireplaces with separate base and top pieces) are drawn from one piece.
- `.dd2vtt` export is checked against the format, but each Foundry importer version should be spot-checked.
