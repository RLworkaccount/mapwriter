# Describing a map to an AI assistant

MapWriter's scene file is short and plain on purpose, so an assistant such as Claude can write it for you. The assistant does the layout thinking; MapWriter does the art and the checking.

MapWriter never calls an AI service itself and never needs an API key. You use the assistant you already have: a chat on claude.ai, Claude Code, or any other. Nothing is uploaded by MapWriter; you choose what to paste.

## Quickest: start from a template

```bash
mapwriter new tavern -o scenes        # tavern, shop, house, market or clearing
```

This writes three different layouts (`tavern-a.yaml`, `-b`, `-c`) and `tavern-options.png` with their sketches side by side. Pick one, change it by hand or with `mapwriter edit`, then render it. `--seed 2` gives three more; `--size 30x20` and `--name "The Drowned Rat"` set the size and name.

## A new map from a description

1. Write the brief:

   ```bash
   mapwriter describe "a smugglers' cove with a sea cave and a hidden jetty" -o scenes
   ```

   `scenes/brief.md` holds your request, the rules for a good layout, the words your own asset packs use (so the assistant asks for art you have), a template to start from when one fits, and the full scene format. `-n 1` asks for one layout instead of three; `--template market` picks the starting template yourself.

2. Give `brief.md` to your assistant: paste it into a chat or attach the file.

3. Save the whole reply as a text file, for example `scenes/reply.md`, then:

   ```bash
   mapwriter apply scenes/reply.md -o scenes
   ```

   MapWriter takes every scene file out of the reply, saves each one (`smugglers-cove-a.yaml` and so on), checks it against your packs, and draws `smugglers-cove-options.png` with the layouts side by side. If it finds problems it writes `fix-brief.md` listing them; give that to the assistant in the same chat and `apply` its next reply.

## Changing a map in words

```bash
mapwriter edit scenes/smugglers-cove-b.yaml "make the cave two squares wider and add a rowing boat" -o scenes
# give scenes/edit-brief.md to your assistant, save its reply, then:
mapwriter apply scenes/edit-reply.md --edit scenes/smugglers-cove-b.yaml -o scenes
```

The new version replaces the scene file; the old one is kept next to it as `smugglers-cove-b.prev.yaml`. MapWriter prints how many lines changed and draws a before-and-after sketch.

## Assistants that can run commands

Claude Code and similar assistants can run the whole loop themselves. `--print` sends a brief to the screen instead of a file:

```bash
mapwriter describe "a moonlit graveyard behind a chapel" --print
```

The assistant reads the brief, writes the scene files, runs `mapwriter apply` or `mapwriter check` and `mapwriter sketch`, fixes what is reported, and shows you the sketches before running `mapwriter render`.

## A prompt you can copy

If you would rather not use a brief, this prompt works with any assistant that can read the repository:

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

- `mapwriter search "words"` shows what art the index will pick, so you can choose words that match your packs.
- `mapwriter check -v` lists every prop and the exact file it chose.
- Change `seed:` for a different pick of variants and auto-placed spots without changing the layout.
- The brief lists words from your packs' file names only. It never includes your folder paths.
