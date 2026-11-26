"""Synonyms, so a scene can ask for 'counter' and find a bar, or 'rug' and find a carpet.

Keep this list plain and general. Pack-specific words belong in a pack's
mapwriter-pack.yaml or the user's tags.yaml.
"""
from __future__ import annotations

from .naming import singular

GROUPS = [
    {"counter", "bar", "countertop"},
    {"shelf", "bookshelf", "bookcase", "shelving"},
    {"table", "desk"},
    {"chair", "seat", "armchair"},
    {"stool"},
    {"bench", "pew"},
    {"bed", "bunk", "cot"},
    {"rug", "carpet", "mat"},
    {"plant", "bush", "shrub", "potted", "pot", "planter"},
    {"flower", "flowers", "bloom"},
    {"tree"},
    {"lamp", "lantern"},
    {"candle", "candelabra", "candlestick"},
    {"torch", "sconce"},
    {"fireplace", "hearth"},
    {"oven", "stove"},
    {"chest", "trunk"},
    {"crate", "box"},
    {"barrel", "cask", "keg"},
    {"sack", "bag"},
    {"cupboard", "wardrobe", "cabinet", "dresser"},
    {"stall", "booth"},
    {"altar", "shrine"},
    {"statue", "sculpture"},
    {"cage", "pen", "hutch"},
    {"well"},
    {"cauldron", "pot"},
    {"book", "tome"},
    {"stairs", "stair", "staircase", "steps"},
    {"wood", "wooden", "timber", "plank", "flooring"},
    {"stone", "flagstone", "rock", "slate", "paving"},
    {"cobble", "cobblestone", "cobbles", "paving", "paved"},
    {"tile", "tiles", "tiled"},
    {"grass", "lawn", "meadow"},
    {"dirt", "earth", "soil", "mud"},
    {"marble"},
    {"brick"},
    {"gold", "golden", "gilded"},
    {"red", "crimson"},
    {"blue", "azure"},
    {"green", "emerald"},
    {"dark", "walnut", "black"},
    {"light", "pale", "ashen"},
]

_MAP: dict[str, set[str]] = {}
for g in GROUPS:
    for w in g:
        _MAP.setdefault(w, set()).update(g)

LIGHT_WORDS = {"candle", "candelabra", "candlestick", "lantern", "lamp", "torch", "brazier",
               "fireplace", "hearth", "campfire", "bonfire", "sconce", "chandelier", "lightsource"}
RUG_WORDS = {"rug", "carpet", "mat"}


def expand(word: str) -> set[str]:
    w = singular(word.lower())
    return {w} | _MAP.get(w, set())
