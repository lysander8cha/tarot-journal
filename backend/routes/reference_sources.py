"""
Reference-source endpoints — sources + their fields + per-(archetype,
field) content.

In the new shape:
  - A source is scoped to a cartomancy type and carries optional
    multi-author attribution.
  - A source defines its own fields (e.g. Upright, Reversed,
    Symbolism). Each field, for each archetype of the source's type,
    can hold a single rich-text content blob.

Lenormand combinations keep using sources the legacy way (per-pair
meanings); those endpoints aren't touched.
"""

from flask import Blueprint, jsonify, request, current_app
from backend.utils import require_json

reference_sources_bp = Blueprint('reference_sources', __name__)


# === Sources =================================================

@reference_sources_bp.route('/api/reference/sources')
def list_sources():
    """List reference sources. ?cartomancy_type=Tarot scopes the result."""
    db = current_app.config['DB']
    ctype = request.args.get('cartomancy_type')
    return jsonify(db.get_reference_sources(cartomancy_type=ctype))


@reference_sources_bp.route('/api/reference/sources', methods=['POST'])
@require_json
def create_source(data):
    db = current_app.config['DB']
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    cartomancy_types = data.get('cartomancy_types')
    # Backwards-compat: accept a single cartomancy_type if that's what
    # an older caller sends.
    if cartomancy_types is None and data.get('cartomancy_type'):
        cartomancy_types = [data['cartomancy_type']]
    if not cartomancy_types or not isinstance(cartomancy_types, list):
        return jsonify({'error': 'cartomancy_types is required'}), 400
    authors = data.get('authors') or []
    try:
        new_id = db.create_reference_source(
            name, cartomancy_types=cartomancy_types, authors=authors,
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Could not create source: {e}'}), 400
    return jsonify({'id': new_id})


@reference_sources_bp.route('/api/reference/sources/<int:source_id>', methods=['PUT'])
@require_json
def update_source(source_id, data):
    db = current_app.config['DB']
    name = data.get('name')
    if name is not None and not str(name).strip():
        return jsonify({'error': 'Name cannot be blank'}), 400
    cartomancy_types = data.get('cartomancy_types')
    # Same single-value fallback as create for older callers.
    if cartomancy_types is None and data.get('cartomancy_type'):
        cartomancy_types = [data['cartomancy_type']]
    if cartomancy_types is not None and not isinstance(cartomancy_types, list):
        return jsonify({'error': 'cartomancy_types must be an array'}), 400
    authors = data.get('authors')
    try:
        db.update_reference_source(
            source_id,
            name=name.strip() if isinstance(name, str) else None,
            cartomancy_types=cartomancy_types,
            authors=authors if isinstance(authors, list) else None,
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'ok': True})


@reference_sources_bp.route('/api/reference/sources/<int:source_id>', methods=['DELETE'])
def delete_source(source_id):
    db = current_app.config['DB']
    reassign_to = request.args.get('reassign_to')
    reassign_id = int(reassign_to) if reassign_to else None
    db.delete_reference_source(source_id, reassign_to=reassign_id)
    return jsonify({'ok': True})


@reference_sources_bp.route('/api/reference/sources/<int:source_id>/dependencies')
def source_dependencies(source_id):
    db = current_app.config['DB']
    return jsonify(db.count_reference_source_dependencies(source_id))


# === Fields ===================================================

@reference_sources_bp.route('/api/reference/sources/<int:source_id>/fields')
def list_fields(source_id):
    """List fields on a source. ?cartomancy_type=... scopes to one
    bucket — the Settings UI uses that to show only the fields
    relevant to the active editing type."""
    db = current_app.config['DB']
    ctype = request.args.get('cartomancy_type')
    return jsonify(db.get_source_fields(source_id, cartomancy_type=ctype))


@reference_sources_bp.route('/api/reference/sources/<int:source_id>/fields', methods=['POST'])
@require_json
def create_field(source_id, data):
    db = current_app.config['DB']
    name = (data.get('name') or '').strip()
    cartomancy_type = (data.get('cartomancy_type') or '').strip()
    if not name:
        return jsonify({'error': 'Field name is required'}), 400
    if not cartomancy_type:
        return jsonify({'error': 'cartomancy_type is required'}), 400
    collapsible = bool(data.get('collapsible'))
    try:
        new_id = db.create_source_field(
            source_id, name, cartomancy_type, collapsible=collapsible,
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Could not create field: {e}'}), 400
    return jsonify({'id': new_id})


@reference_sources_bp.route('/api/source-fields/<int:field_id>', methods=['PUT'])
@require_json
def update_field(field_id, data):
    db = current_app.config['DB']
    name = data.get('name')
    if name is not None and not str(name).strip():
        return jsonify({'error': 'Field name cannot be blank'}), 400
    sort_order = data.get('sort_order')
    # `collapsible` is optional — we only persist when present so
    # rename/reorder PATCHes don't accidentally reset the flag.
    raw_collapsible = data.get('collapsible')
    collapsible = (
        bool(raw_collapsible) if raw_collapsible is not None else None
    )
    db.update_source_field(
        field_id,
        name=name.strip() if isinstance(name, str) else None,
        sort_order=sort_order if isinstance(sort_order, int) else None,
        collapsible=collapsible,
    )
    return jsonify({'ok': True})


@reference_sources_bp.route(
    '/api/reference/sources/<int:source_id>/fields/reorder',
    methods=['PUT'],
)
@require_json
def reorder_fields(source_id, data):
    """Body: {"cartomancy_type": "Tarot", "field_ids": [id1, id2, ...]}.
    Reassigns sort_order within the given (source, type) bucket to
    match list position."""
    db = current_app.config['DB']
    ctype = (data.get('cartomancy_type') or '').strip()
    if not ctype:
        return jsonify({'error': 'cartomancy_type is required'}), 400
    ids = data.get('field_ids') or []
    if not isinstance(ids, list):
        return jsonify({'error': 'field_ids must be an array'}), 400
    db.reorder_source_fields(source_id, ctype, [int(x) for x in ids])
    return jsonify({'ok': True})


@reference_sources_bp.route('/api/source-fields/<int:field_id>', methods=['DELETE'])
def delete_field(field_id):
    """Removes the field and all authored content under it (CASCADE)."""
    db = current_app.config['DB']
    db.delete_source_field(field_id)
    return jsonify({'ok': True})


# === Per-archetype source entries ============================

@reference_sources_bp.route('/api/archetypes/<int:archetype_id>/source-entries')
def list_entries_for_archetype(archetype_id):
    """Non-empty entries for an archetype, hydrated with source + field
    info. ?cartomancy_type=... scopes to a single type — the
    Archetypes viewer calls this with the active type."""
    db = current_app.config['DB']
    ctype = request.args.get('cartomancy_type')
    return jsonify(db.get_source_entries_for_archetype(archetype_id, cartomancy_type=ctype))


@reference_sources_bp.route('/api/reference/sources/<int:source_id>/entries')
def list_entries_for_source(source_id):
    """Every entry across every field of a source. ?cartomancy_type=...
    scopes to one type bucket — the Settings authoring page passes the
    active type so it can render the appropriate cell grid."""
    db = current_app.config['DB']
    ctype = request.args.get('cartomancy_type')
    return jsonify(db.get_source_entries_for_source(source_id, cartomancy_type=ctype))


@reference_sources_bp.route(
    '/api/archetypes/<int:archetype_id>/source-fields/<int:field_id>',
    methods=['PUT'],
)
@require_json
def set_entry(archetype_id, field_id, data):
    """Upsert (archetype, field) content. Blank deletes."""
    db = current_app.config['DB']
    content = data.get('content', '')
    db.set_source_entry(archetype_id, field_id, content)
    return jsonify({'ok': True})


