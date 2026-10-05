"""
Database operations for journal entries, spreads, readings, and follow-up notes.
"""

import json
from datetime import datetime


class EntriesMixin:
    """Mixin providing journal entry, spread, and reading operations."""

    # === Spreads ===
    def get_spreads(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT s.*, rs.name AS source_name FROM spreads s
            LEFT JOIN reference_sources rs ON rs.id = s.source_id
            ORDER BY s.name
        ''')
        return cursor.fetchall()

    def get_spread(self, spread_id: int):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT s.*, rs.name AS source_name FROM spreads s
            LEFT JOIN reference_sources rs ON rs.id = s.source_id
            WHERE s.id = ?
        ''', (spread_id,))
        return cursor.fetchone()

    def add_spread(self, name: str, positions: list, description: str = None,
                   cartomancy_type: str = None, allowed_deck_types: list = None,
                   default_deck_id: int = None, deck_slots: list = None,
                   source_id: int = None):
        """
        positions is a list of dicts: [{"x": 0, "y": 0, "label": "Past"}, ...]
        cartomancy_type: 'Tarot', 'Lenormand', 'Oracle', etc. (deprecated, for backwards compat)
        allowed_deck_types: list of cartomancy type names allowed for this spread, e.g. ['Tarot', 'Oracle']
        default_deck_id: ID of the default deck for this spread (overrides global default)
        deck_slots: list of deck slots for multi-deck spreads, e.g. [{"key": "A", "cartomancy_type": "Tarot"}]
        source_id: reference source the spread is attributed to
        """
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT INTO spreads (name, description, positions, cartomancy_type, allowed_deck_types, default_deck_id, deck_slots, source_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (name, description, json.dumps(positions), cartomancy_type,
             json.dumps(allowed_deck_types) if allowed_deck_types else None,
             default_deck_id,
             json.dumps(deck_slots) if deck_slots else None,
             source_id)
        )
        self._commit()
        return cursor.lastrowid

    def update_spread(self, spread_id: int, name: str = None, positions: list = None,
                      description: str = None, allowed_deck_types: list = None,
                      default_deck_id: int = None, clear_default_deck: bool = False,
                      deck_slots: list = None, archived: bool = None,
                      favorite: bool = None, source_id: int = None, clear_source: bool = False):
        cursor = self.conn.cursor()
        if source_id is not None or clear_source:
            cursor.execute('UPDATE spreads SET source_id = ? WHERE id = ?',
                           (source_id, spread_id))
        if name:
            cursor.execute('UPDATE spreads SET name = ? WHERE id = ?', (name, spread_id))
        if positions:
            cursor.execute('UPDATE spreads SET positions = ? WHERE id = ?', (json.dumps(positions), spread_id))
        if description is not None:
            cursor.execute('UPDATE spreads SET description = ? WHERE id = ?', (description, spread_id))
        if allowed_deck_types is not None:
            cursor.execute('UPDATE spreads SET allowed_deck_types = ? WHERE id = ?',
                          (json.dumps(allowed_deck_types) if allowed_deck_types else None, spread_id))
        if default_deck_id is not None or clear_default_deck:
            cursor.execute('UPDATE spreads SET default_deck_id = ? WHERE id = ?',
                          (default_deck_id, spread_id))
        if deck_slots is not None:
            cursor.execute('UPDATE spreads SET deck_slots = ? WHERE id = ?',
                          (json.dumps(deck_slots) if deck_slots else None, spread_id))
        if archived is not None:
            cursor.execute('UPDATE spreads SET archived = ? WHERE id = ?',
                          (1 if archived else 0, spread_id))
        if favorite is not None:
            cursor.execute('UPDATE spreads SET favorite = ? WHERE id = ?',
                          (1 if favorite else 0, spread_id))
        self._commit()

    def delete_spread(self, spread_id: int):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM spreads WHERE id = ?', (spread_id,))
        self._commit()

    # === Journal Entries ===
    # Whitelisted sort expressions for entry listings. 'reading' sorts
    # by when the reading happened (falling back to created_at for
    # entries without a reading datetime); 'created' by row creation.
    _ENTRY_SORTS = {
        'reading': 'COALESCE(reading_datetime, created_at) DESC',
        'created': 'created_at DESC',
    }

    def get_entries(self, limit: int = 50, offset: int = 0,
                    sort_by: str = 'reading'):
        order = self._ENTRY_SORTS.get(sort_by, self._ENTRY_SORTS['reading'])
        cursor = self.conn.cursor()
        # Safe dynamic SQL: `order` comes from the whitelist above.
        cursor.execute(f'''
            SELECT * FROM journal_entries
            ORDER BY {order}
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        return cursor.fetchall()

    def get_entry(self, entry_id: int):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM journal_entries WHERE id = ?', (entry_id,))
        return cursor.fetchone()

    def get_recent_locations(self, limit: int = 8):
        """Distinct locations from past entries, most recently used
        first, each with the coordinates of its latest use — so
        re-picking a known place needs no fresh geocode lookup."""
        cursor = self.conn.cursor()
        # SQLite's bare-column rule: with MAX() in the select, the
        # other columns come from the row that holds the maximum.
        cursor.execute('''
            SELECT location_name, location_lat, location_lon,
                   MAX(COALESCE(reading_datetime, created_at)) AS last_used
            FROM journal_entries
            WHERE location_name IS NOT NULL AND TRIM(location_name) != ''
            GROUP BY location_name
            ORDER BY last_used DESC
            LIMIT ?
        ''', (limit,))
        return cursor.fetchall()

    def search_entries(self, query: str = None, tag_ids: list = None,
                      deck_id: int = None, spread_id: int = None,
                      cartomancy_type: str = None, card_name: str = None,
                      date_from: str = None, date_to: str = None,
                      querent_id: int = None, sort_by: str = 'reading'):
        """Search entries with various filters"""
        cursor = self.conn.cursor()

        sql = 'SELECT DISTINCT je.* FROM journal_entries je'
        joins = []
        conditions = []
        params = []

        if tag_ids:
            joins.append('JOIN entry_tags et ON je.id = et.entry_id')
            # Safe IN clause: placeholders are '?' chars, values passed as params
            placeholders = ','.join('?' * len(tag_ids))
            conditions.append(f'et.tag_id IN ({placeholders})')
            params.extend(tag_ids)

        if querent_id:
            joins.append('JOIN entry_querents eq ON je.id = eq.entry_id')
            conditions.append('eq.profile_id = ?')
            params.append(querent_id)

        if deck_id or spread_id or cartomancy_type or card_name:
            joins.append('JOIN entry_readings er ON je.id = er.entry_id')
            if deck_id:
                conditions.append('er.deck_id = ?')
                params.append(deck_id)
            if spread_id:
                conditions.append('er.spread_id = ?')
                params.append(spread_id)
            if cartomancy_type:
                conditions.append('er.cartomancy_type = ?')
                params.append(cartomancy_type)
            if card_name:
                conditions.append('er.cards_used LIKE ?')
                params.append(f'%{card_name}%')
            if querent_id:
                # The matching reading must be this querent's (or unmarked).
                conditions.append('(er.querent_id IS NULL OR er.querent_id = ?)')
                params.append(querent_id)

        if query:
            conditions.append('(je.title LIKE ? OR je.content LIKE ?)')
            params.extend([f'%{query}%', f'%{query}%'])

        # Date filters apply to when the READING happened (falling back
        # to created_at for entries without a reading datetime) — that's
        # the date a user remembers, not when the row was inserted.
        if date_from:
            conditions.append("COALESCE(je.reading_datetime, je.created_at) >= ?")
            params.append(date_from)

        if date_to:
            # Strictly-before-the-next-day makes a bare YYYY-MM-DD end
            # date inclusive: the old `<= date_to` compare excluded
            # everything on the end date itself, because a timestamped
            # value like '2026-07-02T10:00' sorts after '2026-07-02'.
            conditions.append("COALESCE(je.reading_datetime, je.created_at) < date(?, '+1 day')")
            params.append(date_to)

        sql += ' ' + ' '.join(joins)
        if conditions:
            sql += ' WHERE ' + ' AND '.join(conditions)
        if sort_by == 'created':
            sql += ' ORDER BY je.created_at DESC'
        else:
            sql += ' ORDER BY COALESCE(je.reading_datetime, je.created_at) DESC'

        cursor.execute(sql, params)
        return cursor.fetchall()

    def add_entry(self, title: str = None, content: str = None,
                  reading_datetime: str = None, location_name: str = None,
                  location_lat: float = None, location_lon: float = None,
                  querent_id: int = None, reader_id: int = None):
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        # Use provided reading_datetime or default to now
        if reading_datetime is None:
            reading_datetime = now
        cursor.execute(
            '''INSERT INTO journal_entries
               (title, content, created_at, updated_at, reading_datetime, location_name, location_lat, location_lon, querent_id, reader_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (title, content, now, now, reading_datetime, location_name, location_lat, location_lon, querent_id, reader_id)
        )
        self._commit()
        return cursor.lastrowid

    def update_entry(self, entry_id: int, title: str = None, content: str = None,
                     reading_datetime: str = None, location_name: str = None,
                     location_lat: float = None, location_lon: float = None,
                     querent_id: int = None, reader_id: int = None):
        """Update entry fields. Safe dynamic SQL: column names are hardcoded, values use ? params."""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        updates = []
        params = []

        if title is not None:
            updates.append('title = ?')
            params.append(title)
        if content is not None:
            updates.append('content = ?')
            params.append(content)
        if reading_datetime is not None:
            updates.append('reading_datetime = ?')
            params.append(reading_datetime)
        if location_name is not None:
            updates.append('location_name = ?')
            params.append(location_name)
        if location_lat is not None:
            updates.append('location_lat = ?')
            params.append(location_lat)
        if location_lon is not None:
            updates.append('location_lon = ?')
            params.append(location_lon)
        if querent_id is not None:
            updates.append('querent_id = ?')
            params.append(querent_id if querent_id != 0 else None)
        if reader_id is not None:
            updates.append('reader_id = ?')
            params.append(reader_id if reader_id != 0 else None)

        if updates:
            updates.append('updated_at = ?')
            params.append(now)
            params.append(entry_id)
            cursor.execute(f'UPDATE journal_entries SET {", ".join(updates)} WHERE id = ?', params)
            self._commit()

    def set_entry_breakdown_settings(self, entry_id: int, settings_json: str):
        """Persist Reading Breakdown panel state. Doesn't bump updated_at —
        this is UI preference, not content."""
        cursor = self.conn.cursor()
        cursor.execute(
            'UPDATE journal_entries SET breakdown_settings = ? WHERE id = ?',
            (settings_json, entry_id)
        )
        self._commit()

    def delete_entry(self, entry_id: int):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM journal_entries WHERE id = ?', (entry_id,))
        self._commit()

    # === Entry Readings ===
    def _touch_entry(self, cursor, entry_id: int):
        """Bump the parent entry's updated_at — the entry aggregate is
        the phone-sync unit, so child writes (readings, tags,
        querents, follow-ups) must move the parent's timestamp."""
        cursor.execute(
            'UPDATE journal_entries SET updated_at = ? WHERE id = ?',
            (datetime.now().isoformat(), entry_id))

    def get_entry_readings(self, entry_id: int):
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT * FROM entry_readings WHERE entry_id = ? ORDER BY position_order',
            (entry_id,)
        )
        return cursor.fetchall()

    def add_entry_reading(self, entry_id: int, spread_id: int = None, spread_name: str = None,
                         deck_id: int = None, deck_name: str = None,
                         cartomancy_type: str = None, cards_used: list = None,
                         position_order: int = 0, notes: str = None,
                         querent_id: int = None):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO entry_readings
            (entry_id, spread_id, spread_name, deck_id, deck_name, cartomancy_type, cards_used, position_order, notes, querent_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (entry_id, spread_id, spread_name, deck_id, deck_name,
              cartomancy_type, json.dumps(cards_used) if cards_used else None, position_order, notes,
              querent_id))
        self._touch_entry(cursor, entry_id)
        self._commit()
        return cursor.lastrowid

    def replace_entry_readings(self, entry_id: int, readings: list) -> list:
        """Atomically replace all readings for an entry.

        The delete and re-inserts happen inside one transaction, so if
        anything fails partway (bad data, lock timeout, crash) the
        entry's original readings are left untouched instead of
        half-deleted. This is the safe path the entry editor uses when
        saving edits.

        Returns the new reading ids in order.
        """
        new_ids = []
        with self.transaction():
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM entry_readings WHERE entry_id = ?', (entry_id,))
            for i, r in enumerate(readings):
                cards_used = r.get('cards_used')
                cursor.execute('''
                    INSERT INTO entry_readings
                    (entry_id, spread_id, spread_name, deck_id, deck_name, cartomancy_type, cards_used, position_order, notes, querent_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (entry_id, r.get('spread_id'), r.get('spread_name'),
                      r.get('deck_id'), r.get('deck_name'), r.get('cartomancy_type'),
                      json.dumps(cards_used) if cards_used else None,
                      r.get('position_order', i), r.get('notes'), r.get('querent_id')))
                new_ids.append(cursor.lastrowid)
            self._touch_entry(cursor, entry_id)
        return new_ids

    # === Follow-up Notes ===
    def get_follow_up_notes(self, entry_id: int):
        """Get all follow-up notes for an entry, ordered by date"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM follow_up_notes
            WHERE entry_id = ?
            ORDER BY created_at ASC
        ''', (entry_id,))
        return cursor.fetchall()

    def add_follow_up_note(self, entry_id: int, content: str):
        """Add a follow-up note to an entry"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO follow_up_notes (entry_id, content, created_at)
            VALUES (?, ?, ?)
        ''', (entry_id, content, datetime.now().isoformat()))
        self._touch_entry(cursor, entry_id)
        self._commit()
        return cursor.lastrowid

    def _touch_note_entry(self, cursor, note_id: int):
        row = cursor.execute(
            'SELECT entry_id FROM follow_up_notes WHERE id = ?', (note_id,)
        ).fetchone()
        if row:
            self._touch_entry(cursor, row[0] if not isinstance(row, dict) else row['entry_id'])

    def update_follow_up_note(self, note_id: int, content: str):
        """Update a follow-up note's content"""
        cursor = self.conn.cursor()
        self._touch_note_entry(cursor, note_id)
        cursor.execute('''
            UPDATE follow_up_notes SET content = ? WHERE id = ?
        ''', (content, note_id))
        self._commit()

    def delete_follow_up_note(self, note_id: int):
        """Delete a follow-up note"""
        cursor = self.conn.cursor()
        self._touch_note_entry(cursor, note_id)
        cursor.execute('DELETE FROM follow_up_notes WHERE id = ?', (note_id,))
        self._commit()

    # === Entry Querents ===
    def get_entry_querents(self, entry_id: int):
        """Get all querents for an entry, ordered by position"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT p.* FROM profiles p
            JOIN entry_querents eq ON p.id = eq.profile_id
            WHERE eq.entry_id = ?
            ORDER BY eq.position
        ''', (entry_id,))
        return cursor.fetchall()

    def set_entry_querents(self, entry_id: int, profile_ids: list):
        """Set the querents for an entry (replaces all existing)"""
        with self.transaction():
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM entry_querents WHERE entry_id = ?', (entry_id,))
            for position, profile_id in enumerate(profile_ids):
                cursor.execute('''
                    INSERT INTO entry_querents (entry_id, profile_id, position)
                    VALUES (?, ?, ?)
                ''', (entry_id, profile_id, position))
            # A reading can only be "for" someone still on the entry.
            cursor.execute(
                'UPDATE entry_readings SET querent_id = NULL WHERE entry_id = ? '
                'AND querent_id IS NOT NULL AND querent_id NOT IN '
                '(SELECT profile_id FROM entry_querents WHERE entry_id = ?)',
                (entry_id, entry_id))
            self._touch_entry(cursor, entry_id)
            # Also update the legacy querent_id column (first querent or NULL)
            legacy_querent_id = profile_ids[0] if profile_ids else None
            cursor.execute('''
                UPDATE journal_entries SET querent_id = ? WHERE id = ?
            ''', (legacy_querent_id, entry_id))
