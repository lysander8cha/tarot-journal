"""
Database operations for cross-cartomancy-type card-combination meanings.

Schema overview:
- archetype_combinations: ordered (archetype_1_id, archetype_2_id) pair,
  tagged with the cartomancy type for fast picker filtering. Created on
  demand when the first meaning is added to a pair.
- combination_meanings: individual meaning entries, optionally tagged
  with a source from the shared reference_sources table.

Card identities live in card_archetypes; only the FK is stored here.
Names + images are looked up at display time from the user's selected
default deck for the active type.
"""


class CombinationsMixin:
    """CRUD for card-pair combination meanings, parameterized by
    cartomancy type."""

    # === Combinations (internal) ===

    def _get_or_create_combination(
        self,
        cursor,
        cartomancy_type: str,
        archetype_1_id: int,
        archetype_2_id: int,
        archetype_1_reversed: bool = False,
        archetype_2_reversed: bool = False,
        archetype_3_id: int = None,
        archetype_3_reversed: bool = False,
    ) -> int:
        r1, r2 = int(bool(archetype_1_reversed)), int(bool(archetype_2_reversed))
        r3 = int(bool(archetype_3_reversed)) if archetype_3_id else 0
        cursor.execute(
            'SELECT id FROM archetype_combinations '
            'WHERE cartomancy_type = ? AND archetype_1_id = ? AND archetype_2_id = ? '
            'AND archetype_1_reversed = ? AND archetype_2_reversed = ? '
            'AND archetype_3_id IS ? AND archetype_3_reversed = ?',
            (cartomancy_type, archetype_1_id, archetype_2_id, r1, r2,
             archetype_3_id, r3)
        )
        row = cursor.fetchone()
        if row:
            return row[0] if not isinstance(row, dict) else row['id']
        cursor.execute(
            'INSERT INTO archetype_combinations '
            '(cartomancy_type, archetype_1_id, archetype_2_id, '
            ' archetype_1_reversed, archetype_2_reversed, '
            ' archetype_3_id, archetype_3_reversed) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (cartomancy_type, archetype_1_id, archetype_2_id, r1, r2,
             archetype_3_id, r3)
        )
        return cursor.lastrowid

    # === Read ===

    def count_other_reversal_meanings(
        self,
        cartomancy_type: str,
        archetype_1_id: int,
        archetype_2_id: int,
        archetype_1_reversed: bool = False,
        archetype_2_reversed: bool = False,
        archetype_3_id: int = None,
        archetype_3_reversed: bool = False,
    ) -> int:
        """Meanings this same (ordered) pair/triad holds under OTHER
        reversal states — powers the viewer's "n more meanings with
        reversals" hint so reversed combinations aren't invisible."""
        cursor = self.conn.cursor()
        row = cursor.execute(
            '''
            SELECT COUNT(*) FROM combination_meanings m
            JOIN archetype_combinations c ON c.id = m.combination_id
            WHERE c.cartomancy_type = ?
              AND c.archetype_1_id = ? AND c.archetype_2_id = ?
              AND c.archetype_3_id IS ?
              AND NOT (c.archetype_1_reversed = ?
                       AND c.archetype_2_reversed = ?
                       AND c.archetype_3_reversed = ?)
            ''',
            (cartomancy_type, archetype_1_id, archetype_2_id,
             archetype_3_id,
             int(bool(archetype_1_reversed)), int(bool(archetype_2_reversed)),
             int(bool(archetype_3_reversed)) if archetype_3_id else 0)
        ).fetchone()
        return row[0]

    def get_combination_meanings(
        self,
        cartomancy_type: str,
        archetype_1_id: int,
        archetype_2_id: int,
        archetype_1_reversed: bool = False,
        archetype_2_reversed: bool = False,
        archetype_3_id: int = None,
        archetype_3_reversed: bool = False,
    ):
        """All meanings for an ordered pair, joined with source name +
        archetype names so the UI can render without follow-up fetches.

        Returns an empty list if no combination row exists yet.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            '''
            SELECT m.id, m.combination_id, m.meaning, m.source_id,
                   m.sort_order, m.created_at,
                   s.name AS source_name,
                   c.cartomancy_type AS cartomancy_type,
                   c.archetype_1_id AS archetype_1_id,
                   c.archetype_2_id AS archetype_2_id,
                   c.archetype_1_reversed AS archetype_1_reversed,
                   c.archetype_2_reversed AS archetype_2_reversed,
                   c.archetype_3_id AS archetype_3_id,
                   c.archetype_3_reversed AS archetype_3_reversed,
                   a1.name AS archetype_1_name,
                   a2.name AS archetype_2_name,
                   a3.name AS archetype_3_name
            FROM combination_meanings m
            JOIN archetype_combinations c ON c.id = m.combination_id
            JOIN card_archetypes a1 ON a1.id = c.archetype_1_id
            JOIN card_archetypes a2 ON a2.id = c.archetype_2_id
            LEFT JOIN card_archetypes a3 ON a3.id = c.archetype_3_id
            LEFT JOIN reference_sources s ON s.id = m.source_id
            WHERE c.cartomancy_type = ?
              AND c.archetype_1_id = ?
              AND c.archetype_2_id = ?
              AND c.archetype_1_reversed = ?
              AND c.archetype_2_reversed = ?
              AND c.archetype_3_id IS ?
              AND c.archetype_3_reversed = ?
            ORDER BY m.sort_order, m.id
            ''',
            (cartomancy_type, archetype_1_id, archetype_2_id,
             int(bool(archetype_1_reversed)), int(bool(archetype_2_reversed)),
             archetype_3_id,
             int(bool(archetype_3_reversed)) if archetype_3_id else 0)
        )
        return cursor.fetchall()

    def get_combination_partners(
        self,
        cartomancy_type: str,
        archetype_1_id: int,
        archetype_1_reversed: bool = False,
        triad: bool = False,
        archetype_2_id: int = None,
        archetype_2_reversed: bool = False,
    ):
        """Partner archetypes that already have authored meanings, for
        the picker dropdowns' "has meanings" hints.

        - triad=False: second-card partners among two-card combinations.
        - triad=True, no archetype_2_id: second-card partners among
          three-card combinations.
        - triad=True with archetype_2_id: third-card partners for the
          chosen pair.
        The partner's own reversal flag is ignored (any variant counts);
        the chosen cards' flags are exact. Returns [(archetype_id,
        meaning_count)] rows.
        """
        cursor = self.conn.cursor()
        r1 = int(bool(archetype_1_reversed))
        if triad and archetype_2_id is not None:
            cursor.execute(
                '''
                SELECT c.archetype_3_id AS archetype_id, COUNT(m.id) AS meaning_count
                FROM archetype_combinations c
                JOIN combination_meanings m ON m.combination_id = c.id
                WHERE c.cartomancy_type = ? AND c.archetype_1_id = ?
                  AND c.archetype_1_reversed = ? AND c.archetype_2_id = ?
                  AND c.archetype_2_reversed = ? AND c.archetype_3_id IS NOT NULL
                GROUP BY c.archetype_3_id
                ''',
                (cartomancy_type, archetype_1_id, r1,
                 archetype_2_id, int(bool(archetype_2_reversed)))
            )
        else:
            cursor.execute(
                f'''
                SELECT c.archetype_2_id AS archetype_id, COUNT(m.id) AS meaning_count
                FROM archetype_combinations c
                JOIN combination_meanings m ON m.combination_id = c.id
                WHERE c.cartomancy_type = ? AND c.archetype_1_id = ?
                  AND c.archetype_1_reversed = ?
                  AND c.archetype_3_id IS {'NOT NULL' if triad else 'NULL'}
                GROUP BY c.archetype_2_id
                ''',
                (cartomancy_type, archetype_1_id, r1)
            )
        return cursor.fetchall()

    def get_meanings_by_source(self, cartomancy_type: str,
                               source_id: int = None):
        """Every meaning of a type attributed to one source (or
        unattributed when source_id is None), with combination info and
        archetype names, ordered by card names. Powers the viewer's
        browse-by-source listing."""
        cursor = self.conn.cursor()
        source_clause = ('m.source_id IS NULL' if source_id is None
                         else 'm.source_id = ?')
        params = [cartomancy_type]
        if source_id is not None:
            params.append(source_id)
        cursor.execute(
            f'''
            SELECT m.id, m.combination_id, m.meaning, m.source_id,
                   m.sort_order, m.created_at,
                   s.name AS source_name,
                   c.cartomancy_type AS cartomancy_type,
                   c.archetype_1_id, c.archetype_2_id, c.archetype_3_id,
                   c.archetype_1_reversed, c.archetype_2_reversed,
                   c.archetype_3_reversed,
                   a1.name AS archetype_1_name,
                   a2.name AS archetype_2_name,
                   a3.name AS archetype_3_name
            FROM combination_meanings m
            JOIN archetype_combinations c ON c.id = m.combination_id
            JOIN card_archetypes a1 ON a1.id = c.archetype_1_id
            JOIN card_archetypes a2 ON a2.id = c.archetype_2_id
            LEFT JOIN card_archetypes a3 ON a3.id = c.archetype_3_id
            LEFT JOIN reference_sources s ON s.id = m.source_id
            WHERE c.cartomancy_type = ? AND {source_clause}
            ORDER BY a1.name, a2.name, a3.name, m.sort_order, m.id
            ''',
            params)
        return cursor.fetchall()

    # === Write ===

    def add_combination_meaning(
        self,
        cartomancy_type: str,
        archetype_1_id: int,
        archetype_2_id: int,
        meaning: str,
        source_id: int = None,
        archetype_1_reversed: bool = False,
        archetype_2_reversed: bool = False,
        archetype_3_id: int = None,
        archetype_3_reversed: bool = False,
    ) -> int:
        """Create the combination row if needed, then append a new meaning
        at the end of its sort order."""
        if archetype_1_id == archetype_2_id:
            raise ValueError('Combinations must use two different cards')
        if archetype_3_id in (archetype_1_id, archetype_2_id):
            raise ValueError('Combinations must use distinct cards')
        if not meaning or not meaning.strip():
            raise ValueError('Meaning text is required')
        cursor = self.conn.cursor()
        combination_id = self._get_or_create_combination(
            cursor, cartomancy_type, archetype_1_id, archetype_2_id,
            archetype_1_reversed, archetype_2_reversed,
            archetype_3_id, archetype_3_reversed,
        )
        cursor.execute(
            'SELECT COALESCE(MAX(sort_order), -1) + 1 FROM combination_meanings '
            'WHERE combination_id = ?',
            (combination_id,)
        )
        next_order = cursor.fetchone()[0]
        cursor.execute(
            '''
            INSERT INTO combination_meanings
                (combination_id, meaning, source_id, sort_order)
            VALUES (?, ?, ?, ?)
            ''',
            (combination_id, meaning.strip(), source_id, next_order)
        )
        new_id = cursor.lastrowid
        self._commit()
        return new_id

    def update_combination_meaning(
        self,
        meaning_id: int,
        meaning: str = None,
        source_id: int = None,
        clear_source: bool = False,
    ):
        """Update text and/or source on an existing meaning. Pass
        clear_source=True to NULL out the source explicitly; passing
        source_id=None alone leaves it unchanged."""
        cursor = self.conn.cursor()
        if meaning is not None:
            cursor.execute(
                'UPDATE combination_meanings SET meaning = ? WHERE id = ?',
                (meaning, meaning_id)
            )
        if clear_source:
            cursor.execute(
                'UPDATE combination_meanings SET source_id = NULL WHERE id = ?',
                (meaning_id,)
            )
        elif source_id is not None:
            cursor.execute(
                'UPDATE combination_meanings SET source_id = ? WHERE id = ?',
                (source_id, meaning_id)
            )
        self._commit()

    def delete_combination_meaning(self, meaning_id: int):
        """Delete a meaning. If it was the last one in its combination,
        also drop the combination row so empty pairs don't accumulate."""
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT combination_id FROM combination_meanings WHERE id = ?',
            (meaning_id,)
        )
        row = cursor.fetchone()
        if not row:
            return
        combination_id = row[0] if not isinstance(row, dict) else row['combination_id']
        cursor.execute('DELETE FROM combination_meanings WHERE id = ?', (meaning_id,))
        cursor.execute(
            'SELECT COUNT(*) FROM combination_meanings WHERE combination_id = ?',
            (combination_id,)
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                'DELETE FROM archetype_combinations WHERE id = ?',
                (combination_id,)
            )
        self._commit()

    def reorder_combination_meanings(self, combination_id: int, ordered_ids: list):
        """Sort_order tracks position in ordered_ids."""
        cursor = self.conn.cursor()
        for i, meaning_id in enumerate(ordered_ids):
            cursor.execute(
                'UPDATE combination_meanings SET sort_order = ? '
                'WHERE id = ? AND combination_id = ?',
                (i, meaning_id, combination_id)
            )
        self._commit()
