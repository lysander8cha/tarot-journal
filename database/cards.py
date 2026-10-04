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
        # Within a card_order tier, sort by variant_order (NULLs last) so
        # users can choose the in-slot ordering of cards sharing a slot —
        # whether they share a name (Terra Volatile's three "Two of Cups")
        # or just a slot (Terra Volatile's slot 0: The Fool / The Fooless
        # / Chaos). Name is the final tiebreak when nothing's been set.
        cursor.execute(
            'SELECT * FROM cards WHERE deck_id = ? '
            'ORDER BY card_order, variant_order IS NULL, variant_order, name, id',
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
            SELECT c.*, d.name as deck_name,
                (SELECT ct.name FROM deck_type_assignments dta
                 JOIN cartomancy_types ct ON dta.type_id = ct.id
                 WHERE dta.deck_id = d.id
                 ORDER BY ct.name LIMIT 1) as cartomancy_type_name
            FROM cards c
            JOIN decks d ON c.deck_id = d.id
        '''

        conditions = []
        params = []

        # Deck filter
        if deck_id is not None:
            conditions.append('c.deck_id = ?')
            params.append(deck_id)

        # Deck type filter
        if deck_type:
            conditions.append('''EXISTS (
                SELECT 1 FROM deck_type_assignments dta
                JOIN cartomancy_types ct ON dta.type_id = ct.id
                WHERE dta.deck_id = d.id AND ct.name = ?
            )''')
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

    def update_card(self, card_id: int, name: str = None, image_path: str = None,
                    card_order: int = None, variant_order: int = None):
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
        if variant_order is not None:
            updates.append('variant_order = ?')
            params.append(variant_order)
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
        If auto_metadata is True and legacy format is used, automatically assign archetype/rank/suit.

        All operations are wrapped in a transaction for atomicity - if any card fails,
        the entire batch is rolled back.
        """
        with self.transaction():
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

    def add_archetype(self, name: str, cartomancy_type: str,
                      rank: str = None, suit: str = None,
                      card_type: str = None) -> int:
        """Create one archetype. UNIQUE(name, cartomancy_type) makes a
        duplicate raise IntegrityError — callers surface that."""
        if not name or not name.strip():
            raise ValueError('Archetype name is required')
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT INTO card_archetypes (name, cartomancy_type, rank, suit, card_type) '
            'VALUES (?, ?, ?, ?, ?)',
            (name.strip(), cartomancy_type, rank, suit, card_type))
        self._commit()
        return cursor.lastrowid

    def update_archetype(self, archetype_id: int, name: str = None,
                         rank: str = None, suit: str = None):
        """Rename / retag an archetype. A rename also updates the
        plain-text archetype field on cards in decks of this type so
        card-to-archetype matching keeps working."""
        cursor = self.conn.cursor()
        row = cursor.execute(
            'SELECT name, cartomancy_type FROM card_archetypes WHERE id = ?',
            (archetype_id,)).fetchone()
        if not row:
            raise ValueError('Archetype not found')
        old = row if isinstance(row, dict) else dict(row)
        if name is not None and name.strip() and name.strip() != old['name']:
            new_name = name.strip()
            cursor.execute('UPDATE card_archetypes SET name = ? WHERE id = ?',
                           (new_name, archetype_id))
            cursor.execute('''
                UPDATE cards SET archetype = ?
                WHERE archetype = ? AND deck_id IN (
                    SELECT dta.deck_id FROM deck_type_assignments dta
                    JOIN cartomancy_types ct ON ct.id = dta.type_id
                    WHERE ct.name = ?)
            ''', (new_name, old['name'], old['cartomancy_type']))
        if rank is not None:
            cursor.execute('UPDATE card_archetypes SET rank = ? WHERE id = ?',
                           (rank or None, archetype_id))
        if suit is not None:
            cursor.execute('UPDATE card_archetypes SET suit = ? WHERE id = ?',
                           (suit or None, archetype_id))
        self._commit()

    def delete_archetype(self, archetype_id: int):
        """Delete an archetype; combinations, source entries, language
        names, and correspondence assignments cascade via FK."""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM card_archetypes WHERE id = ?',
                       (archetype_id,))
        self._commit()

    def seed_archetypes_from_deck(self, deck_id: int,
                                  cartomancy_type: str) -> int:
        """Create an archetype for every distinct card name in a deck
        that doesn't already exist for the type (matching each card's
        archetype field when set, its name otherwise), carrying the
        card's rank and suit onto the archetype. Existing name-matched
        archetypes that lack rank AND suit are backfilled, so
        re-running the seed repairs earlier passes. Cards without an
        archetype tag get one pointing at their new archetype. Returns
        how many archetypes were created."""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT id, name, archetype, rank, suit FROM cards '
            'WHERE deck_id = ? ORDER BY card_order', (deck_id,))
        rows = [r if isinstance(r, dict) else dict(r) for r in cursor.fetchall()]
        existing = {}
        for row in cursor.execute(
                'SELECT id, name, rank, suit FROM card_archetypes '
                'WHERE cartomancy_type = ?', (cartomancy_type,)).fetchall():
            e = row if isinstance(row, dict) else dict(row)
            existing[e['name'].lower()] = e
        created = 0
        seen = set()
        for r in rows:
            label = (r.get('archetype') or r.get('name') or '').strip()
            if not label or label.lower() in seen:
                continue
            seen.add(label.lower())
            rank = (r.get('rank') or '').strip() or None
            suit = (r.get('suit') or '').strip() or None
            prior = existing.get(label.lower())
            if prior is not None:
                if (rank or suit) and not prior.get('rank') and not prior.get('suit'):
                    cursor.execute(
                        'UPDATE card_archetypes SET rank = ?, suit = ? WHERE id = ?',
                        (rank, suit, prior['id']))
                continue
            cursor.execute(
                'INSERT INTO card_archetypes (name, cartomancy_type, rank, suit) '
                'VALUES (?, ?, ?, ?)',
                (label, cartomancy_type, rank, suit))
            created += 1
        # Tag untagged cards with their own name so they resolve.
        cursor.execute(
            "UPDATE cards SET archetype = name "
            "WHERE deck_id = ? AND (archetype IS NULL OR archetype = '')",
            (deck_id,))
        self._commit()
        return created

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
        elif cartomancy_type == 'Petit Lenormand':
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

    def get_card_full(self, card_id: int):
        """Get a card with deck name, tags, groups, and custom fields in 4 queries.

        Returns a dict with all the data the card detail endpoint needs,
        instead of requiring 6 separate method calls from the route.
        """
        cursor = self.conn.cursor()

        # 1. Card + deck name + cartomancy type in one query via JOIN
        cursor.execute('''
            SELECT c.*, d.name as deck_name,
                (SELECT ct.name FROM deck_type_assignments dta
                 JOIN cartomancy_types ct ON dta.type_id = ct.id
                 WHERE dta.deck_id = d.id
                 ORDER BY ct.name LIMIT 1) as cartomancy_type_name
            FROM cards c
            JOIN decks d ON d.id = c.deck_id
            WHERE c.id = ?
        ''', (card_id,))
        row = cursor.fetchone()
        if not row:
            return None
        card = dict(row)

        # 2. Own tags (card-level)
        cursor.execute('''
            SELECT t.* FROM card_tags t
            JOIN card_tag_assignments cta ON t.id = cta.tag_id
            WHERE cta.card_id = ?
            ORDER BY t.name
        ''', (card_id,))
        card['own_tags'] = [dict(r) for r in cursor.fetchall()]

        # 3. Inherited tags (from parent deck)
        cursor.execute('''
            SELECT dt.* FROM deck_tags dt
            JOIN deck_tag_assignments dta ON dt.id = dta.tag_id
            WHERE dta.deck_id = ?
            ORDER BY dt.name
        ''', (card['deck_id'],))
        card['inherited_tags'] = [dict(r) for r in cursor.fetchall()]

        # 4. Groups
        cursor.execute('''
            SELECT g.* FROM card_groups g
            JOIN card_group_assignments cga ON g.id = cga.group_id
            WHERE cga.card_id = ?
            ORDER BY g.sort_order, g.name
        ''', (card_id,))
        card['groups'] = [dict(r) for r in cursor.fetchall()]

        # 5. Custom fields (ordered by deck definition)
        cursor.execute('''
            SELECT ccf.* FROM card_custom_fields ccf
            JOIN cards c ON c.id = ccf.card_id
            LEFT JOIN deck_custom_fields dcf
                ON dcf.deck_id = c.deck_id AND dcf.field_name = ccf.field_name
            WHERE ccf.card_id = ?
            ORDER BY COALESCE(dcf.field_order, ccf.field_order, 9999), ccf.id
        ''', (card_id,))
        card['card_custom_fields'] = [dict(r) for r in cursor.fetchall()]

        return card

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
        """Update a deck custom field definition. Safe dynamic SQL: column names are hardcoded.
        When field_name changes, cascades the rename to all card data in the deck."""
        cursor = self.conn.cursor()

        # If renaming, cascade to card data before updating the definition
        if field_name is not None:
            cursor.execute('SELECT deck_id, field_name FROM deck_custom_fields WHERE id = ?', (field_id,))
            row = cursor.fetchone()
            if row and row['field_name'] != field_name:
                deck_id, old_name = row['deck_id'], row['field_name']
                old_lower = old_name.lower()

                # Rename in card_custom_fields table (case-insensitive match)
                cursor.execute('''
                    UPDATE card_custom_fields SET field_name = ?
                    WHERE LOWER(field_name) = ? AND card_id IN (
                        SELECT id FROM cards WHERE deck_id = ?
                    )
                ''', (field_name, old_lower, deck_id))

                # Rename key in legacy cards.custom_fields JSON blobs (case-insensitive)
                read_cursor = self.conn.cursor()
                read_cursor.execute(
                    'SELECT id, custom_fields FROM cards WHERE deck_id = ? AND custom_fields IS NOT NULL',
                    (deck_id,))
                for card_row in read_cursor.fetchall():
                    try:
                        parsed = json.loads(card_row['custom_fields'])
                        # Find the key case-insensitively
                        matching_key = next((k for k in parsed if k.lower() == old_lower), None)
                        if matching_key is not None:
                            parsed[field_name] = parsed.pop(matching_key)
                            cursor.execute('UPDATE cards SET custom_fields = ? WHERE id = ?',
                                           (json.dumps(parsed), card_row['id']))
                    except (json.JSONDecodeError, TypeError):
                        pass

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
        """Delete a deck custom field definition, cascading to all cards in the deck.

        Removes both the table-based card_custom_fields rows and any legacy
        JSON blob entries on cards.custom_fields for the same field_name.
        """
        cursor = self.conn.cursor()

        # Look up the field's deck and name so we can cascade
        cursor.execute(
            'SELECT deck_id, field_name FROM deck_custom_fields WHERE id = ?',
            (field_id,)
        )
        row = cursor.fetchone()
        if not row:
            return
        deck_id = row['deck_id']
        field_name = row['field_name']

        # Remove table-based card custom field values for this field in this deck
        cursor.execute(
            '''DELETE FROM card_custom_fields
               WHERE field_name = ?
                 AND card_id IN (SELECT id FROM cards WHERE deck_id = ?)''',
            (field_name, deck_id)
        )

        # Strip the field from any legacy JSON custom_fields blobs on this deck's cards
        cursor.execute(
            'SELECT id, custom_fields FROM cards WHERE deck_id = ? AND custom_fields IS NOT NULL',
            (deck_id,)
        )
        import json
        for card_row in cursor.fetchall():
            try:
                blob = json.loads(card_row['custom_fields']) if card_row['custom_fields'] else {}
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(blob, dict):
                continue
            # Case-insensitive key match, consistent with other legacy field handling
            keys_to_remove = [k for k in blob.keys() if k.lower() == field_name.lower()]
            if keys_to_remove:
                for k in keys_to_remove:
                    blob.pop(k, None)
                new_blob = json.dumps(blob) if blob else None
                cursor.execute(
                    'UPDATE cards SET custom_fields = ? WHERE id = ?',
                    (new_blob, card_row['id'])
                )

        # Finally, remove the deck-level field definition
        cursor.execute('DELETE FROM deck_custom_fields WHERE id = ?', (field_id,))
        self._commit()

    # === Card Custom Fields ===
    def get_card_custom_fields(self, card_id: int):
        """Get custom fields for a specific card, ordered by the deck's field_order"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT ccf.* FROM card_custom_fields ccf
            JOIN cards c ON c.id = ccf.card_id
            LEFT JOIN deck_custom_fields dcf
                ON dcf.deck_id = c.deck_id AND dcf.field_name = ccf.field_name
            WHERE ccf.card_id = ?
            ORDER BY COALESCE(dcf.field_order, ccf.field_order, 9999), ccf.id
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

