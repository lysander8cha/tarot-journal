"""
Import/export endpoints -- deck import from folder, JSON export/import.

Security: Folder paths are validated before scanning/importing to prevent
path traversal attacks.
"""

import os
import json
import logging
from io import BytesIO
from flask import Blueprint, jsonify, request, current_app, send_file

from backend.security import is_valid_directory

logger = logging.getLogger(__name__)
import_export_bp = Blueprint('import_export', __name__)


@import_export_bp.route('/api/import/preset-info')
def get_preset_info():
    """Get info about a specific import preset (type, suit names, etc.)."""
    preset_name = request.args.get('preset_name', '')

    from import_presets import get_presets
    presets = get_presets()

    preset = presets.get_preset(preset_name)
    if not preset:
        return jsonify(None)

    return jsonify({
        'type': preset.get('type', 'Oracle'),
        'suit_names': preset.get('suit_names'),
    })


@import_export_bp.route('/api/import/scan-folder', methods=['POST'])
def scan_folder():
    """Scan a folder and preview what cards would be imported."""
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    folder = data.get('folder', '').strip()
    preset_name = data.get('preset_name', '')
    custom_suit_names = data.get('custom_suit_names')
    custom_court_names = data.get('custom_court_names')
    archetype_mapping = data.get('archetype_mapping')

    # Security: Validate the folder path
    if not folder or not is_valid_directory(folder):
        logger.warning(f"Invalid folder path for scan: {folder}")
        return jsonify({'error': 'Invalid folder path'}), 400

    from import_presets import get_presets
    presets = get_presets()

    try:
        preview = presets.preview_import_with_metadata(
            folder,
            preset_name,
            custom_suit_names=custom_suit_names,
            custom_court_names=custom_court_names,
            archetype_mapping=archetype_mapping,
        )
        card_back = presets.find_card_back_image(folder, preset_name)
        return jsonify({
            'cards': preview,
            'card_back': card_back,
            'count': len(preview),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@import_export_bp.route('/api/import/from-folder', methods=['POST'])
def import_from_folder():
    """Import a deck from a folder of images."""
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400

    folder = data.get('folder', '').strip()
    deck_name = data.get('deck_name', '').strip()
    cartomancy_type_id = data.get('cartomancy_type_id')
    preset_name = data.get('preset_name', '')
    custom_suit_names = data.get('custom_suit_names')
    custom_court_names = data.get('custom_court_names')
    archetype_mapping = data.get('archetype_mapping')

    # Security: Validate the folder path
    if not folder or not is_valid_directory(folder):
        logger.warning(f"Invalid folder path for import: {folder}")
        return jsonify({'error': 'Invalid folder path'}), 400
    if not deck_name:
        return jsonify({'error': 'Deck name is required'}), 400
    if not cartomancy_type_id:
        return jsonify({'error': 'Cartomancy type is required'}), 400

    from import_presets import get_presets
    presets = get_presets()

    try:
        # Get card metadata preview
        cards_meta = presets.preview_import_with_metadata(
            folder,
            preset_name,
            custom_suit_names=custom_suit_names,
            custom_court_names=custom_court_names,
            archetype_mapping=archetype_mapping,
        )

        # Create deck (save suit/court names so edit modal has correct initial values)
        deck_id = db.add_deck(
            name=deck_name,
            type_ids=[cartomancy_type_id],
            image_folder=folder,
            suit_names=custom_suit_names,
            court_names=custom_court_names,
        )

        # Find card back
        card_back = presets.find_card_back_image(folder, preset_name)
        if card_back:
            db.update_deck(deck_id, card_back_image=card_back)

        # Format cards for bulk insert
        cards = []
        for c in cards_meta:
            cards.append({
                'name': c.get('name', c.get('filename', '')),
                'image_path': os.path.join(folder, c['filename']),
                'sort_order': c.get('sort_order', 0),
                'archetype': c.get('archetype'),
                'rank': c.get('rank'),
                'suit': c.get('suit'),
                'custom_fields': c.get('custom_fields'),
            })

        db.bulk_add_cards(deck_id, cards, auto_metadata=False)

        # Pre-generate thumbnails
        thumb_cache = current_app.config['THUMB_CACHE']
        for card_row in db.get_cards(deck_id):
            card = dict(card_row)
            if card.get('image_path'):
                try:
                    thumb_cache.get_thumbnail(card['image_path'], (300, 450))
                except Exception as e:
                    # Log but continue - thumbnail generation failure shouldn't
                    # block the import
                    logger.warning(f"Failed to generate thumbnail for {card['image_path']}: {e}")

        return jsonify({
            'deck_id': deck_id,
            'cards_imported': len(cards),
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@import_export_bp.route('/api/import/add-cards-to-deck', methods=['POST'])
def add_cards_to_deck():
    """Scan a folder and add new card images to an existing deck."""
    db = current_app.config['DB']
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400

    deck_id = data.get('deck_id')
    folder = data.get('folder', '').strip()

    if not deck_id:
        return jsonify({'error': 'deck_id is required'}), 400
    if not folder or not is_valid_directory(folder):
        logger.warning(f"Invalid folder path for add-cards: {folder}")
        return jsonify({'error': 'Invalid folder path'}), 400

    deck = db.get_deck(deck_id)
    if not deck:
        return jsonify({'error': 'Deck not found'}), 404

    try:
        # Get existing card image paths for this deck to avoid duplicates
        existing_cards = db.get_cards(deck_id)
        existing_paths = set()
        for c in existing_cards:
            c = dict(c)
            if c.get('image_path'):
                existing_paths.add(os.path.normpath(c['image_path']))

        # Find image files in the folder
        from backend.security import ALLOWED_IMAGE_EXTENSIONS
        image_files = []
        for f in sorted(os.listdir(folder)):
            ext = os.path.splitext(f)[1].lower()
            if ext in ALLOWED_IMAGE_EXTENSIONS:
                full_path = os.path.normpath(os.path.join(folder, f))
                # Skip only if the exact same path is already in the deck
                if full_path in existing_paths:
                    continue
                image_files.append(f)

        if not image_files:
            return jsonify({'error': 'No new image files found in folder'}), 400

        # Determine starting sort order
        max_order = max((dict(c).get('card_order', 0) for c in existing_cards), default=-1)

        # Build card data
        cards = []
        for i, filename in enumerate(image_files):
            name = os.path.splitext(filename)[0]
            # Clean up common filename patterns: replace underscores/hyphens, strip numbers
            name = name.replace('_', ' ').replace('-', ' ').strip()
            cards.append({
                'name': name,
                'image_path': os.path.join(folder, filename),
                'sort_order': max_order + 1 + i,
            })

        db.bulk_add_cards(deck_id, cards, auto_metadata=False)

        # Pre-generate thumbnails
        thumb_cache = current_app.config['THUMB_CACHE']
        for card_row in db.get_cards(deck_id):
            card = dict(card_row)
            if card.get('image_path') and os.path.join(folder, '') in card['image_path']:
                try:
                    thumb_cache.get_thumbnail(card['image_path'], (300, 450))
                except Exception as e:
                    logger.warning(f"Failed to generate thumbnail for {card['image_path']}: {e}")

        return jsonify({
            'cards_added': len(cards),
            'filenames': [c['name'] for c in cards],
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@import_export_bp.route('/api/import/scan-new-cards', methods=['POST'])
def scan_new_cards():
    """Scan a folder and preview which images would be added to a deck (skipping existing)."""
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400

    deck_id = data.get('deck_id')
    folder = data.get('folder', '').strip()

    if not deck_id:
        return jsonify({'error': 'deck_id is required'}), 400
    if not folder or not is_valid_directory(folder):
        return jsonify({'error': 'Invalid folder path'}), 400

    db = current_app.config['DB']
    deck = db.get_deck(deck_id)
    if not deck:
        return jsonify({'error': 'Deck not found'}), 404

    try:
        # Get existing image paths to skip exact duplicates
        existing_cards = db.get_cards(deck_id)
        existing_paths = set()
        for c in existing_cards:
            c = dict(c)
            if c.get('image_path'):
                existing_paths.add(os.path.normpath(c['image_path']))

        from backend.security import ALLOWED_IMAGE_EXTENSIONS
        new_cards = []
        for f in sorted(os.listdir(folder)):
            ext = os.path.splitext(f)[1].lower()
            if ext in ALLOWED_IMAGE_EXTENSIONS:
                full_path = os.path.normpath(os.path.join(folder, f))
                if full_path in existing_paths:
                    continue
                name = os.path.splitext(f)[0].replace('_', ' ').replace('-', ' ').strip()
                new_cards.append({
                    'filename': f,
                    'name': name,
                })

        return jsonify({
            'cards': new_cards,
            'count': len(new_cards),
            'existing_count': len(existing_cards),
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@import_export_bp.route('/api/import/presets')
def get_import_presets():
    """Get available import preset names."""
    from import_presets import get_presets
    presets = get_presets()
    return jsonify(presets.get_preset_names())


@import_export_bp.route('/api/import/presets/details')
def get_import_presets_details():
    """Get all presets with full details (for settings UI)."""
    from import_presets import get_presets, BUILTIN_PRESETS
    presets = get_presets()
    result = []
    for name in presets.get_preset_names():
        preset = presets.get_preset(name)
        if not preset:
            continue
        clean_name = name.replace("Custom: ", "")
        is_builtin = clean_name in BUILTIN_PRESETS
        is_customized = presets.is_preset_customized(name)
        # Group mappings by card name for the UI:
        # { "The Fool": ["00", "0", "fool"], ... }
        mappings = preset.get('mappings', {})
        grouped = {}
        for pattern, card_name in mappings.items():
            grouped.setdefault(card_name, []).append(pattern)

        result.append({
            'name': name,
            'type': preset.get('type', 'Oracle'),
            'description': preset.get('description', ''),
            'suit_names': preset.get('suit_names', {}),
            'card_count': len(set(mappings.values())) if mappings else 0,
            'is_builtin': is_builtin,
            'is_customized': is_customized,
            'mappings_grouped': grouped,
        })
    return jsonify(result)


@import_export_bp.route('/api/import/presets', methods=['POST'])
def save_import_preset():
    """Create or update a custom import preset."""
    from import_presets import get_presets
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    cartomancy_type = data.get('type', 'Oracle')
    description = data.get('description', '')
    suit_names = data.get('suit_names', {})
    mappings = data.get('mappings')

    presets = get_presets()
    # If no mappings provided, preserve existing ones from the preset being edited
    if mappings is None:
        existing = presets.get_preset(name)
        mappings = existing.get('mappings', {}) if existing else {}

    presets.add_custom_preset(name, cartomancy_type, mappings, description, suit_names)
    return jsonify({'ok': True})


@import_export_bp.route('/api/import/presets/<path:name>', methods=['DELETE'])
def delete_import_preset(name):
    """Delete a custom import preset."""
    from import_presets import get_presets, BUILTIN_PRESETS
    presets = get_presets()
    clean_name = name.replace("Custom: ", "")
    # Can't delete a builtin unless it's been customized (in which case we revert it)
    if clean_name in BUILTIN_PRESETS and clean_name not in presets.custom_presets:
        return jsonify({'error': 'Cannot delete a built-in preset'}), 400
    presets.delete_custom_preset(name)
    return jsonify({'ok': True})


@import_export_bp.route('/api/import/presets/<path:name>/reset', methods=['POST'])
def reset_import_preset(name):
    """Reset a customized built-in preset back to its default."""
    from import_presets import get_presets, BUILTIN_PRESETS
    if name not in BUILTIN_PRESETS:
        return jsonify({'error': 'Not a built-in preset'}), 400
    presets = get_presets()
    if name in presets.custom_presets:
        del presets.custom_presets[name]
        presets._save_presets()
    return jsonify({'ok': True})


@import_export_bp.route('/api/export/deck/<int:deck_id>')
def export_deck(deck_id):
    """Export a deck as JSON download."""
    db = current_app.config['DB']
    try:
        data = db.export_deck_json(deck_id)
    except ValueError:
        # export_deck_json raises for a missing deck (it never returns
        # a falsy value), e.g. exporting a deck that was just deleted.
        return jsonify({'error': 'Deck not found'}), 404

    deck_name = data.get('deck', {}).get('name', 'deck')
    safe_name = ''.join(c for c in deck_name if c.isalnum() or c in ' _-').strip() or 'deck'

    # Deck JSON is small (metadata only, no images) — serve it straight
    # from memory. The old temp-file flow leaked its file on every
    # export: its call_on_close cleanup never ran, because werkzeug
    # skips close callbacks for direct_passthrough file responses.
    payload = json.dumps(data, indent=2).encode('utf-8')
    return send_file(
        BytesIO(payload),
        as_attachment=True,
        download_name=f'{safe_name}.json',
        mimetype='application/json',
    )


