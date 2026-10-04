"""
Statistics endpoints for the Stats/Insights tab.
"""

from flask import Blueprint, jsonify, current_app, request
from database.correspondences import CORRESPONDENCE_FIELDS

stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/api/stats/tag-trends')
def get_tag_trends():
    """Get entry tag usage counts.

    Query params:
        limit: Max tags to return (default 15, max 50)
    """
    db = current_app.config['DB']
    limit = request.args.get('limit', 15, type=int)
    limit = min(max(limit, 1), 50)
    data = db.get_tag_trends(limit=limit)
    return jsonify(data)


@stats_bp.route('/api/stats/usage')
def get_usage_stats():
    """Get deck and spread usage counts.

    Query params:
        limit: Max items per category (default 10, max 50)
    """
    db = current_app.config['DB']
    limit = request.args.get('limit', 10, type=int)
    limit = min(max(limit, 1), 50)
    data = db.get_usage_stats(limit=limit)
    return jsonify(data)


@stats_bp.route('/api/stats/correspondence-frequency')
def get_correspondence_frequency():
    """Get frequency of correspondence field values across readings.

    Query params:
        field: Correspondence field name (required)
        months: Time period in months (default 6, max 36)
    """
    db = current_app.config['DB']
    field = request.args.get('field', '')
    if field not in CORRESPONDENCE_FIELDS:
        return jsonify({'error': f'Invalid field. Must be one of: {", ".join(CORRESPONDENCE_FIELDS)}'}), 400
    months = request.args.get('months', 6, type=int)
    months = min(max(months, 1), 36)
    data = db.get_correspondence_frequency(field, months=months)
    return jsonify(data)

