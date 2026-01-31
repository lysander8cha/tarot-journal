"""
Tag endpoints -- CRUD for entry tags, deck tags, and card tags.
"""

from flask import Blueprint, jsonify, request, current_app

tags_bp = Blueprint('tags', __name__)


def _row_to_dict(row):
    return dict(row) if row else None


# ── Entry Tags ───────────────────────────────────────────────

@tags_bp.route('/api/entry-tags')
def get_entry_tags():
    """Get all available entry tags."""
    db = current_app.config['DB']
    rows = db.get_tags()
    return jsonify([_row_to_dict(r) for r in rows])


@tags_bp.route('/api/entry-tags', methods=['POST'])
def add_entry_tag():
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    tag_id = db.add_tag(name=name, color=data.get('color', '#6B5B95'))
    return jsonify({'id': tag_id}), 201


@tags_bp.route('/api/entry-tags/<int:tag_id>', methods=['PUT'])
def update_entry_tag(tag_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    db.update_tag(tag_id, name=data.get('name'), color=data.get('color'))
    return jsonify({'ok': True})


@tags_bp.route('/api/entry-tags/<int:tag_id>', methods=['DELETE'])
def delete_entry_tag(tag_id):
    db = current_app.config['DB']
    db.delete_tag(tag_id)
    return jsonify({'ok': True})


# ── Deck Tags ────────────────────────────────────────────────

@tags_bp.route('/api/deck-tags')
def get_deck_tags():
    """Get all available deck tags."""
    db = current_app.config['DB']
    rows = db.get_deck_tags()
    return jsonify([_row_to_dict(r) for r in rows])


@tags_bp.route('/api/deck-tags', methods=['POST'])
def add_deck_tag():
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    tag_id = db.add_deck_tag(name=name, color=data.get('color', '#6B5B95'))
    return jsonify({'id': tag_id}), 201


@tags_bp.route('/api/deck-tags/<int:tag_id>', methods=['PUT'])
def update_deck_tag(tag_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    db.update_deck_tag(tag_id, name=data.get('name'), color=data.get('color'))
    return jsonify({'ok': True})


@tags_bp.route('/api/deck-tags/<int:tag_id>', methods=['DELETE'])
def delete_deck_tag(tag_id):
    db = current_app.config['DB']
    db.delete_deck_tag(tag_id)
    return jsonify({'ok': True})


# ── Card Tags ────────────────────────────────────────────────

@tags_bp.route('/api/card-tags')
def get_card_tags():
    """Get all available card tags."""
    db = current_app.config['DB']
    rows = db.get_card_tags()
    return jsonify([_row_to_dict(r) for r in rows])


@tags_bp.route('/api/card-tags', methods=['POST'])
def add_card_tag():
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    tag_id = db.add_card_tag(name=name, color=data.get('color', '#6B5B95'))
    return jsonify({'id': tag_id}), 201


@tags_bp.route('/api/card-tags/<int:tag_id>', methods=['PUT'])
def update_card_tag(tag_id):
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    db.update_card_tag(tag_id, name=data.get('name'), color=data.get('color'))
    return jsonify({'ok': True})


@tags_bp.route('/api/card-tags/<int:tag_id>', methods=['DELETE'])
def delete_card_tag(tag_id):
    db = current_app.config['DB']
    db.delete_card_tag(tag_id)
    return jsonify({'ok': True})
