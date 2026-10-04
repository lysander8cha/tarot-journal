"""
Image serving endpoints -- serves card images and thumbnails over HTTP.

Card images are stored as local file paths in the database.
This module reads those paths and streams the files to the browser.

Security: All paths are validated before serving to prevent path traversal
attacks. Only image files with recognized extensions are served.
"""

import os
from flask import Blueprint, current_app, send_file, abort
import logging

from backend.security import is_valid_image_path, is_safe_path

logger = logging.getLogger(__name__)
images_bp = Blueprint('images', __name__)

# Map common extensions to MIME types
_MIME_TYPES = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
}


def _mime_for(path):
    ext = os.path.splitext(path)[1].lower()
    return _MIME_TYPES.get(ext, 'image/jpeg')


@images_bp.route('/api/images/card/<int:card_id>/thumbnail')
def card_thumbnail(card_id):
    """Serve a cached thumbnail (300x450) for a card."""
    db = current_app.config['DB']
    cache = current_app.config['THUMB_CACHE']
    card = db.get_card(card_id)
    if not card or not card['image_path']:
        abort(404)

    # Security: Validate source image path before generating thumbnail
    if not is_valid_image_path(card['image_path']):
        logger.warning(f"Invalid source image for thumbnail, card {card_id}")
        abort(404)

    thumb_path = cache.get_thumbnail_path(card['image_path'])
    if not thumb_path:
        abort(404)

    # Security: Ensure thumbnail is within the cache directory
    cache_dir = str(cache.cache_dir)
    if not is_safe_path(thumb_path, [cache_dir]):
        logger.warning(f"Thumbnail path outside cache dir for card {card_id}")
        abort(404)

    resp = send_file(thumb_path, mimetype='image/png')
    resp.cache_control.max_age = 86400
    return resp


@images_bp.route('/api/images/card/<int:card_id>/preview')
def card_preview(card_id):
    """Serve a larger preview (500x750) for a card."""
    db = current_app.config['DB']
    cache = current_app.config['THUMB_CACHE']
    card = db.get_card(card_id)
    if not card or not card['image_path']:
        abort(404)

    # Security: Validate source image path before generating preview
    if not is_valid_image_path(card['image_path']):
        logger.warning(f"Invalid source image for preview, card {card_id}")
        abort(404)

    thumb_path = cache.get_thumbnail_path(
        card['image_path'],
        size=cache.PREVIEW_SIZE,
    )
    if not thumb_path:
        abort(404)

    # Security: Ensure preview is within the cache directory
    cache_dir = str(cache.cache_dir)
    if not is_safe_path(thumb_path, [cache_dir]):
        logger.warning(f"Preview path outside cache dir for card {card_id}")
        abort(404)

    resp = send_file(thumb_path, mimetype='image/png')
    resp.cache_control.max_age = 86400
    return resp


@images_bp.route('/api/images/deck/<int:deck_id>/back')
def deck_back_image(deck_id):
    """Serve the card-back image for a deck."""
    db = current_app.config['DB']
    deck = db.get_deck(deck_id)
    if not deck or not deck['card_back_image']:
        abort(404)
    path = deck['card_back_image']

    # Security: Validate the path is a real image file
    if not is_valid_image_path(path):
        logger.warning(f"Invalid card-back path for deck {deck_id}: {path}")
        abort(404)

    resp = send_file(path, mimetype=_mime_for(path))
    resp.cache_control.max_age = 86400
    return resp
