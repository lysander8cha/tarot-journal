"""
Database operations for decks and cartomancy types.
"""

import json
from typing import Optional, List


class DecksMixin:
    """Mixin providing deck and cartomancy type operations."""

    # === Cartomancy Types ===
    def get_cartomancy_types(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM cartomancy_types ORDER BY name')
        return cursor.fetchall()

    def add_cartomancy_type(self, name: str):
        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO cartomancy_types (name) VALUES (?)', (name,))
        self._commit()
        return cursor.lastrowid

    # === Decks ===
    def get_decks(self, cartomancy_type_id: Optional[int] = None):
        cursor = self.conn.cursor()
        if cartomancy_type_id:
            # Filter by type using junction table - find decks with ANY matching type
            cursor.execute('''
                SELECT DISTINCT d.*, ct.name as cartomancy_type_name
                FROM decks d
                JOIN cartomancy_types ct ON d.cartomancy_type_id = ct.id
                JOIN deck_type_assignments dta ON d.id = dta.deck_id
                WHERE dta.type_id = ?
                ORDER BY d.name
            ''', (cartomancy_type_id,))
        else:
            cursor.execute('''
                SELECT d.*, ct.name as cartomancy_type_name
                FROM decks d
                JOIN cartomancy_types ct ON d.cartomancy_type_id = ct.id
                ORDER BY ct.name, d.name
            ''')
        rows = cursor.fetchall()
        # Add multiple type names to each deck
        result = []
        for row in rows:
            deck = dict(row)
            types = self.get_types_for_deck(deck['id'])
            if types:
                deck['cartomancy_type_names'] = ', '.join(t['name'] for t in types)
                deck['cartomancy_types'] = types
            else:
                deck['cartomancy_type_names'] = deck['cartomancy_type_name']
                deck['cartomancy_types'] = [{'id': deck['cartomancy_type_id'], 'name': deck['cartomancy_type_name']}]
            result.append(deck)
        return result

    def get_deck(self, deck_id: int):
        cursor = self.conn.cursor()
        # Get deck with primary type (for backward compatibility)
        cursor.execute('''
            SELECT d.*, ct.name as cartomancy_type_name
            FROM decks d
            JOIN cartomancy_types ct ON d.cartomancy_type_id = ct.id
            WHERE d.id = ?
        ''', (deck_id,))
        row = cursor.fetchone()
        if row:
            # Get all types from junction table
            types = self.get_types_for_deck(deck_id)
            if types:
                type_names = ', '.join(t['name'] for t in types)
            else:
                type_names = row['cartomancy_type_name']
            # Return as dict so we can add the extra field
            deck = dict(row)
            deck['cartomancy_type_names'] = type_names
            deck['cartomancy_types'] = types
            return deck
        return None

    def add_deck(self, name: str, cartomancy_type_id: int, image_folder: str = None,
                 suit_names: dict = None, court_names: dict = None):
        cursor = self.conn.cursor()
        suit_names_json = json.dumps(suit_names) if suit_names else None
        court_names_json = json.dumps(court_names) if court_names else None
        cursor.execute(
            'INSERT INTO decks (name, cartomancy_type_id, image_folder, suit_names, court_names) VALUES (?, ?, ?, ?, ?)',
            (name, cartomancy_type_id, image_folder, suit_names_json, court_names_json)
        )
        self._commit()
        return cursor.lastrowid

    def update_deck(self, deck_id: int, name: str = None, image_folder: str = None, suit_names: dict = None,
                    court_names: dict = None, date_published: str = None, publisher: str = None,
                    credits: str = None, notes: str = None, card_back_image: str = None,
                    booklet_info: str = None, cartomancy_type_id: int = None):
        cursor = self.conn.cursor()
        if name:
            cursor.execute('UPDATE decks SET name = ? WHERE id = ?', (name, deck_id))
        if cartomancy_type_id is not None:
            cursor.execute('UPDATE decks SET cartomancy_type_id = ? WHERE id = ?', (cartomancy_type_id, deck_id))
        if image_folder:
            cursor.execute('UPDATE decks SET image_folder = ? WHERE id = ?', (image_folder, deck_id))
        if suit_names is not None:
            suit_names_json = json.dumps(suit_names) if suit_names else None
            cursor.execute('UPDATE decks SET suit_names = ? WHERE id = ?', (suit_names_json, deck_id))
        if court_names is not None:
            court_names_json = json.dumps(court_names) if court_names else None
            cursor.execute('UPDATE decks SET court_names = ? WHERE id = ?', (court_names_json, deck_id))
        if date_published is not None:
            cursor.execute('UPDATE decks SET date_published = ? WHERE id = ?', (date_published, deck_id))
        if publisher is not None:
            cursor.execute('UPDATE decks SET publisher = ? WHERE id = ?', (publisher, deck_id))
        if credits is not None:
            cursor.execute('UPDATE decks SET credits = ? WHERE id = ?', (credits, deck_id))
        if notes is not None:
            cursor.execute('UPDATE decks SET notes = ? WHERE id = ?', (notes, deck_id))
        if card_back_image is not None:
            cursor.execute('UPDATE decks SET card_back_image = ? WHERE id = ?', (card_back_image, deck_id))
        if booklet_info is not None:
            cursor.execute('UPDATE decks SET booklet_info = ? WHERE id = ?', (booklet_info, deck_id))
        self._commit()

    # === Deck Type Assignments (multiple types per deck) ===
    def get_types_for_deck(self, deck_id: int) -> List[dict]:
        """Get all cartomancy types assigned to a deck."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT ct.id, ct.name
            FROM deck_type_assignments dta
            JOIN cartomancy_types ct ON dta.type_id = ct.id
            WHERE dta.deck_id = ?
            ORDER BY ct.name
        ''', (deck_id,))
        return [{'id': row[0], 'name': row[1]} for row in cursor.fetchall()]

    def set_deck_types(self, deck_id: int, type_ids: List[int]):
        """Replace all type assignments for a deck."""
        cursor = self.conn.cursor()
        # Remove existing assignments
        cursor.execute('DELETE FROM deck_type_assignments WHERE deck_id = ?', (deck_id,))
        # Add new assignments
        for type_id in type_ids:
            cursor.execute(
                'INSERT INTO deck_type_assignments (deck_id, type_id) VALUES (?, ?)',
                (deck_id, type_id)
            )
        # Also update the legacy cartomancy_type_id (use first type for backward compatibility)
        if type_ids:
            cursor.execute('UPDATE decks SET cartomancy_type_id = ? WHERE id = ?', (type_ids[0], deck_id))
        self._commit()

    def add_type_to_deck(self, deck_id: int, type_id: int):
        """Add a type to a deck."""
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT OR IGNORE INTO deck_type_assignments (deck_id, type_id) VALUES (?, ?)',
            (deck_id, type_id)
        )
        self._commit()

    def remove_type_from_deck(self, deck_id: int, type_id: int):
        """Remove a type from a deck."""
        cursor = self.conn.cursor()
        cursor.execute(
            'DELETE FROM deck_type_assignments WHERE deck_id = ? AND type_id = ?',
            (deck_id, type_id)
        )
        self._commit()

    def get_deck_suit_names(self, deck_id: int) -> dict:
        """Get custom suit names for a deck, or defaults"""
        deck = self.get_deck(deck_id)
        if deck and deck['suit_names']:
            return json.loads(deck['suit_names'])
        return {
            'wands': 'Wands',
            'cups': 'Cups',
            'swords': 'Swords',
            'pentacles': 'Pentacles'
        }

    def get_deck_court_names(self, deck_id: int) -> dict:
        """Get custom court card names for a deck, or defaults"""
        deck = self.get_deck(deck_id)
        if deck:
            try:
                court_names = deck['court_names']
                if court_names:
                    return json.loads(court_names)
            except (KeyError, TypeError):
                pass
        return {
            'page': 'Page',
            'knight': 'Knight',
            'queen': 'Queen',
            'king': 'King'
        }

    def update_deck_suit_names(self, deck_id: int, suit_names: dict, old_suit_names: dict = None):
        """Update suit names and rename all cards accordingly"""
        cursor = self.conn.cursor()

        # Update deck
        suit_names_json = json.dumps(suit_names)
        cursor.execute('UPDATE decks SET suit_names = ? WHERE id = ?', (suit_names_json, deck_id))

        # Update cards if old names provided
        if old_suit_names:
            for suit_key in ['wands', 'cups', 'swords', 'pentacles']:
                old_name = old_suit_names.get(suit_key)
                new_name = suit_names.get(suit_key)
                if old_name and new_name and old_name != new_name:
                    # Replace "of OldSuit" with "of NewSuit"
                    cursor.execute('''
                        UPDATE cards
                        SET name = REPLACE(name, ?, ?)
                        WHERE deck_id = ? AND name LIKE ?
                    ''', (f'of {old_name}', f'of {new_name}', deck_id, f'%of {old_name}'))

        self._commit()

    def delete_deck(self, deck_id: int):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM decks WHERE id = ?', (deck_id,))
        self._commit()
