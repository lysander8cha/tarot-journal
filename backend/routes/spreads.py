"""
Spread endpoints -- CRUD, clone for card spreads.
"""

import json
from flask import Blueprint, jsonify, request, current_app
from backend.utils import row_to_dict, require_json, validate_length

spreads_bp = Blueprint('spreads', __name__)


def _parse_spread(d):
    """Parse JSON fields in a spread dict."""
    if d.get('positions') and isinstance(d['positions'], str):
        try:
            d['positions'] = json.loads(d['positions'])
        except json.JSONDecodeError:
            d['positions'] = []
    if d.get('allowed_deck_types') and isinstance(d['allowed_deck_types'], str):
        try:
            d['allowed_deck_types'] = json.loads(d['allowed_deck_types'])
        except json.JSONDecodeError:
            d['allowed_deck_types'] = None
    if d.get('deck_slots') and isinstance(d['deck_slots'], str):
        try:
            d['deck_slots'] = json.loads(d['deck_slots'])
        except json.JSONDecodeError:
            d['deck_slots'] = None
    return d


@spreads_bp.route('/api/spreads')
def get_spreads():
    db = current_app.config['DB']
    rows = db.get_spreads()
    tags_by_spread = db.get_tags_for_spreads()
    out = []
    for r in rows:
        spread = _parse_spread(row_to_dict(r))
        spread['tags'] = tags_by_spread.get(spread['id'], [])
        out.append(spread)
    return jsonify(out)


@spreads_bp.route('/api/spreads/<int:spread_id>/tags', methods=['PUT'])
@require_json
def set_spread_tag_assignments(spread_id, data):
    db = current_app.config['DB']
    db.set_spread_tags(spread_id, data.get('tag_ids', []))
    return jsonify({'ok': True})


@spreads_bp.route('/api/spreads/<int:spread_id>')
def get_spread(spread_id):
    db = current_app.config['DB']
    row = db.get_spread(spread_id)
    if not row:
        return jsonify({'error': 'Spread not found'}), 404
    return jsonify(_parse_spread(row_to_dict(row)))


@spreads_bp.route('/api/spreads', methods=['POST'])
@require_json
def add_spread(data):
    db = current_app.config['DB']
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    err = validate_length(name, field_name='name')
    if err:
        return jsonify({'error': err}), 400

    spread_id = db.add_spread(
        name=name,
        positions=data.get('positions', []),
        description=data.get('description'),
        cartomancy_type=data.get('cartomancy_type'),
        allowed_deck_types=data.get('allowed_deck_types'),
        default_deck_id=data.get('default_deck_id'),
        deck_slots=data.get('deck_slots'),
        source_id=data.get('source_id'),
    )
    return jsonify({'id': spread_id}), 201


@spreads_bp.route('/api/spreads/<int:spread_id>', methods=['PUT'])
@require_json
def update_spread(spread_id, data):
    db = current_app.config['DB']
    db.update_spread(
        spread_id,
        name=data.get('name'),
        positions=data.get('positions'),
        description=data.get('description'),
        allowed_deck_types=data.get('allowed_deck_types'),
        default_deck_id=data.get('default_deck_id'),
        clear_default_deck=data.get('clear_default_deck', False),
        deck_slots=data.get('deck_slots'),
        archived=data.get('archived'),
        favorite=data.get('favorite'),
        # A present-but-null source_id clears the attribution.
        source_id=data.get('source_id'),
        clear_source='source_id' in data and data.get('source_id') is None,
    )
    return jsonify({'ok': True})


@spreads_bp.route('/api/spreads/<int:spread_id>', methods=['DELETE'])
def delete_spread(spread_id):
    db = current_app.config['DB']
    if not db.get_spread(spread_id):
        return jsonify({'error': 'Spread not found'}), 404
    db.delete_spread(spread_id)
    return jsonify({'ok': True})


@spreads_bp.route('/api/spreads/<int:spread_id>/clone', methods=['POST'])
def clone_spread(spread_id):
    """Clone a spread with a new name."""
    db = current_app.config['DB']
    row = db.get_spread(spread_id)
    if not row:
        return jsonify({'error': 'Spread not found'}), 404

    original = _parse_spread(row_to_dict(row))
    data = request.get_json() or {}
    new_name = data.get('name', f"Copy of {original['name']}")

    new_id = db.add_spread(
        name=new_name,
        positions=original.get('positions', []),
        description=original.get('description'),
        cartomancy_type=original.get('cartomancy_type'),
        allowed_deck_types=original.get('allowed_deck_types'),
        source_id=original.get('source_id'),
        default_deck_id=original.get('default_deck_id'),
        deck_slots=original.get('deck_slots'),
    )
    return jsonify({'id': new_id}), 201
