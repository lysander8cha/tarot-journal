"""
Phone-companion sync endpoints (Phase 0 of the iOS companion plan).

Protocol overview:
  - /api/sync/manifest        — per-table counts + max timestamps, so
    the phone can skip unchanged tables entirely.
  - /api/sync/snapshot/<t>    — full snapshot of a small table
    (deletions come free: the phone mirrors the snapshot).
  - /api/sync/entries         — journal entries as whole aggregates
    (entry + readings + tags + querents + follow-ups), delta by the
    parent's updated_at, plus a full ID list for pruning deletions.
  - /api/sync/source-entries  — archetype source texts, same delta
    pattern.
  - /api/sync/card-image/<id> — phone-sized derivative (favorited
    decks only), generated lazily and cached.

Security model: the app normally listens on loopback only. When the
"phone sync" setting is on, run.py binds the LAN as well — and an
app-wide guard (backend/app.py) rejects every NON-loopback request
outside /api/sync/. Within /api/sync/, non-loopback callers must
present the bearer token obtained by pairing: the desktop shows a
short-lived 6-digit code (loopback-only endpoint), the phone exchanges
it once for a long-lived token whose hash is stored in settings.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time

from flask import Blueprint, abort, current_app, jsonify, request, send_file

from backend.security import is_safe_path, is_valid_image_path
from backend.utils import require_json, row_to_dict

sync_bp = Blueprint('sync', __name__)

SYNC_ENABLED_KEY = 'phone_sync_enabled'
SYNC_TOKEN_HASH_KEY = 'phone_sync_token_hash'
SYNC_DEVICE_KEY = 'phone_sync_device_name'
PAIRING_TTL_SECONDS = 300

LOOPBACK_ADDRS = ('127.0.0.1', '::1')


def is_loopback() -> bool:
    return (request.remote_addr or '') in LOOPBACK_ADDRS


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def sync_request_authorized(db) -> bool:
    """Loopback callers are implicitly trusted (same machine); LAN
    callers must present the paired bearer token."""
    if is_loopback():
        return True
    stored = db.get_setting(SYNC_TOKEN_HASH_KEY)
    if not stored:
        return False
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return False
    supplied = auth[len('Bearer '):].strip()
    return bool(supplied) and secrets.compare_digest(
        _token_hash(supplied), stored)


def _require_auth():
    if not sync_request_authorized(current_app.config['DB']):
        abort(401)


def install_lan_guard(app):
    """App-wide guard: when run.py binds the LAN (phone sync enabled),
    every non-loopback request outside /api/sync/ is refused, so the
    desktop API surface never opens to the network."""
    @app.before_request
    def _lan_guard():
        if not is_loopback() and not (request.path or '').startswith('/api/sync/'):
            return jsonify({'error': 'LAN access is limited to phone sync'}), 403


# ── Pairing & status ─────────────────────────────────────────

@sync_bp.route('/api/sync/status')
def sync_status():
    """Loopback-only status for the Settings UI."""
    if not is_loopback():
        abort(403)
    db = current_app.config['DB']
    pairing = current_app.config.get('PHONE_PAIRING')
    return jsonify({
        'enabled': db.get_setting(SYNC_ENABLED_KEY) == 'true',
        'paired': bool(db.get_setting(SYNC_TOKEN_HASH_KEY)),
        'device_name': db.get_setting(SYNC_DEVICE_KEY),
        'pairing_code_active': bool(
            pairing and pairing['expires'] > time.time()),
    })


@sync_bp.route('/api/sync/enabled', methods=['PUT'])
@require_json
def set_sync_enabled(data):
    """Toggle the LAN listener setting (takes effect on next app
    start — binding happens at startup)."""
    if not is_loopback():
        abort(403)
    db = current_app.config['DB']
    db.set_setting(SYNC_ENABLED_KEY, 'true' if data.get('enabled') else 'false')
    return jsonify({'enabled': data.get('enabled', False),
                    'restart_required': True})


@sync_bp.route('/api/sync/pairing/start', methods=['POST'])
def start_pairing():
    """Generate a short-lived 6-digit pairing code (shown in Settings)."""
    if not is_loopback():
        abort(403)
    code = f'{secrets.randbelow(1_000_000):06d}'
    current_app.config['PHONE_PAIRING'] = {
        'code': code,
        'expires': time.time() + PAIRING_TTL_SECONDS,
    }
    return jsonify({'code': code, 'expires_in': PAIRING_TTL_SECONDS})


@sync_bp.route('/api/sync/pair', methods=['POST'])
@require_json
def pair(data):
    """Exchange the on-screen code for a long-lived bearer token —
    the one sync endpoint a not-yet-paired LAN caller may hit."""
    pairing = current_app.config.get('PHONE_PAIRING')
    code = str(data.get('code') or '')
    if (not pairing or pairing['expires'] < time.time()
            or not secrets.compare_digest(code, pairing['code'])):
        abort(401)
    current_app.config['PHONE_PAIRING'] = None   # single use
    token = secrets.token_urlsafe(32)
    db = current_app.config['DB']
    db.set_setting(SYNC_TOKEN_HASH_KEY, _token_hash(token))
    db.set_setting(SYNC_DEVICE_KEY, str(data.get('device_name') or 'phone'))
    return jsonify({'token': token})


@sync_bp.route('/api/sync/unpair', methods=['POST'])
def unpair():
    if not is_loopback():
        abort(403)
    db = current_app.config['DB']
    db.set_setting(SYNC_TOKEN_HASH_KEY, '')
    db.set_setting(SYNC_DEVICE_KEY, '')
    return jsonify({'ok': True})


# ── Data endpoints ───────────────────────────────────────────

# Small tables that sync as full snapshots. Each entry: SQL producing
# exactly the columns the phone needs.
SNAPSHOT_TABLES = {
    'spreads': ('SELECT id, name, description, positions, deck_slots, '
                'allowed_deck_types, archived FROM spreads'),
    'profiles': 'SELECT id, name, hidden FROM profiles',
    'decks': ('SELECT id, name, favorite, correspondence_system_id '
              'FROM decks WHERE favorite = 1'),
    'cards': ('SELECT c.id, c.deck_id, c.name, c.archetype, c.rank, '
              'c.suit, c.card_order, c.notes, c.custom_fields '
              'FROM cards c '
              'JOIN decks d ON d.id = c.deck_id WHERE d.favorite = 1'),
    'tags': 'SELECT id, name, color FROM tags',
    'reference_sources': ('SELECT id, name, cartomancy_type '
                          'FROM reference_sources'),
    'source_fields': ('SELECT id, source_id, cartomancy_type, name, '
                      'sort_order, collapsible FROM source_fields'),
    'card_archetypes': ('SELECT id, name, cartomancy_type, rank, suit '
                        'FROM card_archetypes'),
    'archetype_combinations': 'SELECT * FROM archetype_combinations',
    'combination_meanings': ('SELECT id, combination_id, meaning, '
                             'source_id, sort_order FROM combination_meanings'),
    'entity_source_notes': ('SELECT id, entity_kind, entity_key, '
                            'source_id, content FROM entity_source_notes'),
    'correspondence_systems': ('SELECT id, name, cartomancy_type '
                               'FROM correspondence_systems'),
    'correspondence_assignments': ('SELECT id, system_id, archetype_id, '
                                   'field_name, field_value '
                                   'FROM correspondence_assignments'),
    'card_correspondence_overrides': (
        'SELECT o.id, o.card_id, o.field_name, o.field_value '
        'FROM card_correspondence_overrides o '
        'JOIN cards c ON c.id = o.card_id '
        'JOIN decks d ON d.id = c.deck_id WHERE d.favorite = 1'),
}


def _reference_entity_catalog(db):
    """The Reference section's entity lists (signs, planets, sephiroth,
    paths, chakras, numbers, per-type suits and ranks), flattened for
    the phone. Keys match what the desktop stores entity notes under.
    Served as a pseudo snapshot table ('reference_entities')."""
    import reference_content as rc
    from backend.routes.reference_content import (
        _suit_types, _suited_archetypes, _suit_sort_key, _rank_sort_key)

    rows = []

    def add(kind, key, name, subtitle=None, ctype=None):
        rows.append({'id': len(rows) + 1, 'kind': kind, 'key': str(key),
                     'name': str(name), 'subtitle': subtitle,
                     'cartomancy_type': ctype, 'sort': len(rows)})

    for s in rc.SIGNS:
        add('sign', s['name'], f"{s.get('glyph', '')} {s['name']}".strip(),
            ' · '.join(x for x in (s.get('element'), s.get('modality')) if x))
    for p in rc.PLANETS:
        add('planet', p['name'], f"{p.get('glyph', '')} {p['name']}".strip(),
            p.get('rules'))
    for s in rc.SEPHIROTH:
        add('sephira', s['name'], f"{s['number']}. {s['name']}",
            s.get('translation'))
    for p in rc.TREE_PATHS:
        add('path', p['letter'],
            f"Path {p['path']} — {p['letter']} {p.get('glyph', '')}".strip(),
            f"{p['from']} → {p['to']}")
    for c in rc.CHAKRAS:
        add('chakra', c['name'], c['name'],
            ' · '.join(x for x in (c.get('sanskrit'), c.get('location')) if x))
    for n in rc.NUMBERS:
        add('number', n['number'], f"Number {n['number']}", n.get('system'))
    for ctype in _suit_types(db):
        cards = _suited_archetypes(db, ctype)
        suit_names = sorted({c['suit'] for c in cards if c['suit']},
                            key=_suit_sort_key)
        rank_names = sorted({c['rank'] for c in cards if c['rank']},
                            key=_rank_sort_key)
        for name in suit_names:
            add('suit', f'{ctype}::{name}', name, ctype, ctype)
        for name in rank_names:
            add('rank', f'{ctype}::{name}', name, ctype, ctype)
    return rows


@sync_bp.route('/api/sync/manifest')
def manifest():
    _require_auth()
    db = current_app.config['DB']
    cursor = db.conn.cursor()

    def one(sql):
        row = cursor.execute(sql).fetchone()
        return row[0] if row else None

    tables = {}
    for name, sql in SNAPSHOT_TABLES.items():
        tables[name] = {'count': one(f'SELECT COUNT(*) FROM ({sql})')}
    tables['reference_entities'] = {
        'count': len(_reference_entity_catalog(db))}
    tables['entries'] = {
        'count': one('SELECT COUNT(*) FROM journal_entries'),
        'max_updated_at': one('SELECT MAX(updated_at) FROM journal_entries'),
    }
    tables['source_entries'] = {
        'count': one('SELECT COUNT(*) FROM archetype_source_entries'),
        'max_updated_at': one(
            'SELECT MAX(updated_at) FROM archetype_source_entries'),
    }
    return jsonify({'app': 'tarot-journal', 'protocol': 1, 'tables': tables})


@sync_bp.route('/api/sync/snapshot/<table>')
def snapshot(table):
    _require_auth()
    if table == 'reference_entities':
        rows = _reference_entity_catalog(current_app.config['DB'])
        return jsonify({'table': table, 'rows': rows})
    sql = SNAPSHOT_TABLES.get(table)
    if not sql:
        return jsonify({'error': f'unknown snapshot table {table!r}'}), 404
    cursor = current_app.config['DB'].conn.cursor()
    rows = [row_to_dict(r) for r in cursor.execute(sql).fetchall()]
    return jsonify({'table': table, 'rows': rows})


def _entry_aggregate(db, entry_row) -> dict:
    e = row_to_dict(entry_row)
    entry_id = e['id']
    cursor = db.conn.cursor()
    readings = [row_to_dict(r) for r in db.get_entry_readings(entry_id)]
    for r in readings:
        if r.get('cards_used') and isinstance(r['cards_used'], str):
            try:
                r['cards_used'] = json.loads(r['cards_used'])
            except ValueError:
                r['cards_used'] = []
    tag_ids = [row[0] if not isinstance(row, dict) else row['tag_id']
               for row in cursor.execute(
                   'SELECT tag_id FROM entry_tags WHERE entry_id = ?',
                   (entry_id,)).fetchall()]
    querent_ids = [row[0] if not isinstance(row, dict) else row['profile_id']
                   for row in cursor.execute(
                       'SELECT profile_id FROM entry_querents '
                       'WHERE entry_id = ? ORDER BY position',
                       (entry_id,)).fetchall()]
    follow_ups = [row_to_dict(r) for r in db.get_follow_up_notes(entry_id)]
    # UI-only state stays on the desktop.
    e.pop('breakdown_settings', None)
    return {**e, 'readings': readings, 'tag_ids': tag_ids,
            'querent_ids': querent_ids, 'follow_up_notes': follow_ups}


@sync_bp.route('/api/sync/entries')
def sync_entries():
    """Changed entry aggregates since ?since= (ISO timestamp; empty =
    everything), plus the full ID list so the phone prunes deletions."""
    _require_auth()
    db = current_app.config['DB']
    since = request.args.get('since', '')
    cursor = db.conn.cursor()
    ids = [r[0] for r in cursor.execute(
        'SELECT id FROM journal_entries').fetchall()]
    if since:
        rows = cursor.execute(
            'SELECT * FROM journal_entries WHERE updated_at > ? '
            'ORDER BY updated_at', (since,)).fetchall()
    else:
        rows = cursor.execute(
            'SELECT * FROM journal_entries ORDER BY updated_at').fetchall()
    return jsonify({
        'ids': ids,
        'changed': [_entry_aggregate(db, r) for r in rows],
    })


@sync_bp.route('/api/sync/source-entries')
def sync_source_entries():
    _require_auth()
    db = current_app.config['DB']
    since = request.args.get('since', '')
    cursor = db.conn.cursor()
    ids = [r[0] for r in cursor.execute(
        'SELECT id FROM archetype_source_entries').fetchall()]
    if since:
        rows = cursor.execute(
            'SELECT id, archetype_id, field_id, content, updated_at '
            'FROM archetype_source_entries WHERE updated_at > ? '
            'ORDER BY updated_at', (since,)).fetchall()
    else:
        rows = cursor.execute(
            'SELECT id, archetype_id, field_id, content, updated_at '
            'FROM archetype_source_entries ORDER BY updated_at').fetchall()
    return jsonify({'ids': ids, 'changed': [row_to_dict(r) for r in rows]})


PHONE_TAG_NAME = 'logged on phone'
PUSH_STAMP_KEY = 'last_phone_push_at'


@sync_bp.route('/api/sync/push-activity')
def push_activity():
    """Loopback-only: when the last phone entry arrived. The desktop
    frontend polls this cheaply and refreshes its journal cache when
    it changes, so phone entries appear without a restart."""
    if not is_loopback():
        abort(403)
    db = current_app.config['DB']
    return jsonify({'last_push_at': db.get_setting(PUSH_STAMP_KEY)})


@sync_bp.route('/api/sync/push-entry', methods=['POST'])
@require_json
def push_entry(data):
    """Create a journal entry logged on the phone.

    Idempotent on sync_uuid: the phone may retry a push after a
    dropped connection without creating duplicates. The entry gets
    the 'logged on phone' tag so it's easy to find and polish on the
    desktop.
    """
    _require_auth()
    db = current_app.config['DB']

    sync_uuid = str(data.get('sync_uuid') or '').strip()
    if not sync_uuid:
        return jsonify({'error': 'sync_uuid is required'}), 400

    cursor = db.conn.cursor()
    existing = cursor.execute(
        'SELECT id FROM journal_entries WHERE sync_uuid = ?',
        (sync_uuid,)).fetchone()
    if existing:
        return jsonify({'id': existing[0], 'deduped': True})

    location_name = (str(data.get('location_name') or '')).strip() or None
    location_lat = data.get('location_lat')
    location_lon = data.get('location_lon')
    if location_name and location_lat is None:
        # The phone sends only a typed place name; resolve coordinates
        # here so event charts can be cast later. Best-effort — a name
        # the gazetteer doesn't know still saves fine without them.
        try:
            from geocoder import lookup
            matches = lookup(location_name, limit=1)
            if matches:
                location_lat = matches[0]['latitude']
                location_lon = matches[0]['longitude']
        except Exception:
            pass

    entry_id = db.add_entry(
        title=data.get('title'),
        content=data.get('content'),
        reading_datetime=data.get('reading_datetime'),
        location_name=location_name,
        location_lat=location_lat,
        location_lon=location_lon,
    )
    cursor = db.conn.cursor()
    cursor.execute(
        'UPDATE journal_entries SET sync_uuid = ? WHERE id = ?',
        (sync_uuid, entry_id))
    db.conn.commit()

    # Entries may carry several readings (like the desktop editor);
    # older phone builds send a single 'reading' — accept both.
    readings = data.get('readings')
    if not readings and data.get('reading'):
        readings = [data['reading']]
    for order, reading in enumerate(readings or []):
        deck_id = reading.get('deck_id')
        deck = db.get_deck(deck_id) if deck_id else None
        db.add_entry_reading(
            entry_id,
            spread_id=reading.get('spread_id'),
            spread_name=reading.get('spread_name'),
            deck_id=deck_id,
            deck_name=(deck or {}).get('name') or reading.get('deck_name'),
            cartomancy_type=(deck or {}).get('cartomancy_type_name'),
            cards_used=reading.get('cards_used') or [],
            position_order=order,
            notes=reading.get('notes'),
        )

    querent_ids = [int(q) for q in (data.get('querent_ids') or [])]
    if querent_ids:
        db.set_entry_querents(entry_id, querent_ids)

    phone_tag = next(
        (t for t in db.get_tags()
         if t['name'].lower() == PHONE_TAG_NAME), None)
    tag_id = phone_tag['id'] if phone_tag else db.add_tag(PHONE_TAG_NAME)
    db.add_entry_tag(entry_id, tag_id)

    # Signal the desktop UI (see /api/sync/push-activity).
    from datetime import datetime
    db.set_setting(PUSH_STAMP_KEY, datetime.now().isoformat())

    return jsonify({'id': entry_id}), 201


@sync_bp.route('/api/sync/card-image/<int:card_id>')
def card_image(card_id):
    """Phone-sized derivative for a favorited deck's card. Generated
    lazily; the mtime-keyed cache persists it."""
    _require_auth()
    db = current_app.config['DB']
    cursor = db.conn.cursor()
    row = cursor.execute(
        'SELECT c.image_path FROM cards c JOIN decks d ON d.id = c.deck_id '
        'WHERE c.id = ? AND d.favorite = 1', (card_id,)).fetchone()
    image_path = (row[0] if row and not isinstance(row, dict)
                  else (row or {}).get('image_path'))
    if not image_path:
        abort(404)
    if not is_valid_image_path(image_path):
        abort(404)
    cache = current_app.config['THUMB_CACHE']
    path = cache.get_thumbnail_path(image_path, size=cache.PHONE_SIZE)
    if not path or not is_safe_path(path, [str(cache.cache_dir)]):
        abort(404)
    resp = send_file(path, mimetype='image/png')
    resp.cache_control.max_age = 86400
    return resp
