"""
Database operations for tags (entry tags, deck tags, and card tags).
"""


class TagsMixin:
    """Mixin providing tag operations for entries, decks, and cards."""

    # === Entry Tags ===
    def get_tags(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM tags ORDER BY name')
        return cursor.fetchall()

    def get_tag(self, tag_id: int):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM tags WHERE id = ?', (tag_id,))
        return cursor.fetchone()

    def add_tag(self, name: str, color: str = '#6B5B95'):
        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO tags (name, color) VALUES (?, ?)', (name, color))
        self._commit()
        return cursor.lastrowid

    def update_tag(self, tag_id: int, name: str = None, color: str = None):
        cursor = self.conn.cursor()
        if name:
            cursor.execute('UPDATE tags SET name = ? WHERE id = ?', (name, tag_id))
        if color:
            cursor.execute('UPDATE tags SET color = ? WHERE id = ?', (color, tag_id))
        self._commit()

    def delete_tag(self, tag_id: int):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM tags WHERE id = ?', (tag_id,))
        self._commit()

    def get_entry_tags(self, entry_id: int):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT t.* FROM tags t
            JOIN entry_tags et ON t.id = et.tag_id
            WHERE et.entry_id = ?
            ORDER BY t.name
        ''', (entry_id,))
        return cursor.fetchall()

    def add_entry_tag(self, entry_id: int, tag_id: int):
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT OR IGNORE INTO entry_tags (entry_id, tag_id) VALUES (?, ?)',
            (entry_id, tag_id)
        )
        self._commit()

    def remove_entry_tag(self, entry_id: int, tag_id: int):
        cursor = self.conn.cursor()
        cursor.execute(
            'DELETE FROM entry_tags WHERE entry_id = ? AND tag_id = ?',
            (entry_id, tag_id)
        )
        self._commit()

    def set_entry_tags(self, entry_id: int, tag_ids: list):
        """Replace all tags for an entry"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM entry_tags WHERE entry_id = ?', (entry_id,))
        for tag_id in tag_ids:
            cursor.execute(
                'INSERT INTO entry_tags (entry_id, tag_id) VALUES (?, ?)',
                (entry_id, tag_id)
            )
        self._commit()

    # === Deck Tags ===
    def get_deck_tags(self):
        """Get all deck tags"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM deck_tags ORDER BY name')
        return cursor.fetchall()

    def get_deck_tag(self, tag_id: int):
        """Get a single deck tag by ID"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM deck_tags WHERE id = ?', (tag_id,))
        return cursor.fetchone()

    def add_deck_tag(self, name: str, color: str = '#6B5B95'):
        """Create a new deck tag"""
        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO deck_tags (name, color) VALUES (?, ?)', (name, color))
        self._commit()
        return cursor.lastrowid

    def update_deck_tag(self, tag_id: int, name: str = None, color: str = None):
        """Update a deck tag's name and/or color"""
        cursor = self.conn.cursor()
        if name:
            cursor.execute('UPDATE deck_tags SET name = ? WHERE id = ?', (name, tag_id))
        if color:
            cursor.execute('UPDATE deck_tags SET color = ? WHERE id = ?', (color, tag_id))
        self._commit()

    def delete_deck_tag(self, tag_id: int):
        """Delete a deck tag (cascades to assignments)"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM deck_tags WHERE id = ?', (tag_id,))
        self._commit()

    def get_tags_for_deck(self, deck_id: int):
        """Get all tags assigned to a deck"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT t.* FROM deck_tags t
            JOIN deck_tag_assignments dta ON t.id = dta.tag_id
            WHERE dta.deck_id = ?
            ORDER BY t.name
        ''', (deck_id,))
        return cursor.fetchall()

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

    def add_tag_to_deck(self, deck_id: int, tag_id: int):
        """Assign a tag to a deck"""
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT OR IGNORE INTO deck_tag_assignments (deck_id, tag_id) VALUES (?, ?)',
            (deck_id, tag_id)
        )
        self._commit()

    def remove_tag_from_deck(self, deck_id: int, tag_id: int):
        """Remove a tag from a deck"""
        cursor = self.conn.cursor()
        cursor.execute(
            'DELETE FROM deck_tag_assignments WHERE deck_id = ? AND tag_id = ?',
            (deck_id, tag_id)
        )
        self._commit()

    def set_deck_tags(self, deck_id: int, tag_ids: list):
        """Replace all tags for a deck"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM deck_tag_assignments WHERE deck_id = ?', (deck_id,))
        for tag_id in tag_ids:
            cursor.execute(
                'INSERT INTO deck_tag_assignments (deck_id, tag_id) VALUES (?, ?)',
                (deck_id, tag_id)
            )
        self._commit()

    # === Card Tags ===
    def get_card_tags(self):
        """Get all card tags"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM card_tags ORDER BY name')
        return cursor.fetchall()

    def get_card_tag(self, tag_id: int):
        """Get a single card tag by ID"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM card_tags WHERE id = ?', (tag_id,))
        return cursor.fetchone()

    def add_card_tag(self, name: str, color: str = '#6B5B95'):
        """Create a new card tag"""
        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO card_tags (name, color) VALUES (?, ?)', (name, color))
        self._commit()
        return cursor.lastrowid

    def update_card_tag(self, tag_id: int, name: str = None, color: str = None):
        """Update a card tag's name and/or color"""
        cursor = self.conn.cursor()
        if name:
            cursor.execute('UPDATE card_tags SET name = ? WHERE id = ?', (name, tag_id))
        if color:
            cursor.execute('UPDATE card_tags SET color = ? WHERE id = ?', (color, tag_id))
        self._commit()

    def delete_card_tag(self, tag_id: int):
        """Delete a card tag (cascades to assignments)"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM card_tags WHERE id = ?', (tag_id,))
        self._commit()

    def get_tags_for_card(self, card_id: int):
        """Get all tags directly assigned to a card"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT t.* FROM card_tags t
            JOIN card_tag_assignments cta ON t.id = cta.tag_id
            WHERE cta.card_id = ?
            ORDER BY t.name
        ''', (card_id,))
        return cursor.fetchall()

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

    def add_tag_to_card(self, card_id: int, tag_id: int):
        """Assign a tag to a card"""
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT OR IGNORE INTO card_tag_assignments (card_id, tag_id) VALUES (?, ?)',
            (card_id, tag_id)
        )
        self._commit()

    def remove_tag_from_card(self, card_id: int, tag_id: int):
        """Remove a tag from a card"""
        cursor = self.conn.cursor()
        cursor.execute(
            'DELETE FROM card_tag_assignments WHERE card_id = ? AND tag_id = ?',
            (card_id, tag_id)
        )
        self._commit()

    def set_card_tags(self, card_id: int, tag_ids: list):
        """Replace all tags for a card"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM card_tag_assignments WHERE card_id = ?', (card_id,))
        for tag_id in tag_ids:
            cursor.execute(
                'INSERT INTO card_tag_assignments (card_id, tag_id) VALUES (?, ?)',
                (card_id, tag_id)
            )
        self._commit()
