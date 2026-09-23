"""Tests for the phone-companion sync layer (Phase 0).

Covers: pairing (code exchange, single use, expiry), the auth model
(loopback trusted, LAN needs the bearer token, LAN locked out of the
rest of the API), deck favorites, the snapshot/delta sync endpoints,
and the updated_at touch guarantees the delta sync relies on.

LAN callers are simulated with environ_overrides={'REMOTE_ADDR': ...}.
"""

import json

from backend.routes.sync import install_lan_guard
from tests.conftest import make_deck_with_card

LAN = {'REMOTE_ADDR': '192.168.1.50'}


def _pair(client, device_name='test-phone'):
    """Run the whole pairing dance; returns the bearer token."""
    code = client.post('/api/sync/pairing/start').get_json()['code']
    res = client.post('/api/sync/pair', json={
        'code': code, 'device_name': device_name,
    }, environ_overrides=LAN)
    assert res.status_code == 200
    return res.get_json()['token']


def _auth(token):
    return {'Authorization': f'Bearer {token}'}


# ── Pairing & auth ───────────────────────────────────────────

def test_pairing_flow(client, db):
    status = client.get('/api/sync/status').get_json()
    assert status['paired'] is False

    token = _pair(client)
    assert token

    status = client.get('/api/sync/status').get_json()
    assert status['paired'] is True
    assert status['device_name'] == 'test-phone'

    # The token works from the LAN
    res = client.get('/api/sync/manifest', headers=_auth(token),
                     environ_overrides=LAN)
    assert res.status_code == 200


def test_pairing_code_is_single_use(client):
    code = client.post('/api/sync/pairing/start').get_json()['code']
    ok = client.post('/api/sync/pair', json={'code': code},
                     environ_overrides=LAN)
    assert ok.status_code == 200
    again = client.post('/api/sync/pair', json={'code': code},
                        environ_overrides=LAN)
    assert again.status_code == 401


def test_wrong_or_expired_code_rejected(client, flask_app):
    client.post('/api/sync/pairing/start')
    res = client.post('/api/sync/pair', json={'code': '000000'},
                      environ_overrides=LAN)
    # (Astronomically unlikely collision aside — the real code is random.)
    if flask_app.config['PHONE_PAIRING']['code'] != '000000':
        assert res.status_code == 401

    # Force expiry
    flask_app.config['PHONE_PAIRING']['expires'] = 0
    real_code = flask_app.config['PHONE_PAIRING']['code']
    res = client.post('/api/sync/pair', json={'code': real_code},
                      environ_overrides=LAN)
    assert res.status_code == 401


def test_lan_needs_token(client):
    res = client.get('/api/sync/manifest', environ_overrides=LAN)
    assert res.status_code == 401
    res = client.get('/api/sync/manifest',
                     headers=_auth('not-the-real-token'),
                     environ_overrides=LAN)
    assert res.status_code == 401


def test_loopback_is_trusted_without_token(client):
    assert client.get('/api/sync/manifest').status_code == 200


def test_unpair_revokes_token(client):
    token = _pair(client)
    client.post('/api/sync/unpair')
    res = client.get('/api/sync/manifest', headers=_auth(token),
                     environ_overrides=LAN)
    assert res.status_code == 401


def test_pairing_endpoints_are_loopback_only(client):
    assert client.post('/api/sync/pairing/start',
                       environ_overrides=LAN).status_code == 403
    assert client.get('/api/sync/status',
                      environ_overrides=LAN).status_code == 403
    assert client.post('/api/sync/unpair',
                       environ_overrides=LAN).status_code == 403
    assert client.put('/api/sync/enabled', json={'enabled': True},
                      environ_overrides=LAN).status_code == 403


def test_lan_guard_blocks_rest_of_api(flask_app, client):
    install_lan_guard(flask_app)
    # Loopback still reaches everything
    assert client.get('/api/decks').status_code == 200
    # LAN callers are refused outside /api/sync/, token or not
    token = _pair(client)
    res = client.get('/api/decks', environ_overrides=LAN)
    assert res.status_code == 403
    res = client.get('/api/decks', headers=_auth(token),
                     environ_overrides=LAN)
    assert res.status_code == 403
    # ...but sync routes still work
    res = client.get('/api/sync/manifest', headers=_auth(token),
                     environ_overrides=LAN)
    assert res.status_code == 200


def test_enabled_toggle_persists(client, db):
    res = client.put('/api/sync/enabled', json={'enabled': True})
    assert res.get_json()['restart_required'] is True
    assert db.get_setting('phone_sync_enabled') == 'true'
    client.put('/api/sync/enabled', json={'enabled': False})
    assert db.get_setting('phone_sync_enabled') == 'false'


# ── Favorites ────────────────────────────────────────────────

def test_deck_favorite_toggle(client, db):
    deck_id, _ = make_deck_with_card(db)
    assert db.get_deck(deck_id)['favorite'] == 0
    res = client.put(f'/api/decks/{deck_id}', json={'favorite': True})
    assert res.status_code == 200
    assert db.get_deck(deck_id)['favorite'] == 1
    client.put(f'/api/decks/{deck_id}', json={'favorite': False})
    assert db.get_deck(deck_id)['favorite'] == 0


# ── Data endpoints ───────────────────────────────────────────

def test_snapshot_decks_and_cards_favorites_only(client, db):
    fav_id, fav_card = make_deck_with_card(db, deck_name='ZZ Fav')
    other_id, other_card = make_deck_with_card(db, deck_name='ZZ Other')
    db.update_deck(fav_id, favorite=True)

    rows = client.get('/api/sync/snapshot/decks').get_json()['rows']
    assert [r['id'] for r in rows] == [fav_id]

    cards = client.get('/api/sync/snapshot/cards').get_json()['rows']
    deck_ids = {c['deck_id'] for c in cards}
    assert fav_id in deck_ids and other_id not in deck_ids
    # Card-info fields ride along for the phone's card page
    assert 'notes' in cards[0] and 'custom_fields' in cards[0]


def test_snapshot_unknown_table_404(client):
    res = client.get('/api/sync/snapshot/settings')
    assert res.status_code == 404


def test_manifest_shape(client, db):
    make_deck_with_card(db)
    m = client.get('/api/sync/manifest').get_json()
    assert m['protocol'] == 1
    for table in ('spreads', 'profiles', 'decks', 'cards', 'tags',
                  'reference_sources', 'source_fields', 'card_archetypes'):
        assert 'count' in m['tables'][table]
    assert 'max_updated_at' in m['tables']['entries']
    assert 'max_updated_at' in m['tables']['source_entries']


def _make_entry(db, deck_id, card_id, title='ZZ Sync Entry'):
    entry_id = db.add_entry(title=title)
    db.add_entry_reading(entry_id, deck_id=deck_id, cards_used=[
        {'card_id': card_id, 'position': 0},
    ])
    return entry_id


def test_entries_delta_and_id_list(client, db):
    deck_id, card_id = make_deck_with_card(db)
    e1 = _make_entry(db, deck_id, card_id, title='ZZ First')

    everything = client.get('/api/sync/entries').get_json()
    assert e1 in everything['ids']
    agg = next(e for e in everything['changed'] if e['id'] == e1)
    assert agg['title'] == 'ZZ First'
    assert isinstance(agg['readings'], list) and agg['readings']
    assert isinstance(agg['readings'][0]['cards_used'], list)
    assert 'tag_ids' in agg and 'querent_ids' in agg
    assert 'follow_up_notes' in agg
    assert 'breakdown_settings' not in agg

    # Delta: nothing changed since the max timestamp
    since = max(e['updated_at'] for e in everything['changed'])
    delta = client.get(f'/api/sync/entries?since={since}').get_json()
    assert delta['changed'] == []
    assert e1 in delta['ids']  # ID list always full, for pruning

    # A child write (tags) bumps the parent and reappears in the delta
    tag_id = db.add_tag('ZZ Phone')
    db.set_entry_tags(e1, [tag_id])
    delta = client.get(f'/api/sync/entries?since={since}').get_json()
    assert [e['id'] for e in delta['changed']] == [e1]
    assert delta['changed'][0]['tag_ids'] == [tag_id]


def test_source_entries_delta(client, db):
    res = client.get('/api/sync/source-entries')
    assert res.status_code == 200
    body = res.get_json()
    assert 'ids' in body and 'changed' in body


def test_card_image_requires_favorite(client, db):
    deck_id, card_id = make_deck_with_card(db)
    # Not favorited → 404 even though the card exists
    res = client.get(f'/api/sync/card-image/{card_id}')
    assert res.status_code == 404


# ── Touch audit: child writes must bump the parent updated_at ─

def test_child_writes_touch_entry(db):
    deck_id, card_id = make_deck_with_card(db)
    entry_id = _make_entry(db, deck_id, card_id)

    def stamp():
        cur = db.conn.cursor()
        return cur.execute(
            'SELECT updated_at FROM journal_entries WHERE id = ?',
            (entry_id,)).fetchone()[0]

    def reset():
        cur = db.conn.cursor()
        cur.execute("UPDATE journal_entries SET updated_at = '2000-01-01' "
                    'WHERE id = ?', (entry_id,))
        db.conn.commit()

    reset()
    tag_id = db.add_tag('ZZ Touch')
    db.set_entry_tags(entry_id, [tag_id])
    assert stamp() > '2000-01-01', 'set_entry_tags must touch the entry'

    reset()
    note_id = db.add_follow_up_note(entry_id, 'ZZ note')
    assert stamp() > '2000-01-01', 'add_follow_up_note must touch the entry'

    reset()
    db.update_follow_up_note(note_id, 'ZZ edited')
    assert stamp() > '2000-01-01', 'update_follow_up_note must touch'

    reset()
    db.delete_follow_up_note(note_id)
    assert stamp() > '2000-01-01', 'delete_follow_up_note must touch'

    reset()
    db.replace_entry_readings(entry_id, [{
        'deck_id': deck_id,
        'cards_used': [{'card_id': card_id, 'position': 0}],
    }])
    assert stamp() > '2000-01-01', 'replace_entry_readings must touch'


def test_sync_uuid_column_exists(db):
    cur = db.conn.cursor()
    cols = [r[1] for r in cur.execute(
        'PRAGMA table_info(journal_entries)').fetchall()]
    assert 'sync_uuid' in cols
    assert 'favorite' in [r[1] for r in cur.execute(
        'PRAGMA table_info(decks)').fetchall()]


# ── Phase 2: pushing phone-logged entries ────────────────────

def _push_payload(db, deck_id, card_id, uuid='zz-phone-uuid-1'):
    return {
        'sync_uuid': uuid,
        'title': 'ZZ Phone Entry',
        'content': '<p>logged at the table</p>',
        'reading_datetime': '2026-09-03T21:15:00',
        'querent_ids': [],
        'reading': {
            'deck_id': deck_id,
            'spread_name': 'Daily Draw',
            'cards_used': [{'card_id': card_id, 'name': 'The Fool',
                            'reversed': True, 'position_index': 0,
                            'deck_id': deck_id}],
            'notes': 'quick note',
        },
    }


def test_push_entry_creates_full_entry(client, db):
    deck_id, card_id = make_deck_with_card(db)
    token = _pair(client)
    res = client.post('/api/sync/push-entry',
                      json=_push_payload(db, deck_id, card_id),
                      headers=_auth(token), environ_overrides=LAN)
    assert res.status_code == 201
    entry_id = res.get_json()['id']

    entry = db.get_entry(entry_id)
    assert entry['title'] == 'ZZ Phone Entry'
    readings = db.get_entry_readings(entry_id)
    assert len(readings) == 1
    reading = dict(readings[0])
    assert reading['deck_name'] == 'Test Deck'
    assert reading['cartomancy_type'] == 'Tarot'
    cards = json.loads(reading['cards_used'])
    assert cards[0]['reversed'] is True

    tag_names = [t['name'] for t in db.get_entry_tags(entry_id)]
    assert 'logged on phone' in tag_names


def test_push_entry_is_idempotent(client, db):
    deck_id, card_id = make_deck_with_card(db)
    token = _pair(client)
    payload = _push_payload(db, deck_id, card_id, uuid='zz-same-uuid')
    first = client.post('/api/sync/push-entry', json=payload,
                        headers=_auth(token), environ_overrides=LAN)
    again = client.post('/api/sync/push-entry', json=payload,
                        headers=_auth(token), environ_overrides=LAN)
    assert again.status_code == 200
    assert again.get_json()['deduped'] is True
    assert again.get_json()['id'] == first.get_json()['id']
    cur = db.conn.cursor()
    count = cur.execute(
        "SELECT COUNT(*) FROM journal_entries WHERE sync_uuid = 'zz-same-uuid'"
    ).fetchone()[0]
    assert count == 1


def test_push_entry_requires_auth_and_uuid(client, db):
    deck_id, card_id = make_deck_with_card(db)
    res = client.post('/api/sync/push-entry',
                      json=_push_payload(db, deck_id, card_id),
                      environ_overrides=LAN)
    assert res.status_code == 401

    token = _pair(client)
    bad = _push_payload(db, deck_id, card_id)
    bad['sync_uuid'] = ''
    res = client.post('/api/sync/push-entry', json=bad,
                      headers=_auth(token), environ_overrides=LAN)
    assert res.status_code == 400


def test_push_entry_with_location(client, db):
    deck_id, card_id = make_deck_with_card(db)
    token = _pair(client)
    payload = _push_payload(db, deck_id, card_id, uuid='zz-loc-uuid')
    payload['location_name'] = 'ZZ Hotel'
    payload['location_lat'] = 40.7
    payload['location_lon'] = -74.0
    res = client.post('/api/sync/push-entry', json=payload,
                      headers=_auth(token), environ_overrides=LAN)
    assert res.status_code == 201
    entry = db.get_entry(res.get_json()['id'])
    assert entry['location_name'] == 'ZZ Hotel'
    assert entry['location_lat'] == 40.7
    assert entry['location_lon'] == -74.0


# ── Whole-reference sync (combinations, entities, entity notes) ──

def test_reference_entity_catalog(client, db):
    res = client.get('/api/sync/snapshot/reference_entities')
    assert res.status_code == 200
    rows = res.get_json()['rows']
    kinds = {r['kind'] for r in rows}
    assert {'sign', 'planet', 'sephira', 'path', 'chakra',
            'number'} <= kinds
    signs = [r for r in rows if r['kind'] == 'sign']
    assert len(signs) == 12
    paths = [r for r in rows if r['kind'] == 'path']
    assert len(paths) == 22
    # Suit/rank keys follow the desktop's Type::Name convention
    for r in rows:
        if r['kind'] in ('suit', 'rank'):
            assert '::' in r['key']
    # And the manifest counts it so the phone pulls it
    m = client.get('/api/sync/manifest').get_json()
    assert m['tables']['reference_entities']['count'] == len(rows)


def test_combinations_and_entity_notes_snapshots(client, db):
    for table in ('archetype_combinations', 'combination_meanings',
                  'entity_source_notes', 'correspondence_systems',
                  'correspondence_assignments',
                  'card_correspondence_overrides'):
        res = client.get(f'/api/sync/snapshot/{table}')
        assert res.status_code == 200, table
        assert 'rows' in res.get_json()


def test_push_entry_with_multiple_readings(client, db):
    deck_id, card_id = make_deck_with_card(db)
    deck2_id, card2_id = make_deck_with_card(db, deck_name='ZZ Second Deck',
                                             card_name='The Magician')
    token = _pair(client)
    payload = _push_payload(db, deck_id, card_id, uuid='zz-multi-uuid')
    del payload['reading']
    payload['readings'] = [
        {'deck_id': deck_id, 'spread_name': 'Daily Draw',
         'cards_used': [{'card_id': card_id, 'name': 'The Fool',
                         'reversed': False, 'position_index': 0}]},
        {'deck_id': deck2_id, 'spread_name': 'Clarifier',
         'cards_used': [{'card_id': card2_id, 'name': 'The Magician',
                         'reversed': True, 'position_index': 0}]},
    ]
    res = client.post('/api/sync/push-entry', json=payload,
                      headers=_auth(token), environ_overrides=LAN)
    assert res.status_code == 201
    readings = [dict(r) for r in db.get_entry_readings(res.get_json()['id'])]
    assert len(readings) == 2
    assert [r['spread_name'] for r in readings] == ['Daily Draw', 'Clarifier']
    assert [r['position_order'] for r in readings] == [0, 1]
    assert readings[1]['deck_name'] == 'ZZ Second Deck'


def test_push_entry_stamps_activity(client, db):
    assert client.get('/api/sync/push-activity').get_json() == {
        'last_push_at': None}
    deck_id, card_id = make_deck_with_card(db)
    token = _pair(client)
    client.post('/api/sync/push-entry',
                json=_push_payload(db, deck_id, card_id, uuid='zz-stamp'),
                headers=_auth(token), environ_overrides=LAN)
    stamp = client.get('/api/sync/push-activity').get_json()['last_push_at']
    assert stamp  # set by the push
    # The desktop-only endpoint is invisible from the LAN
    assert client.get('/api/sync/push-activity',
                      environ_overrides=LAN).status_code == 403


def test_push_entry_with_reader(client, db):
    deck_id, card_id = make_deck_with_card(db)
    reader_id = db.add_profile('ZZ Reader')
    token = _pair(client)
    payload = _push_payload(db, deck_id, card_id, uuid='zz-reader-uuid')
    payload['reader_id'] = reader_id
    res = client.post('/api/sync/push-entry', json=payload,
                      headers=_auth(token), environ_overrides=LAN)
    assert res.status_code == 201
    entry = db.get_entry(res.get_json()['id'])
    assert entry['reader_id'] == reader_id
    # And the profiles snapshot carries the querent_only flag
    rows = client.get('/api/sync/snapshot/profiles').get_json()['rows']
    assert 'querent_only' in rows[0]
