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
                    querent_only: bool = False, hidden: bool = False):
        """Add a new profile"""
        if not name or not name.strip():
            raise ValueError("Profile name is required")
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO profiles (name, gender, birth_date, birth_time,
                                  birth_place_name, birth_place_lat, birth_place_lon,
                                  querent_only, hidden)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, gender, birth_date, birth_time, birth_place_name,
              birth_place_lat, birth_place_lon, 1 if querent_only else 0,
              1 if hidden else 0))
        self._commit()
        return cursor.lastrowid

    def update_profile(self, profile_id: int, name: str = None, gender: str = None,
                       birth_date: str = None, birth_time: str = None,
                       birth_place_name: str = None, birth_place_lat: float = None,
                       birth_place_lon: float = None, querent_only: bool = None,
                       hidden: bool = None):
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

        if updates:
            params.append(profile_id)
            cursor.execute(f'UPDATE profiles SET {", ".join(updates)} WHERE id = ?', params)
            self._commit()

    def delete_profile(self, profile_id: int):
        """Delete a profile and clean up all references."""
        cursor = self.conn.cursor()
        # Clear legacy references in journal entries
        cursor.execute('UPDATE journal_entries SET querent_id = NULL WHERE querent_id = ?', (profile_id,))
        cursor.execute('UPDATE journal_entries SET reader_id = NULL WHERE reader_id = ?', (profile_id,))
        # Remove from entry_querents junction table (multiple querents feature)
        cursor.execute('DELETE FROM entry_querents WHERE profile_id = ?', (profile_id,))
        # Delete the profile
        cursor.execute('DELETE FROM profiles WHERE id = ?', (profile_id,))
        self._commit()
