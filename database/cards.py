"""
Database operations for cards, archetypes, and card metadata.
"""

import json

from logger_config import get_logger
from card_metadata import (
    MAJOR_ARCANA_ALIASES,
    TAROT_SUIT_ALIASES,
    TAROT_RANK_ALIASES,
    TAROT_SUIT_BASES,
    LENORMAND_ALIASES,
    PLAYING_CARD_SUIT_ALIASES,
    PLAYING_CARD_RANK_ALIASES,
)

logger = get_logger('database')


class CardsMixin:
    """Mixin providing card CRUD and metadata operations."""

    # === Cards ===
    def get_cards(self, deck_id: int):
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT * FROM cards WHERE deck_id = ? ORDER BY card_order, name',
            (deck_id,)
        )
        return cursor.fetchall()

    def search_cards(self, query: str = None, deck_id: int = None, deck_type: str = None,
                     card_category: str = None, archetype: str = None, rank: str = None,
                     suit: str = None, has_notes: bool = None, has_image: bool = None,
                     sort_by: str = 'name', sort_asc: bool = True, limit: int = None):
        """
        Search cards with flexible filtering across one or all decks.

        Args:
            query: Text search across name, archetype, notes, custom_fields
            deck_id: Filter to specific deck (None = all decks)
            deck_type: Filter by deck type (Tarot, Lenormand, etc.)
            card_category: Major Arcana, Minor Arcana, or Court Cards (Tarot only)
            archetype: Filter by archetype (partial match)
            rank: Filter by rank (exact match)
            suit: Filter by suit (exact match)
            has_notes: True = only cards with notes, False = only without
            has_image: True = only cards with images, False = only without
            sort_by: 'name', 'deck', or 'card_order'
            sort_asc: Sort ascending if True
            limit: Maximum number of results (None = unlimited)

        Returns:
            List of card rows with deck_name and cartomancy_type_name included
        """
        cursor = self.conn.cursor()

        # Base query with JOINs for deck info
        sql = '''
            SELECT c.*, d.name as deck_name, ct.name as cartomancy_type_name
            FROM cards c
            JOIN decks d ON c.deck_id = d.id
            JOIN cartomancy_types ct ON d.cartomancy_type_id = ct.id
        '''

        conditions = []
        params = []

        # Deck filter
        if deck_id is not None:
            conditions.append('c.deck_id = ?')
            params.append(deck_id)

        # Deck type filter
        if deck_type:
            conditions.append('ct.name = ?')
            params.append(deck_type)

        # Text search across multiple fields
        if query:
            query_like = f'%{query}%'
            conditions.append('''(
                c.name LIKE ? OR
                c.archetype LIKE ? OR
                c.notes LIKE ? OR
                c.custom_fields LIKE ?
            )''')
            params.extend([query_like, query_like, query_like, query_like])

        # Card category (Major/Minor/Court for Tarot)
        if card_category:
            if card_category == 'Major Arcana':
                conditions.append("(c.suit = 'Major Arcana' OR c.suit IS NULL OR c.suit = '' OR c.suit = 'None')")
            elif card_category == 'Court Cards':
                conditions.append("c.rank IN ('Page', 'Knight', 'Queen', 'King', 'Princess', 'Prince', 'Valet')")
            elif card_category == 'Minor Arcana':
                conditions.append("(c.suit IS NOT NULL AND c.suit != '' AND c.suit != 'None' AND c.suit != 'Major Arcana')")

        # Specific field filters
        if archetype:
            conditions.append('c.archetype LIKE ?')
            params.append(f'%{archetype}%')

        if rank:
            conditions.append('c.rank = ?')
            params.append(rank)

        if suit:
            conditions.append('c.suit = ?')
            params.append(suit)

        # Has notes filter
        if has_notes is True:
            conditions.append("c.notes IS NOT NULL AND c.notes != ''")
        elif has_notes is False:
            conditions.append("(c.notes IS NULL OR c.notes = '')")

        # Has image filter
        if has_image is True:
            conditions.append("c.image_path IS NOT NULL AND c.image_path != ''")
        elif has_image is False:
            conditions.append("(c.image_path IS NULL OR c.image_path = '')")

        # Build WHERE clause
        if conditions:
            sql += ' WHERE ' + ' AND '.join(conditions)

        # Sort order - uses whitelist dict to prevent SQL injection
        sort_column = {
            'name': 'c.name',
            'deck': 'd.name, c.card_order',
            'card_order': 'c.card_order'
        }.get(sort_by, 'c.name')

        sort_dir = 'ASC' if sort_asc else 'DESC'
        sql += f' ORDER BY {sort_column} {sort_dir}'

        # Limit - use parameterized query for consistency
        if limit:
            sql += ' LIMIT ?'
            params.append(int(limit))

        cursor.execute(sql, params)
        return cursor.fetchall()

    def get_card(self, card_id: int):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM cards WHERE id = ?', (card_id,))
        return cursor.fetchone()

    def add_card(self, deck_id: int, name: str, image_path: str = None, card_order: int = 0,
                 auto_metadata: bool = True):
        """Add a card to a deck. If auto_metadata is True, automatically assign archetype/rank/suit."""
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT INTO cards (deck_id, name, image_path, card_order) VALUES (?, ?, ?, ?)',
            (deck_id, name, image_path, card_order)
        )
        self._commit()
        card_id = cursor.lastrowid

        # Auto-assign metadata based on card name
        if auto_metadata:
            deck = self.get_deck(deck_id)
            if deck:
                cartomancy_type = deck['cartomancy_type_name']
                self.auto_assign_card_metadata(card_id, name, cartomancy_type)

        return card_id

    def update_card(self, card_id: int, name: str = None, image_path: str = None, card_order: int = None):
        """Update card fields. Safe dynamic SQL: column names are hardcoded, values use ? params."""
        cursor = self.conn.cursor()
        updates = []
        params = []
        if name is not None:
            updates.append('name = ?')
            params.append(name)
        if image_path is not None:
            updates.append('image_path = ?')
            params.append(image_path)
        if card_order is not None:
            updates.append('card_order = ?')
            params.append(card_order)
        if updates:
            params.append(card_id)
            cursor.execute(f'UPDATE cards SET {", ".join(updates)} WHERE id = ?', params)
            self._commit()

    def delete_card(self, card_id: int):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM cards WHERE id = ?', (card_id,))
        self._commit()

    def bulk_add_cards(self, deck_id: int, cards: list, auto_metadata: bool = True):
        """Add multiple cards at once.
        cards can be:
        - list of (name, image_path, order) tuples (legacy format)
        - list of dicts with keys: name, image_path, sort_order, archetype, rank, suit, custom_fields (new format)
        If auto_metadata is True and legacy format is used, automatically assign archetype/rank/suit."""
        cursor = self.conn.cursor()

        # Check if new dict format or legacy tuple format
        if cards and isinstance(cards[0], dict):
            # New format with pre-computed metadata
            # Insert cards and collect custom_fields to apply after
            cards_with_custom_fields = []
            for c in cards:
                cursor.execute(
                    '''INSERT INTO cards (deck_id, name, image_path, card_order, archetype, rank, suit)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (deck_id, c['name'], c['image_path'], c['sort_order'],
                     c.get('archetype'), c.get('rank'), c.get('suit'))
                )
                card_id = cursor.lastrowid
                if c.get('custom_fields'):
                    cards_with_custom_fields.append((card_id, c['custom_fields']))

            # Apply custom_fields after all cards are inserted
            for card_id, custom_fields in cards_with_custom_fields:
                self.update_card_metadata(card_id, custom_fields=custom_fields)
        else:
            # Legacy tuple format
            cursor.executemany(
                'INSERT INTO cards (deck_id, name, image_path, card_order) VALUES (?, ?, ?, ?)',
                [(deck_id, name, path, order) for name, path, order in cards]
            )
            self._commit()

            # Auto-assign metadata for all cards
            if auto_metadata:
                deck = self.get_deck(deck_id)
                if deck:
                    cartomancy_type = deck['cartomancy_type_name']
                    # Get all cards we just added and assign metadata
                    all_cards = self.get_cards(deck_id)
                    for card in all_cards:
                        # Only update if metadata is not already set
                        existing_archetype = card['archetype'] if 'archetype' in card.keys() else None
                        if not existing_archetype:
                            self.auto_assign_card_metadata(card['id'], card['name'], cartomancy_type)
                    return

        self._commit()
        logger.info("Bulk added %d cards to deck %d", len(cards), deck_id)

    # === Card Archetypes ===
    def get_archetypes(self, cartomancy_type: str = None):
        """Get all archetypes, optionally filtered by cartomancy type"""
        cursor = self.conn.cursor()
        if cartomancy_type:
            cursor.execute('''
                SELECT * FROM card_archetypes
                WHERE cartomancy_type = ?
                ORDER BY id
            ''', (cartomancy_type,))
        else:
            cursor.execute('SELECT * FROM card_archetypes ORDER BY cartomancy_type, id')
        return cursor.fetchall()

    def search_archetypes(self, query: str, cartomancy_type: str = None):
        """Search archetypes by name for autocomplete"""
        cursor = self.conn.cursor()
        search_pattern = f'%{query}%'
        if cartomancy_type:
            cursor.execute('''
                SELECT * FROM card_archetypes
                WHERE cartomancy_type = ? AND name LIKE ?
                ORDER BY name
                LIMIT 20
            ''', (cartomancy_type, search_pattern))
        else:
            cursor.execute('''
                SELECT * FROM card_archetypes
                WHERE name LIKE ?
                ORDER BY cartomancy_type, name
                LIMIT 20
            ''', (search_pattern,))
        return cursor.fetchall()

    def get_archetype_by_name(self, name: str, cartomancy_type: str):
        """Get a specific archetype by name and type"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM card_archetypes
            WHERE name = ? AND cartomancy_type = ?
        ''', (name, cartomancy_type))
        return cursor.fetchone()

    def parse_card_name_for_archetype(self, card_name: str, cartomancy_type: str):
        """
        Parse a card name and return archetype info (archetype, rank, suit).
        Handles various naming conventions for Tarot and Lenormand.
        Returns (archetype_name, rank, suit) or (None, None, None) if not found.
        """
        if not card_name:
            return None, None, None

        card_name_lower = card_name.lower().strip()

        if cartomancy_type == 'Tarot':
            return self._parse_tarot_card_name(card_name, card_name_lower)
        elif cartomancy_type == 'Lenormand':
            return self._parse_lenormand_card_name(card_name, card_name_lower)
        elif cartomancy_type == 'Playing Cards':
            return self._parse_playing_card_name(card_name, card_name_lower)

        return None, None, None

    def _parse_tarot_card_name(self, card_name: str, card_name_lower: str):
        """Parse Tarot card names and return (archetype, rank, suit)"""
        # Check for exact major arcana match
        if card_name_lower in MAJOR_ARCANA_ALIASES:
            return MAJOR_ARCANA_ALIASES[card_name_lower]

        # Minor Arcana parsing - find suit and rank
        found_suit = None
        found_rank = None
        found_rank_num = None

        for suit_key, suit_name in TAROT_SUIT_ALIASES.items():
            if suit_key in card_name_lower:
                found_suit = suit_name
                break

        for rank_key, (rank_name, rank_num) in TAROT_RANK_ALIASES.items():
            if rank_key in card_name_lower.split() or card_name_lower.startswith(rank_key + ' '):
                found_rank = rank_name
                found_rank_num = rank_num
                break

        if found_suit and found_rank:
            archetype = f"{found_rank} of {found_suit}"
            rank = str(TAROT_SUIT_BASES[found_suit] + found_rank_num)
            return archetype, rank, found_suit

        return None, None, None

    def _parse_lenormand_card_name(self, card_name: str, card_name_lower: str):
        """Parse Lenormand card names and return (archetype, rank, suit)"""
        import re

        # Try alias match first
        for key, (name, rank) in LENORMAND_ALIASES.items():
            if key in card_name_lower:
                return name, rank, None

        # Try matching by number prefix (e.g., "01 Rider", "1. Rider")
        num_match = re.match(r'^(\d+)\D', card_name)
        if num_match:
            num = int(num_match.group(1))
            if 1 <= num <= 36:
                # Find the card with this number
                for key, (name, rank) in LENORMAND_ALIASES.items():
                    if rank == str(num):
                        return name, rank, None

        return None, None, None

    def _parse_playing_card_name(self, card_name: str, card_name_lower: str):
        """Parse Playing Card names and return (archetype, rank, suit)"""
        # Check for joker
        if 'joker' in card_name_lower:
            if 'red' in card_name_lower:
                return 'Red Joker', 'Joker', None
            elif 'black' in card_name_lower:
                return 'Black Joker', 'Joker', None
            else:
                return 'Red Joker', 'Joker', None  # Default to red

        found_suit = None
        found_rank = None

        for suit_key, suit_name in PLAYING_CARD_SUIT_ALIASES.items():
            if suit_key in card_name_lower:
                found_suit = suit_name
                break

        for rank_key, (rank_name, _) in PLAYING_CARD_RANK_ALIASES.items():
            if rank_key in card_name_lower.split() or card_name_lower.startswith(rank_key + ' '):
                found_rank = rank_name
                break

        if found_suit and found_rank:
            archetype = f"{found_rank} of {found_suit}"
            return archetype, found_rank, found_suit

        return None, None, None

    def auto_assign_card_metadata(self, card_id: int, card_name: str, cartomancy_type: str,
                                   preset_name: str = None):
        """Automatically assign archetype, rank, and suit based on card name.
        If preset_name is provided, uses the import_presets module for ordering-aware metadata."""
        if preset_name:
            # Use import_presets for ordering-aware metadata
            from import_presets import get_presets
            presets = get_presets()
            metadata = presets.get_card_metadata(card_name, preset_name)
            if metadata.get('archetype') or metadata.get('rank') or metadata.get('suit'):
                self.update_card_metadata(card_id, archetype=metadata.get('archetype'),
                                         rank=metadata.get('rank'), suit=metadata.get('suit'))
            # Also update card_order if sort_order is valid
            sort_order = metadata.get('sort_order')
            if sort_order is not None and sort_order != 999:
                self.update_card(card_id, card_order=sort_order)
        else:
            # Fall back to legacy parsing
            archetype, rank, suit = self.parse_card_name_for_archetype(card_name, cartomancy_type)
            if archetype or rank or suit:
                self.update_card_metadata(card_id, archetype=archetype, rank=rank, suit=suit)

    def auto_assign_deck_metadata(self, deck_id: int, overwrite: bool = False,
                                   preset_name: str = None, use_sort_order: bool = False):
        """
        Automatically assign metadata to all cards in a deck.
        If overwrite is False, only updates cards without existing archetype.
        If preset_name is provided, uses ordering-aware metadata from import_presets.
        If use_sort_order is True, assigns metadata based on card sort order (1, 2, 3...)
        instead of parsing card names.
        Returns the number of cards updated.
        """
        deck = self.get_deck(deck_id)
        if not deck:
            return 0

        cartomancy_type = deck['cartomancy_type_name']
        cards = self.get_cards(deck_id)
        updated = 0

        # Get custom suit names from deck if available
        custom_suit_names = None
        if deck['suit_names']:
            try:
                custom_suit_names = json.loads(deck['suit_names'])
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Failed to parse suit_names for deck %s: %s", deck['id'], e)

        # Get custom court names from deck if available
        custom_court_names = None
        if deck['court_names']:
            try:
                custom_court_names = json.loads(deck['court_names'])
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Failed to parse court_names for deck %s: %s", deck['id'], e)

        # Use import_presets if preset_name is provided
        if preset_name:
            from import_presets import get_presets
            presets = get_presets()

            # If using sort order, sort cards and assign metadata sequentially
            if use_sort_order:
                # Sort cards by their current card_order
                sorted_cards = sorted(cards, key=lambda c: c['card_order'] if c['card_order'] else 999)
                for idx, card in enumerate(sorted_cards):
                    # Skip if already has archetype and not overwriting
                    existing_archetype = card['archetype'] if 'archetype' in card.keys() else None
                    if not overwrite and existing_archetype:
                        continue

                    # Use 1-based index as the sort order for metadata lookup
                    sort_order = idx + 1
                    metadata = presets.get_card_metadata_by_sort_order(sort_order, preset_name)

                    if metadata:
                        self.update_card_metadata(card['id'], archetype=metadata.get('archetype'),
                                                 rank=metadata.get('rank'), suit=metadata.get('suit'),
                                                 custom_fields=metadata.get('custom_fields'))
                        # Update sort order to match
                        self.update_card(card['id'], card_order=sort_order)
                        updated += 1
            else:
                # Parse card names for metadata
                for card in cards:
                    # Skip if already has archetype and not overwriting
                    existing_archetype = card['archetype'] if 'archetype' in card.keys() else None
                    if not overwrite and existing_archetype:
                        continue

                    metadata = presets.get_card_metadata(card['name'], preset_name, custom_suit_names,
                                                         custom_court_names)
                    # Check if we have any metadata to update (including sort_order for Oracle decks)
                    has_metadata = metadata.get('archetype') or metadata.get('rank') or metadata.get('suit')
                    has_sort_order = metadata.get('sort_order') is not None and metadata.get('sort_order') != 999

                    if has_metadata or has_sort_order:
                        if has_metadata:
                            self.update_card_metadata(card['id'], archetype=metadata.get('archetype'),
                                                     rank=metadata.get('rank'), suit=metadata.get('suit'),
                                                     custom_fields=metadata.get('custom_fields'))
                        # Also update sort order
                        if has_sort_order:
                            self.update_card(card['id'], card_order=metadata.get('sort_order'))
                        updated += 1
        else:
            # Fall back to legacy parsing (no preset ordering)
            for card in cards:
                existing_archetype = card['archetype'] if 'archetype' in card.keys() else None
                if not overwrite and existing_archetype:
                    continue

                archetype, rank, suit = self.parse_card_name_for_archetype(card['name'], cartomancy_type)
                if archetype or rank or suit:
                    self.update_card_metadata(card['id'], archetype=archetype, rank=rank, suit=suit)
                    updated += 1

        return updated

    # === Card Metadata ===
    def update_card_metadata(self, card_id: int, archetype: str = None, rank: str = None,
                             suit: str = None, notes: str = None, custom_fields: dict = None):
        """Update card metadata fields. Safe dynamic SQL: column names are hardcoded, values use ? params."""
        cursor = self.conn.cursor()
        updates = []
        params = []

        if archetype is not None:
            updates.append('archetype = ?')
            params.append(archetype)
        if rank is not None:
            updates.append('rank = ?')
            params.append(rank)
        if suit is not None:
            updates.append('suit = ?')
            params.append(suit)
        if notes is not None:
            updates.append('notes = ?')
            params.append(notes)
        if custom_fields is not None:
            updates.append('custom_fields = ?')
            if not custom_fields:
                params.append(None)
            elif isinstance(custom_fields, str):
                params.append(custom_fields)
            else:
                params.append(json.dumps(custom_fields))

        if updates:
            params.append(card_id)
            cursor.execute(f'UPDATE cards SET {", ".join(updates)} WHERE id = ?', params)
            self._commit()

    def get_card_with_metadata(self, card_id: int):
        """Get a card with all its metadata"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT c.*, d.cartomancy_type_id, ct.name as cartomancy_type_name
            FROM cards c
            JOIN decks d ON c.deck_id = d.id
            JOIN cartomancy_types ct ON d.cartomancy_type_id = ct.id
            WHERE c.id = ?
        ''', (card_id,))
        return cursor.fetchone()

    # === Deck Custom Fields ===
    def get_deck_custom_fields(self, deck_id: int):
        """Get custom field definitions for a deck"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM deck_custom_fields
            WHERE deck_id = ?
            ORDER BY field_order, id
        ''', (deck_id,))
        return cursor.fetchall()

    def add_deck_custom_field(self, deck_id: int, field_name: str, field_type: str,
                              field_options: list = None, field_order: int = 0):
        """Add a custom field definition to a deck"""
        cursor = self.conn.cursor()
        options_json = json.dumps(field_options) if field_options else None
        cursor.execute('''
            INSERT INTO deck_custom_fields (deck_id, field_name, field_type, field_options, field_order)
            VALUES (?, ?, ?, ?, ?)
        ''', (deck_id, field_name, field_type, options_json, field_order))
        self._commit()
        return cursor.lastrowid

    def update_deck_custom_field(self, field_id: int, field_name: str = None,
                                 field_type: str = None, field_options: list = None,
                                 field_order: int = None):
        """Update a deck custom field definition. Safe dynamic SQL: column names are hardcoded."""
        cursor = self.conn.cursor()
        updates = []
        params = []

        if field_name is not None:
            updates.append('field_name = ?')
            params.append(field_name)
        if field_type is not None:
            updates.append('field_type = ?')
            params.append(field_type)
        if field_options is not None:
            updates.append('field_options = ?')
            params.append(json.dumps(field_options) if field_options else None)
        if field_order is not None:
            updates.append('field_order = ?')
            params.append(field_order)

        if updates:
            params.append(field_id)
            cursor.execute(f'UPDATE deck_custom_fields SET {", ".join(updates)} WHERE id = ?', params)
            self._commit()

    def delete_deck_custom_field(self, field_id: int):
        """Delete a deck custom field definition"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM deck_custom_fields WHERE id = ?', (field_id,))
        self._commit()

    # === Card Custom Fields ===
    def get_card_custom_fields(self, card_id: int):
        """Get custom fields for a specific card"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM card_custom_fields
            WHERE card_id = ?
            ORDER BY field_order, id
        ''', (card_id,))
        return cursor.fetchall()

    def add_card_custom_field(self, card_id: int, field_name: str, field_type: str,
                              field_value: str = None, field_options: list = None,
                              field_order: int = 0):
        """Add a custom field to a specific card"""
        cursor = self.conn.cursor()
        options_json = json.dumps(field_options) if field_options else None
        cursor.execute('''
            INSERT INTO card_custom_fields (card_id, field_name, field_type, field_options, field_value, field_order)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (card_id, field_name, field_type, options_json, field_value, field_order))
        self._commit()
        return cursor.lastrowid

    def update_card_custom_field(self, field_id: int, field_name: str = None,
                                 field_type: str = None, field_value: str = None,
                                 field_options: list = None, field_order: int = None):
        """Update a card custom field. Safe dynamic SQL: column names are hardcoded."""
        cursor = self.conn.cursor()
        updates = []
        params = []

        if field_name is not None:
            updates.append('field_name = ?')
            params.append(field_name)
        if field_type is not None:
            updates.append('field_type = ?')
            params.append(field_type)
        if field_value is not None:
            updates.append('field_value = ?')
            params.append(field_value)
        if field_options is not None:
            updates.append('field_options = ?')
            params.append(json.dumps(field_options) if field_options else None)
        if field_order is not None:
            updates.append('field_order = ?')
            params.append(field_order)

        if updates:
            params.append(field_id)
            cursor.execute(f'UPDATE card_custom_fields SET {", ".join(updates)} WHERE id = ?', params)
            self._commit()

    def delete_card_custom_field(self, field_id: int):
        """Delete a card custom field"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM card_custom_fields WHERE id = ?', (field_id,))
        self._commit()

    def get_deck_card_custom_field_values(self, deck_id: int, field_name: str):
        """Get all values for a deck-level custom field across all cards in the deck"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT c.id as card_id, c.name as card_name, c.custom_fields
            FROM cards c
            WHERE c.deck_id = ?
        ''', (deck_id,))
        results = []
        for row in cursor.fetchall():
            custom_fields = json.loads(row['custom_fields']) if row['custom_fields'] else {}
            results.append({
                'card_id': row['card_id'],
                'card_name': row['card_name'],
                'value': custom_fields.get(field_name)
            })
        return results

    def set_card_deck_field_value(self, card_id: int, field_name: str, value):
        """Set a deck-level custom field value for a specific card (stored in cards.custom_fields JSON)"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT custom_fields FROM cards WHERE id = ?', (card_id,))
        row = cursor.fetchone()
        custom_fields = json.loads(row['custom_fields']) if row and row['custom_fields'] else {}
        custom_fields[field_name] = value
        cursor.execute('UPDATE cards SET custom_fields = ? WHERE id = ?',
                       (json.dumps(custom_fields), card_id))
        self._commit()
