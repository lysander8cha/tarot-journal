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
        cursor.execute('SELECT * FROM spreads ORDER BY name')
        return cursor.fetchall()

    def get_spread(self, spread_id: int):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM spreads WHERE id = ?', (spread_id,))
        return cursor.fetchone()

    def add_spread(self, name: str, positions: list, description: str = None,
                   cartomancy_type: str = None, allowed_deck_types: list = None,
                   default_deck_id: int = None, deck_slots: list = None):
        """
        positions is a list of dicts: [{"x": 0, "y": 0, "label": "Past"}, ...]
        cartomancy_type: 'Tarot', 'Lenormand', 'Oracle', etc. (deprecated, for backwards compat)
        allowed_deck_types: list of cartomancy type names allowed for this spread, e.g. ['Tarot', 'Oracle']
        default_deck_id: ID of the default deck for this spread (overrides global default)
        deck_slots: list of deck slots for multi-deck spreads, e.g. [{"key": "A", "cartomancy_type": "Tarot"}]
        """
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT INTO spreads (name, description, positions, cartomancy_type, allowed_deck_types, default_deck_id, deck_slots) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (name, description, json.dumps(positions), cartomancy_type,
             json.dumps(allowed_deck_types) if allowed_deck_types else None,
             default_deck_id,
             json.dumps(deck_slots) if deck_slots else None)
        )
        self._commit()
        return cursor.lastrowid

    def update_spread(self, spread_id: int, name: str = None, positions: list = None,
                      description: str = None, allowed_deck_types: list = None,
                      default_deck_id: int = None, clear_default_deck: bool = False,
                      deck_slots: list = None):
        cursor = self.conn.cursor()
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
        self._commit()

    def delete_spread(self, spread_id: int):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM spreads WHERE id = ?', (spread_id,))
        self._commit()

    # === Journal Entries ===
    def get_entries(self, limit: int = 50, offset: int = 0):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM journal_entries
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        return cursor.fetchall()

    def get_entry(self, entry_id: int):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM journal_entries WHERE id = ?', (entry_id,))
        return cursor.fetchone()

    def search_entries(self, query: str = None, tag_ids: list = None,
                      deck_id: int = None, spread_id: int = None,
                      cartomancy_type: str = None, card_name: str = None,
                      date_from: str = None, date_to: str = None):
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

        if query:
            conditions.append('(je.title LIKE ? OR je.content LIKE ?)')
            params.extend([f'%{query}%', f'%{query}%'])

        if date_from:
            conditions.append('je.created_at >= ?')
            params.append(date_from)

        if date_to:
            conditions.append('je.created_at <= ?')
            params.append(date_to)

        sql += ' ' + ' '.join(joins)
        if conditions:
            sql += ' WHERE ' + ' AND '.join(conditions)
        sql += ' ORDER BY je.created_at DESC'

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

    def delete_entry(self, entry_id: int):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM journal_entries WHERE id = ?', (entry_id,))
        self._commit()

    # === Entry Readings ===
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
                         position_order: int = 0):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO entry_readings
            (entry_id, spread_id, spread_name, deck_id, deck_name, cartomancy_type, cards_used, position_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (entry_id, spread_id, spread_name, deck_id, deck_name,
              cartomancy_type, json.dumps(cards_used) if cards_used else None, position_order))
        self._commit()
        return cursor.lastrowid

    def delete_entry_readings(self, entry_id: int):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM entry_readings WHERE entry_id = ?', (entry_id,))
        self._commit()

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
        self._commit()
        return cursor.lastrowid

    def update_follow_up_note(self, note_id: int, content: str):
        """Update a follow-up note's content"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE follow_up_notes SET content = ? WHERE id = ?
        ''', (content, note_id))
        self._commit()

    def delete_follow_up_note(self, note_id: int):
        """Delete a follow-up note"""
        cursor = self.conn.cursor()
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
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM entry_querents WHERE entry_id = ?', (entry_id,))
        for position, profile_id in enumerate(profile_ids):
            cursor.execute('''
                INSERT INTO entry_querents (entry_id, profile_id, position)
                VALUES (?, ?, ?)
            ''', (entry_id, profile_id, position))
        # Also update the legacy querent_id column (first querent or NULL)
        legacy_querent_id = profile_ids[0] if profile_ids else None
        cursor.execute('''
            UPDATE journal_entries SET querent_id = ? WHERE id = ?
        ''', (legacy_querent_id, entry_id))
        self._commit()
