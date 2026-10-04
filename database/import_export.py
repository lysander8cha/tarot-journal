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

    # === Deck Export/Import with Metadata ===
    def export_deck_json(self, deck_id: int) -> dict:
        """Export a deck with all its cards and metadata to a JSON-serializable dictionary."""
        deck = self.get_deck(deck_id)
        if not deck:
            raise ValueError(f"Deck {deck_id} not found")

        deck_dict = dict(deck)

        # Get suit and court names
        deck_dict['suit_names'] = self.get_deck_suit_names(deck_id)
        deck_dict['court_names'] = self.get_deck_court_names(deck_id)

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

    # === Full Backup/Restore ===
    def _snapshot_db_to(self, dest_path: str) -> None:
        """Write a consistent snapshot of the live database to dest_path.

        Uses sqlite's online backup API, which is the only correct way
        to copy a WAL-mode database that may be in active use: it
        includes un-checkpointed writes from the -wal sidecar and takes
        a coherent point-in-time image even under concurrent writers.
        """
        dest = sqlite3.connect(dest_path)
        try:
            self.conn.backup(dest)
        finally:
            dest.close()

    def auto_backup(self, backup_dir: str, keep: int = 10) -> str:
        """Write a rotating safety snapshot of the database.

        Called on every app launch. Keeps the newest `keep` snapshots
        in backup_dir and deletes older ones, so disk use stays bounded
        while there is always a recent fallback if the live database is
        ever corrupted or edited by mistake.

        Returns the path of the snapshot that was written.
        """
        dir_path = Path(backup_dir)
        dir_path.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = dir_path / f"tarot_journal_auto_{stamp}.db"
        self._snapshot_db_to(str(dest))

        # Prune the oldest snapshots beyond the keep limit. The
        # timestamped names sort chronologically.
        snapshots = sorted(dir_path.glob("tarot_journal_auto_*.db"))
        for old in snapshots[:-keep] if keep > 0 else []:
            try:
                old.unlink()
            except OSError as err:
                logger.warning("Could not prune old auto-backup %s: %s", old, err)

        logger.info("Auto-backup written: %s", dest)
        return str(dest)

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

        # Snapshot the database with sqlite's online backup API rather
        # than copying the .db file directly. In WAL mode, recently
        # committed writes live in the tarot_journal.db-wal sidecar
        # until a checkpoint, so a raw copy of the main file can
        # silently miss the newest journal entries. Connection.backup()
        # folds everything into one consistent snapshot and stays
        # correct even if another thread writes while the backup runs.
        snapshot_fd, snapshot_path = tempfile.mkstemp(suffix=".db")
        os.close(snapshot_fd)

        # Build the archive in one pass. ZIP_DEFLATED is reserved for the DB
        # and small JSON entries that compress well; image entries are stored
        # uncompressed because JPEG/PNG/WebP gain nothing from re-deflation
        # and re-deflating an 80 GB image library was the actual cause of the
        # backup hanging for users with large collections.
        presets_path = script_dir / "import_presets.json"
        presets_included = presets_path.exists()
        images_added = 0

        try:
            self._snapshot_db_to(snapshot_path)

            with zipfile.ZipFile(filepath, 'w', allowZip64=True) as zf:
                zf.writestr(
                    "manifest.json",
                    json.dumps(manifest, indent=2),
                    compress_type=zipfile.ZIP_DEFLATED,
                )
                zf.write(snapshot_path, "tarot_journal.db",
                         compress_type=zipfile.ZIP_DEFLATED)
                if presets_included:
                    zf.write(presets_path, "import_presets.json",
                             compress_type=zipfile.ZIP_DEFLATED)

                if include_images:
                    for img_path in image_paths:
                        img_file = Path(img_path)
                        if not img_file.exists():
                            continue
                        archive_path = f"images/{img_file.parent.name}/{img_file.name}"
                        zf.write(img_file, archive_path,
                                 compress_type=zipfile.ZIP_STORED)
                        images_added += 1
                        if images_added % 500 == 0:
                            logger.info("Backup progress: %d/%d images written",
                                        images_added, len(image_paths))
        finally:
            try:
                os.unlink(snapshot_path)
            except OSError:
                pass

        # Store last backup time in settings. Track with-images backups
        # separately — they're the only backups that protect the deck
        # scans, so the UI reports their staleness on its own.
        self.set_setting("last_backup_time", datetime.now().isoformat())
        if include_images:
            self.set_setting("last_backup_with_images_time", datetime.now().isoformat())

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

        # Snapshot the current DB as a rollback point. Uses the sqlite
        # backup API rather than a raw file copy so the snapshot
        # includes writes still sitting in the WAL sidecar, and mkstemp
        # (not the race-prone, deprecated mktemp) for the temp path.
        safety_fd, safety_backup_path = tempfile.mkstemp(suffix=".db.safety")
        os.close(safety_fd)
        try:
            self._snapshot_db_to(safety_backup_path)

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Extract backup contents
                with zipfile.ZipFile(filepath, 'r') as zf:
                    zf.extractall(temp_path)

                # Swap the database file under the guard: every live
                # connection is closed, stale -wal/-shm sidecars from
                # the old database are removed, and no thread can open
                # a new connection until the copy completes — so
                # nothing ever reads a half-copied file. After the
                # guard, self.conn lazily reopens against the new file
                # (with WAL, FK enforcement, and busy_timeout).
                with self.db_swap_guard():
                    shutil.copy2(temp_path / "tarot_journal.db", self.db_path)

                try:
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

                    # The new .db file is in place; self.conn lazily
                    # reopens on next access thanks to db_swap_guard's
                    # epoch bump.

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
                    # Roll back to the safety snapshot, under the same
                    # guard so the rollback copy is just as protected
                    # as the forward swap.
                    logger.error("Restore failed, rolling back to safety backup: %s", e)
                    if safety_backup_path and Path(safety_backup_path).exists():
                        with self.db_swap_guard():
                            shutil.copy2(safety_backup_path, self.db_path)
                    raise e

        except Exception as e:
            # Clean up safety backup on error
            if safety_backup_path and Path(safety_backup_path).exists():
                try:
                    Path(safety_backup_path).unlink()
                except OSError as err:
                    logger.warning("Failed to clean up safety backup %s: %s", safety_backup_path, err)
            raise e
