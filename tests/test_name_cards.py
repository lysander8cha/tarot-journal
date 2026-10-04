"""Tests for the Greer name-card calculator (name_cards.py).

The JOHN QUINCY ADAMS vector and the property assertions come from the
spec's §10 (computed for the spec, hand-verified). The shared-root
property is structural: all three of theme_note/rhythm/melody sum the
same digits with reduction at different points, and digit-summing
preserves value mod 9 — a failure means a reduction moved.
"""

import random
import string

import pytest

import name_cards as nc
from birth_cards import reduce_to_22


# === The JOHN QUINCY ADAMS vector (§10, y_mode always_vowel) ===

@pytest.fixture
def jqa():
    return nc.calculate_name_cards(
        ['John', 'Quincy', 'Adams'], y_mode='always_vowel')


def test_jqa_per_part_sums(jqa):
    assert [p['vowel_sum'] for p in jqa['parts']] == [15, 37, 2]
    assert [p['consonant_sum'] for p in jqa['parts']] == [32, 34, 36]
    assert [p['sum'] for p in jqa['parts']] == [47, 71, 38]
    assert [p['role'] for p in jqa['parts']] == ['first', 'middle', 'last']


def test_jqa_name_cards(jqa):
    assert jqa['first_name_card'] == 11
    assert jqa['middle_name_card'] == 8
    assert jqa['last_name_card'] == 11
    assert jqa['theme_chord'] == [11, 8, 11]


def test_jqa_whole_name_cards(jqa):
    assert jqa['all_vowels'] == 54
    assert jqa['all_consonants'] == 102
    assert jqa['all_letters'] == 156
    assert jqa['desires_inner_motivation'] == 9
    assert jqa['outer_persona'] == 3
    assert jqa['theme_note'] == 3
    assert jqa['rhythm'] == 12
    assert jqa['melody'] == 12
    assert jqa['shared_root'] == 3
    assert jqa['hidden_factor_name'] == [21]


def test_jqa_constellation_count(jqa):
    assert jqa['constellation_count'] == {
        1: 4, 2: 0, 3: 2, 4: 2, 5: 2, 6: 1, 7: 1, 8: 2, 9: 1}
    assert sum(jqa['constellation_count'].values()) == 15
    assert jqa['absent'] == [2]
    assert jqa['most_represented'] == [1]


def test_jqa_life_potential():
    # Paired with birth date 1961-08-04 (base_number 1973)
    assert nc.life_potential(1973, 156) == 14


def test_jqa_presentation(jqa):
    assert jqa['leading_letter'] == {'letter': 'J', 'key': 10, 'is_vowel': False}
    assert jqa['first_vowel'] == {'letter': 'O', 'key': 15}
    assert len(jqa['mandala']) == 15
    assert jqa['max_letter_frequency'] == 2   # A and N appear twice
    assert jqa['rhythm_pattern'] == ['CVCC', 'CVVCCV', 'VCVCC']


# === Key numbers (§2) ===

def test_wxyz_use_reduced_values_only():
    assert nc.KEY_NUMBERS['W'] == 5
    assert nc.KEY_NUMBERS['X'] == 6
    assert nc.KEY_NUMBERS['Y'] == 7
    assert nc.KEY_NUMBERS['Z'] == 8
    assert max(nc.KEY_NUMBERS.values()) == 22


# === Role assignment (§1) ===

def test_two_part_name_has_null_middle():
    p = nc.calculate_name_cards(['Mary', 'Smith'])
    assert p['middle_name_card'] is None
    assert p['theme_chord'][1] is None
    # Theme Note sums only the two present cards
    assert p['theme_note'] == reduce_to_22(
        p['first_name_card'] + p['last_name_card'])


def test_mononym():
    p = nc.calculate_name_cards(['Cher'])
    assert p['first_name_card'] is not None
    assert p['middle_name_card'] is None
    assert p['last_name_card'] is None


def test_four_plus_parts_merge_interior_as_one_middle():
    p = nc.calculate_name_cards(['Anna', 'Maria', 'Luisa', 'Rossi'])
    roles = [part['role'] for part in p['parts']]
    assert roles == ['first', 'middle', 'middle', 'last']
    maria = nc.calculate_name_cards(['Maria'])['parts'][0]['sum']
    luisa = nc.calculate_name_cards(['Luisa'])['parts'][0]['sum']
    assert p['middle_name_card'] == reduce_to_22(maria + luisa)


def test_explicit_roles_override():
    # Two surnames, declared explicitly
    p = nc.calculate_name_cards(
        ['Gabriel', 'García', 'Márquez'],
        roles=['first', 'last', 'last'])
    assert p['middle_name_card'] is None
    garcia = nc.calculate_name_cards(['García'])['parts'][0]['sum']
    marquez = nc.calculate_name_cards(['Márquez'])['parts'][0]['sum']
    assert p['last_name_card'] == reduce_to_22(garcia + marquez)


def test_single_letter_part_is_a_normal_part():
    p = nc.calculate_name_cards(['Harry', 'S', 'Truman'])
    assert p['parts'][1]['sum'] == 19   # S = 19
    assert p['middle_name_card'] == 19


# === Normalization (§1) ===

def test_diacritics_stripped_and_flagged():
    a = nc.calculate_name_cards(['José'])
    b = nc.calculate_name_cards(['Jose'])
    assert a['normalized'] is True
    assert b['normalized'] is False
    for key in ('first_name_card', 'all_letters', 'melody'):
        assert a[key] == b[key]


def test_punctuation_dropped():
    a = nc.calculate_name_cards(["O'Brien"])
    b = nc.calculate_name_cards(['OBrien'])
    assert a['all_letters'] == b['all_letters']
    c = nc.calculate_name_cards(['Smith-Jones'])
    d = nc.calculate_name_cards(['Smithjones'])
    assert c['all_letters'] == d['all_letters']


def test_non_latin_rejected_not_coerced():
    with pytest.raises(ValueError, match='Latin'):
        nc.calculate_name_cards(['О\'Brien'])   # Cyrillic О
    with pytest.raises(ValueError, match='Latin'):
        nc.calculate_name_cards(['Владимир'])


def test_generational_suffixes_dropped_by_default():
    a = nc.calculate_name_cards(['Sammy', 'Davis', 'Jr.'])
    b = nc.calculate_name_cards(['Sammy', 'Davis'])
    assert a['all_letters'] == b['all_letters']
    assert a['dropped_suffixes'] == ['Jr.']
    assert a['last_name_card'] == b['last_name_card']
    c = nc.calculate_name_cards(['Sammy', 'Davis', 'Jr.'],
                                drop_suffixes=False)
    assert c['all_letters'] != b['all_letters']


def test_empty_input_rejected():
    with pytest.raises(ValueError):
        nc.calculate_name_cards([])
    with pytest.raises(ValueError):
        nc.calculate_name_cards(['   '])


# === Y handling (§3) ===

def test_y_heuristic():
    def y_class(parts):
        return [y['classified_as']
                for y in nc.calculate_name_cards(parts)['y_positions']]
    assert y_class(['Yvonne']) == ['consonant']   # word-initial
    assert y_class(['Mary']) == ['vowel']          # final
    assert y_class(['Kayla']) == ['vowel']         # Y before consonant... before L
    assert y_class(['Maya']) == ['consonant']      # Y before vowel A


def test_y_override_flips_single_letter():
    base = nc.calculate_name_cards(['Mary'])
    assert base['y_positions'][0]['classified_as'] == 'vowel'
    flipped = nc.calculate_name_cards(
        ['Mary'], y_overrides=[{'part': 0, 'index': 3, 'as': 'consonant'}])
    assert flipped['y_positions'][0]['classified_as'] == 'consonant'
    assert flipped['y_positions'][0]['overridden'] is True
    # Vowel/consonant totals shift by Y's key (7); the total doesn't move
    assert flipped['all_vowels'] == base['all_vowels'] - 7
    assert flipped['all_consonants'] == base['all_consonants'] + 7
    assert flipped['all_letters'] == base['all_letters']


def test_y_mode_changes_split_but_never_melody():
    v = nc.calculate_name_cards(['Quincy', 'Mayberry'], y_mode='always_vowel')
    c = nc.calculate_name_cards(['Quincy', 'Mayberry'], y_mode='always_consonant')
    assert v['desires_inner_motivation'] != c['desires_inner_motivation']
    assert v['outer_persona'] != c['outer_persona']
    assert v['melody'] == c['melody']
    assert v['all_letters'] == c['all_letters']


# === Property tests over random names ===

def _random_parts(rng):
    n_parts = rng.randint(1, 4)
    return [''.join(rng.choice(string.ascii_uppercase)
                    for _ in range(rng.randint(1, 10)))
            for _ in range(n_parts)]


def test_partition_and_shared_root_properties():
    """10,000 random names: vowels + consonants always partition the
    letters exactly, and theme_note/rhythm/melody always share a
    constellation root."""
    rng = random.Random(20260824)
    for _ in range(10_000):
        parts = _random_parts(rng)
        y_mode = rng.choice(nc.Y_MODES)
        p = nc.calculate_name_cards(parts, y_mode=y_mode)
        assert p['all_vowels'] + p['all_consonants'] == p['all_letters']
        roots = {nc.digital_root(p['theme_note']),
                 nc.digital_root(p['rhythm']),
                 nc.digital_root(p['melody'])}
        assert roots == {p['shared_root']}, parts
        assert sum(p['constellation_count'].values()) == len(
            ''.join(part['normalized'] for part in p['parts']))
        for card in (p['theme_note'], p['rhythm'], p['melody']):
            assert 1 <= card <= 22


def test_all_consonant_name_has_absent_desires_card():
    p = nc.calculate_name_cards(['Ng'])
    assert p['desires_inner_motivation'] is None
    assert p['outer_persona'] is not None
    assert p['rhythm'] == p['outer_persona']
    assert nc.digital_root(p['rhythm']) == p['shared_root']


# === API endpoints ===

def test_api_calculate_jqa(client):
    res = client.post('/api/name-cards/calculate', json={
        'parts': ['John', 'Quincy', 'Adams'], 'y_mode': 'always_vowel'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['theme_chord'] == [11, 8, 11]
    assert data['cards']['first_name']['name'] == 'Justice'
    assert data['cards']['theme_note']['name'] == 'The Empress'
    assert data['cards']['hidden_factor_name'][0]['number'] == 21
    assert data['life_potential'] is None       # no profile attached
    assert len(data['majors_by_number']) == 22


def test_api_calculate_with_profile_life_potential(client, db):
    pid = db.add_profile('JQA', birth_date='1961-08-04',
                         full_name='John Quincy Adams')
    res = client.post('/api/name-cards/calculate', json={
        'parts': ['John', 'Quincy', 'Adams'], 'y_mode': 'always_vowel',
        'profile_id': pid})
    data = res.get_json()
    assert data['life_potential'] == 14
    assert data['cards']['life_potential']['name'] == 'Temperance'


def test_api_calculate_rejects_bad_input(client):
    assert client.post('/api/name-cards/calculate',
                       json={'parts': []}).status_code == 400
    res = client.post('/api/name-cards/calculate',
                      json={'parts': ['Владимир']})
    assert res.status_code == 400
    assert 'Latin' in res.get_json()['error']


def test_api_name_cards_config_roundtrip(client, db):
    pid = db.add_profile('Config Test', full_name='Mary Ann van der Berg')
    res = client.get(f'/api/profiles/{pid}/name-cards-config')
    assert res.get_json() == {'full_name': 'Mary Ann van der Berg',
                              'config': None}
    config = {'parts': ['Mary', 'Ann', 'van der Berg'],
              'roles': ['first', 'middle', 'last'],
              'y_mode': 'heuristic',
              'y_overrides': [{'part': 0, 'index': 3, 'as': 'consonant'}]}
    res = client.put(f'/api/profiles/{pid}/name-cards-config',
                     json={'config': config})
    assert res.status_code == 200
    assert client.get(
        f'/api/profiles/{pid}/name-cards-config').get_json()['config'] == config
    # Null clears
    client.put(f'/api/profiles/{pid}/name-cards-config', json={'config': None})
    assert client.get(
        f'/api/profiles/{pid}/name-cards-config').get_json()['config'] is None


def test_api_full_name_persists_via_profile_routes(client):
    res = client.post('/api/profiles', json={
        'name': 'Display Name', 'full_name': 'Full Birth Name'})
    pid = res.get_json()['id']
    def full_name():
        return next(p for p in client.get('/api/profiles').get_json()
                    if p['id'] == pid)['full_name']
    assert full_name() == 'Full Birth Name'
    client.put(f'/api/profiles/{pid}', json={'full_name': 'Changed Name'})
    assert full_name() == 'Changed Name'


# === Profile PDF export ===

def _weasyprint_available():
    try:
        import weasyprint  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _weasyprint_available(),
                    reason='weasyprint needs DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib')
def test_profile_pdf_export(client, db):
    pid = db.add_profile('PDF Test', birth_date='1929-01-15',
                         full_name='John Quincy Adams')
    res = client.post(f'/api/profiles/{pid}/export-pdf', json={
        'include_birth_cards': True,
        'birth_card_methods': ['greer', 'amberstone'],
        'include_name_cards': True,
        'include_chart': True,   # no birth place -> section quietly omitted
    })
    assert res.status_code == 200
    assert res.mimetype == 'application/pdf'
    assert res.data[:5] == b'%PDF-'
    assert len(res.data) > 5000
    assert 'PDF_Test' in res.headers.get('Content-Disposition', '')


@pytest.mark.skipif(not _weasyprint_available(),
                    reason='weasyprint needs DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib')
def test_profile_pdf_unknown_profile(client):
    assert client.post('/api/profiles/99999/export-pdf',
                       json={}).status_code == 404


# === Alternate names (spec §9) ===

def test_profile_names_crud(client, db):
    pid = db.add_profile('Alt Names', full_name='Birth Name Here')
    assert client.get(f'/api/profiles/{pid}/names').get_json() == []

    r = client.post(f'/api/profiles/{pid}/names', json={
        'display_name': 'Stage Persona', 'name_kind': 'chosen'})
    assert r.status_code == 201
    nid = r.get_json()['id']

    names = client.get(f'/api/profiles/{pid}/names').get_json()
    assert len(names) == 1
    assert names[0]['display_name'] == 'Stage Persona'
    assert names[0]['name_kind'] == 'chosen'
    assert names[0]['y_mode'] == 'heuristic'

    client.put(f'/api/profile-names/{nid}', json={
        'parts': ['Stage', 'Persona'],
        'y_overrides': [{'part': 0, 'index': 0, 'as': 'vowel'}],
        'y_mode': 'always_consonant'})
    got = client.get(f'/api/profiles/{pid}/names').get_json()[0]
    assert got['parts'] == ['Stage', 'Persona']
    assert got['y_mode'] == 'always_consonant'
    assert got['y_overrides'] == [{'part': 0, 'index': 0, 'as': 'vowel'}]

    assert client.delete(f'/api/profile-names/{nid}').status_code == 200
    assert client.get(f'/api/profiles/{pid}/names').get_json() == []


def test_profile_names_travel_in_share_export(client, db):
    pid = db.add_profile('Sharer', full_name='Share Person')
    db.add_profile_name(pid, 'Nick', name_kind='nickname',
                        parts='["Nick"]')
    data = client.get(f'/api/profiles/export?ids={pid}').get_json()
    p = data['profiles'][0]
    assert p['alternate_names'][0]['display_name'] == 'Nick'
    assert p['alternate_names'][0]['parts'] == ['Nick']

    p['name'] = 'Sharer (copy)'
    res = client.post('/api/profiles/import', json=data).get_json()
    assert res['imported'] == 1
    profs = client.get('/api/profiles').get_json()
    new_pid = next(x['id'] for x in profs if x['name'] == 'Sharer (copy)')
    names = client.get(f'/api/profiles/{new_pid}/names').get_json()
    assert names[0]['display_name'] == 'Nick'
    assert names[0]['name_kind'] == 'nickname'
