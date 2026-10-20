"""Regional playing-card import presets: native names, the right
archetypes, and suit-name edits from the import dialog."""
import pytest

from import_presets import get_presets


def _preview(tmp_path, preset, files, suits=None):
    for f in files:
        (tmp_path / f).write_bytes(b'')
    return {r['filename']: r for r in get_presets().preview_import_with_metadata(
        str(tmp_path), preset, custom_suit_names=suits)}


@pytest.mark.parametrize('preset, filename, name, archetype', [
    ('Italian Playing Cards (40 cards)', 'd08.jpg', 'Fante di Denari', 'Knave of Coins'),
    ('Italian Playing Cards (40 cards)', 'b10.jpg', 'Re di Bastoni', 'King of Batons'),
    ('Spanish Playing Cards (40 cards)', 'o10.jpg', 'Sota de Oros', 'Knave of Coins'),
    ('Spanish Playing Cards (50 cards)', 'b09.jpg', 'Nueve de Bastos', 'Nine of Batons'),
    ('German Playing Cards (36 cards)', 'h14.jpg', 'Herz Ass', 'Ace of Hearts'),
    ('German Playing Cards (32 cards)', 'e12.jpg', 'Eichel Ober', 'Ober of Acorns'),
    ('German Playing Cards (36 cards)', 'b06.jpg', 'Schellen Sechs', 'Six of Bells'),
    ('German Playing Cards (36 cards)', 'a01.jpg', 'Eichel Ass', 'Ace of Acorns'),
    ('German Playing Cards (36 cards)', 'l13.jpg', 'Laub König', 'King of Leaves'),
    ('German Playing Cards (32 cards)', 'h11.jpg', 'Herz Unter', 'Unter of Hearts'),
    ('German Playing Cards (36 cards)', 'Two of Bells.jpg', 'Two Of Bells', 'Two of Bells'),
    ('Swiss Playing Cards (36 cards)', 's10.jpg', 'Schilten Banner', 'Banner of Shields'),
    ('Playing Cards (52 cards)', 'h01.jpg', 'Ace of Hearts', 'Ace of Hearts'),
    ('Playing Cards with Jokers (54 cards)', 'j1.jpg', 'Red Joker', 'Joker'),
    ('Playing Cards with Jokers (54 cards)', 'j2.jpg', 'Black Joker', 'Joker'),
    ('Playing Cards with Jokers (54 cards)', 'jb.jpg', 'Black Joker', 'Joker'),
])
def test_preset_maps_files(tmp_path, preset, filename, name, archetype):
    row = _preview(tmp_path, preset, [filename])[filename]
    assert (row['name'], row['archetype']) == (name, archetype)


def test_preset_suit_names_cover_all_four_suits():
    presets = get_presets()
    for name in ('Italian Playing Cards (40 cards)', 'Spanish Playing Cards (40 cards)',
                 'German Playing Cards (36 cards)', 'Swiss Playing Cards (36 cards)',
                 'Playing Cards (52 cards)'):
        suits = presets.get_preset(name)['suit_names']
        assert len(suits) == 4 and len(set(suits.values())) == 4, name


def test_edited_suit_name_renames_cards_keeping_archetype(tmp_path):
    suits = {'coins': 'Ori', 'cups': 'Coppe', 'swords': 'Spade', 'batons': 'Bastoni'}
    row = _preview(tmp_path, 'Italian Playing Cards (40 cards)', ['d01.jpg'], suits)['d01.jpg']
    assert (row['name'], row['archetype']) == ('Asso di Ori', 'Ace of Coins')


@pytest.mark.parametrize('preset, filename, name', [
    ('Tarocco Bolognese', 'm2.jpg', 'Moro 2'),
    ('Tarocco Bolognese', '09.jpg', 'Forza'),
    ('Tarocco Siciliano', '04.jpg', 'Costanza'),
    ('Tarocco Siciliano', 'c11.jpg', 'Donna di Coppe'),
    ('Tarocco Siciliano', 'd04.jpg', 'Quattro di Denari'),
])
def test_tarocco_presets(tmp_path, preset, filename, name):
    row = _preview(tmp_path, preset, [filename])[filename]
    assert row['name'] == row['archetype'] == name


def test_tarocco_types_seeded(db):
    counts = dict(db.conn.execute(
        "SELECT cartomancy_type, COUNT(*) FROM card_archetypes "
        "WHERE cartomancy_type LIKE 'Tarocco%' GROUP BY 1").fetchall())
    assert counts == {'Tarocco Bolognese': 62, 'Tarocco Siciliano': 64}


@pytest.mark.parametrize('filename, name, archetype', [
    ('08.jpg', 'La Giustizia', 'Justice'),
    ('11.jpg', 'La Forza', 'Strength'),
    ('c11.jpg', 'Fante di Coppe', 'Page of Cups'),
    ('d01.jpg', 'Asso di Denari', 'Ace of Pentacles'),
])
def test_piemontese_imports_as_tarot(tmp_path, filename, name, archetype):
    row = _preview(tmp_path, 'Tarocco Piemontese (78 cards)', [filename])[filename]
    assert (row['name'], row['archetype']) == (name, archetype)


def test_piemontese_type_folds_into_tarot(db):
    """A database from the day the Piemontese had its own type: its
    decks move to Tarot, cards relink, the type is gone."""
    from database.core import TAROCCO_PIEMONTESE
    c = db.conn.cursor()
    c.execute('INSERT INTO cartomancy_types (name) VALUES (?)', (TAROCCO_PIEMONTESE,))
    tid = c.lastrowid
    c.execute("INSERT INTO card_archetypes (name, cartomancy_type) VALUES ('La Giustizia', ?)",
              (TAROCCO_PIEMONTESE,))
    c.execute("INSERT INTO decks (name) VALUES ('Dal Negro')")
    deck = c.lastrowid
    c.execute('INSERT INTO deck_type_assignments (deck_id, type_id) VALUES (?, ?)', (deck, tid))
    c.execute("INSERT INTO cards (deck_id, name, archetype) VALUES (?, 'La Giustizia', 'La Giustizia')",
              (deck,))
    db._fold_piemontese_into_tarot(c)
    assert c.execute("SELECT archetype FROM cards WHERE deck_id = ?", (deck,)).fetchone()[0] == 'Justice'
    types = [r[0] for r in c.execute(
        'SELECT t.name FROM deck_type_assignments a JOIN cartomancy_types t ON t.id = a.type_id '
        'WHERE a.deck_id = ?', (deck,))]
    assert types == ['Tarot']
    assert c.execute('SELECT COUNT(*) FROM cartomancy_types WHERE name = ?',
                     (TAROCCO_PIEMONTESE,)).fetchone()[0] == 0
