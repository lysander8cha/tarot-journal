"""
Card-name alias tables.

Maps the many spellings of tarot, Lenormand and playing-card names to
canonical names, ranks and suits. Used by database/cards.py to parse card
names when assigning archetype/rank/suit metadata.
"""

from typing import Dict, Tuple

# =============================================================================
# TAROT - MAJOR ARCANA
# =============================================================================

# Aliases that map to canonical Major Arcana names
# Each alias maps to (canonical_name, number_string, "Major Arcana")
MAJOR_ARCANA_ALIASES: Dict[str, Tuple[str, str, str]] = {
    # The Fool (0)
    'fool': ('The Fool', '0', 'Major Arcana'),
    'the fool': ('The Fool', '0', 'Major Arcana'),
    # The Magician (1)
    'magician': ('The Magician', '1', 'Major Arcana'),
    'the magician': ('The Magician', '1', 'Major Arcana'),
    'magus': ('The Magician', '1', 'Major Arcana'),  # Thoth
    'the magus': ('The Magician', '1', 'Major Arcana'),
    # The High Priestess (2)
    'high priestess': ('The High Priestess', '2', 'Major Arcana'),
    'the high priestess': ('The High Priestess', '2', 'Major Arcana'),
    'priestess': ('The High Priestess', '2', 'Major Arcana'),
    'the priestess': ('The High Priestess', '2', 'Major Arcana'),
    # The Empress (3)
    'empress': ('The Empress', '3', 'Major Arcana'),
    'the empress': ('The Empress', '3', 'Major Arcana'),
    # The Emperor (4)
    'emperor': ('The Emperor', '4', 'Major Arcana'),
    'the emperor': ('The Emperor', '4', 'Major Arcana'),
    # The Hierophant (5)
    'hierophant': ('The Hierophant', '5', 'Major Arcana'),
    'the hierophant': ('The Hierophant', '5', 'Major Arcana'),
    'high priest': ('The Hierophant', '5', 'Major Arcana'),
    'the high priest': ('The Hierophant', '5', 'Major Arcana'),
    # The Lovers (6)
    'lovers': ('The Lovers', '6', 'Major Arcana'),
    'the lovers': ('The Lovers', '6', 'Major Arcana'),
    # The Chariot (7)
    'chariot': ('The Chariot', '7', 'Major Arcana'),
    'the chariot': ('The Chariot', '7', 'Major Arcana'),
    # Strength (8)
    'strength': ('Strength', '8', 'Major Arcana'),
    'lust': ('Strength', '8', 'Major Arcana'),  # Thoth
    # The Hermit (9)
    'hermit': ('The Hermit', '9', 'Major Arcana'),
    'the hermit': ('The Hermit', '9', 'Major Arcana'),
    # Wheel of Fortune (10)
    'wheel of fortune': ('Wheel of Fortune', '10', 'Major Arcana'),
    'the wheel of fortune': ('Wheel of Fortune', '10', 'Major Arcana'),
    'wheel': ('Wheel of Fortune', '10', 'Major Arcana'),
    'fortune': ('Wheel of Fortune', '10', 'Major Arcana'),
    # Justice (11)
    'justice': ('Justice', '11', 'Major Arcana'),
    'adjustment': ('Justice', '11', 'Major Arcana'),  # Thoth
    # The Hanged Man (12)
    'hanged man': ('The Hanged Man', '12', 'Major Arcana'),
    'the hanged man': ('The Hanged Man', '12', 'Major Arcana'),
    # Death (13)
    'death': ('Death', '13', 'Major Arcana'),
    # Temperance (14)
    'temperance': ('Temperance', '14', 'Major Arcana'),
    'art': ('Temperance', '14', 'Major Arcana'),  # Thoth
    # The Devil (15)
    'devil': ('The Devil', '15', 'Major Arcana'),
    'the devil': ('The Devil', '15', 'Major Arcana'),
    # The Tower (16)
    'tower': ('The Tower', '16', 'Major Arcana'),
    'the tower': ('The Tower', '16', 'Major Arcana'),
    # The Star (17)
    'star': ('The Star', '17', 'Major Arcana'),
    'the star': ('The Star', '17', 'Major Arcana'),
    # The Moon (18)
    'moon': ('The Moon', '18', 'Major Arcana'),
    'the moon': ('The Moon', '18', 'Major Arcana'),
    # The Sun (19)
    'sun': ('The Sun', '19', 'Major Arcana'),
    'the sun': ('The Sun', '19', 'Major Arcana'),
    # Judgement (20)
    'judgement': ('Judgement', '20', 'Major Arcana'),
    'judgment': ('Judgement', '20', 'Major Arcana'),  # US spelling
    'the aeon': ('Judgement', '20', 'Major Arcana'),  # Thoth
    'aeon': ('Judgement', '20', 'Major Arcana'),
    # The World (21)
    'world': ('The World', '21', 'Major Arcana'),
    'the world': ('The World', '21', 'Major Arcana'),
    'universe': ('The World', '21', 'Major Arcana'),  # Thoth
    'the universe': ('The World', '21', 'Major Arcana'),
}

# =============================================================================
# TAROT - SUITS
# =============================================================================

# Maps alias names to canonical suit names
TAROT_SUIT_ALIASES: Dict[str, str] = {
    # Wands
    'wands': 'Wands', 'wand': 'Wands',
    'rods': 'Wands', 'staves': 'Wands', 'batons': 'Wands',
    # Cups
    'cups': 'Cups', 'cup': 'Cups',
    'chalices': 'Cups', 'chalice': 'Cups',
    # Swords
    'swords': 'Swords', 'sword': 'Swords',
    # Pentacles
    'pentacles': 'Pentacles', 'pentacle': 'Pentacles',
    'coins': 'Pentacles', 'coin': 'Pentacles',
    'disks': 'Pentacles', 'discs': 'Pentacles',
    'disk': 'Pentacles', 'disc': 'Pentacles',
}

# Sort order base values (suit starts at this number, ranks add to it)
TAROT_SUIT_BASES: Dict[str, int] = {
    'Wands': 100,
    'Cups': 200,
    'Swords': 300,
    'Pentacles': 400,
}

# =============================================================================
# TAROT - RANKS
# =============================================================================

# Maps alias names to (canonical_rank, sort_order)
TAROT_RANK_ALIASES: Dict[str, Tuple[str, int]] = {
    # Ace (1)
    'ace': ('Ace', 1), 'one': ('Ace', 1), '1': ('Ace', 1), 'i': ('Ace', 1),
    # Two (2)
    'two': ('Two', 2), '2': ('Two', 2), 'ii': ('Two', 2),
    # Three (3)
    'three': ('Three', 3), '3': ('Three', 3), 'iii': ('Three', 3),
    # Four (4)
    'four': ('Four', 4), '4': ('Four', 4), 'iv': ('Four', 4),
    # Five (5)
    'five': ('Five', 5), '5': ('Five', 5), 'v': ('Five', 5),
    # Six (6)
    'six': ('Six', 6), '6': ('Six', 6), 'vi': ('Six', 6),
    # Seven (7)
    'seven': ('Seven', 7), '7': ('Seven', 7), 'vii': ('Seven', 7),
    # Eight (8)
    'eight': ('Eight', 8), '8': ('Eight', 8), 'viii': ('Eight', 8),
    # Nine (9)
    'nine': ('Nine', 9), '9': ('Nine', 9), 'ix': ('Nine', 9),
    # Ten (10)
    'ten': ('Ten', 10), '10': ('Ten', 10), 'x': ('Ten', 10),
    # Page/Princess (11)
    'page': ('Page', 11), 'princess': ('Page', 11),
    # Knight/Prince (12)
    'knight': ('Knight', 12), 'prince': ('Knight', 12),
    # Queen (13)
    'queen': ('Queen', 13),
    # King (14)
    'king': ('King', 14),
}

# =============================================================================
# LENORMAND
# =============================================================================

# Aliases for Lenormand card names -> (canonical_name, number_string)
LENORMAND_ALIASES: Dict[str, Tuple[str, str]] = {
    # Rider (1)
    'rider': ('Rider', '1'), 'cavalier': ('Rider', '1'),
    # Clover (2)
    'clover': ('Clover', '2'),
    # Ship (3)
    'ship': ('Ship', '3'),
    # House (4)
    'house': ('House', '4'),
    # Tree (5)
    'tree': ('Tree', '5'),
    # Clouds (6)
    'clouds': ('Clouds', '6'), 'cloud': ('Clouds', '6'),
    # Snake (7)
    'snake': ('Snake', '7'),
    # Coffin (8)
    'coffin': ('Coffin', '8'),
    # Bouquet (9)
    'bouquet': ('Bouquet', '9'), 'flowers': ('Bouquet', '9'),
    # Scythe (10)
    'scythe': ('Scythe', '10'),
    # Whip (11)
    'whip': ('Whip', '11'), 'broom': ('Whip', '11'), 'birch': ('Whip', '11'),
    # Birds (12)
    'birds': ('Birds', '12'), 'owls': ('Birds', '12'),
    # Child (13)
    'child': ('Child', '13'),
    # Fox (14)
    'fox': ('Fox', '14'),
    # Bear (15)
    'bear': ('Bear', '15'),
    # Stars (16)
    'stars': ('Stars', '16'), 'star': ('Stars', '16'),
    # Stork (17)
    'stork': ('Stork', '17'),
    # Dog (18)
    'dog': ('Dog', '18'),
    # Tower (19)
    'tower': ('Tower', '19'),
    # Garden (20)
    'garden': ('Garden', '20'),
    # Mountain (21)
    'mountain': ('Mountain', '21'),
    # Crossroads (22)
    'crossroads': ('Crossroads', '22'), 'crossroad': ('Crossroads', '22'),
    'paths': ('Crossroads', '22'), 'path': ('Crossroads', '22'),
    # Mice (23)
    'mice': ('Mice', '23'), 'mouse': ('Mice', '23'),
    # Heart (24)
    'heart': ('Heart', '24'),
    # Ring (25)
    'ring': ('Ring', '25'),
    # Book (26)
    'book': ('Book', '26'),
    # Letter (27)
    'letter': ('Letter', '27'),
    # Man (28)
    'man': ('Man', '28'), 'gentleman': ('Man', '28'),
    # Woman (29)
    'woman': ('Woman', '29'), 'lady': ('Woman', '29'),
    # Lily (30)
    'lily': ('Lily', '30'), 'lilies': ('Lily', '30'),
    # Sun (31)
    'sun': ('Sun', '31'),
    # Moon (32)
    'moon': ('Moon', '32'),
    # Key (33)
    'key': ('Key', '33'),
    # Fish (34)
    'fish': ('Fish', '34'),
    # Anchor (35)
    'anchor': ('Anchor', '35'),
    # Cross (36)
    'cross': ('Cross', '36'),
}

# =============================================================================
# PLAYING CARDS
# =============================================================================

PLAYING_CARD_SUIT_ALIASES: Dict[str, str] = {
    'hearts': 'Hearts', 'heart': 'Hearts', '\u2665': 'Hearts',
    'diamonds': 'Diamonds', 'diamond': 'Diamonds', '\u2666': 'Diamonds',
    'clubs': 'Clubs', 'club': 'Clubs', '\u2663': 'Clubs',
    'spades': 'Spades', 'spade': 'Spades', '\u2660': 'Spades',
}

PLAYING_CARD_RANK_ALIASES: Dict[str, Tuple[str, int]] = {
    'ace': ('Ace', 1), 'a': ('Ace', 1), '1': ('Ace', 1),
    'two': ('Two', 2), '2': ('Two', 2),
    'three': ('Three', 3), '3': ('Three', 3),
    'four': ('Four', 4), '4': ('Four', 4),
    'five': ('Five', 5), '5': ('Five', 5),
    'six': ('Six', 6), '6': ('Six', 6),
    'seven': ('Seven', 7), '7': ('Seven', 7),
    'eight': ('Eight', 8), '8': ('Eight', 8),
    'nine': ('Nine', 9), '9': ('Nine', 9),
    'ten': ('Ten', 10), '10': ('Ten', 10),
    'jack': ('Jack', 11), 'j': ('Jack', 11), 'knave': ('Jack', 11),
    'queen': ('Queen', 12), 'q': ('Queen', 12),
    'king': ('King', 13), 'k': ('King', 13),
}
