"""
Archetype endpoints -- search/autocomplete for card archetypes.
"""

from flask import Blueprint, jsonify, request, current_app
from backend.utils import row_to_dict

archetypes_bp = Blueprint('archetypes', __name__)


@archetypes_bp.route('/api/archetypes')
def get_archetypes():
    """Get archetypes, optionally filtered by cartomancy type."""
    db = current_app.config['DB']
    ctype = request.args.get('cartomancy_type')
    rows = db.get_archetypes(cartomancy_type=ctype)
    return jsonify([row_to_dict(r) for r in rows])


@archetypes_bp.route('/api/archetypes/search')
def search_archetypes():
    """Search archetypes for autocomplete."""
    db = current_app.config['DB']
    query = request.args.get('query', '')
    ctype = request.args.get('cartomancy_type')
    rows = db.search_archetypes(query, cartomancy_type=ctype)
    return jsonify([_row_to_dict(r) for r in rows])
