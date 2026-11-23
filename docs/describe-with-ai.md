# Describing a map to an AI assistant

MapWriter's scene file is short and plain on purpose, so an assistant such as Claude can write it for you. The assistant does the layout thinking; MapWriter does the art and the checking.

## The loop

1. Describe the place in your own words: what it's for, rooms, size, mood, anything that must be there.
2. The assistant writes a scene file.
3. It runs `mapwriter check` and `mapwriter sketch`, reads the warnings and looks at the sketch.
4. It fixes problems (no art found, overlaps, rooms you can't get into) and shows you the sketch.
5. You ask for changes in words ("make the kitchen two squares wider", "move the stall left").
6. When you're happy, it runs `mapwriter render`.

## A prompt you can copy

> I use MapWriter (https://github.com/RLworkaccount/mapwriter) to make battlemaps. Please write a scene file for the map below, following docs/scene-format.md.
>
> Rules:
> - Grid squares are 5 ft. Make rooms a believable size: a bedroom is about 3 x 4 squares, a tavern common room 10 x 8 or more.
> - Every walled room needs a door or arch, and doors should not open straight into furniture.
> - Put furniture where people would use it: chairs around tables, beds against walls, shelves along walls (`along:`).
> - Use `want:` words that are likely to match asset file names (table, chair, bed, barrel, crate, shelf, rug, lantern, candle, fireplace, plant, tree).
> - Add `notes:` for anything the GM needs to know, and `label:` for important props.
> - After writing it, run `mapwriter check` and `mapwriter sketch`, fix anything it reports, and show me the sketch before painting.
>
> The map: *(describe it here)*

## Tips

- `mapwriter search "words"` shows what art the index will pick, so the assistant can choose words that match your packs.
- `mapwriter check -v` lists every prop and the exact file it chose.
- Change `seed:` for a different pick of variants and auto-placed spots without changing the layout.
