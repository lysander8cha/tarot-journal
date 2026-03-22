"""
Cartomancy type endpoints (Tarot, Lenormand, Oracle, etc.)
"""

from flask import Blueprint, jsonify, request, current_app
from backend.utils import row_to_dict, sort_types

types_bp = Blueprint('types', __name__)


@types_bp.route('/api/types')
def get_types():
    db = current_app.config['DB']
    rows = db.get_cartomancy_types()
    types = [row_to_dict(r) for r in rows]
    return jsonify(sort_types(types))


@types_bp.route('/api/types', methods=['POST'])
def add_type():
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    type_id = db.add_cartomancy_type(name)
    return jsonify({'id': type_id, 'name': name}), 201
