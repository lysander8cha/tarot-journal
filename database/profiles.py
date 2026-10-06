"""
Database operations for profiles (querent and reader information).
"""


class ProfilesMixin:
    """Mixin providing profile operations."""

    def get_profiles(self):
        """Get all profiles"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM profiles ORDER BY name')
        return cursor.fetchall()

    def get_profile(self, profile_id: int):
        """Get a single profile by ID"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM profiles WHERE id = ?', (profile_id,))
        return cursor.fetchone()

    def add_profile(self, name: str, gender: str = None, birth_date: str = None,
                    birth_time: str = None, birth_place_name: str = None,
                    birth_place_lat: float = None, birth_place_lon: float = None,
                    querent_only: bool = False, hidden: bool = False,
                    full_name: str = None):
        """Add a new profile"""
        if not name or not name.strip():
            raise ValueError("Profile name is required")
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO profiles (name, gender, birth_date, birth_time,
                                  birth_place_name, birth_place_lat, birth_place_lon,
                                  querent_only, hidden, full_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, gender, birth_date, birth_time, birth_place_name,
              birth_place_lat, birth_place_lon, 1 if querent_only else 0,
              1 if hidden else 0, full_name))
        self._commit()
        return cursor.lastrowid

    def update_profile(self, profile_id: int, name: str = None, gender: str = None,
                       birth_date: str = None, birth_time: str = None,
                       birth_place_name: str = None, birth_place_lat: float = None,
                       birth_place_lon: float = None, querent_only: bool = None,
                       hidden: bool = None, full_name: str = None,
                       name_cards_config: str = None):
        """Update an existing profile. Safe dynamic SQL: column names are hardcoded, values use ? params."""
        cursor = self.conn.cursor()
        updates = []
        params = []

        if name is not None:
            updates.append('name = ?')
            params.append(name)
        if gender is not None:
            updates.append('gender = ?')
            params.append(gender)
        if birth_date is not None:
            updates.append('birth_date = ?')
            params.append(birth_date)
        if birth_time is not None:
            updates.append('birth_time = ?')
            params.append(birth_time)
        if birth_place_name is not None:
            updates.append('birth_place_name = ?')
            params.append(birth_place_name)
        if birth_place_lat is not None:
            updates.append('birth_place_lat = ?')
            params.append(birth_place_lat)
        if birth_place_lon is not None:
            updates.append('birth_place_lon = ?')
            params.append(birth_place_lon)
        if querent_only is not None:
            updates.append('querent_only = ?')
            params.append(1 if querent_only else 0)
        if hidden is not None:
            updates.append('hidden = ?')
            params.append(1 if hidden else 0)
        if full_name is not None:
            updates.append('full_name = ?')
            params.append(full_name)
        if name_cards_config is not None:
            # Empty string clears the saved adjustments
            updates.append('name_cards_config = ?')
            params.append(name_cards_config or None)

        if updates:
            params.append(profile_id)
            cursor.execute(f'UPDATE profiles SET {", ".join(updates)} WHERE id = ?', params)
            self._commit()

    # === Alternate names (name-cards inputs beyond the birth name) ===

    NAME_KINDS = ('birth', 'chosen', 'nickname', 'other')

    def get_profile_names(self, profile_id: int):
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT * FROM profile_names WHERE profile_id = ? ORDER BY id',
            (profile_id,))
        return cursor.fetchall()

    def add_profile_name(self, profile_id: int, display_name: str,
                         name_kind: str = 'other', parts: str = None,
                         roles: str = None, y_mode: str = 'heuristic',
                         y_overrides: str = None, drop_suffixes: bool = True):
        """parts/roles/y_overrides arrive as JSON strings (or None)."""
        if not display_name or not display_name.strip():
            raise ValueError('Name is required')
        if name_kind not in self.NAME_KINDS:
            name_kind = 'other'
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO profile_names
                (profile_id, name_kind, display_name, parts, roles,
                 y_mode, y_overrides, drop_suffixes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (profile_id, name_kind, display_name.strip(), parts, roles,
              y_mode, y_overrides, 1 if drop_suffixes else 0))
        self._commit()
        return cursor.lastrowid

    def update_profile_name(self, name_id: int, display_name: str = None,
                            name_kind: str = None, parts: str = None,
                            roles: str = None, clear_roles: bool = False,
                            y_mode: str = None, y_overrides: str = None,
                            drop_suffixes: bool = None):
        cursor = self.conn.cursor()
        updates, params = [], []
        if display_name is not None and display_name.strip():
            updates.append('display_name = ?')
            params.append(display_name.strip())
        if name_kind is not None and name_kind in self.NAME_KINDS:
            updates.append('name_kind = ?')
            params.append(name_kind)
        if parts is not None:
            updates.append('parts = ?')
            params.append(parts)
        if clear_roles:
            updates.append('roles = NULL')
        elif roles is not None:
            updates.append('roles = ?')
            params.append(roles)
        if y_mode is not None:
            updates.append('y_mode = ?')
            params.append(y_mode)
        if y_overrides is not None:
            updates.append('y_overrides = ?')
            params.append(y_overrides)
        if drop_suffixes is not None:
            updates.append('drop_suffixes = ?')
            params.append(1 if drop_suffixes else 0)
        if updates:
            params.append(name_id)
            cursor.execute(
                f'UPDATE profile_names SET {", ".join(updates)} WHERE id = ?',
                params)
            self._commit()

    def delete_profile_name(self, name_id: int):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM profile_names WHERE id = ?', (name_id,))
        self._commit()

    def delete_profile(self, profile_id: int):
        """Delete a profile and clean up all references."""
        cursor = self.conn.cursor()
        # Clear legacy references in journal entries
        cursor.execute('UPDATE journal_entries SET querent_id = NULL WHERE querent_id = ?', (profile_id,))
        cursor.execute('UPDATE journal_entries SET reader_id = NULL WHERE reader_id = ?', (profile_id,))
        # Remove from entry_querents junction table (multiple querents feature)
        cursor.execute('DELETE FROM entry_querents WHERE profile_id = ?', (profile_id,))
        self._prune_reading_querents(cursor, '1 = 1', (), drop=profile_id)
        # Delete the profile
        cursor.execute('DELETE FROM profiles WHERE id = ?', (profile_id,))
        self._commit()
