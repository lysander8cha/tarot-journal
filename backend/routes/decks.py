"""
Deck endpoints -- CRUD for card decks.
"""

import json
from flask import Blueprint, jsonify, request, current_app

decks_bp = Blueprint('decks', __name__)

# Preferred display order for cartomancy types
TYPE_ORDER = ['Tarot', 'Lenormand', 'Oracle', 'Playing Cards', 'Kipper', 'I Ching']


def _row_to_dict(row):
    return dict(row) if row else None


def _sort_types(types):
    """Sort types by preferred display order, with unknown types at the end."""
    def sort_key(t):
        name = t.get('name', '') if isinstance(t, dict) else t['name']
        try:
            return TYPE_ORDER.index(name)
        except ValueError:
            return len(TYPE_ORDER)
    return sorted(types, key=sort_key)


@decks_bp.route('/api/decks')
def get_decks():
    db = current_app.config['DB']
    type_id = request.args.get('type_id', type=int)

    # Fetch all data with bulk queries (4 queries total instead of N+1)
    decks = db.get_decks(cartomancy_type_id=type_id)
    card_counts = db.get_deck_card_counts()
    all_tags = db.get_tags_for_decks()
    all_types = db.get_types_for_decks()

    # Assemble results using fast dictionary lookups (no additional queries)
    result = []
    for deck in decks:
        deck_id = deck['id']

        # Card count from bulk query
        deck['card_count'] = card_counts.get(deck_id, 0)

        # Tags from bulk query
        deck['tags'] = all_tags.get(deck_id, [])

        # Cartomancy types from bulk query
        types = all_types.get(deck_id, [])
        if types:
            deck['cartomancy_types'] = _sort_types(types)
            deck['cartomancy_type_names'] = ', '.join(t['name'] for t in types)
        else:
            # Fall back to primary type if no assignments exist
            deck['cartomancy_types'] = [{'id': deck['cartomancy_type_id'], 'name': deck['cartomancy_type_name']}]
            deck['cartomancy_type_names'] = deck['cartomancy_type_name']

        # Normalize field name for frontend compatibility
        deck['cartomancy_type'] = deck['cartomancy_type_names']

        result.append(deck)

    return jsonify(result)


@decks_bp.route('/api/decks/<int:deck_id>')
def get_deck(deck_id):
    db = current_app.config['DB']
    row = db.get_deck(deck_id)
    if not row:
        return jsonify({'error': 'Deck not found'}), 404
    return jsonify(_row_to_dict(row))


@decks_bp.route('/api/decks', methods=['POST'])
def add_deck():
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    name = data.get('name', '').strip()
    cartomancy_type_id = data.get('cartomancy_type_id')
    if not name or not cartomancy_type_id:
        return jsonify({'error': 'name and cartomancy_type_id are required'}), 400

    deck_id = db.add_deck(
        name=name,
        cartomancy_type_id=cartomancy_type_id,
        image_folder=data.get('image_folder'),
        suit_names=data.get('suit_names'),
        court_names=data.get('court_names'),
    )
    return jsonify({'id': deck_id}), 201


@decks_bp.route('/api/decks/<int:deck_id>', methods=['PUT'])
def update_deck(deck_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    db.update_deck(
        deck_id,
        name=data.get('name'),
        image_folder=data.get('image_folder'),
        suit_names=data.get('suit_names'),
        court_names=data.get('court_names'),
        date_published=data.get('date_published'),
        publisher=data.get('publisher'),
        credits=data.get('credits'),
        notes=data.get('notes'),
        card_back_image=data.get('card_back_image'),
        booklet_info=data.get('booklet_info'),
        cartomancy_type_id=data.get('cartomancy_type_id'),
    )
    return jsonify({'ok': True})


@decks_bp.route('/api/decks/<int:deck_id>', methods=['DELETE'])
def delete_deck(deck_id):
    db = current_app.config['DB']
    db.delete_deck(deck_id)
    return jsonify({'ok': True})


@decks_bp.route('/api/decks/<int:deck_id>/types')
def get_deck_types(deck_id):
    db = current_app.config['DB']
    rows = db.get_types_for_deck(deck_id)
    types = [_row_to_dict(r) for r in rows]
    return jsonify(_sort_types(types))


@decks_bp.route('/api/decks/<int:deck_id>/types', methods=['PUT'])
def set_deck_types(deck_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    type_ids = data.get('type_ids', [])
    db.set_deck_types(deck_id, type_ids)
    return jsonify({'ok': True})


@decks_bp.route('/api/decks/<int:deck_id>/suit-names')
def get_suit_names(deck_id):
    db = current_app.config['DB']
    names = db.get_deck_suit_names(deck_id)
    return jsonify(names or {})


@decks_bp.route('/api/decks/<int:deck_id>/suit-names', methods=['PUT'])
def update_suit_names(deck_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    suit_names = data.get('suit_names')
    old_suit_names = data.get('old_suit_names')
    db.update_deck_suit_names(deck_id, suit_names, old_suit_names)
    return jsonify({'ok': True})


@decks_bp.route('/api/decks/<int:deck_id>/court-names')
def get_court_names(deck_id):
    db = current_app.config['DB']
    names = db.get_deck_court_names(deck_id)
    return jsonify(names or {})


@decks_bp.route('/api/decks/<int:deck_id>/court-names', methods=['PUT'])
def update_court_names(deck_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    court_names = data.get('court_names')
    old_court_names = data.get('old_court_names')
    db.update_deck_court_names(deck_id, court_names, old_court_names)
    return jsonify({'ok': True})


@decks_bp.route('/api/decks/<int:deck_id>/tags')
def get_deck_tags(deck_id):
    db = current_app.config['DB']
    rows = db.get_tags_for_deck(deck_id)
    return jsonify([_row_to_dict(r) for r in rows])


@decks_bp.route('/api/decks/<int:deck_id>/tags', methods=['PUT'])
def set_deck_tag_assignments(deck_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    tag_ids = data.get('tag_ids', [])
    db.set_deck_tags(deck_id, tag_ids)
    return jsonify({'ok': True})


# ── Deck Custom Fields ────────────────────────────────────────

@decks_bp.route('/api/decks/<int:deck_id>/custom-fields')
def get_deck_custom_fields(deck_id):
    db = current_app.config['DB']
    rows = db.get_deck_custom_fields(deck_id)
    return jsonify([_row_to_dict(r) for r in rows])


@decks_bp.route('/api/decks/<int:deck_id>/custom-fields', methods=['POST'])
def add_deck_custom_field(deck_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    field_name = data.get('field_name', '').strip()
    if not field_name:
        return jsonify({'error': 'field_name is required'}), 400
    field_id = db.add_deck_custom_field(
        deck_id,
        field_name=field_name,
        field_type=data.get('field_type', 'text'),
        field_options=data.get('field_options'),
        field_order=data.get('field_order', 0),
    )
    return jsonify({'id': field_id}), 201


@decks_bp.route('/api/decks/custom-fields/<int:field_id>', methods=['PUT'])
def update_deck_custom_field(field_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    db.update_deck_custom_field(
        field_id,
        field_name=data.get('field_name'),
        field_type=data.get('field_type'),
        field_options=data.get('field_options'),
        field_order=data.get('field_order'),
    )
    return jsonify({'ok': True})


@decks_bp.route('/api/decks/custom-fields/<int:field_id>', methods=['DELETE'])
def delete_deck_custom_field(field_id):
    db = current_app.config['DB']
    db.delete_deck_custom_field(field_id)
    return jsonify({'ok': True})


@decks_bp.route('/api/decks/<int:deck_id>/groups')
def get_deck_groups(deck_id):
    db = current_app.config['DB']
    rows = db.get_card_groups(deck_id)
    return jsonify([_row_to_dict(r) for r in rows])


@decks_bp.route('/api/decks/<int:deck_id>/groups', methods=['POST'])
def add_deck_group(deck_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    name = data.get('name', '').strip()
    color = data.get('color', '#6B5B95')
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    group_id = db.add_card_group(deck_id, name, color)
    return jsonify({'id': group_id}), 201


@decks_bp.route('/api/groups/<int:group_id>', methods=['PUT'])
def update_deck_group(group_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    db.update_card_group(group_id, name=data.get('name'), color=data.get('color'))
    return jsonify({'ok': True})


@decks_bp.route('/api/groups/<int:group_id>', methods=['DELETE'])
def delete_deck_group(group_id):
    db = current_app.config['DB']
    db.delete_card_group(group_id)
    return jsonify({'ok': True})
