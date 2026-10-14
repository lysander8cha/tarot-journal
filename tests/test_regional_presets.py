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
    ('Swiss Playing Cards (36 cards)', 's10.jpg', 'Schilten Banner', 'Banner of Shields'),
    ('Playing Cards (52 cards)', 'h01.jpg', 'Ace of Hearts', 'Ace of Hearts'),
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
