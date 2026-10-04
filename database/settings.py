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

    # === Astrology charts ===
    # Whole Sign is the project default — every house spans one zodiac sign,
    # which keeps charts legible at extreme latitudes where quadrant systems
    # (Placidus, Koch) get distorted. Users can switch in Settings; doing so
    # invalidates every cached chart on next view via the input_hash compare.
    DEFAULT_HOUSE_SYSTEM = 'Whole Sign'

    def get_house_system(self) -> str:
        return self.get_setting('astrology_house_system') or self.DEFAULT_HOUSE_SYSTEM

    def set_house_system(self, name: str):
        self.set_setting('astrology_house_system', name)

    def get_allow_solar_chart(self) -> bool:
        """When True and a profile has birth_date+lat+lon but no birth_time,
        a solar chart is generated at local noon with a disclaimer flag in
        chart_data. When False, no chart is generated without a time."""
        return self.get_setting('astrology_allow_solar_chart') == '1'

    def set_allow_solar_chart(self, allow: bool):
        self.set_setting('astrology_allow_solar_chart', '1' if allow else '0')

    # === Statistics ===
    def get_tag_trends(self, limit: int = 15):
        """Get entry tag usage counts.

        Counts how many journal entries use each tag.

        Args:
            limit: Maximum tags to return (default 15)

        Returns:
            List of dicts with name, color, count
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT t.name, t.color, COUNT(et.entry_id) as count
            FROM entry_tags et
            JOIN tags t ON et.tag_id = t.id
            GROUP BY t.id
            ORDER BY count DESC
            LIMIT ?
        ''', (limit,))

        return [
            {
                'name': row['name'],
                'color': row['color'],
                'count': row['count']
            }
            for row in cursor.fetchall()
        ]

    def get_usage_stats(self, limit: int = 10):
        """Get deck and spread usage counts.

        Args:
            limit: Maximum items per category (default 10)

        Returns:
            Dict with top_decks and top_spreads lists
        """
        cursor = self.conn.cursor()

        cursor.execute('''
            SELECT deck_name as name, COUNT(*) as count
            FROM entry_readings
            WHERE deck_name IS NOT NULL
            GROUP BY deck_name
            ORDER BY count DESC
            LIMIT ?
        ''', (limit,))
        top_decks = [
            {'name': row['name'], 'count': row['count']}
            for row in cursor.fetchall()
        ]

        cursor.execute('''
            SELECT spread_name as name, COUNT(*) as count
            FROM entry_readings
            WHERE spread_name IS NOT NULL
            GROUP BY spread_name
            ORDER BY count DESC
            LIMIT ?
        ''', (limit,))
        top_spreads = [
            {'name': row['name'], 'count': row['count']}
            for row in cursor.fetchall()
        ]

        return {
            'top_decks': top_decks,
            'top_spreads': top_spreads
        }
