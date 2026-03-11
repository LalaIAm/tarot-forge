"""Canonical tarot card names by position (0-based). Major Arcana 0-21, then Minor Arcana 22-77."""

MAJOR_ARCANA = [
    "The Fool",
    "The Magician",
    "The High Priestess",
    "The Empress",
    "The Emperor",
    "The Hierophant",
    "The Lovers",
    "The Chariot",
    "Strength",
    "The Hermit",
    "Wheel of Fortune",
    "Justice",
    "The Hanged Man",
    "Death",
    "Temperance",
    "The Devil",
    "The Tower",
    "The Star",
    "The Moon",
    "The Sun",
    "Judgement",
    "The World",
]

# Minor Arcana: Wands (22-35), Cups (36-49), Swords (50-63), Pentacles (64-77)
# Each suit: Ace, 2-10, Page, Knight, Queen, King
_SUIT_NAMES = ["Wands", "Cups", "Swords", "Pentacles"]
_MINOR_RANKS = ["Ace", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Page", "Knight", "Queen", "King"]

def _minor_arcana_names() -> list[str]:
    out = []
    for suit in _SUIT_NAMES:
        for rank in _MINOR_RANKS:
            out.append(f"{rank} of {suit}")
    return out

TAROT_CARD_NAMES_78: list[str] = MAJOR_ARCANA + _minor_arcana_names()
assert len(TAROT_CARD_NAMES_78) == 78


def card_name_for_position(position: int, deck_size: int) -> str:
    """Return canonical card name for position. deck_size 22 = Major only; 78 = full deck."""
    if deck_size == 22:
        if 0 <= position < 22:
            return MAJOR_ARCANA[position]
        return ""
    if deck_size == 78 and 0 <= position < 78:
        return TAROT_CARD_NAMES_78[position]
    return ""
