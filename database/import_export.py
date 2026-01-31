"""
Database operations for import/export and backup/restore.
"""

import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List

from logger_config import get_logger

logger = get_logger('database')


class ImportExportMixin:
    """Mixin providing import/export and backup/restore operations."""

    # === Entry Export/Import ===
    def export_entries_json(self, entry_ids: List[int] = None) -> dict:
        """
        Export entries to a JSON-serializable dictionary.
        If entry_ids is None, exports all entries.

        Uses batch queries to avoid N+1 query pattern.
        """
        cursor = self.conn.cursor()

        # Fetch all entries
        if entry_ids:
            # Safe IN clause: placeholders are '?' chars, values passed as params
            placeholders = ','.join('?' * len(entry_ids))
            cursor.execute(f'SELECT * FROM journal_entries WHERE id IN ({placeholders})', entry_ids)
        else:
            cursor.execute('SELECT * FROM journal_entries')

        entries = cursor.fetchall()
        if not entries:
            return {
                'version': '1.0',
                'exported_at': datetime.now().isoformat(),
                'entries': []
            }

        # Collect all entry IDs for batch queries
        all_entry_ids = [entry['id'] for entry in entries]
        placeholders = ','.join('?' * len(all_entry_ids))

        # Batch fetch all readings
        cursor.execute(f'''
            SELECT * FROM entry_readings
            WHERE entry_id IN ({placeholders})
            ORDER BY entry_id, position_order
        ''', all_entry_ids)
        readings_by_entry = {}
        for reading in cursor.fetchall():
            entry_id = reading['entry_id']
            if entry_id not in readings_by_entry:
                readings_by_entry[entry_id] = []
            reading_dict = dict(reading)
            if reading_dict.get('cards_used'):
                try:
                    reading_dict['cards_used'] = json.loads(reading_dict['cards_used'])
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning("Failed to parse cards_used for reading in entry %s: %s", entry_id, e)
                    reading_dict['cards_used'] = []
            readings_by_entry[entry_id].append(reading_dict)

        # Batch fetch all tags
        cursor.execute(f'''
            SELECT t.*, et.entry_id FROM tags t
            JOIN entry_tags et ON t.id = et.tag_id
            WHERE et.entry_id IN ({placeholders})
        ''', all_entry_ids)
        tags_by_entry = {}
        for row in cursor.fetchall():
            entry_id = row['entry_id']
            if entry_id not in tags_by_entry:
                tags_by_entry[entry_id] = []
            tag_dict = dict(row)
            del tag_dict['entry_id']  # Remove join column
            tags_by_entry[entry_id].append(tag_dict)

        # Batch fetch all follow-up notes
        cursor.execute(f'''
            SELECT * FROM follow_up_notes
            WHERE entry_id IN ({placeholders})
            ORDER BY entry_id, created_at ASC
        ''', all_entry_ids)
        notes_by_entry = {}
        for note in cursor.fetchall():
            entry_id = note['entry_id']
            if entry_id not in notes_by_entry:
                notes_by_entry[entry_id] = []
            notes_by_entry[entry_id].append(dict(note))

        # Collect unique profile IDs and batch fetch
        profile_ids = set()
        for entry in entries:
            if entry['querent_id']:
                profile_ids.add(entry['querent_id'])
            if entry['reader_id']:
                profile_ids.add(entry['reader_id'])

        profiles_by_id = {}
        if profile_ids:
            profile_placeholders = ','.join('?' * len(profile_ids))
            cursor.execute(f'SELECT * FROM profiles WHERE id IN ({profile_placeholders})',
                          list(profile_ids))
            for profile in cursor.fetchall():
                profiles_by_id[profile['id']] = dict(profile)

        # Assemble the results
        entries_data = []
        for entry in entries:
            entry_dict = dict(entry)
            entry_id = entry_dict['id']

            # Attach readings
            entry_dict['readings'] = readings_by_entry.get(entry_id, [])

            # Attach tags
            entry_dict['tags'] = tags_by_entry.get(entry_id, [])

            # Attach profile names
            querent_id = entry_dict.get('querent_id')
            if querent_id and querent_id in profiles_by_id:
                entry_dict['querent_name'] = profiles_by_id[querent_id]['name']
            else:
                entry_dict['querent_name'] = None

            reader_id = entry_dict.get('reader_id')
            if reader_id and reader_id in profiles_by_id:
                entry_dict['reader_name'] = profiles_by_id[reader_id]['name']
            else:
                entry_dict['reader_name'] = None

            # Attach follow-up notes
            entry_dict['follow_up_notes'] = notes_by_entry.get(entry_id, [])

            entries_data.append(entry_dict)

        return {
            'version': '1.0',
            'exported_at': datetime.now().isoformat(),
            'entries': entries_data
        }

    def export_entries_to_file(self, filepath: str, entry_ids: List[int] = None):
        """Export entries to a JSON file."""
        data = self.export_entries_json(entry_ids)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Exported %d entries to %s", len(data.get('entries', [])), filepath)

    def export_entries_to_zip(self, filepath: str, entry_ids: List[int] = None):
        """
        Export entries to a ZIP file containing JSON data and card images.
        """
        data = self.export_entries_json(entry_ids)

        # Collect all unique image paths from readings
        image_paths = set()
        for entry in data['entries']:
            for reading in entry.get('readings', []):
                deck_id = reading.get('deck_id')
                if deck_id:
                    cards = self.get_cards(deck_id)
                    for card in cards:
                        if card['image_path'] and os.path.exists(card['image_path']):
                            image_paths.add(card['image_path'])

        # Create ZIP file
        with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add JSON data
            zf.writestr('entries.json', json.dumps(data, indent=2, ensure_ascii=False))

            # Add images
            for img_path in image_paths:
                if os.path.exists(img_path):
                    # Store with relative path
                    archive_path = f"images/{os.path.basename(img_path)}"
                    zf.write(img_path, archive_path)

        logger.info("Exported %d entries with %d images to %s",
                    len(data.get('entries', [])), len(image_paths), filepath)

    def import_entries_from_json(self, data: dict, merge_tags: bool = True) -> dict:
        """
        Import entries from a JSON dictionary.
        Returns a summary of what was imported.
        """
        if not isinstance(data, dict) or 'entries' not in data:
            raise ValueError("Invalid entry import data format")

        entries_imported = 0
        readings_imported = 0
        tags_created = 0
        follow_ups_imported = 0

        # Build profile name -> id mapping for querent/reader lookup
        profiles = self.get_profiles()
        profile_map = {p['name']: p['id'] for p in profiles}

        with self.transaction():
            # Process each entry
            for entry_data in data['entries']:
                # Look up querent/reader by name
                querent_id = None
                reader_id = None
                if entry_data.get('querent_name') and entry_data['querent_name'] in profile_map:
                    querent_id = profile_map[entry_data['querent_name']]
                if entry_data.get('reader_name') and entry_data['reader_name'] in profile_map:
                    reader_id = profile_map[entry_data['reader_name']]

                # Create entry
                entry_id = self.add_entry(
                    title=entry_data.get('title'),
                    content=entry_data.get('content'),
                    reading_datetime=entry_data.get('reading_datetime'),
                    location_name=entry_data.get('location_name'),
                    location_lat=entry_data.get('location_lat'),
                    location_lon=entry_data.get('location_lon'),
                    querent_id=querent_id,
                    reader_id=reader_id
                )
                entries_imported += 1

                # Import readings
                for reading in entry_data.get('readings', []):
                    self.add_entry_reading(
                        entry_id=entry_id,
                        spread_id=reading.get('spread_id'),
                        spread_name=reading.get('spread_name'),
                        deck_id=reading.get('deck_id'),
                        deck_name=reading.get('deck_name'),
                        cartomancy_type=reading.get('cartomancy_type'),
                        cards_used=reading.get('cards_used'),
                        position_order=reading.get('position_order', 0)
                    )
                    readings_imported += 1

                # Import tags
                if merge_tags:
                    for tag_data in entry_data.get('tags', []):
                        # Find or create tag
                        existing_tags = self.get_tags()
                        tag_id = None
                        for t in existing_tags:
                            if t['name'] == tag_data['name']:
                                tag_id = t['id']
                                break
                        if not tag_id:
                            tag_id = self.add_tag(tag_data['name'], tag_data.get('color', '#6B5B95'))
                            tags_created += 1
                        self.add_entry_tag(entry_id, tag_id)

                # Import follow-up notes
                for note in entry_data.get('follow_up_notes', []):
                    self.add_follow_up_note(entry_id, note.get('content', ''))
                    follow_ups_imported += 1

        return {
            'entries_imported': entries_imported,
            'readings_imported': readings_imported,
            'tags_created': tags_created,
            'follow_ups_imported': follow_ups_imported
        }

    def import_entries_from_file(self, filepath: str, merge_tags: bool = True) -> dict:
        """Import entries from a JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return self.import_entries_from_json(data, merge_tags)

    def import_entries_from_zip(self, filepath: str, merge_tags: bool = True) -> dict:
        """Import entries from a ZIP file."""
        with zipfile.ZipFile(filepath, 'r') as zf:
            # Read JSON data
            with zf.open('entries.json') as f:
                data = json.load(f)
            return self.import_entries_from_json(data, merge_tags)

    # === Deck Export/Import with Metadata ===
    def export_deck_json(self, deck_id: int) -> dict:
        """Export a deck with all its cards and metadata to a JSON-serializable dictionary."""
        deck = self.get_deck(deck_id)
        if not deck:
            raise ValueError(f"Deck {deck_id} not found")

        deck_dict = dict(deck)

        # Get suit names
        deck_dict['suit_names'] = self.get_deck_suit_names(deck_id)

        # Get custom field definitions
        custom_fields = self.get_deck_custom_fields(deck_id)
        deck_dict['custom_field_definitions'] = []
        for cf in custom_fields:
            cf_dict = {
                'field_name': cf['field_name'],
                'field_type': cf['field_type'],
                'field_order': cf['field_order']
            }
            if cf['field_options']:
                try:
                    cf_dict['field_options'] = json.loads(cf['field_options'])
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning("Failed to parse field_options for custom field: %s", e)
                    cf_dict['field_options'] = None
            deck_dict['custom_field_definitions'].append(cf_dict)

        # Get all cards with metadata
        cards = self.get_cards(deck_id)
        deck_dict['cards'] = []
        for card in cards:
            card_dict = {
                'name': card['name'],
                'image_path': card['image_path'],
                'card_order': card['card_order'],
                'archetype': card['archetype'] if 'archetype' in card.keys() else None,
                'rank': card['rank'] if 'rank' in card.keys() else None,
                'suit': card['suit'] if 'suit' in card.keys() else None,
                'notes': card['notes'] if 'notes' in card.keys() else None,
            }
            # Parse custom fields
            custom_fields_json = card['custom_fields'] if 'custom_fields' in card.keys() else None
            if custom_fields_json:
                try:
                    card_dict['custom_fields'] = json.loads(custom_fields_json)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning("Failed to parse custom_fields for card '%s': %s", card_dict.get('name', '?'), e)
                    card_dict['custom_fields'] = None
            else:
                card_dict['custom_fields'] = None

            deck_dict['cards'].append(card_dict)

        return {
            'version': '1.0',
            'exported_at': datetime.now().isoformat(),
            'deck': deck_dict
        }

    def export_deck_to_file(self, deck_id: int, filepath: str):
        """Export a deck to a JSON file."""
        data = self.export_deck_json(deck_id)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Exported deck '%s' (%d cards) to %s",
                     data.get('deck', {}).get('name', '?'), len(data.get('cards', [])), filepath)

    def import_deck_from_json(self, data: dict) -> dict:
        """
        Import a deck from a JSON dictionary.
        Returns a summary of what was imported.
        """
        logger.info("Importing deck from JSON: '%s'", data.get('deck', {}).get('name', '?'))
        if not isinstance(data, dict) or 'deck' not in data:
            raise ValueError("Invalid deck import data format")

        deck_data = data['deck']

        with self.transaction():
            # Find or create the cartomancy type
            cart_type_name = deck_data.get('cartomancy_type_name', 'Tarot')
            cart_types = self.get_cartomancy_types()
            cart_type_id = None
            for ct in cart_types:
                if ct['name'] == cart_type_name:
                    cart_type_id = ct['id']
                    break
            if not cart_type_id:
                cart_type_id = 1  # Default to Tarot

            # Create the deck
            deck_id = self.add_deck(
                name=deck_data.get('name', 'Imported Deck'),
                cartomancy_type_id=cart_type_id,
                image_folder=deck_data.get('image_folder'),
                suit_names=deck_data.get('suit_names')
            )

            # Import custom field definitions
            custom_field_map = {}  # Maps field_name to field_id for reference
            for cf_def in deck_data.get('custom_field_definitions', []):
                field_id = self.add_deck_custom_field(
                    deck_id=deck_id,
                    field_name=cf_def['field_name'],
                    field_type=cf_def['field_type'],
                    field_options=cf_def.get('field_options'),
                    field_order=cf_def.get('field_order', 0)
                )
                custom_field_map[cf_def['field_name']] = field_id

            # Import cards
            cards_imported = 0
            for card_data in deck_data.get('cards', []):
                # Add the card
                card_id = self.add_card(
                    deck_id=deck_id,
                    name=card_data['name'],
                    image_path=card_data.get('image_path'),
                    card_order=card_data.get('card_order', 0)
                )

                # Update metadata
                self.update_card_metadata(
                    card_id=card_id,
                    archetype=card_data.get('archetype'),
                    rank=card_data.get('rank'),
                    suit=card_data.get('suit'),
                    notes=card_data.get('notes'),
                    custom_fields=card_data.get('custom_fields')
                )

                cards_imported += 1

        return {
            'deck_id': deck_id,
            'deck_name': deck_data.get('name'),
            'cards_imported': cards_imported,
            'custom_fields_created': len(custom_field_map)
        }

    def import_deck_from_file(self, filepath: str) -> dict:
        """Import a deck from a JSON file."""
        logger.info("Importing deck from file: %s", filepath)
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return self.import_deck_from_json(data)

    # === Full Backup/Restore ===
    def create_full_backup(self, filepath: str, include_images: bool = False) -> dict:
        """
        Create a complete backup of the database and config files.

        Args:
            filepath: Path for the output ZIP file
            include_images: Whether to include card images in the backup

        Returns:
            dict with backup statistics
        """
        logger.info("Creating full backup: %s (include_images=%s)", filepath, include_images)
        script_dir = Path(__file__).parent.parent.resolve()

        # Get counts for manifest
        entry_count = len(self.get_entries(limit=999999))
        deck_count = len(self.get_decks())

        # Collect image paths if needed
        image_paths = []
        if include_images:
            cursor = self.conn.cursor()
            cursor.execute("SELECT DISTINCT image_path FROM cards WHERE image_path IS NOT NULL AND image_path != ''")
            image_paths = [row[0] for row in cursor.fetchall()]

        # Create manifest
        manifest = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "includes_images": include_images,
            "entry_count": entry_count,
            "deck_count": deck_count,
            "image_count": len(image_paths) if include_images else 0
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Copy database (always flush, even inside a transaction)
            self.conn.commit()
            db_backup_path = temp_path / "tarot_journal.db"
            shutil.copy2(self.db_path, db_backup_path)

            # Copy import_presets.json if it exists
            presets_path = script_dir / "import_presets.json"
            presets_included = False
            if presets_path.exists():
                shutil.copy2(presets_path, temp_path / "import_presets.json")
                presets_included = True

            # Write manifest
            with open(temp_path / "manifest.json", 'w') as f:
                json.dump(manifest, f, indent=2)

            # Create ZIP file
            with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(temp_path / "manifest.json", "manifest.json")
                zf.write(db_backup_path, "tarot_journal.db")

                if presets_included:
                    zf.write(temp_path / "import_presets.json", "import_presets.json")

                # Add images if requested
                images_added = 0
                if include_images:
                    for img_path in image_paths:
                        img_file = Path(img_path)
                        if img_file.exists():
                            # Store with relative path under images/
                            archive_path = f"images/{img_file.parent.name}/{img_file.name}"
                            zf.write(img_file, archive_path)
                            images_added += 1

        # Store last backup time in settings
        self.set_setting("last_backup_time", datetime.now().isoformat())

        logger.info("Backup complete: %d entries, %d decks, %d images",
                     entry_count, deck_count, images_added if include_images else 0)
        return {
            "filepath": filepath,
            "entry_count": entry_count,
            "deck_count": deck_count,
            "images_included": images_added if include_images else 0,
            "presets_included": presets_included
        }

    def restore_from_backup(self, filepath: str) -> dict:
        """
        Restore database and config files from a backup ZIP.

        Args:
            filepath: Path to the backup ZIP file

        Returns:
            dict with restore statistics
        """
        logger.info("Restoring from backup: %s", filepath)
        script_dir = Path(__file__).parent.parent.resolve()

        # Validate ZIP file
        if not zipfile.is_zipfile(filepath):
            raise ValueError("Invalid backup file: not a valid ZIP archive")

        with zipfile.ZipFile(filepath, 'r') as zf:
            # Check for manifest
            if "manifest.json" not in zf.namelist():
                raise ValueError("Invalid backup file: missing manifest.json")

            # Check for database
            if "tarot_journal.db" not in zf.namelist():
                raise ValueError("Invalid backup file: missing database")

            # Read manifest
            with zf.open("manifest.json") as f:
                manifest = json.load(f)

        # Create safety backup before restore
        safety_backup_path = None
        try:
            safety_backup_path = tempfile.mktemp(suffix=".db.safety")
            shutil.copy2(self.db_path, safety_backup_path)

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Extract backup contents
                with zipfile.ZipFile(filepath, 'r') as zf:
                    zf.extractall(temp_path)

                # Close current database connection
                self.conn.close()

                try:
                    # Replace database
                    shutil.copy2(temp_path / "tarot_journal.db", self.db_path)

                    # Restore import_presets.json if it was in the backup
                    presets_restored = False
                    if (temp_path / "import_presets.json").exists():
                        shutil.copy2(temp_path / "import_presets.json", script_dir / "import_presets.json")
                        presets_restored = True

                    # Restore images if they were included
                    images_restored = 0
                    images_dir = temp_path / "images"
                    if images_dir.exists():
                        # Get image path mapping from database
                        temp_conn = sqlite3.connect(self.db_path)
                        cursor = temp_conn.cursor()
                        cursor.execute("SELECT DISTINCT image_path FROM cards WHERE image_path IS NOT NULL AND image_path != ''")
                        db_image_paths = {Path(row[0]).name: row[0] for row in cursor.fetchall()}
                        temp_conn.close()

                        # Copy images to their original locations
                        for deck_dir in images_dir.iterdir():
                            if deck_dir.is_dir():
                                for img_file in deck_dir.iterdir():
                                    if img_file.name in db_image_paths:
                                        dest_path = Path(db_image_paths[img_file.name])
                                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                                        if not dest_path.exists():
                                            shutil.copy2(img_file, dest_path)
                                            images_restored += 1

                    # Reconnect to database
                    self.conn = sqlite3.connect(self.db_path)
                    self.conn.row_factory = sqlite3.Row

                    # Delete safety backup on success
                    if safety_backup_path and Path(safety_backup_path).exists():
                        Path(safety_backup_path).unlink()

                    logger.info("Restore complete: %d entries, %d decks, %d images restored",
                                manifest.get("entry_count", 0), manifest.get("deck_count", 0), images_restored)
                    return {
                        "entry_count": manifest.get("entry_count", 0),
                        "deck_count": manifest.get("deck_count", 0),
                        "images_restored": images_restored,
                        "presets_restored": presets_restored,
                        "backup_date": manifest.get("created_at", "Unknown")
                    }

                except Exception as e:
                    # Restore safety backup if something went wrong
                    logger.error("Restore failed, rolling back to safety backup: %s", e)
                    if safety_backup_path and Path(safety_backup_path).exists():
                        shutil.copy2(safety_backup_path, self.db_path)
                    # Reconnect to database
                    self.conn = sqlite3.connect(self.db_path)
                    self.conn.row_factory = sqlite3.Row
                    raise e

        except Exception as e:
            # Clean up safety backup on error
            if safety_backup_path and Path(safety_backup_path).exists():
                try:
                    Path(safety_backup_path).unlink()
                except OSError as err:
                    logger.warning("Failed to clean up safety backup %s: %s", safety_backup_path, err)
            raise e
