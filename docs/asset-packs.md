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

## Picking by the pictures

Names only go so far. Two packs can both have 'apple' in a file name, one an apple and the other a handcart full of them. Run this once after indexing:

```bash
mapwriter look -i mapwriter-index.json --suggest tags-suggested.yaml
```

(or `mapwriter index ... --look` to do both in one go). It opens every image on your own computer, shrinks it to a thumbnail and measures plain things: how much of its squares it fills and how solid it is, which colours cover it, how much black ink outlines it, how bright and how strongly coloured it is, and whether it tiles seamlessly. No AI model or online service is involved and nothing is sent anywhere: it is arithmetic on pixels. The numbers are stored in the index, so later runs only look at new or changed files. A big pack such as FA Core takes a few minutes the first time.

With pictures measured, picking also goes by what the art looks like:

- **Looks unlike the thing**: among files matching `apple`, MapWriter works out the middle look of the files named for apples (`Apple_Red_1x1`, `Apple_Green_1x1`...). A file that only has the word elsewhere in its name and looks nothing like them, such as `Handcart_Apples_3x2`, loses points, and no longer wins just because its pack is listed first. Ask for `handcart` and you still get it.
- **Colours from the picture**: `green apple` or `red cloak` finds green or red art even when the file name gives no colour, and a plain `tree` avoids art that is mostly orange or red (autumn) unless the scene names a colour.
- **Vague names**: a file such as `IMG_0042.png` takes the word of the named files it looks most like (`rock`, say) when one group is clearly nearest. Guessed words count for less than real ones, and the render tells you when one was used. `--suggest` writes the guesses to a file to check: fix any that are wrong and use it as your `tags.yaml`.
- **Seamless pictures** filed among props (a `Grass_01.png` outside a textures folder, at least two squares across) are used as floor textures.

`mapwriter search "apple"` shows the colours seen in each picture, and `mapwriter search Barrel_Oak_1x1 --like` lists the art that looks most like a file.

Indexes made before v0.4 still work; they simply pick by words until `mapwriter look` has run.

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

It prints how many images of each kind it found, its guess at the pack's pixels per square (from files that name their size, such as `Cart_3x2.png`, or else the commonest small-prop size), and files whose names say too little to be found by words. It also measures the pictures (skip that with `--no-look`): it reports the pack's style on average (black ink, colour strength, brightness, soft shadow), seamless pictures it will use as floors, and a guessed word for vaguely named files, which `--write` puts in the yaml as commented lines to check. With `--write` it saves a starter `mapwriter-pack.yaml` in the pack folder, unless one is there already. Check the guess against a 1-square item such as a barrel, then index the pack.

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

## The asset browser

```bash
mapwriter browse -o asset-browser
```

writes `asset-browser/index.html` and small thumbnails of your art. Open the page in any browser. It works offline and stays on your computer: nothing is uploaded, and the page reads your files only from your own disk. Don't put the folder anywhere public, since the thumbnails are copies of your packs' art.

- Search by words, and filter by kind, pack, colour, or files with guessed words only.
- Click a picture to see its words, footprint, colours, outline ink and brightness, its pack's style, and the art that looks most like it.
- Correct a picture: add words or change its kind, then **Download tags.yaml**. Use the file with `-t tags.yaml` (or copy its lines into yours). Corrections are remembered in that browser until you clear them.

Thumbnails are made once and only remade when a file changes. For a very large library, `--pack NAME` limits the page to one pack, and `--no-thumbs` shows the original files instead (no copies made, but the page is slower).

## Mixing packs

Packs by different artists look different: one outlines everything in heavy black ink, another has soft colour and baked-in shadows. Once pictures are measured (`mapwriter look`), MapWriter keeps a style profile for each pack (black ink, colour strength, brightness, soft shadow) and `mapwriter look` prints them.

- **The map's main style** is the first pack listed in the index, or the pack named by `style: { pack: ... }` in the scene.
- **Missing art comes from the nearest style.** The main pack still supplies everything it has. When it has nothing for a word, the pack whose style is closest to the main one's goes next, rather than simply the next pack listed.
- **A warning when styles clash.** If a map ends up with art in clearly different styles, `check` and `render` say which packs and how they differ.
- **`style: { match: true }`** gently grades art from other packs towards the main style when painting: colour strength and brightness are moved part of the way (never more than about a third), and transparency is untouched. Outlines and shading drawn into the art stay as they are, so the nearest-style choice above matters most.

```yaml
style: { walls: stone wall, pack: Forgotten Adventures, match: true }
```

## Several packs

Index several folders into one file, or pass several `-i` indexes. The first pack listed that has the thing itself supplies it, so put your main pack first and the starter pack last as a fallback. For example, with Forgotten Adventures Core first, trees and crates come from FA, and market stalls (which Core lacks) come from the starter pack. With pictures measured, packs after the first are tried in order of how close their style is to the first pack's (see Mixing packs).

## Licences

Packs keep their own licences. Most allow maps for your own games but not sharing or bundling the raw files. Don't commit packs to a repository; the `.gitignore` here ignores `assets/` and `packs/`.
