"""
Flask application factory for the Tarot Journal API.

Creates a Flask app that wraps the existing database.py data layer,
serving all data over a REST API for the React frontend.
"""

import sys
import os
import atexit

# Add the project root to Python path so we can import database.py, etc.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, send_from_directory

# Path to the built React frontend
FRONTEND_DIST = os.path.join(PROJECT_ROOT, 'frontend', 'dist')


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__, static_folder=None)

    # Import here to avoid circular imports and ensure PROJECT_ROOT is on path
    from database import Database
    from thumbnail_cache import get_cache

    # The journal database lives in the platform app-data folder
    # (~/Library/Application Support/TarotJournal on macOS), not in
    # the code folder next to git operations and stray files.
    from backend.config import get_data_dir
    data_dir = get_data_dir()
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, 'tarot_journal.db')

    # One-time migration: the database used to live in the repo root.
    # This runs before any connection opens, so moving the file (plus
    # its -shm/-wal sidecars, which must travel together) is safe. If
    # a database already exists at the new location, the old one is
    # left untouched rather than overwritten.
    legacy_db = os.path.join(PROJECT_ROOT, 'tarot_journal.db')
    if not os.path.exists(db_path) and os.path.exists(legacy_db):
        import shutil
        from logger_config import get_logger
        for suffix in ('', '-shm', '-wal'):
            src = legacy_db + suffix
            if os.path.exists(src):
                shutil.move(src, db_path + suffix)
        get_logger('backend').info("Moved database from %s to %s", legacy_db, db_path)
        # Bring existing auto-snapshots along to the new backups home.
        legacy_auto = os.path.join(PROJECT_ROOT, 'backups', 'auto')
        new_auto = os.path.join(data_dir, 'backups', 'auto')
        if os.path.isdir(legacy_auto):
            os.makedirs(new_auto, exist_ok=True)
            for name in os.listdir(legacy_auto):
                if not os.path.exists(os.path.join(new_auto, name)):
                    shutil.move(os.path.join(legacy_auto, name), os.path.join(new_auto, name))

    db = Database(db_path=db_path)
    app.config['DB'] = db

    # Automatic safety net: snapshot the database on every launch,
    # keeping the 10 most recent snapshots. This protects against
    # corruption or accidental data loss even if the user never
    # presses the manual Backup button. A failed snapshot must never
    # prevent the app from starting, hence the broad catch.
    auto_backup_dir = os.path.join(data_dir, 'backups', 'auto')
    app.config['AUTO_BACKUP_DIR'] = auto_backup_dir
    try:
        db.auto_backup(auto_backup_dir, keep=10)
    except Exception as e:
        from logger_config import get_logger
        get_logger('backend').warning("Automatic startup backup failed: %s", e)
    app.config['THUMB_CACHE'] = get_cache()

    # Ensure the database is properly closed (and WAL checkpointed) on exit
    atexit.register(db.close)

    # Register route blueprints
    from backend.routes import register_blueprints
    register_blueprints(app)

    # Phone-sync LAN guard: non-loopback callers may only reach the
    # token-protected /api/sync/ routes. See backend/routes/sync.py.
    from backend.routes.sync import install_lan_guard
    install_lan_guard(app)

    # Serve the built React frontend (production mode)
    if os.path.isdir(FRONTEND_DIST):
        @app.route('/')
        def serve_index():
            return send_from_directory(FRONTEND_DIST, 'index.html')

        @app.route('/assets/<path:filename>')
        def serve_assets(filename):
            return send_from_directory(os.path.join(FRONTEND_DIST, 'assets'), filename)

        # SPA fallback: serve index.html for any non-API, non-file routes
        @app.errorhandler(404)
        def spa_fallback(e):
            # Only serve SPA for non-API routes
            from flask import request
            if request.path.startswith('/api/'):
                return {'error': 'Not found'}, 404
            return send_from_directory(FRONTEND_DIST, 'index.html')

    return app
