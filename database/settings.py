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
        # Key by card name only, so the same card across different decks
        # is combined into one count
        counts = {}

        for row in cursor.fetchall():
            try:
                cards = json.loads(row['cards_used'])
            except (json.JSONDecodeError, TypeError):
                continue

            for card in cards:
                if not isinstance(card, dict):
                    continue
                name = card.get('name', 'Unknown')

                if name not in counts:
                    counts[name] = {'count': 0, 'reversed_count': 0}

                counts[name]['count'] += 1
                if card.get('reversed'):
                    counts[name]['reversed_count'] += 1

        # Sort by count descending and limit
        sorted_cards = sorted(
            counts.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:limit]

        return [
            {
                'name': name,
                'count': data['count'],
                'reversed_count': data['reversed_count']
            }
            for name, data in sorted_cards
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

    def get_timeline_stats(self, limit: int = 12):
        """Get entry and reading counts grouped by month.

        Returns data in chronological order (oldest first) so charts
        read left-to-right over time.

        Args:
            limit: Number of months to return (default 12)

        Returns:
            List of dicts with period, entries, readings
        """
        cursor = self.conn.cursor()

        # Count entries per month
        cursor.execute('''
            SELECT strftime('%Y-%m', created_at) as period,
                   COUNT(*) as entries
            FROM journal_entries
            GROUP BY period
            ORDER BY period DESC
            LIMIT ?
        ''', (limit,))
        entries_by_month = {row['period']: row['entries'] for row in cursor.fetchall()}

        # Count readings per month (via their parent entry's date)
        cursor.execute('''
            SELECT strftime('%Y-%m', je.created_at) as period,
                   COUNT(er.id) as readings
            FROM journal_entries je
            JOIN entry_readings er ON je.id = er.entry_id
            GROUP BY period
            ORDER BY period DESC
            LIMIT ?
        ''', (limit,))
        readings_by_month = {row['period']: row['readings'] for row in cursor.fetchall()}

        # Combine into a single list, sorted chronologically
        all_periods = sorted(
            set(entries_by_month.keys()) | set(readings_by_month.keys())
        )
        # Take only the most recent `limit` periods
        all_periods = all_periods[-limit:]

        return [
            {
                'period': p,
                'entries': entries_by_month.get(p, 0),
                'readings': readings_by_month.get(p, 0)
            }
            for p in all_periods
        ]

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
