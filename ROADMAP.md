# Roadmap

The aim: a map studio you talk to. Describe a place, pick from a few layouts, edit it in words, and get maps that are ready to play in Foundry, drawn from whatever asset packs you own.

| Version | Theme | What it adds |
|---|---|---|
| **v0.1** | Foundations (done) | Asset index with FA and generic naming, scene files, checks, sketch, painter with day and night lighting, GM key, check image, `.dd2vtt` export, starter art, tests |
| v0.2 | Outdoors | Areas with soft edges, paths along a line, water with banks, scatter rules (trees, rocks, flowers, clutter by density), 2-Minute Tabletop adapter, market and garden scenes |
| v0.3 | Talk to it | `mapwriter describe "..."` and `mapwriter edit scene.yaml "..."` using the user's own AI key, three layout options to choose from, templates (tavern, shop, market square, clearing, house) |
| v0.4 | Any pack | Picture-based tagging for packs with vague names, style matching so mixed packs look consistent, an asset browser page |
| v0.5 | Whole places | Generators for buildings with sensible room layouts, multi-storey houses with aligned stairs, dungeons, caves, villages |
| v0.6 | Ready to play | Full Foundry scenes: levels, map notes linked to journal entries, ambient sounds, starting tokens; story-aware GM keys made from an adventure document |
| v0.7 | Everywhere | Local web editor with drag and drop, MCP server so any assistant can drive MapWriter, Dungeondraft export, Owlbear Rodeo and print-ready PDF |
| Stretch | Animated maps | Flickering lights, moving water and drifting particles as short loops |

## Known gaps in v0.1

- Indoor scenes only: no scatter, no curved or diagonal walls.
- Wall corners are plain overlaps; FA corner pieces aren't used yet.
- Lights are clipped to their room's outline, not traced against walls, so a light only spills through a door in Foundry, not in the baked image.
- Props are placed on whole squares when auto-placed; no clustering ("a pile of crates") yet.
- Layered assets (FA fireplaces with separate base and top pieces) are drawn from one piece.
- `.dd2vtt` export is checked against the format, but each Foundry importer version should be spot-checked.
