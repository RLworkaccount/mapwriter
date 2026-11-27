# Roadmap

The aim: a map studio you talk to. Describe a place, pick from a few layouts, edit it in words, and get maps that are ready to play in Foundry, drawn from whatever asset packs you own.

| Version | Theme | What it adds |
|---|---|---|
| **v0.1** | Foundations (done) | Asset index with FA and generic naming, scene files, checks, sketch, painter with day and night lighting, GM key, check image, `.dd2vtt` export, starter art, tests |
| **v0.2** | Outdoors (in progress) | Areas with soft edges, paths along a line, water with banks, scatter rules (trees, rocks, flowers, clutter by density), 2-Minute Tabletop adapter, market and garden scenes |
| **v0.3** | Talk to it (in progress) | Templates (tavern, shop, house, market square, clearing) with three layouts to choose from, `describe` and `edit` briefs for the AI assistant you already use (no API key), `apply` to check and sketch the replies |
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
5. **2-Minute Tabletop adapter** (done, tried on four free 2MT packs on 26 Nov 2026: DPI folders, sized textures and `Category - Item` names): `mapwriter pack-check` guesses any pack's pixels per square, flags vague names and writes its `mapwriter-pack.yaml`; a pack's `credit:` line is written next to every map that uses its art.
6. **Outdoor starter art and test scenes** (done): rocks, bushes, flowers, water, a well and a cart, plus a market and a garden-party scene that render with the starter pack alone.
7. **Tried on the full Forgotten Adventures Core pack** (done, 26 Nov 2026): outdoor words now find plain outdoor art (dirt for paths, green trees and bushes, whole crates), scatter keeps one family of art, canopies stay off buildings and furniture, and a fill-in pack supplies what the main pack lacks.

Later: hills and cliffs, bridges and fords, sight-blocking trees, seasons.

## v0.3 plan: Talk to it

The long view: a map studio you talk to. Say "a smugglers' cove with a sea cave", see three layouts, say "move the jetty north and add fog", and watch the sketch change, with the assistant reading MapWriter's warnings and fixing its own mistakes. It works with whatever assistant you already use, needs no API key and sends nothing anywhere by itself. Later it learns your table's taste (how cluttered, how big rooms run), keeps a history of versions to step back through, and talks to the web editor and the MCP server in v0.7.

v0.3 cuts that to:

1. **Templates** (done): `mapwriter new tavern|shop|house|market|clearing` lays out a scene from a size and a seed, three layout families each, with chairs set at tables, bars with stools, clutter piled in store rooms. Every option renders with the starter pack alone and no warnings.
2. **Briefs** (done): `mapwriter describe "..."` and `mapwriter edit scene.yaml "..."` write a brief for the user's own assistant: the request, layout rules, the words the user's packs use, a starting template and the scene format.
3. **Replies** (done): `mapwriter apply reply.md` saves every scene in the reply, checks each against the packs, draws them side by side and writes a fix-up brief for any problems. `--edit` saves a change and keeps the previous version with a before-and-after sketch.
4. **Leftover v0.1 gaps** (done): layered base and top pieces, fainter light rings in the sketch, and Foundry importer fixes (double doors, light colour strength, secret doors).

Also in v0.3 (26 Nov 2026): per-room and per-wall art (`walls:` on a room, `style:` on a free wall), glass, fence and railing walls that block movement but not sight or light, hedge walls drawn a square thick that block sight in Foundry, and free walls given as a run of `points`.

Later in v0.3 or after: more templates (temple, guard post, cave mouth, ship deck), a template-aware `describe` that fills a template's options from the description, and an MCP server so assistants call MapWriter directly (v0.7).

## Known gaps in v0.1

- Indoor scenes only: no scatter, no curved or diagonal walls.
- Wall corners are plain overlaps; FA corner pieces aren't used yet.
- Lights are clipped to their room's outline, not traced against walls, so a light only spills through a door in Foundry, not in the baked image.
- Props are placed on whole squares when auto-placed; no clustering ("a pile of crates") yet.
- Layered assets: base and top pieces are now paired by name (v0.3). FA's own fireplace and other layered names still need a check against the full pack.
- `.dd2vtt` export is checked against the format and against the Universal Battlemap Importer's code (6.1, Foundry v14), but each importer version should be spot-checked. The importer has no secret doors, and brings windows in as walls that only let sight through from within 10 ft.
