"""
Database operations for correspondence systems and assignments.

Three-tier inheritance:
1. Correspondence systems define canonical assignments per archetype
2. Decks select a system — cards inherit from it
3. Individual cards can override inherited values
"""

import re

CORRESPONDENCE_FIELDS = (
    'element', 'planet', 'zodiac_sign', 'decan',
    'hebrew_letter', 'numerology', 'rune', 'i_ching_hexagram',
    'chakra', 'modality', 'astrological_house',
)

ZODIAC_SIGNS = {
    'aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo',
    'libra', 'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces',
}

PLANETS = {
    'sun', 'moon', 'mercury', 'venus', 'mars',
    'jupiter', 'saturn', 'uranus', 'neptune', 'pluto',
}

# Auto-derive zodiac sign from (element, modality) — used for court cards
MODALITY_ZODIAC = {
    ('Fire', 'Cardinal'): 'Aries',
    ('Fire', 'Fixed'): 'Leo',
    ('Fire', 'Mutable'): 'Sagittarius',
    ('Water', 'Cardinal'): 'Cancer',
    ('Water', 'Fixed'): 'Scorpio',
    ('Water', 'Mutable'): 'Pisces',
    ('Air', 'Cardinal'): 'Libra',
    ('Air', 'Fixed'): 'Aquarius',
    ('Air', 'Mutable'): 'Gemini',
    ('Earth', 'Cardinal'): 'Capricorn',
    ('Earth', 'Fixed'): 'Taurus',
    ('Earth', 'Mutable'): 'Virgo',
}

# Source tag for values derived automatically from other fields
MODALITY_DERIVED_SOURCE = 'auto:modality'

# Reverse of MODALITY_ZODIAC: element → list of all 3 zodiac signs of that element.
# Used when assigning "all signs of element" to a group (e.g. Aces).
ELEMENT_ZODIACS = {
    'Fire': ['Aries', 'Leo', 'Sagittarius'],
    'Water': ['Cancer', 'Scorpio', 'Pisces'],
    'Air': ['Libra', 'Aquarius', 'Gemini'],
    'Earth': ['Capricorn', 'Taurus', 'Virgo'],
}

DECAN_PATTERN = re.compile(
    r'^(\w+)\s+in\s+(\w+)$', re.IGNORECASE
)


def parse_decan(value: str):
    """Parse a decan string like 'Jupiter in Libra'.

    Returns (planet, zodiac_sign) or None if not a decan pattern.
    """
    m = DECAN_PATTERN.match(value.strip())
    if not m:
        return None
    planet, sign = m.group(1), m.group(2)
    if planet.lower() in PLANETS and sign.lower() in ZODIAC_SIGNS:
        return planet.title(), sign.title()
    return None


class CorrespondencesMixin:
    """Mixin providing correspondence system and assignment operations."""

    # === Correspondence Systems ===

    def get_correspondence_systems(self):
        cursor = self.conn.cursor()
        # archetype_count = total archetypes available for this cartomancy
        # type (what the editor table shows as rows). The earlier "distinct
        # archetypes with at least one assignment" definition was misleading
        # — courts seeded with no values would silently shrink the count.
        cursor.execute('''
            SELECT cs.*,
                   (SELECT COUNT(*)
                    FROM card_archetypes
                    WHERE cartomancy_type = cs.cartomancy_type) AS archetype_count,
                   (SELECT COUNT(*)
                    FROM correspondence_assignments
                    WHERE system_id = cs.id) AS assignment_count
            FROM correspondence_systems cs
            ORDER BY cs.is_builtin DESC, cs.name
        ''')
        return cursor.fetchall()

    def get_correspondence_system(self, system_id: int):
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT * FROM correspondence_systems WHERE id = ?', (system_id,)
        )
        return cursor.fetchone()

    def create_correspondence_system(self, name: str, description: str = None,
                                     is_builtin: bool = False,
                                     cartomancy_type: str = 'Tarot',
                                     naming_style: str = None):
        cursor = self.conn.cursor()
        cursor.execute(
            '''INSERT INTO correspondence_systems
                (name, description, is_builtin, cartomancy_type, naming_style)
               VALUES (?, ?, ?, ?, ?)''',
            (name, description, int(is_builtin), cartomancy_type, naming_style)
        )
        self._commit()
        return cursor.lastrowid

    def update_correspondence_system(self, system_id: int, name: str = None,
                                     description: str = None):
        cursor = self.conn.cursor()
        if name is not None:
            cursor.execute(
                'UPDATE correspondence_systems SET name = ? WHERE id = ?',
                (name, system_id)
            )
        if description is not None:
            cursor.execute(
                'UPDATE correspondence_systems SET description = ? WHERE id = ?',
                (description, system_id)
            )
        self._commit()

    def delete_correspondence_system(self, system_id: int):
        cursor = self.conn.cursor()
        cursor.execute(
            'DELETE FROM correspondence_systems WHERE id = ?', (system_id,)
        )
        self._commit()

    def clone_correspondence_system(self, source_id: int, new_name: str):
        """Clone an existing system with all its assignments."""
        source = self.get_correspondence_system(source_id)
        if not source:
            return None
        src_dict = dict(source)
        new_id = self.create_correspondence_system(
            new_name,
            description=src_dict.get('description'),
            cartomancy_type=src_dict.get('cartomancy_type') or 'Tarot',
            naming_style=src_dict.get('naming_style'),
        )
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO correspondence_assignments
                (system_id, archetype_id, field_name, field_value, source_group)
            SELECT ?, archetype_id, field_name, field_value, source_group
            FROM correspondence_assignments
            WHERE system_id = ?
        ''', (new_id, source_id))
        self._commit()
        return new_id

    # === Field Options ===

    def get_field_options(self, field_name: str = None):
        """Get all field options, optionally filtered by field name."""
        cursor = self.conn.cursor()
        if field_name:
            cursor.execute('''
                SELECT * FROM correspondence_field_options
                WHERE field_name = ?
                ORDER BY sort_order, option_value
            ''', (field_name,))
        else:
            cursor.execute('''
                SELECT * FROM correspondence_field_options
                ORDER BY field_name, sort_order, option_value
            ''')
        return cursor.fetchall()

    def add_field_option(self, field_name: str, option_value: str):
        if field_name not in CORRESPONDENCE_FIELDS:
            raise ValueError(f"Invalid field name: {field_name}")
        cursor = self.conn.cursor()
        # Append at the end
        cursor.execute(
            'SELECT COALESCE(MAX(sort_order), -1) + 1 FROM correspondence_field_options WHERE field_name = ?',
            (field_name,)
        )
        next_order = cursor.fetchone()[0]
        cursor.execute('''
            INSERT OR IGNORE INTO correspondence_field_options
                (field_name, option_value, sort_order)
            VALUES (?, ?, ?)
        ''', (field_name, option_value, next_order))
        self._commit()
        return cursor.lastrowid

    def update_field_option(self, option_id: int, option_value: str = None,
                            sort_order: int = None):
        cursor = self.conn.cursor()

        # If renaming: cascade to existing assignments and card overrides so
        # cells still show the option value after the rename.
        if option_value is not None:
            cursor.execute(
                'SELECT field_name, option_value FROM correspondence_field_options WHERE id = ?',
                (option_id,)
            )
            current = cursor.fetchone()
            if current:
                old_value = current['option_value']
                field_name = current['field_name']
                if old_value != option_value:
                    cursor.execute(
                        '''UPDATE correspondence_assignments
                           SET field_value = ?
                           WHERE field_name = ? AND field_value = ?''',
                        (option_value, field_name, old_value)
                    )
                    cursor.execute(
                        '''UPDATE card_correspondence_overrides
                           SET field_value = ?
                           WHERE field_name = ? AND field_value = ?''',
                        (option_value, field_name, old_value)
                    )
            cursor.execute(
                'UPDATE correspondence_field_options SET option_value = ? WHERE id = ?',
                (option_value, option_id)
            )
        if sort_order is not None:
            cursor.execute(
                'UPDATE correspondence_field_options SET sort_order = ? WHERE id = ?',
                (sort_order, option_id)
            )
        self._commit()

    def delete_field_option(self, option_id: int):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM correspondence_field_options WHERE id = ?', (option_id,))
        self._commit()

    def reorder_field_options(self, field_name: str, ordered_ids: list[int]):
        """Set sort_order based on position in ordered_ids list."""
        cursor = self.conn.cursor()
        for i, opt_id in enumerate(ordered_ids):
            cursor.execute(
                'UPDATE correspondence_field_options SET sort_order = ? WHERE id = ? AND field_name = ?',
                (i, opt_id, field_name)
            )
        self._commit()

    # === Auto-derivation helpers ===

    def _refresh_modality_zodiac(self, system_id: int, archetype_id: int):
        """Recompute auto-derived zodiac_sign for a card based on its element + modality.

        Called after any change to element or modality. If we can identify a
        single element and a single modality for this card, and the pair maps
        to a zodiac sign, we insert a zodiac_sign row tagged with
        MODALITY_DERIVED_SOURCE. Prior derived rows are always cleared first.

        When multiple element values exist (e.g. one from the suit bulk assign
        and another from a court rank), we prefer the one whose source_group
        matches the card's suit name — since that's the "elemental nature of
        the suit" needed for the modality→zodiac mapping.
        """
        cursor = self.conn.cursor()
        # Clear previous auto-derived zodiac
        cursor.execute('''
            DELETE FROM correspondence_assignments
            WHERE system_id = ? AND archetype_id = ? AND field_name = 'zodiac_sign'
              AND source_group = ?
        ''', (system_id, archetype_id, MODALITY_DERIVED_SOURCE))

        # Look up the archetype's suit (e.g. "Wands") so we can prefer suit-sourced element
        cursor.execute('SELECT suit FROM card_archetypes WHERE id = ?', (archetype_id,))
        arch_row = cursor.fetchone()
        suit_name = arch_row['suit'] if arch_row else None

        # Collect current element and modality values with their source_group
        cursor.execute('''
            SELECT field_name, field_value, source_group FROM correspondence_assignments
            WHERE system_id = ? AND archetype_id = ?
              AND field_name IN ('element', 'modality')
        ''', (system_id, archetype_id))
        element_rows = []
        modality_rows = []
        for row in cursor.fetchall():
            if row['field_name'] == 'element':
                element_rows.append(row)
            elif row['field_name'] == 'modality':
                modality_rows.append(row)

        # Pick element: prefer one sourced from the card's suit name, else use
        # the single distinct value if unambiguous
        element = None
        if suit_name:
            for r in element_rows:
                if r['source_group'] == suit_name:
                    element = r['field_value']
                    break
        if element is None:
            distinct_elements = {r['field_value'] for r in element_rows}
            if len(distinct_elements) == 1:
                element = next(iter(distinct_elements))

        # Pick modality: use the single distinct value if unambiguous
        modality = None
        distinct_modalities = {r['field_value'] for r in modality_rows}
        if len(distinct_modalities) == 1:
            modality = next(iter(distinct_modalities))

        if element and modality:
            zodiac = MODALITY_ZODIAC.get((element, modality))
            if zodiac:
                # Modality assignment takes ownership of zodiac for this card:
                # clear any other zodiac entries (seed data, other groups) since
                # element+modality is a more specific derivation than free-floating
                # zodiac values would typically provide.
                cursor.execute('''
                    DELETE FROM correspondence_assignments
                    WHERE system_id = ? AND archetype_id = ? AND field_name = 'zodiac_sign'
                ''', (system_id, archetype_id))
                cursor.execute('''
                    INSERT INTO correspondence_assignments
                        (system_id, archetype_id, field_name, field_value, source_group)
                    VALUES (?, ?, 'zodiac_sign', ?, ?)
                ''', (system_id, archetype_id, zodiac, MODALITY_DERIVED_SOURCE))

    # === System-Level Assignments ===

    def get_system_assignments(self, system_id: int, archetype_id: int = None):
        """Get assignments for a system, optionally filtered by archetype."""
        cursor = self.conn.cursor()
        if archetype_id:
            cursor.execute('''
                SELECT ca.*, a.name AS archetype_name, a.cartomancy_type,
                       a.rank, a.suit, a.card_type
                FROM correspondence_assignments ca
                JOIN card_archetypes a ON a.id = ca.archetype_id
                WHERE ca.system_id = ? AND ca.archetype_id = ?
                ORDER BY CAST(a.rank AS INTEGER)
            ''', (system_id, archetype_id))
        else:
            cursor.execute('''
                SELECT ca.*, a.name AS archetype_name, a.cartomancy_type,
                       a.rank, a.suit, a.card_type
                FROM correspondence_assignments ca
                JOIN card_archetypes a ON a.id = ca.archetype_id
                WHERE ca.system_id = ?
                ORDER BY a.cartomancy_type, CAST(a.rank AS INTEGER)
            ''', (system_id,))
        return cursor.fetchall()

    def set_system_assignment(self, system_id: int, archetype_id: int,
                              field_name: str, field_value: str,
                              source_group: str = None):
        """Set an assignment for an archetype/field.

        If source_group is None (individual cell edit), replaces ALL existing
        values for this cell with a single manual value.
        If source_group is provided (bulk edit), replaces only the value from
        that specific group.
        """
        if field_name not in CORRESPONDENCE_FIELDS:
            raise ValueError(f"Invalid field name: {field_name}")
        cursor = self.conn.cursor()

        if source_group is None:
            # Individual edit: clear all existing values for this cell first
            cursor.execute('''
                DELETE FROM correspondence_assignments
                WHERE system_id = ? AND archetype_id = ? AND field_name = ?
            ''', (system_id, archetype_id, field_name))
            cursor.execute('''
                INSERT INTO correspondence_assignments
                    (system_id, archetype_id, field_name, field_value, source_group)
                VALUES (?, ?, ?, ?, NULL)
            ''', (system_id, archetype_id, field_name, field_value))
        else:
            # Bulk edit: replace just the value from this group
            cursor.execute('''
                DELETE FROM correspondence_assignments
                WHERE system_id = ? AND archetype_id = ? AND field_name = ?
                  AND source_group = ?
            ''', (system_id, archetype_id, field_name, source_group))
            cursor.execute('''
                INSERT INTO correspondence_assignments
                    (system_id, archetype_id, field_name, field_value, source_group)
                VALUES (?, ?, ?, ?, ?)
            ''', (system_id, archetype_id, field_name, field_value, source_group))

        # Decan derivation: auto-set planet and zodiac_sign with same source_group
        if field_name == 'decan':
            derived = parse_decan(field_value)
            if derived:
                planet, sign = derived
                for derived_field, derived_value in (('planet', planet), ('zodiac_sign', sign)):
                    if source_group is None:
                        cursor.execute('''
                            DELETE FROM correspondence_assignments
                            WHERE system_id = ? AND archetype_id = ? AND field_name = ?
                        ''', (system_id, archetype_id, derived_field))
                        cursor.execute('''
                            INSERT INTO correspondence_assignments
                                (system_id, archetype_id, field_name, field_value, source_group)
                            VALUES (?, ?, ?, ?, NULL)
                        ''', (system_id, archetype_id, derived_field, derived_value))
                    else:
                        cursor.execute('''
                            DELETE FROM correspondence_assignments
                            WHERE system_id = ? AND archetype_id = ? AND field_name = ?
                              AND source_group = ?
                        ''', (system_id, archetype_id, derived_field, source_group))
                        cursor.execute('''
                            INSERT INTO correspondence_assignments
                                (system_id, archetype_id, field_name, field_value, source_group)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (system_id, archetype_id, derived_field, derived_value, source_group))

        # Auto-derive zodiac from element + modality when either changes
        if field_name in ('element', 'modality'):
            self._refresh_modality_zodiac(system_id, archetype_id)

        self._commit()

    def delete_system_assignment(self, system_id: int, archetype_id: int,
                                 field_name: str, source_group: str = None,
                                 delete_all_sources: bool = False):
        """Delete an assignment.

        By default, deletes only the NULL-sourced (manual) row. Pass
        source_group to delete a specific group's contribution, or
        delete_all_sources=True to clear everything for this cell.
        """
        cursor = self.conn.cursor()
        if delete_all_sources:
            cursor.execute('''
                DELETE FROM correspondence_assignments
                WHERE system_id = ? AND archetype_id = ? AND field_name = ?
            ''', (system_id, archetype_id, field_name))
        elif source_group is not None:
            cursor.execute('''
                DELETE FROM correspondence_assignments
                WHERE system_id = ? AND archetype_id = ? AND field_name = ?
                  AND source_group = ?
            ''', (system_id, archetype_id, field_name, source_group))
        else:
            cursor.execute('''
                DELETE FROM correspondence_assignments
                WHERE system_id = ? AND archetype_id = ? AND field_name = ?
                  AND source_group IS NULL
            ''', (system_id, archetype_id, field_name))

        # Re-derive zodiac if we removed an element or modality value
        if field_name in ('element', 'modality'):
            self._refresh_modality_zodiac(system_id, archetype_id)

        self._commit()

    def set_system_multi_assignment(self, system_id: int, archetype_id: int,
                                    field_name: str, values: list,
                                    source_group: str = None):
        """Set multiple values for the same (system, archetype, field, source_group).

        Replaces any prior rows for this (source_group, field) combination with
        the new set. Pass source_group=None for manual (NULL-sourced) multi-edits;
        pass a group label for bulk/group-sourced multi-values.
        """
        if field_name not in CORRESPONDENCE_FIELDS:
            raise ValueError(f"Invalid field name: {field_name}")
        cursor = self.conn.cursor()
        if source_group is None:
            cursor.execute('''
                DELETE FROM correspondence_assignments
                WHERE system_id = ? AND archetype_id = ? AND field_name = ?
                  AND source_group IS NULL
            ''', (system_id, archetype_id, field_name))
        else:
            cursor.execute('''
                DELETE FROM correspondence_assignments
                WHERE system_id = ? AND archetype_id = ? AND field_name = ?
                  AND source_group = ?
            ''', (system_id, archetype_id, field_name, source_group))
        seen = set()
        for v in values:
            if not v or v in seen:
                continue
            seen.add(v)
            cursor.execute('''
                INSERT INTO correspondence_assignments
                    (system_id, archetype_id, field_name, field_value, source_group)
                VALUES (?, ?, ?, ?, ?)
            ''', (system_id, archetype_id, field_name, v, source_group))
        if field_name in ('element', 'modality'):
            self._refresh_modality_zodiac(system_id, archetype_id)
        self._commit()

    def expand_elemental_zodiac(self, system_id: int, archetype_ids: list,
                                source_group: str):
        """Assign the 3 zodiac signs of each archetype's suit element.

        For each archetype, determines its element (prefer the value sourced
        from the suit name, else the single distinct element value, else the
        element implied by the archetype's suit if it's a tarot minor), then
        assigns the 3 corresponding zodiac signs to that card with the given
        source_group. Returns a list of {archetype_id, signs, skipped_reason?}.
        """
        cursor = self.conn.cursor()
        report = []

        # Default suit → element fallback used when no system assignment exists
        DEFAULT_SUIT_ELEMENT = {
            'Wands': 'Fire',
            'Cups': 'Water',
            'Swords': 'Air',
            'Pentacles': 'Earth',
        }

        for archetype_id in archetype_ids:
            cursor.execute('SELECT suit FROM card_archetypes WHERE id = ?', (archetype_id,))
            arch_row = cursor.fetchone()
            suit_name = arch_row['suit'] if arch_row else None

            # Find this card's element — prefer suit-sourced entry, then any entry,
            # then fall back to the default suit → element mapping
            element = None
            cursor.execute('''
                SELECT field_value, source_group FROM correspondence_assignments
                WHERE system_id = ? AND archetype_id = ? AND field_name = 'element'
            ''', (system_id, archetype_id))
            elem_rows = cursor.fetchall()
            if suit_name:
                for r in elem_rows:
                    if r['source_group'] == suit_name:
                        element = r['field_value']
                        break
            if element is None:
                distinct = {r['field_value'] for r in elem_rows}
                if len(distinct) == 1:
                    element = next(iter(distinct))
            if element is None and suit_name in DEFAULT_SUIT_ELEMENT:
                element = DEFAULT_SUIT_ELEMENT[suit_name]

            signs = ELEMENT_ZODIACS.get(element) if element else None
            if not signs:
                report.append({'archetype_id': archetype_id, 'skipped': True,
                               'reason': f'No element for archetype (element={element!r})'})
                continue

            self.set_system_multi_assignment(
                system_id, archetype_id, 'zodiac_sign', signs, source_group=source_group,
            )
            report.append({'archetype_id': archetype_id, 'signs': signs})

        return report

    # === Card-Level Overrides ===

    def set_card_correspondence_override(self, card_id: int, field_name: str,
                                         field_value: str):
        """Set a single override value for a card field (replaces any existing)."""
        self.set_card_correspondence_overrides(card_id, field_name, [field_value])

    def set_card_correspondence_overrides(self, card_id: int, field_name: str,
                                          values: list):
        """Replace all override rows for (card, field) with the given value list."""
        if field_name not in CORRESPONDENCE_FIELDS:
            raise ValueError(f"Invalid field name: {field_name}")
        cursor = self.conn.cursor()
        cursor.execute(
            'DELETE FROM card_correspondence_overrides WHERE card_id = ? AND field_name = ?',
            (card_id, field_name)
        )
        seen = set()
        for v in values:
            if not v or v in seen:
                continue
            seen.add(v)
            cursor.execute('''
                INSERT INTO card_correspondence_overrides
                    (card_id, field_name, field_value)
                VALUES (?, ?, ?)
            ''', (card_id, field_name, v))

            # Decan derivation: if this is a decan value, also derive planet/zodiac
            if field_name == 'decan':
                derived = parse_decan(v)
                if derived:
                    planet, sign = derived
                    cursor.execute('''
                        INSERT OR IGNORE INTO card_correspondence_overrides
                            (card_id, field_name, field_value)
                        VALUES (?, 'planet', ?)
                    ''', (card_id, planet))
                    cursor.execute('''
                        INSERT OR IGNORE INTO card_correspondence_overrides
                            (card_id, field_name, field_value)
                        VALUES (?, 'zodiac_sign', ?)
                    ''', (card_id, sign))
        self._commit()

    def delete_card_correspondence_override(self, card_id: int,
                                            field_name: str):
        cursor = self.conn.cursor()
        cursor.execute('''
            DELETE FROM card_correspondence_overrides
            WHERE card_id = ? AND field_name = ?
        ''', (card_id, field_name))
        self._commit()

    # === Deck-Level Overrides ===

    def get_deck_correspondence_overrides(self, deck_id: int):
        """Return all deck-level override rows with archetype metadata."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT dco.*, a.name AS archetype_name, a.cartomancy_type,
                   a.rank, a.suit, a.card_type
            FROM deck_correspondence_overrides dco
            JOIN card_archetypes a ON a.id = dco.archetype_id
            WHERE dco.deck_id = ?
            ORDER BY a.cartomancy_type, CAST(a.rank AS INTEGER), a.name, dco.field_name
        ''', (deck_id,))
        return cursor.fetchall()

    def set_deck_correspondence_overrides(self, deck_id: int, archetype_id: int,
                                          field_name: str, values: list,
                                          source_group: str = None):
        """Replace deck-level override rows for (deck, archetype, field, source_group)
        with the given values. Pass source_group=None to replace only NULL-sourced
        (individual) rows; pass a label to replace only that group's contribution.
        """
        if field_name not in CORRESPONDENCE_FIELDS:
            raise ValueError(f"Invalid field name: {field_name}")
        cursor = self.conn.cursor()
        if source_group is None:
            cursor.execute('''
                DELETE FROM deck_correspondence_overrides
                WHERE deck_id = ? AND archetype_id = ? AND field_name = ?
                  AND source_group IS NULL
            ''', (deck_id, archetype_id, field_name))
        else:
            cursor.execute('''
                DELETE FROM deck_correspondence_overrides
                WHERE deck_id = ? AND archetype_id = ? AND field_name = ?
                  AND source_group = ?
            ''', (deck_id, archetype_id, field_name, source_group))
        seen = set()
        for v in values:
            if not v or v in seen:
                continue
            seen.add(v)
            cursor.execute('''
                INSERT INTO deck_correspondence_overrides
                    (deck_id, archetype_id, field_name, field_value, source_group)
                VALUES (?, ?, ?, ?, ?)
            ''', (deck_id, archetype_id, field_name, v, source_group))
        self._commit()

    def delete_deck_correspondence_override(self, deck_id: int,
                                            archetype_id: int,
                                            field_name: str,
                                            source_group: str = None,
                                            delete_all_sources: bool = False):
        """Delete deck override rows.

        By default, deletes only the NULL-sourced rows for this cell. Pass
        source_group to delete a specific group's contribution, or
        delete_all_sources=True to wipe every row for this cell.
        """
        cursor = self.conn.cursor()
        if delete_all_sources:
            cursor.execute('''
                DELETE FROM deck_correspondence_overrides
                WHERE deck_id = ? AND archetype_id = ? AND field_name = ?
            ''', (deck_id, archetype_id, field_name))
        elif source_group is not None:
            cursor.execute('''
                DELETE FROM deck_correspondence_overrides
                WHERE deck_id = ? AND archetype_id = ? AND field_name = ?
                  AND source_group = ?
            ''', (deck_id, archetype_id, field_name, source_group))
        else:
            cursor.execute('''
                DELETE FROM deck_correspondence_overrides
                WHERE deck_id = ? AND archetype_id = ? AND field_name = ?
                  AND source_group IS NULL
            ''', (deck_id, archetype_id, field_name))
        self._commit()

    def delete_deck_correspondence_group(self, deck_id: int,
                                         source_group: str,
                                         field_name: str = None):
        """Delete every deck override row belonging to a group (optionally
        scoped to a single field). Used when the user removes a bulk group
        override from the deck page.
        """
        cursor = self.conn.cursor()
        if field_name:
            cursor.execute('''
                DELETE FROM deck_correspondence_overrides
                WHERE deck_id = ? AND source_group = ? AND field_name = ?
            ''', (deck_id, source_group, field_name))
        else:
            cursor.execute('''
                DELETE FROM deck_correspondence_overrides
                WHERE deck_id = ? AND source_group = ?
            ''', (deck_id, source_group))
        self._commit()

    # === Resolved Correspondences (Three-Tier Inheritance) ===

    def get_card_correspondences(self, card_id: int):
        """Resolve all correspondence fields for a card with inheritance.

        Returns a list of dicts: [{field_name, value, source}]
        where source is 'override', 'inherited', or 'none'.
        """
        cursor = self.conn.cursor()
        # Get card info for archetype lookup
        cursor.execute('''
            SELECT c.archetype, c.deck_id, d.correspondence_system_id
            FROM cards c
            JOIN decks d ON d.id = c.deck_id
            WHERE c.id = ?
        ''', (card_id,))
        card = cursor.fetchone()
        if not card:
            return []

        # Resolve the card's archetype ID so we can check deck-level overrides
        archetype_id = None
        if card['archetype']:
            # Names repeat across types ("Knight of Cups" is Tarot and
            # Latin-suited): prefer the deck's own type.
            cursor.execute('''
                SELECT id FROM card_archetypes WHERE name = ?
                ORDER BY cartomancy_type IN (
                    SELECT t.name FROM deck_type_assignments a
                    JOIN cartomancy_types t ON t.id = a.type_id
                    WHERE a.deck_id = ?) DESC, id
                LIMIT 1
            ''', (card['archetype'], card['deck_id']))
            arch_row = cursor.fetchone()
            if arch_row:
                archetype_id = arch_row['id']

        result = []
        for field in CORRESPONDENCE_FIELDS:
            # Tier 1: card-level override(s) win — may be multi-value
            cursor.execute('''
                SELECT field_value FROM card_correspondence_overrides
                WHERE card_id = ? AND field_name = ?
                ORDER BY field_value
            ''', (card_id, field))
            override_rows = [r['field_value'] for r in cursor.fetchall() if r['field_value']]
            if override_rows:
                result.append({
                    'field_name': field,
                    'value': ', '.join(override_rows),
                    'values': override_rows,
                    'source': 'override',
                })
                continue

            # Tier 2: deck-level override(s) for this archetype
            if archetype_id is not None:
                cursor.execute('''
                    SELECT field_value FROM deck_correspondence_overrides
                    WHERE deck_id = ? AND archetype_id = ? AND field_name = ?
                    ORDER BY field_value
                ''', (card['deck_id'], archetype_id, field))
                deck_override_rows = [r['field_value'] for r in cursor.fetchall() if r['field_value']]
                if deck_override_rows:
                    result.append({
                        'field_name': field,
                        'value': ', '.join(deck_override_rows),
                        'values': deck_override_rows,
                        'source': 'deck-override',
                    })
                    continue

            # Tier 3: system-level inheritance — may return multiple values from
            # different source groups (e.g. Page of Wands: Fire from Wands + Earth from Pages)
            if card['correspondence_system_id'] and card['archetype']:
                cursor.execute('''
                    SELECT DISTINCT ca.field_value
                    FROM correspondence_assignments ca
                    JOIN card_archetypes a ON a.id = ca.archetype_id
                    WHERE ca.system_id = ?
                      AND a.name = ?
                      AND ca.field_name = ?
                    ORDER BY ca.source_group IS NOT NULL, ca.field_value
                ''', (card['correspondence_system_id'], card['archetype'], field))
                inherited_rows = cursor.fetchall()
                if inherited_rows:
                    values = [r['field_value'] for r in inherited_rows]
                    result.append({
                        'field_name': field,
                        'value': ', '.join(values),
                        'values': values,
                        'source': 'inherited',
                    })
                    continue

            result.append({
                'field_name': field,
                'value': None,
                'values': [],
                'source': 'none',
            })

        return result

    # === Cross-System Queries (for Reference tab) ===

    # === Stats / Insights Queries ===

    def get_correspondence_frequency(self, field_name: str, months: int = 6):
        """Count frequency of each value for a correspondence field across readings.

        Resolves correspondences for every card drawn in journal entries
        within the given time period, using the three-tier inheritance.
        Returns: [{value, count}] sorted by count descending.
        """
        if field_name not in CORRESPONDENCE_FIELDS:
            return []

        cursor = self.conn.cursor()
        # Get all readings within the period
        cursor.execute('''
            SELECT er.cards_used, er.deck_id
            FROM entry_readings er
            JOIN journal_entries je ON je.id = er.entry_id
            WHERE er.cards_used IS NOT NULL
              AND je.created_at >= date('now', ?)
        ''', (f'-{months} months',))

        import json
        value_counts = {}
        for row in cursor.fetchall():
            try:
                cards = json.loads(row['cards_used'])
            except (json.JSONDecodeError, TypeError):
                continue
            deck_id = row['deck_id']

            for card_entry in cards:
                card_name = card_entry.get('name')
                card_deck_id = card_entry.get('deck_id', deck_id)
                if not card_name or not card_deck_id:
                    continue

                # Look up the card
                cursor.execute('''
                    SELECT c.id, c.archetype, d.correspondence_system_id
                    FROM cards c
                    JOIN decks d ON d.id = c.deck_id
                    WHERE c.name = ? AND c.deck_id = ?
                    LIMIT 1
                ''', (card_name, card_deck_id))
                card_row = cursor.fetchone()
                if not card_row:
                    continue

                # Resolve the correspondence value (override → inherited → none)
                values = []

                # Check card override
                cursor.execute('''
                    SELECT field_value FROM card_correspondence_overrides
                    WHERE card_id = ? AND field_name = ?
                ''', (card_row['id'], field_name))
                override = cursor.fetchone()
                if override and override['field_value']:
                    values = [override['field_value']]
                elif card_row['correspondence_system_id'] and card_row['archetype']:
                    # System inheritance — may return multiple values from different groups
                    cursor.execute('''
                        SELECT DISTINCT ca.field_value
                        FROM correspondence_assignments ca
                        JOIN card_archetypes a ON a.id = ca.archetype_id
                        WHERE ca.system_id = ?
                          AND a.name = ?
                          AND ca.field_name = ?
                    ''', (card_row['correspondence_system_id'], card_row['archetype'], field_name))
                    values = [r['field_value'] for r in cursor.fetchall()]

                for v in values:
                    if v:
                        value_counts[v] = value_counts.get(v, 0) + 1

        result = [{'value': v, 'count': c} for v, c in value_counts.items()]
        result.sort(key=lambda x: x['count'], reverse=True)
        return result

    def compare_correspondence_systems(self, system_ids: list[int]):
        """Compare assignments across multiple systems.

        Returns assignments grouped by archetype for the given systems.
        """
        if not system_ids:
            return []
        placeholders = ','.join('?' for _ in system_ids)
        cursor = self.conn.cursor()
        cursor.execute(f'''
            SELECT ca.*, cs.name AS system_name,
                   a.name AS archetype_name, a.cartomancy_type,
                   a.rank, a.suit, a.card_type
            FROM correspondence_assignments ca
            JOIN correspondence_systems cs ON cs.id = ca.system_id
            JOIN card_archetypes a ON a.id = ca.archetype_id
            WHERE ca.system_id IN ({placeholders})
            ORDER BY a.cartomancy_type, CAST(a.rank AS INTEGER), a.name, cs.name, ca.field_name
        ''', system_ids)
        return cursor.fetchall()
