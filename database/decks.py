"""
Database operations for decks and cartomancy types.
"""

import json
import re
import sqlite3
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

        # Suit/rank entity notes are keyed 'Type::Name'. The table may
        # not exist yet when startup migrations call this on an old DB.
        try:
            cursor.execute(
                "UPDATE entity_source_notes "
                "SET entity_key = ? || substr(entity_key, ?) "
                "WHERE entity_key LIKE ? || '::%'",
                (new_name, len(old_name) + 1, old_name))
        except sqlite3.OperationalError:
            pass

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

    _SUIT_DEFAULTS = {'wands': 'Wands', 'cups': 'Cups',
                      'swords': 'Swords', 'pentacles': 'Pentacles'}
    _COURT_DEFAULTS = {'page': 'Page', 'knight': 'Knight',
                       'queen': 'Queen', 'king': 'King'}

    def _get_deck_names(self, deck_id: int, column: str, defaults: dict) -> dict:
        """Custom suit/court names stored as JSON in decks.<column>, or defaults."""
        deck = self.get_deck(deck_id)
        if deck and deck.get(column):
            try:
                return json.loads(deck[column])
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Failed to parse %s for deck %s: %s", column, deck_id, e)
        return dict(defaults)

    def get_deck_suit_names(self, deck_id: int) -> dict:
        return self._get_deck_names(deck_id, 'suit_names', self._SUIT_DEFAULTS)

    def get_deck_court_names(self, deck_id: int) -> dict:
        return self._get_deck_names(deck_id, 'court_names', self._COURT_DEFAULTS)

    def _update_deck_names(self, deck_id: int, column: str, names: dict,
                           old_names: dict, like, pattern, replacement) -> int:
        """Save decks.<column> and rename the deck's cards from each old
        name to its new one. `like(name)` is the SQL LIKE that finds
        affected cards, `pattern(name)` the regex to replace and
        `replacement(name)` its substitute. Returns cards renamed."""
        cursor = self.conn.cursor()
        cursor.execute(f'UPDATE decks SET {column} = ? WHERE id = ?',
                       (json.dumps(names), deck_id))

        cards_updated = 0
        for key, old_name in (old_names or {}).items():
            new_name = names.get(key)
            if not (old_name and new_name and old_name != new_name):
                continue
            cursor.execute('SELECT id, name FROM cards WHERE deck_id = ? AND name LIKE ?',
                           (deck_id, like(old_name)))
            cards = cursor.fetchall()

            # No cards under the display name? Try the canonical key
            # (capitalized) — names were set but cards never renamed.
            canonical_name = key.capitalize()
            if not cards and canonical_name != old_name:
                cursor.execute('SELECT id, name FROM cards WHERE deck_id = ? AND name LIKE ?',
                               (deck_id, like(canonical_name)))
                cards = cursor.fetchall()
                old_name = canonical_name

            regex = pattern(old_name)
            for card in cards:
                new_card_name = regex.sub(replacement(new_name), card['name'])
                if new_card_name != card['name']:
                    cursor.execute('UPDATE cards SET name = ? WHERE id = ?',
                                   (new_card_name, card['id']))
                    cards_updated += 1

        self._commit()
        return cards_updated

    def update_deck_suit_names(self, deck_id: int, suit_names: dict, old_suit_names: dict = None):
        """Update suit names and rename "... of OldSuit" cards (case-insensitive, end of name)."""
        return self._update_deck_names(
            deck_id, 'suit_names', suit_names, old_suit_names,
            like=lambda n: f'% of {n}',
            pattern=lambda n: re.compile(r'\bof\s+' + re.escape(n) + r'$', re.IGNORECASE),
            replacement=lambda n: f'of {n}')

    def update_deck_court_names(self, deck_id: int, court_names: dict, old_court_names: dict = None):
        """Update court names and rename "OldCourt of ..." cards (case-insensitive)."""
        return self._update_deck_names(
            deck_id, 'court_names', court_names, old_court_names,
            like=lambda n: f'{n} %',
            pattern=lambda n: re.compile(re.escape(f'{n} of'), re.IGNORECASE),
            replacement=lambda n: f'{n} of')

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
