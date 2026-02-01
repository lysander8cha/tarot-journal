"""
Database operations for application settings and statistics.
"""

import json
from datetime import datetime, timedelta


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
        # Convert Row objects to tuples for JSON serialization
        stats['top_decks'] = [tuple(row) for row in cursor.fetchall()]

        # Most used spreads
        cursor.execute('''
            SELECT spread_name, COUNT(*) as count
            FROM entry_readings
            WHERE spread_name IS NOT NULL
            GROUP BY spread_name
            ORDER BY count DESC
            LIMIT 5
        ''')
        stats['top_spreads'] = [tuple(row) for row in cursor.fetchall()]

        return stats

    def get_card_frequency(self, limit: int = 20, deck_id: int = None):
        """Get frequency of cards appearing in readings.

        Parses the cards_used JSON from entry_readings and counts
        how often each card appears, including reversed counts.

        Args:
            limit: Maximum number of cards to return (default 20)
            deck_id: Optional deck ID to filter results

        Returns:
            List of dicts with name, count, reversed_count, deck_name
        """
        cursor = self.conn.cursor()

        # Build query with optional deck filter
        query = '''
            SELECT cards_used, deck_name, deck_id
            FROM entry_readings
            WHERE cards_used IS NOT NULL
        '''
        params = []
        if deck_id:
            query += ' AND deck_id = ?'
            params.append(deck_id)

        cursor.execute(query, params)

        # Aggregate card appearances in Python (SQLite JSON support is limited)
        # Key: (card_name, deck_name) -> {count, reversed_count}
        counts = {}

        for row in cursor.fetchall():
            try:
                cards = json.loads(row['cards_used'])
            except (json.JSONDecodeError, TypeError):
                continue

            deck_name = row['deck_name'] or 'Unknown Deck'

            for card in cards:
                if not isinstance(card, dict):
                    continue
                name = card.get('name', 'Unknown')
                key = (name, deck_name)

                if key not in counts:
                    counts[key] = {'count': 0, 'reversed_count': 0}

                counts[key]['count'] += 1
                if card.get('reversed'):
                    counts[key]['reversed_count'] += 1

        # Sort by count descending and limit
        sorted_cards = sorted(
            counts.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:limit]

        return [
            {
                'name': name,
                'deck_name': deck_name,
                'count': data['count'],
                'reversed_count': data['reversed_count']
            }
            for (name, deck_name), data in sorted_cards
        ]

    def get_extended_stats(self):
        """Get extended statistics for the Stats tab overview.

        Returns basic stats plus:
        - entries_this_month: Number of entries created this month
        - unique_cards_drawn: Total unique cards that have appeared in readings
        - total_readings: Total number of readings across all entries
        - avg_cards_per_reading: Average cards per reading
        """
        cursor = self.conn.cursor()

        # Start with basic stats
        stats = self.get_stats()

        # Entries this month
        first_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        cursor.execute(
            'SELECT COUNT(*) FROM journal_entries WHERE created_at >= ?',
            (first_of_month.isoformat(),)
        )
        stats['entries_this_month'] = cursor.fetchone()[0]

        # Total readings
        cursor.execute('SELECT COUNT(*) FROM entry_readings')
        stats['total_readings'] = cursor.fetchone()[0]

        # Unique cards drawn (count distinct card names across all readings)
        cursor.execute('SELECT cards_used FROM entry_readings WHERE cards_used IS NOT NULL')
        unique_cards = set()
        total_card_draws = 0

        for row in cursor.fetchall():
            try:
                cards = json.loads(row['cards_used'])
                for card in cards:
                    if isinstance(card, dict) and card.get('name'):
                        unique_cards.add(card['name'])
                        total_card_draws += 1
            except (json.JSONDecodeError, TypeError):
                continue

        stats['unique_cards_drawn'] = len(unique_cards)

        # Average cards per reading
        if stats['total_readings'] > 0:
            stats['avg_cards_per_reading'] = round(total_card_draws / stats['total_readings'], 1)
        else:
            stats['avg_cards_per_reading'] = 0

        return stats
