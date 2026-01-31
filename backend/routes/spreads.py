"""
Spread endpoints -- CRUD, clone for card spreads.
"""

import json
from flask import Blueprint, jsonify, request, current_app

spreads_bp = Blueprint('spreads', __name__)


def _row_to_dict(row):
    return dict(row) if row else None


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
    return jsonify([_parse_spread(_row_to_dict(r)) for r in rows])


@spreads_bp.route('/api/spreads/<int:spread_id>')
def get_spread(spread_id):
    db = current_app.config['DB']
    row = db.get_spread(spread_id)
    if not row:
        return jsonify({'error': 'Spread not found'}), 404
    return jsonify(_parse_spread(_row_to_dict(row)))


@spreads_bp.route('/api/spreads', methods=['POST'])
def add_spread():
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400

    spread_id = db.add_spread(
        name=name,
        positions=data.get('positions', []),
        description=data.get('description'),
        cartomancy_type=data.get('cartomancy_type'),
        allowed_deck_types=data.get('allowed_deck_types'),
        default_deck_id=data.get('default_deck_id'),
        deck_slots=data.get('deck_slots'),
    )
    return jsonify({'id': spread_id}), 201


@spreads_bp.route('/api/spreads/<int:spread_id>', methods=['PUT'])
def update_spread(spread_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    db.update_spread(
        spread_id,
        name=data.get('name'),
        positions=data.get('positions'),
        description=data.get('description'),
        allowed_deck_types=data.get('allowed_deck_types'),
        default_deck_id=data.get('default_deck_id'),
        clear_default_deck=data.get('clear_default_deck', False),
        deck_slots=data.get('deck_slots'),
    )
    return jsonify({'ok': True})


@spreads_bp.route('/api/spreads/<int:spread_id>', methods=['DELETE'])
def delete_spread(spread_id):
    db = current_app.config['DB']
    db.delete_spread(spread_id)
    return jsonify({'ok': True})


@spreads_bp.route('/api/spreads/<int:spread_id>/clone', methods=['POST'])
def clone_spread(spread_id):
    """Clone a spread with a new name."""
    db = current_app.config['DB']
    row = db.get_spread(spread_id)
    if not row:
        return jsonify({'error': 'Spread not found'}), 404

    original = _parse_spread(_row_to_dict(row))
    data = request.get_json() or {}
    new_name = data.get('name', f"Copy of {original['name']}")

    new_id = db.add_spread(
        name=new_name,
        positions=original.get('positions', []),
        description=original.get('description'),
        cartomancy_type=original.get('cartomancy_type'),
        allowed_deck_types=original.get('allowed_deck_types'),
        default_deck_id=original.get('default_deck_id'),
        deck_slots=original.get('deck_slots'),
    )
    return jsonify({'id': new_id}), 201
