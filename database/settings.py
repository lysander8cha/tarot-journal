"""
Database operations for application settings and statistics.
"""


class SettingsMixin:
    """Mixin providing settings and statistics operations."""

    # === Settings ===
    def get_setting(self, key: str, default=None):
        """Get a setting value"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        result = cursor.fetchone()
        return result['value'] if result else default

    def set_setting(self, key: str, value: str):
        """Set a setting value"""
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
            (key, value)
        )
        self._commit()

    def get_default_deck(self, cartomancy_type: str):
        """Get the default deck ID for a cartomancy type"""
        deck_id = self.get_setting(f'default_deck_{cartomancy_type.lower()}')
        return int(deck_id) if deck_id else None

    def set_default_deck(self, cartomancy_type: str, deck_id: int):
        """Set the default deck for a cartomancy type"""
        self.set_setting(f'default_deck_{cartomancy_type.lower()}', str(deck_id))

    def get_default_querent(self):
        """Get the default querent profile ID"""
        profile_id = self.get_setting('default_querent')
        return int(profile_id) if profile_id else None

    def set_default_querent(self, profile_id: int):
        """Set the default querent profile ID"""
        self.set_setting('default_querent', str(profile_id) if profile_id else '')

    def get_default_reader(self):
        """Get the default reader profile ID"""
        profile_id = self.get_setting('default_reader')
        return int(profile_id) if profile_id else None

    def set_default_reader(self, profile_id: int):
        """Set the default reader profile ID"""
        self.set_setting('default_reader', str(profile_id) if profile_id else '')

    def get_default_querent_same_as_reader(self):
        """Get whether default querent should be same as reader"""
        val = self.get_setting('default_querent_same_as_reader')
        return val == '1' if val else False

    def set_default_querent_same_as_reader(self, same: bool):
        """Set whether default querent should be same as reader"""
        self.set_setting('default_querent_same_as_reader', '1' if same else '0')

    # === Statistics ===
    def get_stats(self):
        cursor = self.conn.cursor()
        stats = {}

        cursor.execute('SELECT COUNT(*) FROM journal_entries')
        stats['total_entries'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM decks')
        stats['total_decks'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM cards')
        stats['total_cards'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM spreads')
        stats['total_spreads'] = cursor.fetchone()[0]

        # Most used decks
        cursor.execute('''
            SELECT deck_name, COUNT(*) as count
            FROM entry_readings
            WHERE deck_name IS NOT NULL
            GROUP BY deck_name
            ORDER BY count DESC
            LIMIT 5
        ''')
        stats['top_decks'] = cursor.fetchall()

        # Most used spreads
        cursor.execute('''
            SELECT spread_name, COUNT(*) as count
            FROM entry_readings
            WHERE spread_name IS NOT NULL
            GROUP BY spread_name
            ORDER BY count DESC
            LIMIT 5
        ''')
        stats['top_spreads'] = cursor.fetchall()

        return stats
