# Asset packs

MapWriter works with folders of images you already have. It reads them in place and keeps only an index (paths, words and sizes) in `mapwriter-index.json`.

## How a file is understood

Take `Furniture/Tables/Round_Tables/Table_Round_Wood_Ashen_A2_2x2.webp`:

- **Words** come from every folder and the file name: furniture, table, round, wood, ashen. Variant codes like `A2` or `03` are dropped and plurals are folded (`Tables` to `table`).
- **Footprint** comes from a `_WxH` token: 2 by 2 squares. Without one, it is worked out from the image size and the pack's pixels per square.
- **Layers**: a file with `Base` in its name (or `Bottom`, `Lower`) is drawn with its partner `Top` (or `Upper`) from the same folder, if there is one.
- **Kind** comes from words: `door`, `window`, `wall` (straight wall strips, called paths in FA), `floor` (tileable textures with no footprint), `overlay`, `roof`, `effect`, or `prop` for everything else. Roof textures (`Roof_Thatch_*`, `Roof_Slate_*`) work as floors too: a floor that asks for `thatch roof` looks among roofs first, and any other floor words fall back to roofs when no floor texture matches. If a pack's kinds come out wrong, force them with `kinds:` in `mapwriter-pack.yaml` or `tags.yaml` (see below).

## How art is picked

A scene asks for things in plain words (`oak tree`, `dirt path`, `crate`). The last word is the thing itself; the others describe it. Among the files that match, MapWriter prefers:

- files named for the thing itself (`Dirt_A_01` for `dirt`, not `Stone_Floor_Dirt`), and whole items over lids, parts and ready-made arrangements;
- plain versions over seasonal or special ones: a `tree` is not a Christmas tree, an autumn-red tree or a Feywild bush unless the scene says so (`christmas tree`, `red tree`), and plants come green unless a colour is named;
- for a floor, the ground rather than the route: `dirt path` and `dirt road` look for dirt, so FA's `*_Path` strips are not used as paths.

Scatter rules choose one family of art (all of `Tree_Green_*`, say) and vary the copies inside it, so a wood doesn't mix summer and autumn trees. Flowers may mix colours.

If the only match is through a similar word (a `stall` that came back as a booth), the render says so, so you can check it, name a file with `file:`, or add a tag.

## Packs that work well

| Pack | Notes |
|---|---|
| Forgotten Adventures (FA) | The naming above is FA's, so it works as-is. 200 px per square. Wall strips are the `*_Straight_Path` files. |
| 2-Minute Tabletop | Readable names such as `Storage - Crate 1 - Dark.png`, read as they are (the item is the word after the category). Packs ship the same art in `300 DPI` and `70 DPI` folders: MapWriter keeps the sharpest copy and reads 300 px per square from the folder name. Textures that name their size (`8x8 dirt texture.jpg`, `Water Tile 1 (8x8).jpg`) tile at that size. Run `mapwriter pack-check --write --credit "..."` on each pack first, for the credit line the CC BY-NC licence asks for. Tried on Grass & Road, River & Water, Forest Floor and Furniture (26 Nov 2026). |
| Your own art | Name files like `Barrel_Oak_1x1.png`, or add tags. |

## Checking a new pack

Before indexing a pack you haven't used yet, let MapWriter look it over:

```bash
mapwriter pack-check "Packs/2MT Garden" --write --credit "Art by 2-Minute Tabletop, CC BY-NC 4.0"
```

It prints how many images of each kind it found, its guess at the pack's pixels per square (from files that name their size, such as `Cart_3x2.png`, or else the commonest small-prop size), and files whose names say too little to be found by words. With `--write` it saves a starter `mapwriter-pack.yaml` in the pack folder, unless one is there already. Check the guess against a 1-square item such as a barrel, then index the pack.

## mapwriter-pack.yaml

Put this file at the top of a pack folder to describe it:

```yaml
name: My Pack
px_per_square: 256          # if the pack is not drawn at 200 px per 5 ft square
credit: "Art by My Pack, CC BY-NC 4.0"   # written to <map>-credits.txt whenever its art is used
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

Index several folders into one file, or pass several `-i` indexes. The first pack listed that has the thing itself supplies it, so put your main pack first and the starter pack last as a fallback. For example, with Forgotten Adventures Core first, trees and crates come from FA, and market stalls (which Core lacks) come from the starter pack.

## Licences

Packs keep their own licences. Most allow maps for your own games but not sharing or bundling the raw files. Don't commit packs to a repository; the `.gitignore` here ignores `assets/` and `packs/`.
