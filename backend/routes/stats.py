"""
Statistics endpoints for the Stats tab.
"""

from flask import Blueprint, jsonify, current_app, request

stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/api/stats')
def get_stats():
    """Get basic statistics (totals and top 5 lists)."""
    db = current_app.config['DB']
    data = db.get_stats()
    return jsonify(data)


@stats_bp.route('/api/stats/extended')
def get_extended_stats():
    """Get extended statistics for the Stats tab overview.

    Returns basic stats plus entries_this_month, unique_cards_drawn,
    total_readings, and avg_cards_per_reading.
    """
    db = current_app.config['DB']
    data = db.get_extended_stats()
    return jsonify(data)


@stats_bp.route('/api/stats/card-frequency')
def get_card_frequency():
    """Get card frequency data for visualization.

    Query params:
        limit: Max cards to return (default 20, max 100)
        deck_id: Optional deck ID to filter by

    Returns list of {name, deck_name, count, reversed_count}
    """
    db = current_app.config['DB']

    # Parse query params with validation
    limit = request.args.get('limit', 20, type=int)
    limit = min(max(limit, 1), 100)  # Clamp between 1 and 100

    deck_id = request.args.get('deck_id', type=int)

    data = db.get_card_frequency(limit=limit, deck_id=deck_id)
    return jsonify(data)


@stats_bp.route('/api/stats/timeline')
def get_timeline():
    """Get entry and reading counts grouped by month.

    Query params:
        limit: Number of months to return (default 12, max 36)
    """
    db = current_app.config['DB']
    limit = request.args.get('limit', 12, type=int)
    limit = min(max(limit, 1), 36)
    data = db.get_timeline_stats(limit=limit)
    return jsonify(data)


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
