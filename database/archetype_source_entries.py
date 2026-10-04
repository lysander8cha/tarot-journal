"""
Per-archetype source content, now keyed by (archetype, source_field).

Each reference source defines any number of fields (e.g. Upright,
Reversed, Symbolism). For every archetype of the source's cartomancy
type, each field can hold a single rich-text content blob. Rows only
exist when the user has authored something — the viewer treats absence
and emptiness the same.

This mixin owns both source_fields CRUD and the entry table.
"""

from datetime import datetime


class ArchetypeSourceEntriesMixin:
    # === Source fields =======================================

    def get_source_fields(self, source_id: int, cartomancy_type: str = None):
        """Fields defined on a source, optionally scoped to a single
        cartomancy type. Returned in display order."""
        cursor = self.conn.cursor()
        if cartomancy_type is not None:
            return [
                dict(r)
                for r in cursor.execute(
                    'SELECT * FROM source_fields '
                    'WHERE source_id = ? AND cartomancy_type = ? '
                    'ORDER BY sort_order, id',
                    (source_id, cartomancy_type)
                ).fetchall()
            ]
        return [
            dict(r)
            for r in cursor.execute(
                'SELECT * FROM source_fields WHERE source_id = ? '
                'ORDER BY cartomancy_type, sort_order, id',
                (source_id,)
            ).fetchall()
        ]

    def create_source_field(
        self,
        source_id: int,
        name: str,
        cartomancy_type: str,
        collapsible: bool = False,
    ) -> int:
        """Append a new field within a source's (cartomancy_type) bucket.

        Sort order goes to one past the current max for that bucket so
        each cartomancy_type's fields are independently ordered.
        `collapsible=True` marks the field as one that should render
        with a chevron disclosure in the editor (the Archetype Notes
        page collapses it by default so long-form fields don't take
        up the whole stack).
        """
        if not cartomancy_type or not cartomancy_type.strip():
            raise ValueError('cartomancy_type is required')
        cursor = self.conn.cursor()
        next_order = cursor.execute(
            'SELECT COALESCE(MAX(sort_order), -1) + 1 '
            'FROM source_fields WHERE source_id = ? AND cartomancy_type = ?',
            (source_id, cartomancy_type)
        ).fetchone()[0]
        cursor.execute(
            'INSERT INTO source_fields '
            '(source_id, cartomancy_type, name, sort_order, collapsible) '
            'VALUES (?, ?, ?, ?, ?)',
            (source_id, cartomancy_type, name.strip(), next_order,
             1 if collapsible else 0)
        )
        self._commit()
        return cursor.lastrowid

    def update_source_field(
        self,
        field_id: int,
        name: str = None,
        sort_order: int = None,
        collapsible: bool = None,
    ):
        cursor = self.conn.cursor()
        updates = []
        params: list = []
        if name is not None:
            updates.append('name = ?')
            params.append(name.strip())
        if sort_order is not None:
            updates.append('sort_order = ?')
            params.append(int(sort_order))
        if collapsible is not None:
            updates.append('collapsible = ?')
            params.append(1 if collapsible else 0)
        if not updates:
            return
        params.append(field_id)
        cursor.execute(
            f'UPDATE source_fields SET {", ".join(updates)} WHERE id = ?',
            params
        )
        self._commit()

    def reorder_source_fields(
        self,
        source_id: int,
        cartomancy_type: str,
        field_ids: list,
    ):
        """Set sort_order on the given fields to match list position.

        Scoped to (source, cartomancy_type) so the caller can pass just
        the fields visible in that bucket without having to know about
        other types' fields.
        """
        cursor = self.conn.cursor()
        for i, fid in enumerate(field_ids):
            cursor.execute(
                'UPDATE source_fields SET sort_order = ? '
                'WHERE id = ? AND source_id = ? AND cartomancy_type = ?',
                (i, fid, source_id, cartomancy_type)
            )
        self._commit()

    def delete_source_field(self, field_id: int):
        """Removes the field and (via FK cascade) any authored content
        under it."""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM source_fields WHERE id = ?', (field_id,))
        self._commit()

    # === Read entries =========================================

    def get_source_entries_for_archetype(
        self,
        archetype_id: int,
        cartomancy_type: str = None,
    ):
        """All non-empty source entries for an archetype, hydrated with
        source + field info so the viewer can group by source and list
        fields per source without a follow-up fetch.
        """
        cursor = self.conn.cursor()
        sql = '''
            SELECT
                e.id AS entry_id,
                e.archetype_id,
                e.field_id,
                e.content,
                e.updated_at,
                f.name AS field_name,
                f.sort_order AS field_sort_order,
                f.cartomancy_type AS field_cartomancy_type,
                f.collapsible AS field_collapsible,
                s.id AS source_id,
                s.name AS source_name
            FROM archetype_source_entries e
            JOIN source_fields f ON f.id = e.field_id
            JOIN reference_sources s ON s.id = f.source_id
            WHERE e.archetype_id = ?
              AND e.content IS NOT NULL
              AND TRIM(e.content) != ''
        '''
        params: list = [archetype_id]
        if cartomancy_type is not None:
            sql += ' AND f.cartomancy_type = ?'
            params.append(cartomancy_type)
        sql += ' ORDER BY s.name, f.sort_order, f.id'
        return [dict(r) for r in cursor.execute(sql, params).fetchall()]

    def get_source_entries_for_source(
        self,
        source_id: int,
        cartomancy_type: str = None,
    ):
        """Every entry for any field under this source, optionally
        scoped to a single cartomancy_type bucket."""
        cursor = self.conn.cursor()
        sql = '''
            SELECT
                e.id AS entry_id,
                e.archetype_id,
                e.field_id,
                e.content,
                e.updated_at,
                f.name AS field_name,
                f.sort_order AS field_sort_order,
                f.cartomancy_type AS field_cartomancy_type,
                a.name AS archetype_name,
                a.rank AS archetype_rank
            FROM archetype_source_entries e
            JOIN source_fields f ON f.id = e.field_id
            JOIN card_archetypes a ON a.id = e.archetype_id
            WHERE f.source_id = ?
        '''
        params: list = [source_id]
        if cartomancy_type is not None:
            sql += ' AND f.cartomancy_type = ?'
            params.append(cartomancy_type)
        sql += ' ORDER BY a.rank, f.sort_order'
        rows = cursor.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # === Write entries ========================================

    def set_source_entry(self, archetype_id: int, field_id: int, content: str):
        """Upsert content for a single (archetype, field) cell. Blank
        content deletes the row so the viewer's "absent = hidden" rule
        applies uniformly."""
        cursor = self.conn.cursor()
        is_blank = not content or not content.strip()
        if is_blank:
            cursor.execute(
                'DELETE FROM archetype_source_entries '
                'WHERE archetype_id = ? AND field_id = ?',
                (archetype_id, field_id)
            )
        else:
            now = datetime.now().isoformat()
            cursor.execute(
                '''
                INSERT INTO archetype_source_entries
                    (archetype_id, field_id, content, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (archetype_id, field_id) DO UPDATE SET
                    content = excluded.content,
                    updated_at = excluded.updated_at
                ''',
                (archetype_id, field_id, content, now)
            )
        self._commit()

