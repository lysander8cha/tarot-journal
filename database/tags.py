"""
Database operations for tags (entry tags, deck tags, and card tags).

Uses a generic helper pattern to avoid duplicating identical CRUD logic
across the three tag types. Each tag type has its own table (tags,
deck_tags, card_tags) and junction table.
"""


class TagsMixin:
    """Mixin providing tag operations for entries, decks, and cards."""

    # ── Generic tag helpers ────────────────────────────────────

    def _get_all_tags(self, table: str):
        cursor = self.conn.cursor()
        cursor.execute(f'SELECT * FROM {table} ORDER BY name')
        return cursor.fetchall()

    def _get_tag(self, table: str, tag_id: int):
        cursor = self.conn.cursor()
        cursor.execute(f'SELECT * FROM {table} WHERE id = ?', (tag_id,))
        return cursor.fetchone()

    def _add_tag(self, table: str, name: str, color: str = '#6B5B95'):
        if not name or not name.strip():
            raise ValueError("Tag name is required")
        cursor = self.conn.cursor()
        cursor.execute(f'INSERT INTO {table} (name, color) VALUES (?, ?)', (name, color))
        self._commit()
        return cursor.lastrowid

    def _update_tag(self, table: str, tag_id: int, name: str = None, color: str = None):
        cursor = self.conn.cursor()
        if name:
            cursor.execute(f'UPDATE {table} SET name = ? WHERE id = ?', (name, tag_id))
        if color:
            cursor.execute(f'UPDATE {table} SET color = ? WHERE id = ?', (color, tag_id))
        self._commit()

    def _delete_tag(self, table: str, tag_id: int):
        cursor = self.conn.cursor()
        cursor.execute(f'DELETE FROM {table} WHERE id = ?', (tag_id,))
        self._commit()
        return cursor.rowcount

    def _get_tags_for_entity(self, tag_table: str, junction_table: str,
                              entity_col: str, entity_id: int):
        cursor = self.conn.cursor()
        cursor.execute(f'''
            SELECT t.* FROM {tag_table} t
            JOIN {junction_table} jt ON t.id = jt.tag_id
            WHERE jt.{entity_col} = ?
            ORDER BY t.name
        ''', (entity_id,))
        return cursor.fetchall()

    def _set_tags_for_entity(self, junction_table: str, entity_col: str,
                              entity_id: int, tag_ids: list):
        cursor = self.conn.cursor()
        cursor.execute(f'DELETE FROM {junction_table} WHERE {entity_col} = ?', (entity_id,))
        for tag_id in tag_ids:
            cursor.execute(
                f'INSERT INTO {junction_table} ({entity_col}, tag_id) VALUES (?, ?)',
                (entity_id, tag_id)
            )
        self._commit()

    # ── Entry Tags ─────────────────────────────────────────────

    def get_tags(self):
        return self._get_all_tags('tags')

    def get_tag(self, tag_id: int):
        return self._get_tag('tags', tag_id)

    def add_tag(self, name: str, color: str = '#6B5B95'):
        return self._add_tag('tags', name, color)

    def update_tag(self, tag_id: int, name: str = None, color: str = None):
        self._update_tag('tags', tag_id, name, color)

    def delete_tag(self, tag_id: int):
        return self._delete_tag('tags', tag_id)

    def get_entry_tags(self, entry_id: int):
        return self._get_tags_for_entity('tags', 'entry_tags', 'entry_id', entry_id)

    def add_entry_tag(self, entry_id: int, tag_id: int):
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT OR IGNORE INTO entry_tags (entry_id, tag_id) VALUES (?, ?)',
            (entry_id, tag_id)
        )
        self._commit()

    def set_entry_tags(self, entry_id: int, tag_ids: list):
        self._set_tags_for_entity('entry_tags', 'entry_id', entry_id, tag_ids)
        # Tag changes are part of the entry aggregate for phone sync.
        self._touch_entry(self.conn.cursor(), entry_id)
        self._commit()

    # ── Deck Tags ──────────────────────────────────────────────

    def get_deck_tags(self):
        return self._get_all_tags('deck_tags')

    def get_deck_tag(self, tag_id: int):
        return self._get_tag('deck_tags', tag_id)

    def add_deck_tag(self, name: str, color: str = '#6B5B95'):
        return self._add_tag('deck_tags', name, color)

    def update_deck_tag(self, tag_id: int, name: str = None, color: str = None):
        self._update_tag('deck_tags', tag_id, name, color)

    def delete_deck_tag(self, tag_id: int):
        return self._delete_tag('deck_tags', tag_id)

    def get_tags_for_deck(self, deck_id: int):
        return self._get_tags_for_entity('deck_tags', 'deck_tag_assignments', 'deck_id', deck_id)

    def get_tags_for_decks(self) -> dict:
        """Get all deck-tag assignments in a single query.

        Returns a dictionary mapping deck_id to a list of tag dicts.
        Much more efficient than calling get_tags_for_deck() for each deck.
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT dta.deck_id, t.id, t.name, t.color
            FROM deck_tag_assignments dta
            JOIN deck_tags t ON dta.tag_id = t.id
            ORDER BY t.name
        ''')
        result = {}
        for row in cursor.fetchall():
            deck_id = row['deck_id']
            if deck_id not in result:
                result[deck_id] = []
            result[deck_id].append({
                'id': row['id'],
                'name': row['name'],
                'color': row['color']
            })
        return result

    def set_deck_tags(self, deck_id: int, tag_ids: list):
        self._set_tags_for_entity('deck_tag_assignments', 'deck_id', deck_id, tag_ids)

    # ── Spread Tags ────────────────────────────────────────────

    def get_spread_tags(self):
        return self._get_all_tags('spread_tags')

    def get_spread_tag(self, tag_id: int):
        return self._get_tag('spread_tags', tag_id)

    def add_spread_tag(self, name: str, color: str = '#6B5B95'):
        return self._add_tag('spread_tags', name, color)

    def update_spread_tag(self, tag_id: int, name: str = None, color: str = None):
        self._update_tag('spread_tags', tag_id, name, color)

    def delete_spread_tag(self, tag_id: int):
        return self._delete_tag('spread_tags', tag_id)

    def get_tags_for_spreads(self) -> dict:
        """All spread-tag assignments in one query: spread_id → tag dicts."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT sta.spread_id, t.id, t.name, t.color
            FROM spread_tag_assignments sta
            JOIN spread_tags t ON sta.tag_id = t.id
            ORDER BY t.name
        ''')
        result = {}
        for row in cursor.fetchall():
            result.setdefault(row['spread_id'], []).append({
                'id': row['id'], 'name': row['name'], 'color': row['color'],
            })
        return result

    def set_spread_tags(self, spread_id: int, tag_ids: list):
        self._set_tags_for_entity('spread_tag_assignments', 'spread_id', spread_id, tag_ids)

    # ── Card Tags ──────────────────────────────────────────────

    def get_card_tags(self):
        return self._get_all_tags('card_tags')

    def get_card_tag(self, tag_id: int):
        return self._get_tag('card_tags', tag_id)

    def add_card_tag(self, name: str, color: str = '#6B5B95'):
        return self._add_tag('card_tags', name, color)

    def update_card_tag(self, tag_id: int, name: str = None, color: str = None):
        self._update_tag('card_tags', tag_id, name, color)

    def delete_card_tag(self, tag_id: int):
        return self._delete_tag('card_tags', tag_id)

    def get_tags_for_card(self, card_id: int):
        return self._get_tags_for_entity('card_tags', 'card_tag_assignments', 'card_id', card_id)

    def get_inherited_tags_for_card(self, card_id: int):
        """Get deck tags inherited by a card (from its parent deck)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT dt.* FROM deck_tags dt
            JOIN deck_tag_assignments dta ON dt.id = dta.tag_id
            JOIN cards c ON c.deck_id = dta.deck_id
            WHERE c.id = ?
            ORDER BY dt.name
        ''', (card_id,))
        return cursor.fetchall()

    def set_card_tags(self, card_id: int, tag_ids: list):
        self._set_tags_for_entity('card_tag_assignments', 'card_id', card_id, tag_ids)
