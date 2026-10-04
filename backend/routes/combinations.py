"""
Combination-meaning endpoints. Cards are referenced by archetype id;
the active cartomancy type is required so the picker can list pairs.
The sources list lives in the shared /api/reference/sources blueprint.
"""

import json

from flask import Blueprint, jsonify, request, current_app
from backend.utils import row_to_dict, require_json

combinations_bp = Blueprint('combinations', __name__)


def _flag(value) -> bool:
    return str(value).lower() in ('1', 'true', 'yes')


# === Per-type reversal support ===

REVERSED_TYPES_KEY = 'combination_reversed_types'


@combinations_bp.route('/api/combinations/reversed-types')
def get_reversed_types():
    """Cartomancy types where combinations may involve reversed cards."""
    db = current_app.config['DB']
    raw = db.get_setting(REVERSED_TYPES_KEY) or '[]'
    try:
        types = json.loads(raw)
    except ValueError:
        types = []
    return jsonify({'types': types if isinstance(types, list) else []})


@combinations_bp.route('/api/combinations/reversed-types', methods=['PUT'])
@require_json
def set_reversed_types(data):
    db = current_app.config['DB']
    types = data.get('types')
    if not isinstance(types, list) or not all(isinstance(t, str) for t in types):
        return jsonify({'error': 'types must be a list of type names'}), 400
    db.set_setting(REVERSED_TYPES_KEY, json.dumps(sorted(set(types))))
    return jsonify({'ok': True})


# === Meanings (pair-keyed) ===

@combinations_bp.route('/api/combinations/meanings')
def list_meanings():
    """All meanings for a (cartomancy_type, card_1, card_2) triple.
    Query params: cartomancy_type, card_1, card_2 (archetype ids)."""
    db = current_app.config['DB']
    ctype = (request.args.get('cartomancy_type') or '').strip()
    if not ctype:
        return jsonify({'error': 'cartomancy_type is required'}), 400
    try:
        card_1 = int(request.args.get('card_1', ''))
        card_2 = int(request.args.get('card_2', ''))
    except (TypeError, ValueError):
        return jsonify({'error': 'card_1 and card_2 are required integers'}), 400
    card_3 = request.args.get('card_3', type=int)
    rows = db.get_combination_meanings(
        ctype, card_1, card_2,
        archetype_1_reversed=_flag(request.args.get('card_1_reversed')),
        archetype_2_reversed=_flag(request.args.get('card_2_reversed')),
        archetype_3_id=card_3,
        archetype_3_reversed=_flag(request.args.get('card_3_reversed')),
    )
    return jsonify([row_to_dict(r) for r in rows])


@combinations_bp.route('/api/combinations/meanings/other-reversals')
def other_reversal_count():
    """How many meanings the same pair/triad holds under other
    reversal states — the viewer's discoverability hint."""
    db = current_app.config['DB']
    ctype = (request.args.get('cartomancy_type') or '').strip()
    if not ctype:
        return jsonify({'error': 'cartomancy_type is required'}), 400
    try:
        card_1 = int(request.args.get('card_1', ''))
        card_2 = int(request.args.get('card_2', ''))
    except (TypeError, ValueError):
        return jsonify({'error': 'card_1 and card_2 are required integers'}), 400
    count = db.count_other_reversal_meanings(
        ctype, card_1, card_2,
        archetype_1_reversed=_flag(request.args.get('card_1_reversed')),
        archetype_2_reversed=_flag(request.args.get('card_2_reversed')),
        archetype_3_id=request.args.get('card_3', type=int),
        archetype_3_reversed=_flag(request.args.get('card_3_reversed')),
    )
    return jsonify({'count': count})


@combinations_bp.route('/api/combinations/partners')
def combination_partners():
    """Partner archetypes with authored meanings, for the picker
    dropdowns' "has meanings" hints. Query params: cartomancy_type,
    card_1, card_1_reversed, triad, and (for the third-card slot)
    card_2 + card_2_reversed. Returns {partners: {id: count}}."""
    db = current_app.config['DB']
    ctype = (request.args.get('cartomancy_type') or '').strip()
    if not ctype:
        return jsonify({'error': 'cartomancy_type is required'}), 400
    try:
        card_1 = int(request.args.get('card_1', ''))
    except (TypeError, ValueError):
        return jsonify({'error': 'card_1 is a required integer'}), 400
    rows = db.get_combination_partners(
        ctype, card_1,
        archetype_1_reversed=_flag(request.args.get('card_1_reversed')),
        triad=_flag(request.args.get('triad')),
        archetype_2_id=request.args.get('card_2', type=int),
        archetype_2_reversed=_flag(request.args.get('card_2_reversed')),
    )
    partners = {}
    for r in rows:
        d = row_to_dict(r)
        partners[str(d['archetype_id'])] = d['meaning_count']
    return jsonify({'partners': partners})


@combinations_bp.route('/api/combinations/by-source')
def combinations_by_source():
    """All of a type's meanings from one source — source_id absent or
    empty means unattributed meanings. Query params: cartomancy_type,
    source_id."""
    db = current_app.config['DB']
    ctype = (request.args.get('cartomancy_type') or '').strip()
    if not ctype:
        return jsonify({'error': 'cartomancy_type is required'}), 400
    raw = (request.args.get('source_id') or '').strip()
    source_id = None
    if raw and raw != 'none':
        try:
            source_id = int(raw)
        except ValueError:
            return jsonify({'error': 'source_id must be an integer or "none"'}), 400
    rows = db.get_meanings_by_source(ctype, source_id)
    return jsonify([row_to_dict(r) for r in rows])


@combinations_bp.route('/api/combinations/meanings', methods=['POST'])
@require_json
def create_meaning(data):
    """Add a meaning, creating the combination row if needed.
    Body: {cartomancy_type, card_1, card_2, meaning, source_id?}"""
    db = current_app.config['DB']
    ctype = (data.get('cartomancy_type') or '').strip()
    if not ctype:
        return jsonify({'error': 'cartomancy_type is required'}), 400
    try:
        card_1 = int(data.get('card_1'))
        card_2 = int(data.get('card_2'))
    except (TypeError, ValueError):
        return jsonify({'error': 'card_1 and card_2 are required integers'}), 400
    meaning = (data.get('meaning') or '').strip()
    source_id = data.get('source_id')
    if source_id == '' or source_id is None:
        source_id = None
    else:
        try:
            source_id = int(source_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'source_id must be an integer'}), 400
    try:
        card_3 = data.get('card_3')
        new_id = db.add_combination_meaning(
            ctype, card_1, card_2, meaning, source_id,
            archetype_1_reversed=_flag(data.get('card_1_reversed')),
            archetype_2_reversed=_flag(data.get('card_2_reversed')),
            archetype_3_id=int(card_3) if card_3 else None,
            archetype_3_reversed=_flag(data.get('card_3_reversed')),
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'id': new_id})


@combinations_bp.route('/api/combinations/meanings/<int:meaning_id>', methods=['PUT'])
@require_json
def update_meaning(meaning_id, data):
    """Update text and/or source. Body keys: meaning?, source_id? (null clears)."""
    db = current_app.config['DB']
    meaning = data.get('meaning')
    if meaning is not None:
        meaning = meaning.strip()
        if not meaning:
            return jsonify({'error': 'meaning cannot be empty'}), 400

    clear_source = False
    source_id = data.get('source_id', '__missing__')
    if source_id is None:
        clear_source = True
        source_id = None
    elif source_id == '__missing__':
        source_id = None
    else:
        try:
            source_id = int(source_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'source_id must be an integer or null'}), 400

    db.update_combination_meaning(
        meaning_id,
        meaning=meaning,
        source_id=source_id,
        clear_source=clear_source,
    )
    return jsonify({'ok': True})


@combinations_bp.route('/api/combinations/meanings/<int:meaning_id>', methods=['DELETE'])
def delete_meaning(meaning_id):
    db = current_app.config['DB']
    db.delete_combination_meaning(meaning_id)
    return jsonify({'ok': True})


@combinations_bp.route('/api/combinations/meanings/reorder', methods=['POST'])
@require_json
def reorder_meanings(data):
    """Body: {combination_id, ordered_ids: [int, ...]}"""
    db = current_app.config['DB']
    combination_id = data.get('combination_id')
    ordered_ids = data.get('ordered_ids') or []
    if combination_id is None or not isinstance(ordered_ids, list):
        return jsonify({'error': 'combination_id and ordered_ids are required'}), 400
    db.reorder_combination_meanings(int(combination_id), [int(i) for i in ordered_ids])
    return jsonify({'ok': True})
