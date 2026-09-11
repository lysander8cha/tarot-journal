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

    def _tables_with_cartomancy_type_column(self):
        """Every table carrying the type name as a plain-text
        'cartomancy_type' column. Discovered dynamically so tables
        added later are covered without touching this method."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%'")
        out = []
        for (table,) in cursor.fetchall():
            cols = [c[1] for c in cursor.execute(
                f'PRAGMA table_info({table})').fetchall()]
            if 'cartomancy_type' in cols:
                out.append(table)
        return out

    def rename_cartomancy_type(self, type_id: int, new_name: str):
        """Rename a type everywhere: the types row plus every stored
        reference to the old name (plain columns, spreads' JSON,
        typed entity-note keys)."""
        cursor = self.conn.cursor()
        row = cursor.execute(
            'SELECT name FROM cartomancy_types WHERE id = ?', (type_id,)
        ).fetchone()
        if not row:
            raise ValueError('Type not found')
        old_name = row[0] if not isinstance(row, dict) else row['name']
        cursor.execute('UPDATE cartomancy_types SET name = ? WHERE id = ?',
                       (new_name, type_id))
        self._rename_type_name_references(cursor, old_name, new_name)
        self._commit()

    def _rename_type_name_references(self, cursor, old_name: str, new_name: str):
        """Rewrite every stored occurrence of a type NAME (the types
        row itself is the caller's job): plain cartomancy_type columns
        on every table that has one, the JSON references inside
        spreads (allowed_deck_types elements and deck_slots' per-slot
        cartomancy_type), and typed entity-note keys ('Old::Clubs').
        Matches are exact, so renaming 'Lenormand' can never touch
        'Grand Jeu Lenormand'."""
        for table in self._tables_with_cartomancy_type_column():
            cursor.execute(
                f'UPDATE {table} SET cartomancy_type = ? WHERE cartomancy_type = ?',
                (new_name, old_name))

        rows = cursor.execute(
            'SELECT id, allowed_deck_types, deck_slots FROM spreads '
            'WHERE allowed_deck_types IS NOT NULL OR deck_slots IS NOT NULL'
        ).fetchall()
        for spread in rows:
            allowed = spread['allowed_deck_types']
            slots_raw = spread['deck_slots']
            changed = False
            if allowed:
                try:
                    types = json.loads(allowed)
                    renamed = [new_name if t == old_name else t for t in types]
                    if renamed != types:
                        allowed = json.dumps(renamed)
                        changed = True
                except (ValueError, TypeError):
                    pass
            if slots_raw:
                try:
                    slots = json.loads(slots_raw)
                    slot_changed = False
                    for slot in slots:
                        if isinstance(slot, dict) and slot.get('cartomancy_type') == old_name:
                            slot['cartomancy_type'] = new_name
                            slot_changed = True
                    if slot_changed:
                        slots_raw = json.dumps(slots)
                        changed = True
                except (ValueError, TypeError):
                    pass
            if changed:
                cursor.execute(
                    'UPDATE spreads SET allowed_deck_types = ?, deck_slots = ? '
                    'WHERE id = ?',
                    (allowed, slots_raw, spread['id']))

        # Suit/rank entity notes are keyed 'Type::Name'.
        cursor.execute(
            "UPDATE entity_source_notes "
            "SET entity_key = ? || substr(entity_key, ?) "
            "WHERE entity_key LIKE ? || '::%'",
            (new_name, len(old_name) + 1, old_name))

    def delete_cartomancy_type(self, type_id: int):
        """Delete a type and its per-type data. The caller must have
        verified no decks are assigned. Archetype deletion cascades to
        combinations, source entries, language names, and
        correspondence assignments (all FK ON DELETE CASCADE)."""
        cursor = self.conn.cursor()
        row = cursor.execute(
            'SELECT name FROM cartomancy_types WHERE id = ?', (type_id,)
        ).fetchone()
        if not row:
            raise ValueError('Type not found')
        name = row[0] if not isinstance(row, dict) else row['name']
        cursor.execute('DELETE FROM card_archetypes WHERE cartomancy_type = ?',
                       (name,))
        # Per-type reference structures keyed by name.
        for table in ('source_fields', 'source_cartomancy_types',
                      'correspondence_systems'):
            try:
                cursor.execute(
                    f'DELETE FROM {table} WHERE cartomancy_type = ?', (name,))
            except Exception:
                pass
        # Spreads keep their layouts — only the legacy type tag clears.
        cursor.execute(
            'UPDATE spreads SET cartomancy_type = NULL WHERE cartomancy_type = ?',
            (name,))
        cursor.execute('DELETE FROM cartomancy_types WHERE id = ?', (type_id,))
        self._commit()

    def count_decks_for_type(self, type_id: int) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) FROM deck_type_assignments WHERE type_id = ?',
            (type_id,))
        return cursor.fetchone()[0]

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
                    booklet_info: str = None, correspondence_system_id=None,
                    favorite: bool = None):
        cursor = self.conn.cursor()
        if favorite is not None:
            cursor.execute('UPDATE decks SET favorite = ? WHERE id = ?',
                           (1 if favorite else 0, deck_id))
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
        if correspondence_system_id is not None:
            # Use -1 as sentinel for "clear the value" since None means "don't change"
            val = None if correspondence_system_id == -1 else correspondence_system_id
            cursor.execute('UPDATE decks SET correspondence_system_id = ? WHERE id = ?', (val, deck_id))
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
        # Clear spread default_deck_id references (SQLite can't enforce
        # ON DELETE SET NULL for columns added via ALTER TABLE)
        cursor.execute('UPDATE spreads SET default_deck_id = NULL WHERE default_deck_id = ?', (deck_id,))
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

    def get_deck_field_coverage(self, deck_id: int) -> dict:
        """How many of a deck's cards have content for each custom
        field name — drives the Scribe's "(n of N filled)" hints."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM cards WHERE deck_id = ?', (deck_id,))
        card_count = cursor.fetchone()[0]
        cursor.execute('''
            SELECT ccf.field_name, COUNT(DISTINCT ccf.card_id) AS filled
            FROM card_custom_fields ccf
            JOIN cards c ON c.id = ccf.card_id
            WHERE c.deck_id = ?
              AND ccf.field_value IS NOT NULL
              AND TRIM(ccf.field_value) != ''
            GROUP BY LOWER(ccf.field_name)
        ''', (deck_id,))
        fields = {row['field_name']: row['filled'] for row in cursor.fetchall()}
        return {'card_count': card_count, 'fields': fields}

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
