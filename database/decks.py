"""
Database operations for decks and cartomancy types.
"""

import json
import re
from typing import Optional, List

from logger_config import get_logger

logger = get_logger('database')


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
        """Get all decks, optionally filtered by cartomancy type.

        Returns basic deck info. For card counts, tags, and multi-type info,
        use the bulk methods (get_deck_card_counts, get_tags_for_decks,
        get_types_for_decks) to avoid N+1 query problems.
        """
        cursor = self.conn.cursor()
        if cartomancy_type_id:
            # Filter by type using junction table - find decks with ANY matching type
            cursor.execute('''
                SELECT DISTINCT d.*
                FROM decks d
                JOIN deck_type_assignments dta ON d.id = dta.deck_id
                WHERE dta.type_id = ?
                ORDER BY d.name
            ''', (cartomancy_type_id,))
        else:
            cursor.execute('''
                SELECT d.*
                FROM decks d
                ORDER BY d.name
            ''')
        return [dict(row) for row in cursor.fetchall()]

    def get_deck(self, deck_id: int):
        cursor = self.conn.cursor()
        cursor.execute('SELECT d.* FROM decks d WHERE d.id = ?', (deck_id,))
        row = cursor.fetchone()
        if row:
            deck = dict(row)
            types = self.get_types_for_deck(deck_id)
            type_names = ', '.join(t['name'] for t in types) if types else ''
            deck['cartomancy_type_names'] = type_names
            deck['cartomancy_type_name'] = types[0]['name'] if types else ''
            deck['cartomancy_types'] = types
            return deck
        return None

    def add_deck(self, name: str, type_ids: List[int], image_folder: str = None,
                 suit_names: dict = None, court_names: dict = None):
        cursor = self.conn.cursor()
        suit_names_json = json.dumps(suit_names) if suit_names else None
        court_names_json = json.dumps(court_names) if court_names else None
        cursor.execute(
            'INSERT INTO decks (name, image_folder, suit_names, court_names) VALUES (?, ?, ?, ?)',
            (name, image_folder, suit_names_json, court_names_json)
        )
        deck_id = cursor.lastrowid
        for type_id in type_ids:
            cursor.execute(
                'INSERT OR IGNORE INTO deck_type_assignments (deck_id, type_id) VALUES (?, ?)',
                (deck_id, type_id)
            )
        self._commit()
        return deck_id

    def update_deck(self, deck_id: int, name: str = None, image_folder: str = None, suit_names: dict = None,
                    court_names: dict = None, date_published: str = None, publisher: str = None,
                    credits: str = None, notes: str = None, card_back_image: str = None,
                    booklet_info: str = None):
        cursor = self.conn.cursor()
        if name:
            cursor.execute('UPDATE decks SET name = ? WHERE id = ?', (name, deck_id))
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
        defaults = {
            'wands': 'Wands',
            'cups': 'Cups',
            'swords': 'Swords',
            'pentacles': 'Pentacles'
        }
        deck = self.get_deck(deck_id)
        if deck and deck['suit_names']:
            try:
                return json.loads(deck['suit_names'])
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Failed to parse suit_names for deck %s: %s", deck_id, e)
        return defaults

    def get_deck_court_names(self, deck_id: int) -> dict:
        """Get custom court card names for a deck, or defaults"""
        defaults = {
            'page': 'Page',
            'knight': 'Knight',
            'queen': 'Queen',
            'king': 'King'
        }
        deck = self.get_deck(deck_id)
        if deck and deck.get('court_names'):
            try:
                return json.loads(deck['court_names'])
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Failed to parse court_names for deck %s: %s", deck_id, e)
        return defaults

    def update_deck_suit_names(self, deck_id: int, suit_names: dict, old_suit_names: dict = None):
        """Update suit names and rename all cards accordingly."""
        cursor = self.conn.cursor()

        # Update deck's suit_names field
        suit_names_json = json.dumps(suit_names)
        cursor.execute('UPDATE decks SET suit_names = ? WHERE id = ?', (suit_names_json, deck_id))

        # Update card names if old names provided
        cards_updated = 0
        if old_suit_names:
            for suit_key, old_name in old_suit_names.items():
                new_name = suit_names.get(suit_key)
                if old_name and new_name and old_name != new_name:
                    # Get all cards for this deck that END with "of {suit_name}"
                    cursor.execute(
                        'SELECT id, name FROM cards WHERE deck_id = ? AND name LIKE ?',
                        (deck_id, f'% of {old_name}')
                    )
                    cards = cursor.fetchall()

                    # If no cards found with display name, try canonical key (capitalized)
                    # This handles cases where suit_names was set but cards weren't renamed
                    canonical_name = suit_key.capitalize()
                    if not cards and canonical_name != old_name:
                        cursor.execute(
                            'SELECT id, name FROM cards WHERE deck_id = ? AND name LIKE ?',
                            (deck_id, f'% of {canonical_name}')
                        )
                        cards = cursor.fetchall()
                        old_name = canonical_name

                    for card in cards:
                        card_id, card_name = card['id'], card['name']
                        # Case-insensitive replacement of "of OldSuit" with "of NewSuit"
                        # Match "of {suit}" at end of string to avoid partial matches
                        pattern = re.compile(r'\bof\s+' + re.escape(old_name) + r'$', re.IGNORECASE)
                        new_card_name = pattern.sub(f'of {new_name}', card_name)

                        if new_card_name != card_name:
                            cursor.execute(
                                'UPDATE cards SET name = ? WHERE id = ?',
                                (new_card_name, card_id)
                            )
                            cards_updated += 1

        self._commit()
        return cards_updated

    def update_deck_court_names(self, deck_id: int, court_names: dict, old_court_names: dict = None):
        """Update court card names and rename all cards accordingly."""
        cursor = self.conn.cursor()

        # Update deck's court_names field
        court_names_json = json.dumps(court_names)
        cursor.execute('UPDATE decks SET court_names = ? WHERE id = ?', (court_names_json, deck_id))

        # Update card names if old names provided
        cards_updated = 0
        if old_court_names:
            for court_key, old_name in old_court_names.items():
                new_name = court_names.get(court_key)
                if old_name and new_name and old_name != new_name:
                    # Get all cards for this deck that start with the old court name
                    cursor.execute(
                        'SELECT id, name FROM cards WHERE deck_id = ? AND name LIKE ?',
                        (deck_id, f'{old_name} %')
                    )
                    cards = cursor.fetchall()

                    # If no cards found with display name, try canonical key (capitalized)
                    # This handles cases where court_names was set but cards weren't renamed
                    canonical_name = court_key.capitalize()
                    if not cards and canonical_name != old_name:
                        cursor.execute(
                            'SELECT id, name FROM cards WHERE deck_id = ? AND name LIKE ?',
                            (deck_id, f'{canonical_name} %')
                        )
                        cards = cursor.fetchall()
                        old_name = canonical_name

                    for card in cards:
                        card_id, card_name = card['id'], card['name']
                        # Case-insensitive replacement of "OldCourt of" with "NewCourt of"
                        pattern = re.compile(re.escape(f'{old_name} of'), re.IGNORECASE)
                        new_card_name = pattern.sub(f'{new_name} of', card_name)

                        if new_card_name != card_name:
                            cursor.execute(
                                'UPDATE cards SET name = ? WHERE id = ?',
                                (new_card_name, card_id)
                            )
                            cards_updated += 1

        self._commit()
        return cards_updated

    def delete_deck(self, deck_id: int):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM decks WHERE id = ?', (deck_id,))
        self._commit()

    def get_deck_card_counts(self) -> dict:
        """Get card counts for all decks in a single query.

        Returns a dictionary mapping deck_id to card count.
        Much more efficient than calling get_cards() for each deck.
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT deck_id, COUNT(*) as card_count
            FROM cards
            GROUP BY deck_id
        ''')
        return {row['deck_id']: row['card_count'] for row in cursor.fetchall()}

    def get_types_for_decks(self) -> dict:
        """Get all cartomancy types for all decks in a single query.

        Returns a dictionary mapping deck_id to a list of type dicts.
        Much more efficient than calling get_types_for_deck() for each deck.
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT dta.deck_id, ct.id, ct.name
            FROM deck_type_assignments dta
            JOIN cartomancy_types ct ON dta.type_id = ct.id
            ORDER BY ct.name
        ''')
        result = {}
        for row in cursor.fetchall():
            deck_id = row['deck_id']
            if deck_id not in result:
                result[deck_id] = []
            result[deck_id].append({'id': row['id'], 'name': row['name']})
        return result
