"""
Archetype endpoints -- search/autocomplete plus CRUD for the Deck
Types manager (custom types need their archetypes authored in-app).
"""

import sqlite3

from flask import Blueprint, jsonify, request, current_app
from backend.utils import row_to_dict, require_json, validate_length

archetypes_bp = Blueprint('archetypes', __name__)


@archetypes_bp.route('/api/archetypes')
def get_archetypes():
    """Get archetypes, optionally filtered by cartomancy type."""
    db = current_app.config['DB']
    ctype = request.args.get('cartomancy_type')
    rows = db.get_archetypes(cartomancy_type=ctype)
    return jsonify([row_to_dict(r) for r in rows])


@archetypes_bp.route('/api/archetypes', methods=['POST'])
@require_json
def add_archetype(data):
    db = current_app.config['DB']
    name = (data.get('name') or '').strip()
    ctype = (data.get('cartomancy_type') or '').strip()
    if not name or not ctype:
        return jsonify({'error': 'name and cartomancy_type are required'}), 400
    err = validate_length(name, field_name='name')
    if err:
        return jsonify({'error': err}), 400
    try:
        new_id = db.add_archetype(
            name, ctype,
            rank=(data.get('rank') or '').strip() or None,
            suit=(data.get('suit') or '').strip() or None,
            card_type=(data.get('card_type') or '').strip() or None)
    except sqlite3.IntegrityError:
        return jsonify({'error': f'"{name}" already exists for {ctype}.'}), 400
    return jsonify({'id': new_id}), 201


@archetypes_bp.route('/api/archetypes/bulk', methods=['POST'])
@require_json
def bulk_add_archetypes(data):
    """Add many archetypes at once. Body: {cartomancy_type, rows:
    [{name, rank?, suit?}, ...]}. Existing names are skipped, not
    errors — pasting a full list over a partial one just fills gaps."""
    db = current_app.config['DB']
    ctype = (data.get('cartomancy_type') or '').strip()
    rows = data.get('rows') or []
    if not ctype or not isinstance(rows, list) or not rows:
        return jsonify({'error': 'cartomancy_type and rows are required'}), 400
    created = 0
    skipped = 0
    for r in rows:
        name = (r.get('name') or '').strip() if isinstance(r, dict) else ''
        if not name:
            continue
        try:
            db.add_archetype(
                name, ctype,
                rank=(r.get('rank') or '').strip() or None,
                suit=(r.get('suit') or '').strip() or None)
            created += 1
        except sqlite3.IntegrityError:
            skipped += 1
    return jsonify({'created': created, 'skipped': skipped})


@archetypes_bp.route('/api/archetypes/seed-from-deck', methods=['POST'])
@require_json
def seed_from_deck(data):
    """Create archetypes from a deck's card names (each card's
    archetype tag when set, its name otherwise)."""
    db = current_app.config['DB']
    deck_id = data.get('deck_id')
    ctype = (data.get('cartomancy_type') or '').strip()
    if not deck_id or not ctype:
        return jsonify({'error': 'deck_id and cartomancy_type are required'}), 400
    created = db.seed_archetypes_from_deck(int(deck_id), ctype)
    return jsonify({'created': created})


@archetypes_bp.route('/api/archetypes/<int:archetype_id>', methods=['PUT'])
@require_json
def update_archetype(archetype_id, data):
    db = current_app.config['DB']
    try:
        db.update_archetype(
            archetype_id,
            name=data.get('name'),
            rank=data.get('rank'),
            suit=data.get('suit'))
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except sqlite3.IntegrityError:
        return jsonify({'error': 'That name already exists for this type.'}), 400
    return jsonify({'ok': True})


@archetypes_bp.route('/api/archetypes/<int:archetype_id>', methods=['DELETE'])
def delete_archetype(archetype_id):
    db = current_app.config['DB']
    db.delete_archetype(archetype_id)
    return jsonify({'ok': True})


