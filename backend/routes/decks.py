"""
Deck endpoints -- CRUD for card decks.
"""

import os
from collections import Counter
from flask import Blueprint, jsonify, request, current_app
from backend.utils import row_to_dict, sort_types, require_json, validate_length

decks_bp = Blueprint('decks', __name__)


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
        deck['cartomancy_types'] = sort_types(types) if types else []
        deck['cartomancy_type_names'] = ', '.join(t['name'] for t in types)

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
    return jsonify(row_to_dict(row))


@decks_bp.route('/api/decks', methods=['POST'])
@require_json
def add_deck(data):
    db = current_app.config['DB']
    name = data.get('name', '').strip()
    # Accept type_ids list or single cartomancy_type_id for backward compatibility
    type_ids = data.get('type_ids')
    if not type_ids:
        cartomancy_type_id = data.get('cartomancy_type_id')
        type_ids = [cartomancy_type_id] if cartomancy_type_id else []
    if not name or not type_ids:
        return jsonify({'error': 'name and type_ids (or cartomancy_type_id) are required'}), 400
    err = validate_length(name, field_name='name')
    if err:
        return jsonify({'error': err}), 400

    deck_id = db.add_deck(
        name=name,
        type_ids=type_ids,
        image_folder=data.get('image_folder'),
        suit_names=data.get('suit_names'),
        court_names=data.get('court_names'),
    )
    return jsonify({'id': deck_id}), 201


@decks_bp.route('/api/decks/<int:deck_id>', methods=['PUT'])
@require_json
def update_deck(deck_id, data):
    db = current_app.config['DB']
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
        correspondence_system_id=data.get('correspondence_system_id'),
        favorite=data.get('favorite'),
    )
    return jsonify({'ok': True})


@decks_bp.route('/api/decks/<int:deck_id>', methods=['DELETE'])
def delete_deck(deck_id):
    db = current_app.config['DB']
    if not db.get_deck(deck_id):
        return jsonify({'error': 'Deck not found'}), 404
    db.delete_deck(deck_id)
    return jsonify({'ok': True})


@decks_bp.route('/api/decks/<int:deck_id>/image-health')
def deck_image_health(deck_id):
    """Report how many of a deck's card image files are actually on
    disk, so the UI can warn when a deck folder has moved instead of
    silently showing blanks."""
    db = current_app.config['DB']
    cards = [row_to_dict(c) for c in db.get_cards(deck_id)]
    with_path = [c for c in cards if c.get('image_path')]
    missing = [c for c in with_path if not os.path.exists(c['image_path'])]
    # The folder the missing files were last known to live in — usually
    # one directory, so report the most common parent.
    missing_dir = None
    if missing:
        dirs = Counter(os.path.dirname(c['image_path']) for c in missing)
        missing_dir = dirs.most_common(1)[0][0]
    return jsonify({
        'total': len(cards),
        'with_images': len(with_path),
        'missing_count': len(missing),
        'missing_dir': missing_dir,
    })


@decks_bp.route('/api/decks/<int:deck_id>/field-coverage')
def deck_field_coverage(deck_id):
    """Per-field fill counts for the deck's card custom fields."""
    db = current_app.config['DB']
    return jsonify(db.get_deck_field_coverage(deck_id))


@decks_bp.route('/api/decks/<int:deck_id>/types')
def get_deck_types(deck_id):
    db = current_app.config['DB']
    rows = db.get_types_for_deck(deck_id)
    types = [row_to_dict(r) for r in rows]
    return jsonify(sort_types(types))


@decks_bp.route('/api/decks/<int:deck_id>/types', methods=['PUT'])
@require_json
def set_deck_types(deck_id, data):
    db = current_app.config['DB']
    type_ids = data.get('type_ids', [])
    db.set_deck_types(deck_id, type_ids)
    return jsonify({'ok': True})


@decks_bp.route('/api/decks/<int:deck_id>/suit-names')
def get_suit_names(deck_id):
    db = current_app.config['DB']
    names = db.get_deck_suit_names(deck_id)
    return jsonify(names or {})


@decks_bp.route('/api/decks/<int:deck_id>/suit-names', methods=['PUT'])
@require_json
def update_suit_names(deck_id, data):
    db = current_app.config['DB']
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
@require_json
def update_court_names(deck_id, data):
    db = current_app.config['DB']
    court_names = data.get('court_names')
    old_court_names = data.get('old_court_names')
    db.update_deck_court_names(deck_id, court_names, old_court_names)
    return jsonify({'ok': True})


@decks_bp.route('/api/decks/<int:deck_id>/tags')
def get_deck_tags(deck_id):
    db = current_app.config['DB']
    rows = db.get_tags_for_deck(deck_id)
    return jsonify([row_to_dict(r) for r in rows])


@decks_bp.route('/api/decks/<int:deck_id>/tags', methods=['PUT'])
@require_json
def set_deck_tag_assignments(deck_id, data):
    db = current_app.config['DB']
    tag_ids = data.get('tag_ids', [])
    db.set_deck_tags(deck_id, tag_ids)
    return jsonify({'ok': True})


@decks_bp.route('/api/decks/<int:deck_id>/rename-cards', methods=['POST'])
@require_json
def rename_deck_cards(deck_id, data):
    """Batch-rename cards within one deck (the "card names from
    language" feature). Body: {"renames": [{"card_id": 1, "name": "El
    Loco"}, ...]}. Only cards belonging to the deck are touched;
    per-row failures are reported, not fatal."""
    db = current_app.config['DB']
    renames = data.get('renames') or []
    if not renames:
        return jsonify({'error': 'renames is required'}), 400
    deck_card_ids = {r['id'] for r in (dict(x) for x in db.get_cards(deck_id))}
    applied = 0
    errors = []
    for i, r in enumerate(renames):
        try:
            card_id = int(r['card_id'])
            name = (r.get('name') or '').strip()
            if not name:
                raise ValueError('name is required')
            if card_id not in deck_card_ids:
                raise ValueError(f'card {card_id} is not in deck {deck_id}')
            err = validate_length(name, field_name='name')
            if err:
                raise ValueError(err)
            db.update_card(card_id, name=name)
            applied += 1
        except Exception as e:
            errors.append({'index': i, 'error': str(e)})
    return jsonify({'applied': applied, 'errors': errors})


# ── Deck Custom Fields ────────────────────────────────────────

@decks_bp.route('/api/decks/<int:deck_id>/custom-fields')
def get_deck_custom_fields(deck_id):
    db = current_app.config['DB']
    rows = db.get_deck_custom_fields(deck_id)
    return jsonify([row_to_dict(r) for r in rows])


@decks_bp.route('/api/decks/<int:deck_id>/custom-fields', methods=['POST'])
@require_json
def add_deck_custom_field(deck_id, data):
    db = current_app.config['DB']
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
@require_json
def update_deck_custom_field(field_id, data):
    db = current_app.config['DB']
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
    return jsonify([row_to_dict(r) for r in rows])


@decks_bp.route('/api/decks/<int:deck_id>/groups', methods=['POST'])
@require_json
def add_deck_group(deck_id, data):
    db = current_app.config['DB']
    name = data.get('name', '').strip()
    color = data.get('color', '#6B5B95')
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    group_id = db.add_card_group(deck_id, name, color)
    return jsonify({'id': group_id}), 201


@decks_bp.route('/api/groups/<int:group_id>', methods=['PUT'])
@require_json
def update_deck_group(group_id, data):
    db = current_app.config['DB']
    db.update_card_group(group_id, name=data.get('name'), color=data.get('color'))
    return jsonify({'ok': True})


@decks_bp.route('/api/groups/<int:group_id>', methods=['DELETE'])
def delete_deck_group(group_id):
    db = current_app.config['DB']
    if not db.get_card_group(group_id):
        return jsonify({'error': 'Group not found'}), 404
    db.delete_card_group(group_id)
    return jsonify({'ok': True})
