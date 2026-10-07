"""Reference-content datasets and endpoints: astrology, Kabbalah,
numerology, chakras.

Dataset integrity is asserted structurally (counts, uniqueness, the 22
paths carrying each trump exactly once) so a future edit that breaks
the tables fails loudly; endpoint tests check hydration shape and the
correspondence cross-references.
"""

import reference_content as rc
import birth_cards as bc


# === Dataset integrity ===

def _assign(client, sid, assignments):
    """Set system correspondence cells one at a time (the UI's per-cell route)."""
    for a in assignments:
        r = client.put(f"/api/correspondence-systems/{sid}/assignments/"
                       f"{a['archetype_id']}/{a['field_name']}",
                       json={'value': a['field_value']})
        assert r.status_code == 200, r.get_json()


def test_signs_dataset():
    assert len(rc.SIGNS) == 12
    names = [s['name'] for s in rc.SIGNS]
    assert names == bc._SIGN_ORDER          # same order as the decan calendar
    for s in rc.SIGNS:
        assert s['element'] in ('Fire', 'Earth', 'Air', 'Water')
        assert s['modality'] in ('Cardinal', 'Fixed', 'Mutable')
        assert s['name'] in bc.SIGN_MAJORS  # every sign has a trump


def test_planets_dataset():
    assert len(rc.PLANETS) == 10
    classical = [p['name'] for p in rc.PLANETS if p['classical']]
    assert set(classical) == set(bc.PLANET_MAJORS)
    modern = [p['name'] for p in rc.PLANETS if not p['classical']]
    assert set(modern) == set(rc.MODERN_PLANET_MAJORS)
    # Every sign's ruler is a real planet
    planet_names = {p['name'] for p in rc.PLANETS}
    for s in rc.SIGNS:
        assert s['ruler'] in planet_names
        if 'modern_ruler' in s:
            assert s['modern_ruler'] in planet_names


def test_sephiroth_dataset():
    assert len(rc.SEPHIROTH) == 10
    assert [s['number'] for s in rc.SEPHIROTH] == list(range(1, 11))
    for s in rc.SEPHIROTH:
        assert s['pillar'] in ('middle', 'mercy', 'severity')
        assert 0 <= s['x'] <= 100 and 0 <= s['y'] <= 100
    # Three pillars with the standard membership
    middle = [s['number'] for s in rc.SEPHIROTH if s['pillar'] == 'middle']
    assert middle == [1, 6, 9, 10]


def test_tree_paths_dataset():
    assert len(rc.TREE_PATHS) == 22
    assert [p['path'] for p in rc.TREE_PATHS] == list(range(11, 33))
    # Each trump 1-22 appears exactly once; letters unique; endpoints valid
    assert sorted(p['trump'] for p in rc.TREE_PATHS) == list(range(1, 23))
    assert len({p['letter'] for p in rc.TREE_PATHS}) == 22
    assert len({p['glyph'] for p in rc.TREE_PATHS}) == 22
    # Hebrew letter gematria values sum to 1495
    assert sum(p['value'] for p in rc.TREE_PATHS) == 1495
    sephira_numbers = {s['number'] for s in rc.SEPHIROTH}
    for p in rc.TREE_PATHS:
        assert p['from'] in sephira_numbers and p['to'] in sephira_numbers
        assert p['from'] < p['to']
    # Every sephira is touched by at least one path
    touched = {n for p in rc.TREE_PATHS for n in (p['from'], p['to'])}
    assert touched == sephira_numbers


def test_chakras_and_numbers_datasets():
    assert len(rc.CHAKRAS) == 7
    assert [c['name'] for c in rc.CHAKRAS][0] == 'Root'
    assert [c['name'] for c in rc.CHAKRAS][-1] == 'Crown'
    # NUMBERS is a flat, open-ended list: unique labels, required keys
    labels = [n['number'] for n in rc.NUMBERS]
    assert len(labels) == len(set(labels))
    for n in rc.NUMBERS:
        assert n['title'] and n['meaning']
        assert 'system' in n


# === Endpoints ===

def test_astrology_endpoint(client):
    data = client.get('/api/reference/astrology').get_json()
    assert len(data['signs']) == 12
    assert len(data['planets']) == 10
    assert data['court_system'] in bc.COURT_SYSTEMS

    aries = data['signs'][0]
    assert aries['name'] == 'Aries'
    assert aries['dates'] == 'Mar 21 – Apr 20'
    assert aries['trump']['name'] == 'The Emperor'
    assert len(aries['decans']) == 3
    assert aries['decans'][0]['minor']['name'] == 'Two of Wands'
    assert aries['decans'][0]['planet'] == 'Mars'
    # Both court arcs, under all three systems, all distinct tables
    assert set(aries['courts']) == set(bc.COURT_SYSTEMS)
    for system, arcs in aries['courts'].items():
        assert len(arcs) == 2
    assert aries['courts']['golden_dawn'][0]['name'] == 'Queen of Wands'
    assert aries['courts']['bota'][0]['name'] == 'King of Wands'

    # Leo's trump is always canonical Strength (card identity)
    leo = next(s for s in data['signs'] if s['name'] == 'Leo')
    assert leo['trump']['name'] == 'Strength'

    mars = next(p for p in data['planets'] if p['name'] == 'Mars')
    assert mars['trump']['name'] == 'The Tower'
    assert mars['modern_attribution'] is False
    # Mars rules 6 decans (the Chaldean doubling at the Pisces seam)
    assert len(mars['decans_ruled']) == 6
    uranus = next(p for p in data['planets'] if p['name'] == 'Uranus')
    assert uranus['trump']['name'] == 'The Fool'
    assert uranus['modern_attribution'] is True


def test_astrology_today_decan_and_positions(client):
    """The wheel's markers: today's decan is always a real position,
    and decan_position round-trips the decan table."""
    assert bc.decan_position({'rank': 2, 'suit': 'Wands'}) == {
        'sign': 'Aries', 'index': 1}
    # The year-boundary wrap decan sits in Capricorn II
    assert bc.decan_position({'rank': 3, 'suit': 'Pentacles'}) == {
        'sign': 'Capricorn', 'index': 2}

    data = client.get('/api/reference/astrology').get_json()
    today = data['today_decan']
    assert today['sign'] in [s['name'] for s in rc.SIGNS]
    assert today['index'] in (1, 2, 3)


def test_kabbalah_endpoint(client):
    data = client.get('/api/reference/kabbalah').get_json()
    assert len(data['sephiroth']) == 10
    assert len(data['paths']) == 22
    kether = data['sephiroth'][0]
    assert [m['name'] for m in kether['minors']] == [
        'Ace of Wands', 'Ace of Cups', 'Ace of Swords', 'Ace of Pentacles']
    malkuth = data['sephiroth'][-1]
    assert malkuth['minors'][0]['name'] == 'Ten of Wands'
    path11 = data['paths'][0]
    assert path11['letter'] == 'Aleph'
    assert path11['trump']['name'] == 'The Fool'


def test_tree_courts_follow_court_preference(client):
    """Tetragrammaton courts on 2/3/6/10, rank names per the saved
    Courts preference (user ruling: B.O.T.A. reads as Book T titles)."""
    # Dataset: all three systems present, keys fixed
    assert set(rc.TREE_COURT_RANKS) == set(bc.COURT_SYSTEMS)
    for table in rc.TREE_COURT_RANKS.values():
        assert set(table) == {2, 3, 6, 10}
        assert table[3] == 'Queen' and table[10] == 'Page'

    data = client.get('/api/reference/kabbalah').get_json()
    by_number = {s['number']: s for s in data['sephiroth']}
    assert data['court_system'] == 'golden_dawn'
    assert by_number[2]['court_rank'] == 'King'
    assert [c['name'] for c in by_number[6]['courts']] == [
        'Knight of Wands', 'Knight of Cups', 'Knight of Swords',
        'Knight of Pentacles']
    # No courts off the Tetragrammaton four
    assert 'courts' not in by_number[1] and 'courts' not in by_number[9]

    # Waite figures flip the 2/6 ranks
    client.put('/api/birth-cards/prefs', json={'court_system': 'golden_dawn_waite'})
    data = client.get('/api/reference/kabbalah').get_json()
    by_number = {s['number']: s for s in data['sephiroth']}
    assert by_number[2]['court_rank'] == 'Knight'
    assert by_number[6]['court_rank'] == 'King'

    # B.O.T.A. reads as Book T titles on the tree
    client.put('/api/birth-cards/prefs', json={'court_system': 'bota'})
    data = client.get('/api/reference/kabbalah').get_json()
    by_number = {s['number']: s for s in data['sephiroth']}
    assert by_number[2]['court_rank'] == 'King'
    assert by_number[6]['court_rank'] == 'Knight'


def test_numerology_endpoint(client):
    data = client.get('/api/reference/numerology').get_json()
    entries = {e['number']: e for e in data['entries']}
    # 0: just the Fool, no minors
    assert [m['name'] for m in entries['0']['majors']] == ['The Fool']
    assert 'minors' not in entries['0']
    # 5: constellation pair + four Fives
    assert [m['number'] for m in entries['5']['majors']] == [5, 14]
    assert len(entries['5']['minors']) == 4
    # 10: Tens but no constellation block (10 is not a root)
    assert 'majors' not in entries['10']
    assert entries['10']['minors'][0]['name'] == 'Ten of Wands'


def test_kabbalah_tree_tabs(client):
    """Configured trees: the letter's card comes from the system's
    hebrew_letter assignment (a Thoth-style Tzaddi swap shows through)
    and images come from the tree's own deck, not the default deck."""
    # A system whose Tzaddi is The Emperor (Thoth-style swap)
    sid = client.post('/api/correspondence-systems', json={
        'name': 'ZZ Thoth Style', 'cartomancy_type': 'Tarot'}).get_json()['id']
    arch = client.post('/api/archetypes', json={
        'cartomancy_type': 'Tarot', 'name': 'ZZ Emperor'}).get_json()['id']
    _assign(client, sid, [{'archetype_id': arch, 'field_name': 'hebrew_letter',
                         'field_value': 'Tzaddi'}])
    # A deck holding that card, for the image lookup
    types = client.get('/api/types').get_json()
    tarot = next(t for t in types if t['name'] == 'Tarot')
    deck = client.post('/api/decks', json={
        'name': 'ZZ Tree Deck', 'type_ids': [tarot['id']]}).get_json()
    card = client.post('/api/cards', json={
        'deck_id': deck['id'], 'name': 'ZZ Emperor'}).get_json()

    data = client.get(
        f"/api/reference/kabbalah?system_id={sid}&deck_id={deck['id']}").get_json()
    tzaddi = next(p for p in data['paths'] if p['letter'] == 'Tzaddi')
    assert [c['name'] for c in tzaddi['letter_cards']] == ['ZZ Emperor']
    assert tzaddi['letter_cards'][0]['card_id'] == card['id']
    # Unassigned letters stay bare; the canonical trump is still there
    aleph = data['paths'][0]
    assert aleph['letter_cards'] == []
    assert aleph['trump']['name'] == 'The Fool'


def test_tree_matches_combined_letter_values(client):
    """The seeded systems store hebrew_letter values as 'glyph / name'
    ('צ / Tsadi', 'ה / He', even 'ח/ Chet' with a missing space) and
    put sephira attributions ('כֶּתֶר / Kether') in the same field.
    Both must land on the tree: the Thoth Emperor/Star swap on the
    paths, sephira cards replacing the rank-derived panel."""
    sid = client.post('/api/correspondence-systems', json={
        'name': 'ZZ Combined Values', 'cartomancy_type': 'Tarot'}).get_json()['id']
    ids = {}
    for name in ('ZZ Star', 'ZZ Emperor', 'ZZ Chariot', 'ZZ Ace'):
        ids[name] = client.post('/api/archetypes', json={
            'cartomancy_type': 'Tarot', 'name': name}).get_json()['id']
    _assign(client, sid, [
            {'archetype_id': ids['ZZ Star'], 'field_name': 'hebrew_letter',
             'field_value': 'ה / He'},
            {'archetype_id': ids['ZZ Emperor'], 'field_name': 'hebrew_letter',
             'field_value': 'צ / Tsadi'},
            {'archetype_id': ids['ZZ Chariot'], 'field_name': 'hebrew_letter',
             'field_value': 'ח/ Chet'},
            {'archetype_id': ids['ZZ Ace'], 'field_name': 'hebrew_letter',
             'field_value': 'כֶּתֶר / Kether'},
        ])

    data = client.get(f'/api/reference/kabbalah?system_id={sid}').get_json()
    by_letter = {p['letter']: p for p in data['paths']}
    assert [c['name'] for c in by_letter['Heh']['letter_cards']] == ['ZZ Star']
    assert [c['name'] for c in by_letter['Tzaddi']['letter_cards']] == ['ZZ Emperor']
    assert [c['name'] for c in by_letter['Cheth']['letter_cards']] == ['ZZ Chariot']

    by_number = {s['number']: s for s in data['sephiroth']}
    assert [c['name'] for c in by_number[1]['cards']] == ['ZZ Ace']
    # Sephiroth the system doesn't cover keep the rank-derived panel
    assert 'cards' not in by_number[2]
    assert by_number[2]['court_rank'] == 'King'


def test_sephira_cards_split_pips_from_courts(client):
    """A sephira's system-assigned cards arrive as separate pip and
    court lists so the viewer can segregate them."""
    sid = client.post('/api/correspondence-systems', json={
        'name': 'ZZ Split Test', 'cartomancy_type': 'Tarot'}).get_json()['id']
    ids = {}
    for name in ('Two of ZZTest', 'King of ZZTest', 'Queen of ZZTest'):
        ids[name] = client.post('/api/archetypes', json={
            'cartomancy_type': 'Tarot', 'name': name}).get_json()['id']
    _assign(client, sid, [
            {'archetype_id': aid, 'field_name': 'hebrew_letter',
             'field_value': 'חׇכְמָה / Chokmah'}
            for aid in ids.values()
        ])
    data = client.get(f'/api/reference/kabbalah?system_id={sid}').get_json()
    chokmah = next(s for s in data['sephiroth'] if s['number'] == 2)
    assert [c['name'] for c in chokmah['cards']] == ['Two of ZZTest']
    assert {c['name'] for c in chokmah['court_cards']} == {
        'King of ZZTest', 'Queen of ZZTest'}


def test_kabbalah_trees_config(client):
    """Tree-tab config round-trips through settings with validation."""
    assert client.get('/api/reference/kabbalah/trees').get_json() == {'trees': []}
    trees = [{'label': 'Golden Dawn', 'system_id': 1, 'deck_id': 2},
             {'label': 'Thoth', 'system_id': 3, 'deck_id': 4}]
    r = client.put('/api/reference/kabbalah/trees', json={'trees': trees})
    assert r.status_code == 200
    assert client.get('/api/reference/kabbalah/trees').get_json() == {'trees': trees}
    # Validation: missing label / ids rejected
    assert client.put('/api/reference/kabbalah/trees', json={
        'trees': [{'label': ' ', 'system_id': 1, 'deck_id': 2}]}).status_code == 400
    assert client.put('/api/reference/kabbalah/trees', json={
        'trees': [{'label': 'X', 'system_id': 1}]}).status_code == 400
    # Bad writes leave the stored config untouched
    assert client.get('/api/reference/kabbalah/trees').get_json() == {'trees': trees}


def test_suits_and_ranks_endpoints(client):
    """Suits and ranks per deck type: Tarot curated, other suited
    types derived from their archetypes; type tabs list every deck
    type whose archetypes carry suits, Tarot first."""
    data = client.get('/api/reference/suits').get_json()
    assert data['type'] == 'Tarot'
    assert data['types'][0] == 'Tarot'
    assert 'Playing Cards' in data['types']
    assert [s['name'] for s in data['suits']] == [
        'Wands', 'Cups', 'Swords', 'Pentacles']
    wands = data['suits'][0]
    assert wands['element'] == 'Fire'
    assert [p['name'] for p in wands['pips']][:2] == ['Ace of Wands', 'Two of Wands']
    assert len(wands['pips']) == 10
    assert [c['name'] for c in wands['courts']] == [
        'Page of Wands', 'Knight of Wands', 'Queen of Wands', 'King of Wands']

    # A derived type: suits and pip/court split come from archetypes;
    # suit order mirrors the Tarot suits through their counterparts
    data = client.get('/api/reference/suits?type=Playing Cards').get_json()
    assert data['type'] == 'Playing Cards'
    assert [s['name'] for s in data['suits']] == [
        'Clubs', 'Hearts', 'Spades', 'Diamonds']
    by_name = {s['name']: s for s in data['suits']}
    hearts = by_name['Hearts']
    assert [p['name'] for p in hearts['pips']][:2] == [
        'Ace of Hearts', 'Two of Hearts']
    assert [c['name'] for c in hearts['courts']] == [
        'Jack of Hearts', 'Queen of Hearts', 'King of Hearts']
    # No curated extras off Tarot
    assert 'element' not in hearts

    # An unknown type falls back to Tarot
    assert client.get(
        '/api/reference/suits?type=Nonsense').get_json()['type'] == 'Tarot'

    # Ranks: Tarot rank labels derive from names (stored ranks are
    # sort codes); derived types use their word ranks
    ranks = client.get('/api/reference/ranks').get_json()
    assert ranks['type'] == 'Tarot'
    labels = [r['rank'] for r in ranks['ranks']]
    assert labels[:3] == ['Ace', 'Two', 'Three']
    assert labels[-4:] == ['Page', 'Knight', 'Queen', 'King']
    king = next(r for r in ranks['ranks'] if r['rank'] == 'King')
    assert {c['name'] for c in king['cards']} == {
        'King of Wands', 'King of Cups', 'King of Swords', 'King of Pentacles'}

    ranks = client.get(
        '/api/reference/ranks?type=Playing Cards (Latin-suited)').get_json()
    labels = [r['rank'] for r in ranks['ranks']]
    assert labels[-3:] == ['Knave', 'Knight', 'King']
    ranks = client.get(
        '/api/reference/ranks?type=Playing Cards (German-suited)').get_json()
    labels = [r['rank'] for r in ranks['ranks']]
    assert labels[0] == 'Ace' and labels[-4:] == ['Unter', 'Ober', 'King', 'Weli']
    suits = client.get(
        '/api/reference/suits?type=Playing Cards (German-suited)').get_json()
    assert [s['name'] for s in suits['suits']] == ['Acorns', 'Hearts', 'Leaves', 'Bells']

    # Numerology no longer bundles ranks; it lists the type tabs
    num = client.get('/api/reference/numerology').get_json()
    assert 'ranks' not in num
    assert num['suit_types'][0] == 'Tarot'


def test_lenormand_insets(client):
    """Petit Lenormand archetypes carry the standard playing-card
    inset rank/suit, so the type joins the suited tabs naturally."""
    import reference_content as ref
    # Dataset integrity: 36 insets tiling 4 suits x 9 ranks exactly
    assert len(ref.LENORMAND_INSETS) == 36
    combos = set(ref.LENORMAND_INSETS.values())
    assert len(combos) == 36
    for suit in ('Hearts', 'Clubs', 'Spades', 'Diamonds'):
        ranks = {r for r, s in combos if s == suit}
        assert ranks == {'Ace', 'Six', 'Seven', 'Eight', 'Nine', 'Ten',
                         'Jack', 'Queen', 'King'}

    data = client.get('/api/reference/suits').get_json()
    assert 'Petit Lenormand' in data['types']
    assert 'Lenormand' not in data['types']

    data = client.get('/api/reference/suits?type=Petit Lenormand').get_json()
    hearts = next(s for s in data['suits'] if s['name'] == 'Hearts')
    pips = {c['name']: c['rank'] for c in hearts['pips']}
    assert pips['Rider'] == 'Nine'
    assert pips['Man'] == 'Ace'
    courts = {c['name']: c['rank'] for c in hearts['courts']}
    assert courts == {'Heart': 'Jack', 'Stork': 'Queen', 'House': 'King'}

    ranks = client.get('/api/reference/ranks?type=Petit Lenormand').get_json()
    aces = next(r for r in ranks['ranks'] if r['rank'] == 'Ace')
    assert {c['name'] for c in aces['cards']} == {'Ring', 'Man', 'Woman', 'Sun'}


def test_petit_lenormand_rename_migration(tmp_path):
    """An existing DB with the old 'Lenormand' type name and 1-36
    archetype ranks gets renamed and inset-backfilled on reopen."""
    from database import Database
    path = str(tmp_path / 'migrate.db')
    db = Database(db_path=path)
    cur = db.conn.cursor()
    # Simulate the pre-rename state: old name, card numbers in rank
    cur.execute("UPDATE cartomancy_types SET name='Lenormand' "
                "WHERE name='Petit Lenormand'")
    cur.execute("UPDATE card_archetypes SET cartomancy_type='Lenormand' "
                "WHERE cartomancy_type='Petit Lenormand'")
    cur.execute("UPDATE card_archetypes SET rank='1', suit=NULL "
                "WHERE cartomancy_type='Lenormand' AND name='Rider'")
    cur.execute("DELETE FROM settings WHERE key='petit_lenormand_rename_done'")
    db._commit()
    db.close()

    db = Database(db_path=path)
    cur = db.conn.cursor()
    assert cur.execute("SELECT COUNT(*) FROM cartomancy_types "
                       "WHERE name='Lenormand'").fetchone()[0] == 0
    row = cur.execute(
        "SELECT rank, suit FROM card_archetypes "
        "WHERE cartomancy_type='Petit Lenormand' AND name='Rider'"
    ).fetchone()
    assert (row[0], row[1]) == ('Nine', 'Hearts')
    db.close()


def test_suit_and_rank_entity_notes(client):
    """Suit and rank notes are deck-type-scoped ('<type>::<name>'
    keys) — the same suit name in two traditions holds separate
    notes."""
    src = client.post('/api/reference/sources', json={
        'name': 'ZZ Suit Source', 'cartomancy_types': ['Tarot']}).get_json()['id']
    for kind, key in (('suit', 'Tarot::Wands'), ('rank', 'Tarot::Queen')):
        r = client.put('/api/reference/entity-notes', json={
            'kind': kind, 'key': key, 'source_id': src, 'content': '<p>x</p>'})
        assert r.status_code == 200
        assert len(client.get(
            f'/api/reference/entity-notes?kind={kind}&key={key}'
        ).get_json()['notes']) == 1
    # Another type's same-named suit is a separate entity
    assert client.get(
        '/api/reference/entity-notes?kind=suit&key=Petit Lenormand::Wands'
    ).get_json()['notes'] == []


def test_entity_notes_crud(client):
    """Source texts on reference entities: upsert per (entity, source),
    blank content deletes, invalid kinds and unknown sources rejected."""
    sid = client.post('/api/reference/sources', json={
        'name': 'ZZ Astrology Book', 'cartomancy_types': ['Tarot'],
    }).get_json()['id']

    r = client.put('/api/reference/entity-notes', json={
        'kind': 'sign', 'key': 'Leo', 'source_id': sid,
        'content': '<p>The lion.</p>'})
    assert r.status_code == 200
    notes = client.get(
        '/api/reference/entity-notes?kind=sign&key=Leo').get_json()['notes']
    assert len(notes) == 1
    assert notes[0]['source_name'] == 'ZZ Astrology Book'
    assert notes[0]['content'] == '<p>The lion.</p>'

    # Upsert replaces; other entities unaffected
    client.put('/api/reference/entity-notes', json={
        'kind': 'sign', 'key': 'Leo', 'source_id': sid,
        'content': '<p>Revised.</p>'})
    notes = client.get(
        '/api/reference/entity-notes?kind=sign&key=Leo').get_json()['notes']
    assert [n['content'] for n in notes] == ['<p>Revised.</p>']
    assert client.get(
        '/api/reference/entity-notes?kind=sign&key=Aries'
    ).get_json()['notes'] == []
    # Same source can annotate a different kind
    client.put('/api/reference/entity-notes', json={
        'kind': 'sephira', 'key': 'Geburah', 'source_id': sid,
        'content': '<p>Severity.</p>'})
    assert len(client.get(
        '/api/reference/entity-notes?kind=sephira&key=Geburah'
    ).get_json()['notes']) == 1

    # Blank content deletes
    client.put('/api/reference/entity-notes', json={
        'kind': 'sign', 'key': 'Leo', 'source_id': sid, 'content': '  '})
    assert client.get(
        '/api/reference/entity-notes?kind=sign&key=Leo'
    ).get_json()['notes'] == []

    # Validation
    assert client.put('/api/reference/entity-notes', json={
        'kind': 'geese', 'key': 'Leo', 'source_id': sid,
        'content': 'x'}).status_code == 400
    assert client.put('/api/reference/entity-notes', json={
        'kind': 'sign', 'key': 'Leo', 'source_id': 999999,
        'content': 'x'}).status_code == 404
    assert client.get(
        '/api/reference/entity-notes?kind=geese&key=Leo').status_code == 400


def test_chakra_matching_real_value_formats(client):
    """Chakra values as the seeded systems store them — slash-joined
    ordinal / IAST Sanskrit / common name — and bare IAST spellings
    both land on the right chakra."""
    sid = client.post('/api/correspondence-systems', json={
        'name': 'ZZ Chakra Test', 'cartomancy_type': 'Tarot'}).get_json()['id']
    a1 = client.post('/api/archetypes', json={
        'cartomancy_type': 'Tarot', 'name': 'ZZ Chakra Card A'}).get_json()['id']
    a2 = client.post('/api/archetypes', json={
        'cartomancy_type': 'Tarot', 'name': 'ZZ Chakra Card B'}).get_json()['id']
    _assign(client, sid, [
            {'archetype_id': a1, 'field_name': 'chakra',
             'field_value': 'Fifth Chakra / Viśuddha / Throat Chakra'},
            {'archetype_id': a2, 'field_name': 'chakra',
             'field_value': 'Mūlādhāra'},
        ])
    data = client.get(f'/api/reference/chakras?system_id={sid}').get_json()
    by_name = {c['name']: c for c in data['chakras']}
    assert [a['name'] for a in by_name['Throat']['assigned']] == ['ZZ Chakra Card A']
    assert [a['name'] for a in by_name['Root']['assigned']] == ['ZZ Chakra Card B']
    assert by_name['Heart']['assigned'] == []


def test_chakras_endpoint(client):
    data = client.get('/api/reference/chakras').get_json()
    assert len(data['chakras']) == 7
    assert data['chakras'][3]['name'] == 'Heart'
    assert data['chakras'][3]['assigned'] == []


def test_correspondence_cross_references(client):
    """A chosen system's assignments surface on the matching entities —
    including decan values counting toward their sign and planet, and
    hebrew-letter alias spellings."""
    sid = client.post('/api/correspondence-systems', json={
        'name': 'ZZ Ref Test', 'cartomancy_type': 'Tarot'}).get_json()['id']
    a1 = client.post('/api/archetypes', json={
        'cartomancy_type': 'Tarot', 'name': 'ZZ Test Card A'}).get_json()['id']
    a2 = client.post('/api/archetypes', json={
        'cartomancy_type': 'Tarot', 'name': 'ZZ Test Card B'}).get_json()['id']
    _assign(client, sid, [
            {'archetype_id': a1, 'field_name': 'zodiac_sign', 'field_value': 'Leo'},
            {'archetype_id': a1, 'field_name': 'chakra', 'field_value': 'Anahata'},
            {'archetype_id': a1, 'field_name': 'numerology', 'field_value': '7'},
            {'archetype_id': a1, 'field_name': 'hebrew_letter', 'field_value': 'Alef'},
            {'archetype_id': a2, 'field_name': 'decan', 'field_value': 'Jupiter in Leo'},
        ])

    astro = client.get(f'/api/reference/astrology?system_id={sid}').get_json()
    leo = next(s for s in astro['signs'] if s['name'] == 'Leo')
    assert {a['name'] for a in leo['assigned']} == {'ZZ Test Card A', 'ZZ Test Card B'}
    jupiter = next(p for p in astro['planets'] if p['name'] == 'Jupiter')
    assert {a['name'] for a in jupiter['assigned']} == {'ZZ Test Card B'}
    # Unassigned sign stays empty
    aries = astro['signs'][0]
    assert aries['assigned'] == []

    kab = client.get(f'/api/reference/kabbalah?system_id={sid}').get_json()
    aleph = kab['paths'][0]
    assert [a['name'] for a in aleph['letter_cards']] == ['ZZ Test Card A']

    num = client.get(f'/api/reference/numerology?system_id={sid}').get_json()
    seven = next(e for e in num['entries'] if e['number'] == '7')
    assert [a['name'] for a in seven['assigned']] == ['ZZ Test Card A']

    chak = client.get(f'/api/reference/chakras?system_id={sid}').get_json()
    heart = next(c for c in chak['chakras'] if c['name'] == 'Heart')
    assert [a['name'] for a in heart['assigned']] == ['ZZ Test Card A']

    # No system_id: cross-refs quietly absent
    astro = client.get('/api/reference/astrology').get_json()
    assert astro['signs'][4]['assigned'] == []
