"""
Journal entry endpoints -- CRUD, search, readings, follow-ups, tags, import/export.
Also serves profiles and spreads needed by the journal editor.
"""

import json
from flask import Blueprint, jsonify, request, current_app
from backend.services.richtext import convert_content_to_html

entries_bp = Blueprint('entries', __name__)


def _row_to_dict(row):
    return dict(row) if row else None


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
    """Look up card IDs by deck_id + name so the frontend can fetch thumbnails."""
    for card in cards:
        if card.get('card_id'):
            continue
        deck_id = card.get('deck_id')
        name = card.get('name')
        if deck_id and name:
            row = db.conn.execute(
                'SELECT id FROM cards WHERE deck_id = ? AND name = ?',
                (deck_id, name)
            ).fetchone()
            if row:
                card['card_id'] = row['id']
    return cards


# ── Entries CRUD ──────────────────────────────────────────────

@entries_bp.route('/api/entries')
def list_entries():
    db = current_app.config['DB']
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    rows = db.get_entries(limit=limit, offset=offset)
    return jsonify([_row_to_dict(r) for r in rows])


@entries_bp.route('/api/entries/search')
def search_entries():
    db = current_app.config['DB']
    tag_ids_raw = request.args.get('tag_ids', '')
    tag_ids = [int(x) for x in tag_ids_raw.split(',') if x.strip()] if tag_ids_raw else None

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
    return jsonify([_row_to_dict(r) for r in rows])


@entries_bp.route('/api/entries/<int:entry_id>')
def get_entry(entry_id):
    """Return a fully hydrated entry with readings, tags, follow-ups, and profile names."""
    db = current_app.config['DB']
    row = db.get_entry(entry_id)
    if not row:
        return jsonify({'error': 'Entry not found'}), 404

    entry = _row_to_dict(row)

    # Convert content to HTML
    entry['content'] = convert_content_to_html(entry.get('content'))

    # Readings with parsed + enriched cards
    readings = db.get_entry_readings(entry_id)
    entry['readings'] = []
    for r in readings:
        rd = _row_to_dict(r)
        rd['cards_used'] = _enrich_cards_with_ids(db, _parse_cards_used(rd.get('cards_used')))
        entry['readings'].append(rd)

    # Tags
    tags = db.get_entry_tags(entry_id)
    entry['tags'] = [_row_to_dict(t) for t in tags]

    # Follow-up notes (with HTML conversion)
    notes = db.get_follow_up_notes(entry_id)
    entry['follow_up_notes'] = []
    for n in notes:
        nd = _row_to_dict(n)
        nd['content'] = convert_content_to_html(nd.get('content'))
        entry['follow_up_notes'].append(nd)

    # Profile names
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
        rd = _row_to_dict(r)
        rd['cards_used'] = _enrich_cards_with_ids(db, _parse_cards_used(rd.get('cards_used')))
        result.append(rd)
    return jsonify(result)


@entries_bp.route('/api/entries/<int:entry_id>/readings', methods=['POST'])
def add_entry_reading(entry_id):
    db = current_app.config['DB']
    data = request.get_json()
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
        nd = _row_to_dict(n)
        nd['content'] = convert_content_to_html(nd.get('content'))
        result.append(nd)
    return jsonify(result)


@entries_bp.route('/api/entries/<int:entry_id>/follow-up-notes', methods=['POST'])
def add_follow_up_note(entry_id):
    db = current_app.config['DB']
    data = request.get_json()
    content = data.get('content', '')
    note_id = db.add_follow_up_note(entry_id, content)
    return jsonify({'id': note_id}), 201


@entries_bp.route('/api/follow-up-notes/<int:note_id>', methods=['PUT'])
def update_follow_up_note(note_id):
    db = current_app.config['DB']
    data = request.get_json()
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
    return jsonify([_row_to_dict(r) for r in rows])


@entries_bp.route('/api/entries/<int:entry_id>/tags', methods=['PUT'])
def set_entry_tags(entry_id):
    db = current_app.config['DB']
    data = request.get_json()
    tag_ids = data.get('tag_ids', [])
    db.set_entry_tags(entry_id, tag_ids)
    return jsonify({'ok': True})


# ── Profiles ──────────────────────────────────────────────────

@entries_bp.route('/api/profiles')
def get_profiles():
    db = current_app.config['DB']
    rows = db.get_profiles()
    return jsonify([_row_to_dict(r) for r in rows])


@entries_bp.route('/api/profiles/<int:profile_id>')
def get_profile(profile_id):
    db = current_app.config['DB']
    row = db.get_profile(profile_id)
    if not row:
        return jsonify({'error': 'Profile not found'}), 404
    return jsonify(_row_to_dict(row))


@entries_bp.route('/api/profiles', methods=['POST'])
def add_profile():
    db = current_app.config['DB']
    data = request.get_json()
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
    )
    return jsonify({'id': profile_id}), 201


@entries_bp.route('/api/profiles/<int:profile_id>', methods=['PUT'])
def update_profile(profile_id):
    db = current_app.config['DB']
    data = request.get_json()
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
    entry_ids = [int(x) for x in ids_raw.split(',') if x.strip()] if ids_raw else None
    data = db.export_entries_json(entry_ids)
    return jsonify(data)


@entries_bp.route('/api/entries/import', methods=['POST'])
def import_entries():
    """Import entries from JSON data."""
    db = current_app.config['DB']
    data = request.get_json()
    merge_tags = data.get('merge_tags', True)
    entries_data = data.get('data', data)
    result = db.import_entries_from_json(entries_data, merge_tags=merge_tags)
    return jsonify(result)
