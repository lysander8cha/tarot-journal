"""
Anki export endpoint -- generates a zip file with tab-separated card data
and images that can be imported directly into Anki.
"""

import io
import json
import os
import zipfile

from flask import Blueprint, current_app, send_file, jsonify
from backend.utils import require_json

anki_export_bp = Blueprint('anki_export', __name__)

# Custom-field keys that render under Classification in the card
# modal for I Ching decks — given friendly export labels there too.
ICHING_CLASSIFICATION_CUSTOM = {
    'traditional_chinese': 'Traditional Chinese',
    'simplified_chinese': 'Simplified Chinese',
}


def _deck_is_iching(deck) -> bool:
    return any(t['name'] == 'I Ching'
               for t in (deck.get('cartomancy_types') or []))


# Display labels for correspondence fields (matches frontend labels)
FIELD_LABELS = {
    'element': 'Element',
    'planet': 'Planet',
    'zodiac_sign': 'Zodiac Sign',
    'decan': 'Decan',
    'hebrew_letter': 'Kabbalah',
    'numerology': 'Numerology',
    'rune': 'Rune',
    'i_ching_hexagram': 'I Ching Hexagram',
    'chakra': 'Chakra',
    'modality': 'Modality',
}


@anki_export_bp.route('/api/decks/<int:deck_id>/anki-export', methods=['POST'])
@require_json
def anki_export(deck_id, data):
    """Export a deck as an Anki-importable zip.

    Request body:
        fields: list of field keys in export order
            Available keys: 'image', 'name', 'element', 'planet', 'zodiac_sign',
            'decan', 'hebrew_letter', 'numerology', 'rune', 'i_ching_hexagram',
            'chakra', 'notes', plus any custom field names.

    Response: zip file containing:
        - cards.txt: tab-separated file with Anki directives
        - card images (flat, referenced by filename in the txt)
    """
    db = current_app.config['DB']

    deck = db.get_deck(deck_id)
    if not deck:
        return jsonify({'error': 'Deck not found'}), 404

    fields = data.get('fields', [])
    if not fields:
        return jsonify({'error': 'No fields selected'}), 400

    # Get all cards in the deck (convert Rows to dicts for easier handling)
    cards_raw = db.get_cards(deck_id)
    if not cards_raw:
        return jsonify({'error': 'Deck has no cards'}), 400
    cards = [dict(c) for c in cards_raw]

    # Get correspondences for all cards
    card_correspondences = {}
    for card in cards:
        card_correspondences[card['id']] = {
            c['field_name']: c['value']
            for c in db.get_card_correspondences(card['id'])
            if c['value']
        }

    # Get custom fields for all cards. Two sources, both still in active use:
    #   1) Legacy cards.custom_fields JSON column (older decks like Supra Oracle
    #      have data here).
    #   2) card_custom_fields table (newer storage).
    # Merge per card with the table taking precedence on key collisions.
    card_custom_fields = {}
    for card in cards:
        legacy = {}
        raw = card.get('custom_fields')
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    legacy = {k: ('' if v is None else str(v)) for k, v in parsed.items()}
            except (ValueError, TypeError):
                pass

        cursor = db.conn.cursor()
        cursor.execute(
            'SELECT field_name, field_value FROM card_custom_fields WHERE card_id = ?',
            (card['id'],)
        )
        table_fields = {
            r['field_name']: (r['field_value'] or '')
            for r in cursor.fetchall()
        }

        card_custom_fields[card['id']] = {**legacy, **table_fields}

    # Archetype-note fields ('archnote:<field_id>' keys): pull authored
    # content per (archetype, field) and map each card to its archetype
    # within the deck's cartomancy type(s).
    archnote_ids = []
    for f in fields:
        if f.startswith('archnote:'):
            try:
                archnote_ids.append(int(f.split(':', 1)[1]))
            except ValueError:
                pass

    archnote_content = {}   # (archetype_id, field_id) -> content
    archnote_labels = {}    # field_id -> "Source: Field"
    card_archetype_id = {}  # card_id -> archetype_id
    if archnote_ids:
        placeholders = ','.join('?' * len(archnote_ids))
        cursor = db.conn.cursor()
        cursor.execute(f'''
            SELECT f.id, f.name, s.name AS source_name
            FROM source_fields f
            JOIN reference_sources s ON s.id = f.source_id
            WHERE f.id IN ({placeholders})
        ''', archnote_ids)
        for r in cursor.fetchall():
            archnote_labels[r['id']] = f"{r['source_name']}: {r['name']}"

        cursor.execute(f'''
            SELECT archetype_id, field_id, content
            FROM archetype_source_entries
            WHERE field_id IN ({placeholders})
        ''', archnote_ids)
        for r in cursor.fetchall():
            archnote_content[(r['archetype_id'], r['field_id'])] = r['content'] or ''

        name_to_archetype = {}
        for t in (deck.get('cartomancy_types') or []):
            for a in db.get_archetypes(t['name']):
                name_to_archetype.setdefault(a['name'], a['id'])
        for card in cards:
            arch_name = card.get('archetype')
            if arch_name and arch_name in name_to_archetype:
                card_archetype_id[card['id']] = name_to_archetype[arch_name]

    def parse_archnote_key(key):
        try:
            return int(key.split(':', 1)[1])
        except (ValueError, IndexError):
            return None

    # Correspondence field names (for detecting which fields are correspondences)
    from database.correspondences import CORRESPONDENCE_FIELDS

    def sanitize(value):
        """Make a value safe to drop into a tab-separated, newline-delimited
        row. Newlines become <br> (Anki renders them via #html:true), tabs
        become spaces so columns don't shift. Multi-paragraph card
        descriptions are the main reason this exists."""
        if value is None:
            return ''
        s = str(value)
        s = s.replace('\r\n', '\n').replace('\r', '\n')
        s = s.replace('\n', '<br>')
        s = s.replace('\t', ' ')
        return s

    # Build the zip in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Build tab-separated text file
        lines = []
        lines.append('#separator:tab')
        lines.append('#html:true')

        # Classification labels follow the card modal's I Ching aliases
        is_iching = _deck_is_iching(deck)

        # Header comment with field names
        header_labels = []
        for f in fields:
            if f == 'image':
                header_labels.append('Card Image')
            elif f == 'name':
                header_labels.append('Card Name')
            elif f == 'sort_number':
                header_labels.append('Sort Number')
            elif f == 'archetype':
                header_labels.append('Archetype')
            elif f == 'rank':
                header_labels.append('Hexagram Number' if is_iching else 'Rank')
            elif f == 'suit':
                header_labels.append('Pinyin' if is_iching else 'Suit')
            elif f in ICHING_CLASSIFICATION_CUSTOM:
                header_labels.append(ICHING_CLASSIFICATION_CUSTOM[f])
            elif f == 'notes':
                header_labels.append('Notes')
            elif f.startswith('archnote:'):
                fid = parse_archnote_key(f)
                header_labels.append(archnote_labels.get(fid, f))
            elif f in CORRESPONDENCE_FIELDS:
                header_labels.append(FIELD_LABELS.get(f, f.replace('_', ' ').title()))
            else:
                header_labels.append(f)
        lines.append('#' + '\t'.join(header_labels))

        image_files = {}  # filename -> absolute path on disk

        for card in cards:
            corr = card_correspondences.get(card['id'], {})
            custom = card_custom_fields.get(card['id'], {})
            row = []

            for f in fields:
                if f == 'image':
                    if card.get('image_path') and os.path.isfile(card['image_path']):
                        # Use a safe filename
                        ext = os.path.splitext(card['image_path'])[1] or '.jpg'
                        safe_name = f"card_{card['id']}{ext}"
                        image_files[safe_name] = card['image_path']
                        row.append(f'<img src="{safe_name}">')
                    else:
                        row.append('')
                elif f == 'name':
                    row.append(sanitize(card.get('name')))
                elif f == 'sort_number':
                    row.append(sanitize(card.get('card_order')))
                elif f == 'archetype':
                    row.append(sanitize(card.get('archetype')))
                elif f == 'rank':
                    row.append(sanitize(card.get('rank')))
                elif f == 'suit':
                    row.append(sanitize(card.get('suit')))
                elif f == 'notes':
                    row.append(sanitize(card.get('notes')))
                elif f.startswith('archnote:'):
                    fid = parse_archnote_key(f)
                    aid = card_archetype_id.get(card['id'])
                    value = archnote_content.get((aid, fid), '') if fid and aid else ''
                    row.append(sanitize(value))
                elif f in CORRESPONDENCE_FIELDS:
                    row.append(sanitize(corr.get(f)))
                else:
                    # Custom field
                    row.append(sanitize(custom.get(f)))

            lines.append('\t'.join(row))

        # Write the text file
        zf.writestr('cards.txt', '\n'.join(lines))

        # Write image files
        for filename, filepath in image_files.items():
            zf.write(filepath, filename)

    buf.seek(0)

    safe_deck_name = ''.join(c for c in deck['name'] if c.isalnum() or c in ' -_').strip()
    download_name = f"{safe_deck_name}_anki.zip"

    return send_file(
        buf,
        mimetype='application/zip',
        as_attachment=True,
        download_name=download_name,
    )


@anki_export_bp.route('/api/decks/<int:deck_id>/anki-fields')
def anki_fields(deck_id):
    """Get available fields for Anki export for a given deck.

    Returns fields in recommended order with metadata about which are populated.
    """
    db = current_app.config['DB']

    deck = db.get_deck(deck_id)
    if not deck:
        return jsonify({'error': 'Deck not found'}), 404

    from database.correspondences import CORRESPONDENCE_FIELDS

    # Always-available fields
    fields = [
        {'key': 'image', 'label': 'Card Image', 'always': True},
        {'key': 'name', 'label': 'Card Name', 'always': True},
        {'key': 'sort_number', 'label': 'Sort Number', 'always': True},
    ]

    cards = db.get_cards(deck_id)

    # Classification fields from the card modal: archetype, rank, suit
    # (I Ching decks alias the latter two, matching the modal), plus
    # the Chinese name fields I Ching stores as custom fields.
    is_iching = _deck_is_iching(deck)
    for key, label in (
        ('archetype', 'Archetype'),
        ('rank', 'Hexagram Number' if is_iching else 'Rank'),
        ('suit', 'Pinyin' if is_iching else 'Suit'),
    ):
        fields.append({
            'key': key,
            'label': label,
            'always': False,
            'populated': any(c[key] for c in cards),
        })
    if is_iching:
        for key, label in ICHING_CLASSIFICATION_CUSTOM.items():
            fields.append({'key': key, 'label': label, 'always': False})

    # Check which correspondence fields have any values in this deck
    corr_populated = set()
    for card in cards[:10]:  # Sample first 10 cards for speed
        for c in db.get_card_correspondences(card['id']):
            if c['value']:
                corr_populated.add(c['field_name'])

    for f in CORRESPONDENCE_FIELDS:
        label = FIELD_LABELS.get(f, f.replace('_', ' ').title())
        fields.append({
            'key': f,
            'label': label,
            'always': False,
            'populated': f in corr_populated,
        })

    # Notes
    fields.append({'key': 'notes', 'label': 'Notes', 'always': False})

    # Custom fields defined for this deck
    cursor = db.conn.cursor()
    cursor.execute(
        'SELECT field_name FROM deck_custom_fields WHERE deck_id = ? ORDER BY field_order',
        (deck_id,)
    )
    for row in cursor.fetchall():
        fields.append({
            'key': row['field_name'],
            'label': row['field_name'],
            'always': False,
        })

    # Archetype Notes fields (Reference sources): every source field of
    # the deck's cartomancy type(s) that has authored content for at
    # least one archetype, individually selectable as "Source: Field".
    # Not flagged 'populated' so they stay opt-in rather than
    # auto-selected.
    type_names = [t['name'] for t in (deck.get('cartomancy_types') or [])]
    if type_names:
        placeholders = ','.join('?' * len(type_names))
        cursor.execute(f'''
            SELECT DISTINCT f.id, f.name, f.sort_order, s.name AS source_name
            FROM source_fields f
            JOIN reference_sources s ON s.id = f.source_id
            WHERE f.cartomancy_type IN ({placeholders})
              AND EXISTS (
                SELECT 1 FROM archetype_source_entries e
                WHERE e.field_id = f.id
                  AND e.content IS NOT NULL AND TRIM(e.content) != ''
              )
            ORDER BY s.name, f.sort_order, f.id
        ''', type_names)
        for row in cursor.fetchall():
            fields.append({
                'key': f'archnote:{row["id"]}',
                'label': f'{row["source_name"]}: {row["name"]}',
                'always': False,
            })

    return jsonify(fields)
