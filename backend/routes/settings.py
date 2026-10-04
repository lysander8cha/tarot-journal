"""
Settings endpoints: theme, defaults, backup/restore, cache management.
"""

import json
import os
import re
import tempfile
from flask import Blueprint, jsonify, request, current_app
from theme_config import get_theme

settings_bp = Blueprint('settings', __name__)


# === Theme ===

@settings_bp.route('/api/theme')
def get_current_theme():
    theme = get_theme()
    return jsonify({
        'colors': theme.get_colors(),
        'fonts': theme.get_fonts(),
    })


@settings_bp.route('/api/theme', methods=['PUT'])
def update_theme():
    theme = get_theme()
    data = request.get_json()
    colors = data.get('colors')
    fonts = data.get('fonts')
    if colors:
        for key, value in colors.items():
            theme.set_color(key, value)
    if fonts:
        for key, value in fonts.items():
            theme.set_font(key, value)
    theme.save_theme()
    return jsonify({
        'colors': theme.get_colors(),
        'fonts': theme.get_fonts(),
    })


# === Default Settings ===

@settings_bp.route('/api/settings/defaults')
def get_defaults():
    db = current_app.config['DB']
    types = db.get_cartomancy_types()
    default_decks = {}
    for t in types:
        name = t['name']
        deck_id = db.get_default_deck(name)
        default_decks[name] = deck_id

    return jsonify({
        'default_querent': db.get_default_querent(),
        'default_reader': db.get_default_reader(),
        'default_querent_same_as_reader': db.get_default_querent_same_as_reader(),
        'default_decks': default_decks,
        'last_backup_time': db.get_setting('last_backup_time'),
        'astrology_house_system': db.get_house_system(),
        'astrology_allow_solar_chart': db.get_allow_solar_chart(),
    })


@settings_bp.route('/api/settings/defaults', methods=['PUT'])
def update_defaults():
    db = current_app.config['DB']
    data = request.get_json()

    if 'default_querent' in data:
        db.set_default_querent(data['default_querent'])
    if 'default_reader' in data:
        db.set_default_reader(data['default_reader'])
    if 'default_querent_same_as_reader' in data:
        db.set_default_querent_same_as_reader(data['default_querent_same_as_reader'])
    if 'default_decks' in data:
        for type_name, deck_id in data['default_decks'].items():
            if deck_id is not None:
                db.set_default_deck(type_name, deck_id)
    if 'astrology_house_system' in data:
        # Changing the house system invalidates all cached charts on
        # next view (via the input_hash mismatch). No bulk regen.
        db.set_house_system(data['astrology_house_system'])
    if 'astrology_allow_solar_chart' in data:
        db.set_allow_solar_chart(bool(data['astrology_allow_solar_chart']))

    return jsonify({'ok': True})


# === Backup & Restore ===

@settings_bp.route('/api/backup/status')
def backup_status():
    """Report backup recency so the UI can show (and nudge about)
    how protected the user's data currently is."""
    db = current_app.config['DB']

    latest_auto = None
    auto_count = 0
    auto_dir = current_app.config.get('AUTO_BACKUP_DIR')
    if auto_dir and os.path.isdir(auto_dir):
        import glob
        from datetime import datetime
        snaps = sorted(glob.glob(os.path.join(auto_dir, 'tarot_journal_auto_*.db')))
        auto_count = len(snaps)
        if snaps:
            latest_auto = datetime.fromtimestamp(
                os.path.getmtime(snaps[-1])).isoformat()

    return jsonify({
        'last_auto_snapshot': latest_auto,
        'auto_snapshot_count': auto_count,
        'last_backup_time': db.get_setting('last_backup_time'),
        'last_backup_with_images_time': db.get_setting('last_backup_with_images_time'),
    })


@settings_bp.route('/api/backup', methods=['POST'])
def create_backup():
    """Write a backup zip directly to the user's Downloads folder and
    return its path. The bytes never travel over HTTP: a with-images
    backup can be several GB, and routing that through the renderer as
    a Blob (the old flow) ran the window out of memory and crashed it.
    """
    from datetime import datetime

    db = current_app.config['DB']
    data = request.get_json() or {}
    include_images = data.get('include_images', False)

    # Destination: Downloads (a dest_dir override exists for tests).
    dest_dir = data.get('dest_dir') or os.path.join(os.path.expanduser('~'), 'Downloads')
    if not os.path.isdir(dest_dir):
        dest_dir = os.path.expanduser('~')
    stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    suffix = '_with_images' if include_images else ''
    filepath = os.path.join(dest_dir, f'tarot_backup_{stamp}{suffix}.zip')

    try:
        db.create_full_backup(filepath, include_images=include_images)
        return jsonify({'path': filepath, 'bytes': os.path.getsize(filepath)})
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': str(e)}), 500


@settings_bp.route('/api/backup/restore', methods=['POST'])
def restore_backup():
    db = current_app.config['DB']
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    fd, filepath = tempfile.mkstemp(suffix='.zip')
    os.close(fd)

    try:
        file.save(filepath)
        result = db.restore_from_backup(filepath)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


# === Cache Management ===

@settings_bp.route('/api/cache/stats')
def get_cache_stats():
    cache = current_app.config['THUMB_CACHE']
    return jsonify({
        'count': cache.get_cache_count(),
        'size_bytes': cache.get_cache_size(),
    })


@settings_bp.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    cache = current_app.config['THUMB_CACHE']
    cache.clear_cache()
    return jsonify({'ok': True})


# === Birth & name card indication colors ======================

INDICATION_COLORS_KEY = 'indication_colors'
_HEX_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


@settings_bp.route('/api/settings/indication-colors')
def get_indication_colors():
    db = current_app.config['DB']
    raw = db.get_setting(INDICATION_COLORS_KEY)
    try:
        colors = json.loads(raw) if raw else {}
    except ValueError:
        colors = {}
    return jsonify({'colors': colors if isinstance(colors, dict) else {}})


@settings_bp.route('/api/settings/indication-colors', methods=['PUT'])
def set_indication_colors():
    """Store per-role colors for the Indicate Birth & Name Cards
    feature. Body: {"colors": {"<role key>": "#rrggbb", ...}} — the
    full mapping replaces the stored one; unknown roles are allowed
    (the frontend owns the role registry), bad hex values are not."""
    db = current_app.config['DB']
    data = request.get_json() or {}
    colors = data.get('colors')
    if not isinstance(colors, dict):
        return jsonify({'error': 'colors must be an object'}), 400
    cleaned = {}
    for key, value in colors.items():
        if not isinstance(key, str) or not key.strip():
            return jsonify({'error': 'color keys must be strings'}), 400
        if not isinstance(value, str) or not _HEX_RE.match(value):
            return jsonify({'error': f'{key}: colors must be #rrggbb hex'}), 400
        cleaned[key.strip()] = value.lower()
    db.set_setting(INDICATION_COLORS_KEY, json.dumps(cleaned))
    return jsonify({'colors': cleaned})
