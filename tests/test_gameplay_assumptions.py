from src.agent.gameplay_assumptions import (
    DEFAULT_GAMEPLAY_ASSUMPTIONS,
    assumptions_block,
    extract_from_text,
    merge_with_defaults,
)


def test_extracts_difficulty_and_class_from_short_reply():
    assumptions = extract_from_text("Master summoner", dict(DEFAULT_GAMEPLAY_ASSUMPTIONS))

    assert assumptions["difficulty"] == "Master"
    assert assumptions["player_class"] == "Summoner"


def test_extracts_explicit_character_mode_only_when_labeled():
    assumptions = extract_from_text(
        "character mode is hardcore",
        dict(DEFAULT_GAMEPLAY_ASSUMPTIONS),
    )

    assert assumptions["character"] == "Hardcore"


def test_merge_with_defaults_preserves_existing_assumptions():
    persisted = {
        "difficulty": "Master",
        "character": "Mediumcore",
        "player_class": "Mage",
    }
    merged = merge_with_defaults(persisted)

    assert merged == persisted


def test_assumptions_block_formats_for_prompt_context():
    block = assumptions_block(DEFAULT_GAMEPLAY_ASSUMPTIONS)

    assert "Difficulty: Expert" in block
    assert "Character: Classic" in block
    assert "Class: Ranger" in block
