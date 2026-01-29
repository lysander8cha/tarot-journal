"""
Database operations for card groups (per-deck custom groupings).
"""


class CardGroupsMixin:
    """Mixin providing card group operations."""

    def get_card_groups(self, deck_id: int):
        """Get all card groups for a deck, ordered by sort_order"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM card_groups WHERE deck_id = ? ORDER BY sort_order, name', (deck_id,))
        return cursor.fetchall()

    def get_card_group(self, group_id: int):
        """Get a single card group by ID"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM card_groups WHERE id = ?', (group_id,))
        return cursor.fetchone()

    def add_card_group(self, deck_id: int, name: str, color: str = '#6B5B95'):
        """Create a new card group for a deck, placed at the end"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COALESCE(MAX(sort_order), -1) + 1 FROM card_groups WHERE deck_id = ?', (deck_id,))
        next_order = cursor.fetchone()[0]
        cursor.execute(
            'INSERT INTO card_groups (deck_id, name, color, sort_order) VALUES (?, ?, ?, ?)',
            (deck_id, name, color, next_order)
        )
        self._commit()
        return cursor.lastrowid

    def update_card_group(self, group_id: int, name: str = None, color: str = None):
        """Update a card group's name and/or color"""
        cursor = self.conn.cursor()
        if name:
            cursor.execute('UPDATE card_groups SET name = ? WHERE id = ?', (name, group_id))
        if color:
            cursor.execute('UPDATE card_groups SET color = ? WHERE id = ?', (color, group_id))
        self._commit()

    def delete_card_group(self, group_id: int):
        """Delete a card group (cascades to assignments)"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM card_groups WHERE id = ?', (group_id,))
        self._commit()

    def swap_card_group_order(self, group_id_a: int, group_id_b: int):
        """Swap the sort_order of two card groups"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT sort_order FROM card_groups WHERE id = ?', (group_id_a,))
        row_a = cursor.fetchone()
        cursor.execute('SELECT sort_order FROM card_groups WHERE id = ?', (group_id_b,))
        row_b = cursor.fetchone()
        if row_a and row_b:
            cursor.execute('UPDATE card_groups SET sort_order = ? WHERE id = ?', (row_b['sort_order'], group_id_a))
            cursor.execute('UPDATE card_groups SET sort_order = ? WHERE id = ?', (row_a['sort_order'], group_id_b))
            self._commit()

    def get_groups_for_card(self, card_id: int):
        """Get all groups a card belongs to"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT g.* FROM card_groups g
            JOIN card_group_assignments cga ON g.id = cga.group_id
            WHERE cga.card_id = ?
            ORDER BY g.sort_order, g.name
        ''', (card_id,))
        return cursor.fetchall()

    def set_card_groups(self, card_id: int, group_ids: list):
        """Replace all group memberships for a card"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM card_group_assignments WHERE card_id = ?', (card_id,))
        for group_id in group_ids:
            cursor.execute(
                'INSERT INTO card_group_assignments (card_id, group_id) VALUES (?, ?)',
                (card_id, group_id)
            )
        self._commit()

    def get_cards_in_group(self, group_id: int):
        """Get all card IDs in a specific group"""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT card_id FROM card_group_assignments WHERE group_id = ?',
            (group_id,)
        )
        return [row['card_id'] for row in cursor.fetchall()]
