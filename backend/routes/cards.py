"""
Card endpoints -- CRUD and search for individual cards.
"""

import json
from flask import Blueprint, jsonify, request, current_app

cards_bp = Blueprint('cards', __name__)

# Pagination limits to prevent memory exhaustion
MAX_LIMIT = 500


def _row_to_dict(row):
    return dict(row) if row else None


@cards_bp.route('/api/cards')
def get_cards():
    """Get cards for a deck. Requires ?deck_id= query parameter."""
    db = current_app.config['DB']
    deck_id = request.args.get('deck_id', type=int)
    if not deck_id:
        return jsonify({'error': 'deck_id query parameter is required'}), 400
    rows = db.get_cards(deck_id)
    return jsonify([_row_to_dict(r) for r in rows])


@cards_bp.route('/api/cards/search')
def search_cards():
    """Search cards with flexible filters."""
    db = current_app.config['DB']
    # Validate limit to prevent memory exhaustion
    limit = request.args.get('limit', type=int)
    if limit is not None:
        limit = max(1, min(limit, MAX_LIMIT))
    results = db.search_cards(
        query=request.args.get('query'),
        deck_id=request.args.get('deck_id', type=int),
        deck_type=request.args.get('deck_type'),
        card_category=request.args.get('card_category'),
        archetype=request.args.get('archetype'),
        rank=request.args.get('rank'),
        suit=request.args.get('suit'),
        has_notes=request.args.get('has_notes', type=lambda v: v.lower() == 'true') if request.args.get('has_notes') else None,
        has_image=request.args.get('has_image', type=lambda v: v.lower() == 'true') if request.args.get('has_image') else None,
        sort_by=request.args.get('sort_by', 'name'),
        sort_asc=request.args.get('sort_asc', 'true').lower() == 'true',
        limit=limit,
    )
    return jsonify([_row_to_dict(r) for r in results])


@cards_bp.route('/api/cards/<int:card_id>')
def get_card(card_id):
    db = current_app.config['DB']
    row = db.get_card_with_metadata(card_id)
    if not row:
        return jsonify({'error': 'Card not found'}), 404
    card = _row_to_dict(row)
    # Add deck name
    deck = db.get_deck(card['deck_id'])
    card['deck_name'] = deck['name'] if deck else ''
    # Add tags and groups
    card['own_tags'] = [_row_to_dict(t) for t in db.get_tags_for_card(card_id)]
    card['inherited_tags'] = [_row_to_dict(t) for t in db.get_inherited_tags_for_card(card_id)]
    card['groups'] = [_row_to_dict(g) for g in db.get_groups_for_card(card_id)]
    # Add custom fields
    card['card_custom_fields'] = [_row_to_dict(f) for f in db.get_card_custom_fields(card_id)]
    return jsonify(card)


@cards_bp.route('/api/cards', methods=['POST'])
def add_card():
    db = current_app.config['DB']
    data = request.get_json()
    deck_id = data.get('deck_id')
    name = data.get('name', '').strip()
    if not deck_id or not name:
        return jsonify({'error': 'deck_id and name are required'}), 400
    card_id = db.add_card(
        deck_id=deck_id,
        name=name,
        image_path=data.get('image_path'),
        card_order=data.get('card_order', 0),
    )
    return jsonify({'id': card_id}), 201


@cards_bp.route('/api/cards/<int:card_id>', methods=['PUT'])
def update_card(card_id):
    db = current_app.config['DB']
    data = request.get_json()
    db.update_card(
        card_id,
        name=data.get('name'),
        image_path=data.get('image_path'),
        card_order=data.get('card_order'),
    )
    return jsonify({'ok': True})


@cards_bp.route('/api/cards/<int:card_id>', methods=['DELETE'])
def delete_card(card_id):
    db = current_app.config['DB']
    db.delete_card(card_id)
    return jsonify({'ok': True})


@cards_bp.route('/api/cards/<int:card_id>/metadata', methods=['PUT'])
def update_card_metadata(card_id):
    db = current_app.config['DB']
    data = request.get_json()
    db.update_card_metadata(
        card_id,
        archetype=data.get('archetype'),
        rank=data.get('rank'),
        suit=data.get('suit'),
        notes=data.get('notes'),
        custom_fields=data.get('custom_fields'),
    )
    return jsonify({'ok': True})


@cards_bp.route('/api/cards/<int:card_id>/tags')
def get_card_tags(card_id):
    db = current_app.config['DB']
    own = db.get_tags_for_card(card_id)
    inherited = db.get_inherited_tags_for_card(card_id)
    return jsonify({
        'own': [_row_to_dict(r) for r in own],
        'inherited': [_row_to_dict(r) for r in inherited],
    })


@cards_bp.route('/api/cards/<int:card_id>/tags', methods=['PUT'])
def set_card_tag_assignments(card_id):
    db = current_app.config['DB']
    data = request.get_json()
    tag_ids = data.get('tag_ids', [])
    db.set_card_tags(card_id, tag_ids)
    return jsonify({'ok': True})


@cards_bp.route('/api/cards/<int:card_id>/groups')
def get_card_groups(card_id):
    db = current_app.config['DB']
    rows = db.get_groups_for_card(card_id)
    return jsonify([_row_to_dict(r) for r in rows])


@cards_bp.route('/api/cards/<int:card_id>/groups', methods=['PUT'])
def set_card_group_assignments(card_id):
    db = current_app.config['DB']
    data = request.get_json()
    group_ids = data.get('group_ids', [])
    db.set_card_groups(card_id, group_ids)
    return jsonify({'ok': True})


@cards_bp.route('/api/cards/<int:card_id>/custom-fields')
def get_card_custom_fields(card_id):
    db = current_app.config['DB']
    rows = db.get_card_custom_fields(card_id)
    return jsonify([_row_to_dict(r) for r in rows])


@cards_bp.route('/api/cards/<int:card_id>/custom-fields', methods=['POST'])
def add_card_custom_field(card_id):
    db = current_app.config['DB']
    data = request.get_json()
    field_name = data.get('field_name', '').strip()
    field_type = data.get('field_type', 'text')
    if not field_name:
        return jsonify({'error': 'field_name is required'}), 400
    field_id = db.add_card_custom_field(
        card_id,
        field_name=field_name,
        field_type=field_type,
        field_value=data.get('field_value'),
        field_options=data.get('field_options'),
        field_order=data.get('field_order', 0),
    )
    return jsonify({'id': field_id}), 201


@cards_bp.route('/api/cards/custom-fields/<int:field_id>', methods=['PUT'])
def update_card_custom_field(field_id):
    db = current_app.config['DB']
    data = request.get_json()
    db.update_card_custom_field(
        field_id,
        field_name=data.get('field_name'),
        field_type=data.get('field_type'),
        field_value=data.get('field_value'),
        field_options=data.get('field_options'),
        field_order=data.get('field_order'),
    )
    return jsonify({'ok': True})


@cards_bp.route('/api/cards/custom-fields/<int:field_id>', methods=['DELETE'])
def delete_card_custom_field(field_id):
    db = current_app.config['DB']
    db.delete_card_custom_field(field_id)
    return jsonify({'ok': True})
