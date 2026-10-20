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


# =============================================================================
# REGIONAL SUIT FAMILIES
# =============================================================================
# Decks that share a suit system share one set of English-named
# archetypes; each deck keeps its own native card names (As de Oros,
# Asso di Denari, Herz Ober) and links to these.

LATIN_SUITED = 'Playing Cards (Latin-suited)'    # Spanish, Italian, Portuguese
GERMAN_SUITED = 'Playing Cards (German-suited)'
SWISS_SUITED = 'Playing Cards (Swiss-suited)'      # Jass packs

LATIN_SUITS = ['Coins', 'Cups', 'Swords', 'Batons']
LATIN_RANKS = ['Ace', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven',
               'Eight', 'Nine', 'Knave', 'Knight', 'King']
GERMAN_SUITS = ['Hearts', 'Bells', 'Leaves', 'Acorns']
# Two-Five exist only in some full-pip German packs; 32/36-card packs
# simply don't use them.
GERMAN_RANKS = ['Ace', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven',
                'Eight', 'Nine', 'Ten', 'Unter', 'Ober', 'King']
SWISS_SUITS = ['Roses', 'Bells', 'Shields', 'Acorns']
SWISS_RANKS = ['Ace', 'Six', 'Seven', 'Eight', 'Nine', 'Banner',
               'Under', 'Ober', 'King']


def family_archetypes(cartomancy_type: str) -> list:
    """(name, rank, suit) for every archetype in a suit family, in
    seed order: suit-major, then the family's extra cards."""
    if cartomancy_type == LATIN_SUITED:
        cards = [(f'{r} of {s}', r, s) for s in LATIN_SUITS for r in LATIN_RANKS]
        return cards + [('Joker', 'Joker', None)]
    if cartomancy_type == GERMAN_SUITED:
        cards = [(f'{r} of {s}', r, s) for s in GERMAN_SUITS for r in GERMAN_RANKS]
        # The Weli: an extra Bells card in Bavarian/Salzburg packs.
        return cards + [('Weli', 'Weli', 'Bells')]
    if cartomancy_type == SWISS_SUITED:
        return [(f'{r} of {s}', r, s) for s in SWISS_SUITS for r in SWISS_RANKS]
    if cartomancy_type in TAROCCHI:
        return [(name, rank, suit) for name, rank, suit, _keys in tarocco_cards(cartomancy_type)]
    return []


# --- Tarocco Piemontese: a standard 78-card tarot (Marseille order:
# VIII Justice, XI Strength) with Italian titles and suits — imported as
# Tarot, Italian card names linked to the Tarot archetypes. It briefly
# had its own deck type; database/core.py folds that back into Tarot.
PIEMONTESE_TRUMPS = [
    ('Il Matto', 'The Fool'), ('Il Bagatto', 'The Magician'),
    ('La Papessa', 'The High Priestess'), ("L'Imperatrice", 'The Empress'),
    ("L'Imperatore", 'The Emperor'), ('Il Papa', 'The Hierophant'),
    ('Gli Amanti', 'The Lovers'), ('Il Carro', 'The Chariot'),
    ('La Giustizia', 'Justice'), ("L'Eremita", 'The Hermit'),
    ('La Ruota della Fortuna', 'Wheel of Fortune'), ('La Forza', 'Strength'),
    ("L'Appeso", 'The Hanged Man'), ('La Morte', 'Death'),
    ('La Temperanza', 'Temperance'), ('Il Diavolo', 'The Devil'),
    ('La Torre', 'The Tower'), ('Le Stelle', 'The Star'), ('La Luna', 'The Moon'),
    ('Il Sole', 'The Sun'), ("L'Angelo", 'Judgement'), ('Il Mondo', 'The World'),
]
_PIEMONTESE_SUITS = [('Bastoni', 'Wands', 'b'), ('Coppe', 'Cups', 'c'),
                     ('Spade', 'Swords', 's'), ('Denari', 'Pentacles', 'd')]
_TAROT_RANKS = ['Ace', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight',
                'Nine', 'Ten', 'Page', 'Knight', 'Queen', 'King']


def piemontese_cards() -> list:
    """(Italian name, Tarot archetype, filename keys) for all 78 cards:
    trumps 00-21 by printed number, then b/c/s/d + 01-14."""
    cards = [(it, en, (f'{i:02d}', str(i))) for i, (it, en) in enumerate(PIEMONTESE_TRUMPS)]
    cards[0] = (*cards[0][:2], cards[0][2] + ('matto',))
    ranks = [r for r, *_ in _IT_PIPS + _IT_COURTS]
    for it_suit, suit, letter in _PIEMONTESE_SUITS:
        for n, (it_rank, rank) in enumerate(zip(ranks, _TAROT_RANKS), 1):
            keys = tuple(f'{pre}{k}' for pre in (letter, it_suit.lower())
                         for k in (f'{n:02d}', str(n)))
            cards.append((f'{it_rank} di {it_suit}', f'{rank} of {suit}', keys))
    return cards


# --- Tarocchi: Italian-suited game tarots, each its own deck type with
# Italian-named archetypes (cross-type links to Tarot come later).
# Trumps: (name, filename keys), lowest first; they get suit 'Major
# Arcana' and no rank. Suits/ranks: (Italian, English, printed numbers)
# — English suit/rank values keep sorting, suit pairing and the court
# filter working. Files: printed number + Italian suit letter.
TAROCCO_PIEMONTESE = 'Tarocco Piemontese'
TAROCCO_BOLOGNESE = 'Tarocco Bolognese'
TAROCCO_SICILIANO = 'Tarocco Siciliano'

_IT_TAROCCO_SUITS = [('Bastoni', 'Batons', 'b'), ('Coppe', 'Cups', 'c'),
                     ('Spade', 'Swords', 's'), ('Denari', 'Coins', 'd')]
_IT_PIPS = [('Asso', 'Ace', (1,)), ('Due', 'Two', (2,)), ('Tre', 'Three', (3,)),
            ('Quattro', 'Four', (4,)), ('Cinque', 'Five', (5,)), ('Sei', 'Six', (6,)),
            ('Sette', 'Seven', (7,)), ('Otto', 'Eight', (8,)), ('Nove', 'Nine', (9,)),
            ('Dieci', 'Ten', (10,))]
_IT_COURTS = [('Fante', 'Knave', (11,)), ('Cavallo', 'Knight', (12,)),
              ('Donna', 'Queen', (13,)), ('Re', 'King', (14,))]


def _numbered(names, start):
    return [(n, (f'{i:02d}', str(i))) for i, n in enumerate(names, start)]


TAROCCHI = {
    # 62 cards: no 2-5 pips; only trumps 5-16 are numbered; four
    # interchangeable Moors (two identical) below Amore.
    TAROCCO_BOLOGNESE: {
        'trumps': [('Matto', ('00', '0', 'matto')), ('Begato', ('01', '1', 'begato'))]
        + [(f'Moro {i}', (f'm{i}', f'moro{i}')) for i in range(1, 5)]
        + _numbered(['Amore', 'Carro', 'Tempra', 'Giusta', 'Forza', 'Roda', 'Vecchio',
                     'Traditore', 'Morte', 'Diavolo', 'Saetta', 'Stella'], 5)
        + [('Luna', ('17', 'luna')), ('Sole', ('18', 'sole')),
           ('Mondo', ('19', 'mondo')), ('Angelo', ('20', 'angelo'))],
        'suits': _IT_TAROCCO_SUITS,
        'ranks': [_IT_PIPS[0]] + _IT_PIPS[5:] + _IT_COURTS,
    },
    # 63 cards (+ the tax-stamp Ace of Coins): pips 5-10, Coins also 4;
    # knaves are female (Donna), queens Regina. Unique trumps Miseria,
    # Costanza, Vascello, Atlante, Giove; Fool = Fuggitivo.
    TAROCCO_SICILIANO: {
        'trumps': [('Fuggitivo', ('00', 'fuggitivo', 'matto')),
                   ('Miseria', ('m0', 'miseria'))] + _numbered([
            'Bagotti', 'Imperatrice', 'Imperatore', 'Costanza', 'Temperanza', 'Forza',
            'Giustizia', 'Amore', 'Carro', 'Ruota', 'Impiccato', 'Tempo', 'Morte',
            'Vascello', 'Torre', 'Stella', 'Luna', 'Sole', 'Atlante', 'Giove'], 1),
        'suits': _IT_TAROCCO_SUITS,
        'ranks': _IT_PIPS[4:] + [('Donna', 'Knave', (11,)), ('Cavallo', 'Knight', (12,)),
                                 ('Regina', 'Queen', (13,)), ('Re', 'King', (14,))],
        # Coins add the 4 and the extra tax-stamp Ace.
        'extra_coins': [_IT_PIPS[0], _IT_PIPS[3]],
    },
}


def tarocco_cards(cartomancy_type: str) -> list:
    """(name, english_rank, english_suit, filename keys) for a tarocco
    pack in sort order: trumps, then each suit's pips and courts."""
    spec = TAROCCHI[cartomancy_type]
    cards = [(name, None, 'Major Arcana', keys) for name, keys in spec['trumps']]
    for it_suit, suit, letter in spec['suits']:
        ranks = spec['ranks']
        if suit == 'Coins' and spec.get('extra_coins'):
            ranks = sorted(spec['extra_coins'] + ranks, key=lambda r: r[2][0])
        for it_rank, rank, numbers in ranks:
            keys = [f'{pre}{n:02d}' for pre in (letter, it_suit.lower()) for n in numbers]
            keys += [f'{pre}{n}' for pre in (letter, it_suit.lower()) for n in numbers]
            cards.append((f'{it_rank} di {it_suit}', rank, suit, tuple(keys)))
    return cards


# The old "Playing Cards (Spanish)" archetypes ("As de Oros") became
# the Latin family's English ones ("Ace of Coins").
SPANISH_TO_LATIN_SUIT = {'Oros': 'Coins', 'Copas': 'Cups',
                         'Espadas': 'Swords', 'Bastos': 'Batons'}
SPANISH_TO_LATIN_RANK = dict(zip(
    ['As', 'Dos', 'Tres', 'Cuatro', 'Cinco', 'Seis', 'Siete',
     'Ocho', 'Nueve', 'Sota', 'Caballo', 'Rey'], LATIN_RANKS))


if __name__ == '__main__':
    assert len(family_archetypes(LATIN_SUITED)) == 49
    assert len(family_archetypes(GERMAN_SUITED)) == 53
    assert len(family_archetypes(SWISS_SUITED)) == 36
    assert len(piemontese_cards()) == 78 and piemontese_cards()[8][1] == 'Justice'
    assert len(family_archetypes(TAROCCO_BOLOGNESE)) == 62
    assert len(family_archetypes(TAROCCO_SICILIANO)) == 64   # 63 + tax-stamp Ace
    names = [n for n, *_ in family_archetypes(TAROCCO_SICILIANO)]
    assert len(set(names)) == 64 and 'Donna di Coppe' in names and 'Quattro di Denari' in names
    assert SPANISH_TO_LATIN_RANK['Sota'] == 'Knave'
    print('ok')
