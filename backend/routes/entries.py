"""
Journal entry endpoints -- CRUD, search, readings, follow-ups, tags, import/export.
Also serves profiles and spreads needed by the journal editor.
"""

import json
from flask import Blueprint, jsonify, request, current_app
from backend.services.richtext import convert_content_to_html
from backend.utils import row_to_dict

entries_bp = Blueprint('entries', __name__)

# Pagination limits to prevent memory exhaustion
MAX_LIMIT = 500
DEFAULT_LIMIT = 50


def _parse_cards_used(cards_json):
    """Parse cards_used JSON, handling both string-array and object-array formats."""
    if not cards_json:
        return []
    try:
        cards = json.loads(cards_json) if isinstance(cards_json, str) else cards_json
    except (json.JSONDecodeError, TypeError):
        return []

    result = []
    for card in cards:
        if isinstance(card, str):
            result.append({'name': card, 'reversed': False})
        elif isinstance(card, dict):
            result.append(card)
    return result


def _enrich_cards_with_ids(db, cards):
    """
    Enrich card data for display. Uses card_id as primary lookup (survives renames),
    falls back to deck_id + name for legacy entries without card_id.
    """
    # Separate cards by lookup strategy
    cards_with_id = []
    cards_needing_name_lookup = []

    for card in cards:
        if card.get('card_id'):
            cards_with_id.append(card['card_id'])
        else:
            deck_id = card.get('deck_id')
            name = card.get('name')
            if deck_id and name:
                cards_needing_name_lookup.append((deck_id, name))

    # Batch lookup cards by ID (to verify they exist and get current name)
    id_to_card = {}
    if cards_with_id:
        placeholders = ','.join('?' * len(cards_with_id))
        rows = db.conn.execute(
            f'SELECT id, deck_id, name FROM cards WHERE id IN ({placeholders})',
            cards_with_id
        ).fetchall()
        id_to_card = {row['id']: row for row in rows}

    # Batch lookup cards by (deck_id, name) for legacy entries
    name_to_id = {}
    if cards_needing_name_lookup:
        conditions = ' OR '.join(['(deck_id = ? AND name = ?)'] * len(cards_needing_name_lookup))
        params = [val for pair in cards_needing_name_lookup for val in pair]
        rows = db.conn.execute(
            f'SELECT id, deck_id, name FROM cards WHERE {conditions}',
            params
        ).fetchall()
        name_to_id = {(row['deck_id'], row['name']): row['id'] for row in rows}

    # Apply lookups to cards
    for card in cards:
        card_id = card.get('card_id')
        if card_id:
            # Card has ID - verify it exists and update name to current value
            db_card = id_to_card.get(card_id)
            if db_card:
                # Card still exists - use current name from database
                card['current_name'] = db_card['name']
            # If card was deleted, keep original data but card_id won't resolve to thumbnail
        else:
            # Legacy entry without card_id - try name lookup
            deck_id = card.get('deck_id')
            name = card.get('name')
            if deck_id and name:
                found_id = name_to_id.get((deck_id, name))
                if found_id:
                    card['card_id'] = found_id

    return cards


# ── Entries CRUD ──────────────────────────────────────────────

@entries_bp.route('/api/entries')
def list_entries():
    db = current_app.config['DB']
    limit = request.args.get('limit', DEFAULT_LIMIT, type=int)
    offset = request.args.get('offset', 0, type=int)
    # Clamp values to prevent memory exhaustion
    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)
    rows = db.get_entries(limit=limit, offset=offset)
    return jsonify([row_to_dict(r) for r in rows])


@entries_bp.route('/api/entries/search')
def search_entries():
    db = current_app.config['DB']
    tag_ids_raw = request.args.get('tag_ids', '')
    tag_ids = None
    if tag_ids_raw:
        try:
            tag_ids = [int(x) for x in tag_ids_raw.split(',') if x.strip()]
        except ValueError:
            return jsonify({'error': 'Invalid tag_ids format - must be comma-separated integers'}), 400

    rows = db.search_entries(
        query=request.args.get('query') or None,
        tag_ids=tag_ids,
        deck_id=request.args.get('deck_id', type=int),
        spread_id=request.args.get('spread_id', type=int),
        cartomancy_type=request.args.get('cartomancy_type') or None,
        card_name=request.args.get('card_name') or None,
        date_from=request.args.get('date_from') or None,
        date_to=request.args.get('date_to') or None,
    )
    return jsonify([row_to_dict(r) for r in rows])


@entries_bp.route('/api/entries/<int:entry_id>')
def get_entry(entry_id):
    """Return a fully hydrated entry with readings, tags, follow-ups, and profile names."""
    db = current_app.config['DB']
    row = db.get_entry(entry_id)
    if not row:
        return jsonify({'error': 'Entry not found'}), 404

    entry = row_to_dict(row)

    # Convert content to HTML
    entry['content'] = convert_content_to_html(entry.get('content'))

    # Readings with parsed + enriched cards
    readings = db.get_entry_readings(entry_id)
    entry['readings'] = []
    for r in readings:
        rd = row_to_dict(r)
        rd['cards_used'] = _enrich_cards_with_ids(db, _parse_cards_used(rd.get('cards_used')))
        entry['readings'].append(rd)

    # Tags
    tags = db.get_entry_tags(entry_id)
    entry['tags'] = [row_to_dict(t) for t in tags]

    # Follow-up notes (with HTML conversion)
    notes = db.get_follow_up_notes(entry_id)
    entry['follow_up_notes'] = []
    for n in notes:
        nd = row_to_dict(n)
        nd['content'] = convert_content_to_html(nd.get('content'))
        entry['follow_up_notes'].append(nd)

    # Querents (multiple) - from junction table
    querents = db.get_entry_querents(entry_id)
    entry['querents'] = [row_to_dict(q) for q in querents]

    # Legacy single querent name (for backwards compatibility)
    if entry.get('querent_id'):
        q = db.get_profile(entry['querent_id'])
        entry['querent_name'] = q['name'] if q else None
    else:
        entry['querent_name'] = None

    if entry.get('reader_id'):
        r = db.get_profile(entry['reader_id'])
        entry['reader_name'] = r['name'] if r else None
    else:
        entry['reader_name'] = None

    return jsonify(entry)


@entries_bp.route('/api/entries', methods=['POST'])
def create_entry():
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    entry_id = db.add_entry(
        title=data.get('title'),
        content=data.get('content'),
        reading_datetime=data.get('reading_datetime'),
        location_name=data.get('location_name'),
        location_lat=data.get('location_lat'),
        location_lon=data.get('location_lon'),
        querent_id=data.get('querent_id'),
        reader_id=data.get('reader_id'),
    )
    return jsonify({'id': entry_id}), 201


@entries_bp.route('/api/entries/<int:entry_id>', methods=['PUT'])
def update_entry(entry_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    db.update_entry(
        entry_id,
        title=data.get('title'),
        content=data.get('content'),
        reading_datetime=data.get('reading_datetime'),
        location_name=data.get('location_name'),
        location_lat=data.get('location_lat'),
        location_lon=data.get('location_lon'),
        querent_id=data.get('querent_id'),
        reader_id=data.get('reader_id'),
    )
    return jsonify({'ok': True})


@entries_bp.route('/api/entries/<int:entry_id>', methods=['DELETE'])
def delete_entry(entry_id):
    db = current_app.config['DB']
    db.delete_entry(entry_id)
    return jsonify({'ok': True})


# ── Readings ──────────────────────────────────────────────────

@entries_bp.route('/api/entries/<int:entry_id>/readings')
def get_entry_readings(entry_id):
    db = current_app.config['DB']
    rows = db.get_entry_readings(entry_id)
    result = []
    for r in rows:
        rd = row_to_dict(r)
        rd['cards_used'] = _enrich_cards_with_ids(db, _parse_cards_used(rd.get('cards_used')))
        result.append(rd)
    return jsonify(result)


@entries_bp.route('/api/entries/<int:entry_id>/readings', methods=['POST'])
def add_entry_reading(entry_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    reading_id = db.add_entry_reading(
        entry_id,
        spread_id=data.get('spread_id'),
        spread_name=data.get('spread_name'),
        deck_id=data.get('deck_id'),
        deck_name=data.get('deck_name'),
        cartomancy_type=data.get('cartomancy_type'),
        cards_used=data.get('cards_used'),
        position_order=data.get('position_order', 0),
    )
    return jsonify({'id': reading_id}), 201


@entries_bp.route('/api/entries/<int:entry_id>/readings', methods=['DELETE'])
def delete_entry_readings(entry_id):
    db = current_app.config['DB']
    db.delete_entry_readings(entry_id)
    return jsonify({'ok': True})


# ── Follow-up Notes ───────────────────────────────────────────

@entries_bp.route('/api/entries/<int:entry_id>/follow-up-notes')
def get_follow_up_notes(entry_id):
    db = current_app.config['DB']
    rows = db.get_follow_up_notes(entry_id)
    result = []
    for n in rows:
        nd = row_to_dict(n)
        nd['content'] = convert_content_to_html(nd.get('content'))
        result.append(nd)
    return jsonify(result)


@entries_bp.route('/api/entries/<int:entry_id>/follow-up-notes', methods=['POST'])
def add_follow_up_note(entry_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    content = data.get('content', '')
    note_id = db.add_follow_up_note(entry_id, content)
    return jsonify({'id': note_id}), 201


@entries_bp.route('/api/follow-up-notes/<int:note_id>', methods=['PUT'])
def update_follow_up_note(note_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    db.update_follow_up_note(note_id, data.get('content', ''))
    return jsonify({'ok': True})


@entries_bp.route('/api/follow-up-notes/<int:note_id>', methods=['DELETE'])
def delete_follow_up_note(note_id):
    db = current_app.config['DB']
    db.delete_follow_up_note(note_id)
    return jsonify({'ok': True})


# ── Entry Tags ────────────────────────────────────────────────

@entries_bp.route('/api/entries/<int:entry_id>/tags')
def get_entry_tags(entry_id):
    db = current_app.config['DB']
    rows = db.get_entry_tags(entry_id)
    return jsonify([row_to_dict(r) for r in rows])


@entries_bp.route('/api/entries/<int:entry_id>/tags', methods=['PUT'])
def set_entry_tags(entry_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    tag_ids = data.get('tag_ids', [])
    db.set_entry_tags(entry_id, tag_ids)
    return jsonify({'ok': True})


# ── Entry Querents ─────────────────────────────────────────────

@entries_bp.route('/api/entries/<int:entry_id>/querents')
def get_entry_querents(entry_id):
    db = current_app.config['DB']
    rows = db.get_entry_querents(entry_id)
    return jsonify([row_to_dict(r) for r in rows])


@entries_bp.route('/api/entries/<int:entry_id>/querents', methods=['PUT'])
def set_entry_querents(entry_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    profile_ids = data.get('profile_ids', [])
    db.set_entry_querents(entry_id, profile_ids)
    return jsonify({'ok': True})


# ── Profiles ──────────────────────────────────────────────────

@entries_bp.route('/api/profiles')
def get_profiles():
    db = current_app.config['DB']
    rows = db.get_profiles()
    return jsonify([row_to_dict(r) for r in rows])


@entries_bp.route('/api/profiles/<int:profile_id>')
def get_profile(profile_id):
    db = current_app.config['DB']
    row = db.get_profile(profile_id)
    if not row:
        return jsonify({'error': 'Profile not found'}), 404
    return jsonify(row_to_dict(row))


@entries_bp.route('/api/profiles', methods=['POST'])
def add_profile():
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    profile_id = db.add_profile(
        name=name,
        gender=data.get('gender'),
        birth_date=data.get('birth_date'),
        birth_time=data.get('birth_time'),
        birth_place_name=data.get('birth_place_name'),
        birth_place_lat=data.get('birth_place_lat'),
        birth_place_lon=data.get('birth_place_lon'),
        querent_only=data.get('querent_only', False),
        hidden=data.get('hidden', False),
    )
    return jsonify({'id': profile_id}), 201


@entries_bp.route('/api/profiles/<int:profile_id>', methods=['PUT'])
def update_profile(profile_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    db.update_profile(
        profile_id,
        name=data.get('name'),
        gender=data.get('gender'),
        birth_date=data.get('birth_date'),
        birth_time=data.get('birth_time'),
        birth_place_name=data.get('birth_place_name'),
        birth_place_lat=data.get('birth_place_lat'),
        birth_place_lon=data.get('birth_place_lon'),
        querent_only=data.get('querent_only'),
        hidden=data.get('hidden'),
    )
    return jsonify({'ok': True})


@entries_bp.route('/api/profiles/<int:profile_id>', methods=['DELETE'])
def delete_profile(profile_id):
    db = current_app.config['DB']
    db.delete_profile(profile_id)
    return jsonify({'ok': True})


# ── Export / Import ───────────────────────────────────────────

@entries_bp.route('/api/entries/export')
def export_entries():
    """Export entries as JSON. Optional ?ids=1,2,3 to export specific entries."""
    db = current_app.config['DB']
    ids_raw = request.args.get('ids', '')
    entry_ids = None
    if ids_raw:
        try:
            entry_ids = [int(x) for x in ids_raw.split(',') if x.strip()]
        except ValueError:
            return jsonify({'error': 'Invalid ids format - must be comma-separated integers'}), 400
    data = db.export_entries_json(entry_ids)
    return jsonify(data)


@entries_bp.route('/api/entries/import', methods=['POST'])
def import_entries():
    """Import entries from JSON data."""
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    merge_tags = data.get('merge_tags', True)
    entries_data = data.get('data', data)
    result = db.import_entries_from_json(entries_data, merge_tags=merge_tags)
    return jsonify(result)
