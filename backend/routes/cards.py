"""
Card endpoints -- CRUD and search for individual cards.
"""

from flask import Blueprint, jsonify, request, current_app
from backend.utils import row_to_dict, require_json, validate_length

cards_bp = Blueprint('cards', __name__)

# Pagination limits to prevent memory exhaustion
MAX_LIMIT = 500


@cards_bp.route('/api/cards')
def get_cards():
    """Get cards for a deck. Requires ?deck_id= query parameter."""
    db = current_app.config['DB']
    deck_id = request.args.get('deck_id', type=int)
    if not deck_id:
        return jsonify({'error': 'deck_id query parameter is required'}), 400
    rows = db.get_cards(deck_id)
    return jsonify([row_to_dict(r) for r in rows])


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
    return jsonify([row_to_dict(r) for r in results])


@cards_bp.route('/api/cards/<int:card_id>')
def get_card(card_id):
    db = current_app.config['DB']
    card = db.get_card_full(card_id)
    if not card:
        return jsonify({'error': 'Card not found'}), 404
    return jsonify(card)


@cards_bp.route('/api/cards', methods=['POST'])
@require_json
def add_card(data):
    db = current_app.config['DB']
    deck_id = data.get('deck_id')
    name = data.get('name', '').strip()
    if not deck_id or not name:
        return jsonify({'error': 'deck_id and name are required'}), 400
    err = validate_length(name, field_name='name')
    if err:
        return jsonify({'error': err}), 400
    card_id = db.add_card(
        deck_id=deck_id,
        name=name,
        image_path=data.get('image_path'),
        card_order=data.get('card_order', 0),
    )
    return jsonify({'id': card_id}), 201


@cards_bp.route('/api/cards/<int:card_id>', methods=['PUT'])
@require_json
def update_card(card_id, data):
    db = current_app.config['DB']
    db.update_card(
        card_id,
        name=data.get('name'),
        image_path=data.get('image_path'),
        card_order=data.get('card_order'),
        variant_order=data.get('variant_order'),
    )
    return jsonify({'ok': True})


@cards_bp.route('/api/cards/<int:card_id>', methods=['DELETE'])
def delete_card(card_id):
    db = current_app.config['DB']
    db.delete_card(card_id)
    return jsonify({'ok': True})


@cards_bp.route('/api/cards/<int:card_id>/metadata', methods=['PUT'])
@require_json
def update_card_metadata(card_id, data):
    db = current_app.config['DB']
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
        'own': [row_to_dict(r) for r in own],
        'inherited': [row_to_dict(r) for r in inherited],
    })


@cards_bp.route('/api/cards/<int:card_id>/tags', methods=['PUT'])
@require_json
def set_card_tag_assignments(card_id, data):
    db = current_app.config['DB']
    tag_ids = data.get('tag_ids', [])
    db.set_card_tags(card_id, tag_ids)
    return jsonify({'ok': True})


@cards_bp.route('/api/cards/<int:card_id>/groups')
def get_card_groups(card_id):
    db = current_app.config['DB']
    rows = db.get_groups_for_card(card_id)
    return jsonify([row_to_dict(r) for r in rows])


@cards_bp.route('/api/cards/<int:card_id>/groups', methods=['PUT'])
@require_json
def set_card_group_assignments(card_id, data):
    db = current_app.config['DB']
    group_ids = data.get('group_ids', [])
    db.set_card_groups(card_id, group_ids)
    return jsonify({'ok': True})


@cards_bp.route('/api/cards/<int:card_id>/custom-fields', methods=['POST'])
@require_json
def add_card_custom_field(card_id, data):
    db = current_app.config['DB']
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
@require_json
def update_card_custom_field(field_id, data):
    db = current_app.config['DB']
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
