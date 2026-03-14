"""
Import/export endpoints -- deck import from folder, JSON export/import.

Security: Folder paths are validated before scanning/importing to prevent
path traversal attacks.
"""

import os
import json
import tempfile
import logging
from flask import Blueprint, jsonify, request, current_app, send_file

from backend.security import is_valid_directory
from backend.utils import row_to_dict

logger = logging.getLogger(__name__)
import_export_bp = Blueprint('import_export', __name__)


@import_export_bp.route('/api/import/preset-info')
def get_preset_info():
    """Get info about a specific import preset (type, suit names, etc.)."""
    preset_name = request.args.get('preset_name', '')

    from import_presets import ImportPresets
    presets = ImportPresets()

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

    from import_presets import ImportPresets
    presets = ImportPresets()

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

    from import_presets import ImportPresets
    presets = ImportPresets()

    try:
        # Get card metadata preview
        cards_meta = presets.preview_import_with_metadata(
            folder,
            preset_name,
            custom_suit_names=custom_suit_names,
            custom_court_names=custom_court_names,
            archetype_mapping=archetype_mapping,
        )

        # Create deck
        deck_id = db.add_deck(
            name=deck_name,
            type_ids=[cartomancy_type_id],
            image_folder=folder,
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


@import_export_bp.route('/api/import/presets')
def get_import_presets():
    """Get available import preset names."""
    from import_presets import ImportPresets
    presets = ImportPresets()
    return jsonify(presets.get_preset_names())


@import_export_bp.route('/api/export/deck/<int:deck_id>')
def export_deck(deck_id):
    """Export a deck as JSON download."""
    db = current_app.config['DB']
    data = db.export_deck_json(deck_id)
    if not data:
        return jsonify({'error': 'Deck not found'}), 404

    # Write to temp file and send
    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False, prefix='deck_export_'
    )
    json.dump(data, tmp, indent=2)
    tmp.close()

    deck_name = data.get('deck', {}).get('name', 'deck')
    safe_name = ''.join(c for c in deck_name if c.isalnum() or c in ' _-').strip()

    return send_file(
        tmp.name,
        as_attachment=True,
        download_name=f'{safe_name}.json',
        mimetype='application/json',
    )


@import_export_bp.route('/api/import/deck-json', methods=['POST'])
def import_deck_json():
    """Import a deck from JSON data."""
    db = current_app.config['DB']
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    try:
        result = db.import_deck_from_json(data)
        return jsonify(result), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
