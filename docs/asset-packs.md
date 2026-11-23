# Asset packs

MapWriter works with folders of images you already have. It reads them in place and keeps only an index (paths, words and sizes) in `mapwriter-index.json`.

## How a file is understood

Take `Furniture/Tables/Round_Tables/Table_Round_Wood_Ashen_A2_2x2.webp`:

- **Words** come from every folder and the file name: furniture, table, round, wood, ashen. Variant codes like `A2` or `03` are dropped and plurals are folded (`Tables` to `table`).
- **Footprint** comes from a `_WxH` token: 2 by 2 squares. Without one, it is worked out from the image size and the pack's pixels per square.
- **Kind** comes from words: `door`, `window`, `wall` (straight wall strips, called paths in FA), `floor` (tileable textures with no footprint), `overlay`, `roof`, `effect`, or `prop` for everything else.

## Packs that work well

| Pack | Notes |
|---|---|
| Forgotten Adventures (FA) | The naming above is FA's, so it works as-is. 200 px per square. Wall strips are the `*_Straight_Path` files. |
| 2-Minute Tabletop | Readable names; most packs are 200 px per square. Add a `tags.yaml` for anything vague. |
| Your own art | Name files like `Barrel_Oak_1x1.png`, or add tags. |

## mapwriter-pack.yaml

Put this file at the top of a pack folder to describe it:

```yaml
name: My Pack
px_per_square: 256          # if the pack is not drawn at 200 px per 5 ft square
tags:                       # extra words for files whose path contains the key
  Stall_A: [market, stall]
  Hutch: [cage, animal]
kinds:                      # force a kind for matching paths
  Rug_Square: floor
```

## tags.yaml

Your own fixes, kept outside the packs. If a `tags.yaml` sits in the folder you run MapWriter from, it is used automatically; otherwise pass `-t tags.yaml`.

```yaml
Display_Case_Top: [counter, shop]
Wiwo_Hutch: [cage, rabbit]
kinds:
  Grates/: overlay
```

## Several packs

Index several folders into one file, or pass several `-i` indexes. When two packs have equally good matches, the pack listed first wins, so put your main pack first and the starter pack last as a fallback.

## Licences

Packs keep their own licences. Most allow maps for your own games but not sharing or bundling the raw files. Don't commit packs to a repository; the `.gitignore` here ignores `assets/` and `packs/`.
