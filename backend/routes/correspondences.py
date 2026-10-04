"""
Correspondence system endpoints -- CRUD for systems, assignments, and card overrides.
"""

from flask import Blueprint, jsonify, request, current_app
from backend.utils import row_to_dict, require_json

correspondences_bp = Blueprint('correspondences', __name__)


# === Correspondence Systems ===

@correspondences_bp.route('/api/correspondence-systems')
def list_systems():
    db = current_app.config['DB']
    systems = db.get_correspondence_systems()
    return jsonify([row_to_dict(s) for s in systems])


@correspondences_bp.route('/api/correspondence-systems', methods=['POST'])
@require_json
def create_system(data):
    db = current_app.config['DB']
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    description = (data.get('description') or '').strip() or None
    cartomancy_type = (data.get('cartomancy_type') or 'Tarot').strip() or 'Tarot'
    naming_style = (data.get('naming_style') or '').strip() or None
    try:
        system_id = db.create_correspondence_system(
            name,
            description=description,
            cartomancy_type=cartomancy_type,
            naming_style=naming_style,
        )
    except Exception:
        return jsonify({'error': 'A system with that name already exists'}), 409
    return jsonify({'id': system_id}), 201


@correspondences_bp.route('/api/correspondence-systems/<int:system_id>')
def get_system(system_id):
    db = current_app.config['DB']
    system = db.get_correspondence_system(system_id)
    if not system:
        return jsonify({'error': 'System not found'}), 404
    result = row_to_dict(system)
    result['assignments'] = [
        row_to_dict(a) for a in db.get_system_assignments(system_id)
    ]
    return jsonify(result)


@correspondences_bp.route('/api/correspondence-systems/<int:system_id>', methods=['PUT'])
@require_json
def update_system(system_id, data):
    db = current_app.config['DB']
    system = db.get_correspondence_system(system_id)
    if not system:
        return jsonify({'error': 'System not found'}), 404
    try:
        db.update_correspondence_system(
            system_id,
            name=data.get('name'),
            description=data.get('description'),
        )
    except Exception:
        return jsonify({'error': 'A system with that name already exists'}), 409
    return jsonify({'ok': True})


@correspondences_bp.route('/api/correspondence-systems/<int:system_id>', methods=['DELETE'])
def delete_system(system_id):
    db = current_app.config['DB']
    system = db.get_correspondence_system(system_id)
    if not system:
        return jsonify({'error': 'System not found'}), 404
    db.delete_correspondence_system(system_id)
    return jsonify({'ok': True})


@correspondences_bp.route('/api/correspondence-systems/<int:system_id>/clone', methods=['POST'])
@require_json
def clone_system(system_id, data):
    db = current_app.config['DB']
    new_name = data.get('name', '').strip()
    if not new_name:
        return jsonify({'error': 'Name is required'}), 400
    new_id = db.clone_correspondence_system(system_id, new_name)
    if new_id is None:
        return jsonify({'error': 'Source system not found'}), 404
    return jsonify({'id': new_id}), 201


# === System Assignments ===

@correspondences_bp.route('/api/correspondence-systems/<int:system_id>/assignments')
def get_assignments(system_id):
    db = current_app.config['DB']
    archetype_id = request.args.get('archetype_id', type=int)
    assignments = db.get_system_assignments(system_id, archetype_id=archetype_id)
    return jsonify([row_to_dict(a) for a in assignments])


@correspondences_bp.route(
    '/api/correspondence-systems/<int:system_id>/expand-elemental-zodiac',
    methods=['POST']
)
@require_json
def expand_elemental_zodiac_route(system_id, data):
    """Assign all 3 zodiac signs of each archetype's suit element.

    Body: { archetype_ids: [int], source_group: str }
    """
    db = current_app.config['DB']
    archetype_ids = data.get('archetype_ids', [])
    source_group = data.get('source_group') or ''
    if not archetype_ids or not source_group:
        return jsonify({'error': 'archetype_ids and source_group are required'}), 400
    report = db.expand_elemental_zodiac(system_id, archetype_ids, source_group)
    return jsonify({'ok': True, 'report': report})


@correspondences_bp.route(
    '/api/correspondence-systems/<int:system_id>/assignments/<int:archetype_id>/<field_name>',
    methods=['PUT']
)
@require_json
def set_assignment(system_id, archetype_id, field_name, data):
    """Set one or more values for a cell.

    Accepts either:
      { value: string, source_group?: string }    → single-value assignment
      { values: string[], source_group?: string } → multi-value assignment
    """
    db = current_app.config['DB']
    source_group = data.get('source_group')

    if 'values' in data:
        values = [v.strip() for v in data.get('values') or [] if v and v.strip()]
        try:
            db.set_system_multi_assignment(
                system_id, archetype_id, field_name, values,
                source_group=source_group,
            )
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        return jsonify({'ok': True})

    field_value = (data.get('value') or '').strip()
    if not field_value:
        return jsonify({'error': 'Value is required'}), 400
    try:
        db.set_system_assignment(
            system_id, archetype_id, field_name, field_value,
            source_group=source_group,
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'ok': True})


@correspondences_bp.route(
    '/api/correspondence-systems/<int:system_id>/assignments/<int:archetype_id>/<field_name>',
    methods=['DELETE']
)
def delete_assignment(system_id, archetype_id, field_name):
    """Delete assignment(s) for a cell.

    Query params:
        source_group: only delete the value from this specific group
        all: if 'true', delete all values (both manual and all groups)
    """
    db = current_app.config['DB']
    source_group = request.args.get('source_group')
    delete_all = request.args.get('all') == 'true'
    db.delete_system_assignment(
        system_id, archetype_id, field_name,
        source_group=source_group,
        delete_all_sources=delete_all,
    )
    return jsonify({'ok': True})


# === Card-Level Overrides ===

@correspondences_bp.route('/api/cards/<int:card_id>/correspondences')
def get_card_correspondences(card_id):
    db = current_app.config['DB']
    correspondences = db.get_card_correspondences(card_id)
    return jsonify(correspondences)


@correspondences_bp.route('/api/cards/<int:card_id>/correspondences', methods=['PUT'])
@require_json
def set_card_overrides(card_id, data):
    """Set one or more card-level overrides.

    Body: {overrides: [{field_name, field_value?, field_values?}]}
    - field_values: list of strings → multi-value override
    - field_value: string or null → single-value override (null to clear)
    """
    db = current_app.config['DB']
    overrides = data.get('overrides', [])
    for override in overrides:
        field_name = override.get('field_name')
        if 'field_values' in override:
            values = override.get('field_values') or []
            values = [v.strip() for v in values if v and v.strip()]
            if not values:
                db.delete_card_correspondence_override(card_id, field_name)
            else:
                try:
                    db.set_card_correspondence_overrides(card_id, field_name, values)
                except ValueError as e:
                    return jsonify({'error': str(e)}), 400
        else:
            field_value = override.get('field_value')
            if field_value is None or field_value == '':
                db.delete_card_correspondence_override(card_id, field_name)
            else:
                try:
                    db.set_card_correspondence_override(card_id, field_name, field_value)
                except ValueError as e:
                    return jsonify({'error': str(e)}), 400
    return jsonify({'ok': True})


# === Cross-System Queries (for Reference tab) ===

@correspondences_bp.route('/api/correspondences/compare')
def compare_systems():
    db = current_app.config['DB']
    system_ids_str = request.args.get('systems', '')
    try:
        system_ids = [int(x) for x in system_ids_str.split(',') if x.strip()]
    except ValueError:
        return jsonify({'error': 'Invalid system IDs'}), 400
    if not system_ids:
        return jsonify({'error': 'At least one system ID required'}), 400
    assignments = db.compare_correspondence_systems(system_ids)
    return jsonify([row_to_dict(a) for a in assignments])


@correspondences_bp.route('/api/correspondence-field-options')
def list_field_options():
    """Get all field options, optionally filtered by field name."""
    db = current_app.config['DB']
    field_name = request.args.get('field')
    options = db.get_field_options(field_name=field_name)
    return jsonify([row_to_dict(o) for o in options])


@correspondences_bp.route('/api/correspondence-field-options', methods=['POST'])
@require_json
def create_field_option(data):
    db = current_app.config['DB']
    field_name = data.get('field_name', '')
    option_value = (data.get('option_value', '') or '').strip()
    if not field_name or not option_value:
        return jsonify({'error': 'field_name and option_value are required'}), 400
    try:
        opt_id = db.add_field_option(field_name, option_value)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'id': opt_id}), 201


@correspondences_bp.route('/api/correspondence-field-options/<int:option_id>', methods=['PUT'])
@require_json
def update_field_option(option_id, data):
    db = current_app.config['DB']
    db.update_field_option(
        option_id,
        option_value=data.get('option_value'),
        sort_order=data.get('sort_order'),
    )
    return jsonify({'ok': True})


@correspondences_bp.route('/api/correspondence-field-options/<int:option_id>', methods=['DELETE'])
def delete_field_option(option_id):
    db = current_app.config['DB']
    db.delete_field_option(option_id)
    return jsonify({'ok': True})


@correspondences_bp.route('/api/correspondence-field-options/reorder', methods=['POST'])
@require_json
def reorder_field_options(data):
    db = current_app.config['DB']
    field_name = data.get('field_name')
    ordered_ids = data.get('ordered_ids', [])
    if not field_name:
        return jsonify({'error': 'field_name required'}), 400
    db.reorder_field_options(field_name, ordered_ids)
    return jsonify({'ok': True})


@correspondences_bp.route('/api/decks/<int:deck_id>/correspondence-overrides')
def list_deck_correspondence_overrides(deck_id):
    db = current_app.config['DB']
    rows = db.get_deck_correspondence_overrides(deck_id)
    return jsonify([row_to_dict(r) for r in rows])


@correspondences_bp.route('/api/decks/<int:deck_id>/correspondence-overrides', methods=['PUT'])
@require_json
def set_deck_correspondence_override(deck_id, data):
    """Set a deck-level override.
    Body: {archetype_id, field_name, values: [], source_group?: str}
    """
    db = current_app.config['DB']
    archetype_id = data.get('archetype_id')
    field_name = data.get('field_name')
    values = data.get('values') or []
    values = [v.strip() for v in values if v and v.strip()]
    source_group = data.get('source_group')
    if archetype_id is None or not field_name:
        return jsonify({'error': 'archetype_id and field_name are required'}), 400
    if not values:
        db.delete_deck_correspondence_override(
            deck_id, archetype_id, field_name, source_group=source_group,
        )
    else:
        try:
            db.set_deck_correspondence_overrides(
                deck_id, archetype_id, field_name, values, source_group=source_group,
            )
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
    return jsonify({'ok': True})


@correspondences_bp.route(
    '/api/decks/<int:deck_id>/correspondence-overrides/group',
    methods=['DELETE']
)
def delete_deck_correspondence_group_route(deck_id):
    """Delete every row for a given group (optionally scoped to a field).
    Query params: source_group (required), field_name (optional).
    """
    db = current_app.config['DB']
    source_group = request.args.get('source_group')
    field_name = request.args.get('field_name')
    if not source_group:
        return jsonify({'error': 'source_group is required'}), 400
    db.delete_deck_correspondence_group(deck_id, source_group, field_name=field_name)
    return jsonify({'ok': True})


@correspondences_bp.route('/api/card-names')
def card_names():
    """Get card names in other languages, aggregated by archetype."""
    db = current_app.config['DB']
    cursor = db.conn.cursor()
    # Find all custom fields with "Name" in the field name
    cursor.execute('''
        SELECT ccf.field_name, ccf.field_value, c.archetype, c.name AS card_name,
               d.name AS deck_name
        FROM card_custom_fields ccf
        JOIN cards c ON c.id = ccf.card_id
        JOIN decks d ON d.id = c.deck_id
        WHERE ccf.field_name LIKE '%Name%'
          AND ccf.field_value IS NOT NULL
          AND ccf.field_value != ''
        ORDER BY c.archetype, ccf.field_name
    ''')
    rows = cursor.fetchall()
    return jsonify([row_to_dict(r) for r in rows])
