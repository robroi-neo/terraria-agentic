import re
from collections.abc import Mapping


DEFAULT_GAMEPLAY_ASSUMPTIONS = {
    "difficulty": "Expert",
    "character": "Classic",
    "player_class": "Melee",
    "boss": "no boss defeated",
}


def merge_with_defaults(assumptions: Mapping[str, str] | None) -> dict[str, str]:
    merged = dict(DEFAULT_GAMEPLAY_ASSUMPTIONS)
    if assumptions:
        merged.update(dict(assumptions))
    return merged


def extract_from_text(text: str, current: Mapping[str, str]) -> dict[str, str]:
    updated = dict(current)
    lowered = text.lower()

    # Difficulty (world mode)
    difficulty_map = {
        "journey": "Journey",
        "classic": "Classic",
        "normal": "Classic",
        "expert": "Expert",
        "master": "Master",
    }
    for raw, normalized in difficulty_map.items():
        if re.search(rf"\b{raw}\b", lowered):
            updated["difficulty"] = normalized

    # Character mode: only set when explicitly framed as character mode.
    character_map = {
        "classic": "Classic",
        "softcore": "Softcore",
        "mediumcore": "Mediumcore",
        "hardcore": "Hardcore",
    }
    character_match = re.search(
        r"\b(?:character|char)(?:\s+mode)?\s*(?:is|=|:)?\s*(classic|softcore|mediumcore|hardcore)\b",
        lowered,
    )
    reverse_character_match = re.search(
        r"\b(classic|softcore|mediumcore|hardcore)\s+character\b",
        lowered,
    )
    if character_match:
        updated["character"] = character_map[character_match.group(1)]
    elif reverse_character_match:
        updated["character"] = character_map[reverse_character_match.group(1)]

    # Boss progression
    boss_map = {
        "no boss defeated": "no boss defeated",
        "eye of cthulhu": "Eye of Cthulhu defeated",
        "eater of worlds": "Eater of Worlds defeated",
        "brain of cthulhu": "Brain of Cthulhu defeated",
        "queen bee": "Queen Bee defeated",
        "skeletron": "Skeletron defeated",
        "wall of flesh": "Wall of Flesh defeated",
        "queen slime": "Queen Slime defeated",
        "the twins": "The Twins defeated",
        "the destroyer": "The Destroyer defeated",
        "skeletron prime": "Skeletron Prime defeated",
        "plantera": "Plantera defeated",
        "golem": "Golem defeated",
        "duke fishron": "Duke Fishron defeated",
        "empress of light": "Empress of Light defeated",
        "lunatic cultist": "Lunatic Cultist defeated",
        "moon lord": "Moon Lord defeated",
    }
    for raw, normalized in boss_map.items():
        if re.search(rf"\b{re.escape(raw)}\b", lowered):
            updated["boss"] = normalized
            break

    # Combat class
    class_map = {
        "melee": "Melee",
        "ranger": "Ranger",
        "mage": "Mage",
        "summoner": "Summoner",
    }
    for raw, normalized in class_map.items():
        if re.search(rf"\b{raw}\b", lowered):
            updated["player_class"] = normalized

    return updated


def assumptions_block(assumptions: Mapping[str, str]) -> str:
    return (
        "Current gameplay assumptions (persisted across turns):\n"
        f"- Difficulty: {assumptions['difficulty']}\n"
        f"- Character: {assumptions['character']}\n"
        f"- Class: {assumptions['player_class']}\n"
        f"- Boss progression: {assumptions.get('boss', 'no boss defeated')}"
    )
