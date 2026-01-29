"""
Database core: initialization, migrations, and transaction management.
"""

import atexit
import sqlite3
import threading
from contextlib import contextmanager

from logger_config import get_logger
from app_config import get_config

logger = get_logger('database')
_cfg = get_config()


class CoreMixin:
    """Base mixin providing database initialization and transaction support."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = _cfg.get("paths", "database", "tarot_journal.db")
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._in_transaction = False

        # Thread safety: RLock allows the same thread to acquire multiple times
        # (important because DB methods call other DB methods)
        self._lock = threading.RLock()

        # WAL mode: allows reads during writes and protects against
        # data corruption if the app crashes mid-write
        self.conn.execute('PRAGMA journal_mode=WAL')

        self._create_tables()

        # Ensure the connection is closed if the app exits unexpectedly
        atexit.register(self.close)

    def _commit(self):
        """Commit unless inside a managed transaction (which commits at the end).

        Thread-safe: acquires lock before committing.
        """
        if not self._in_transaction:
            with self._lock:
                self.conn.commit()

    @contextmanager
    def transaction(self):
        """Wrap multiple operations in a single atomic transaction.

        If anything fails, all changes since the start are rolled back
        so the database never ends up in a half-finished state.

        Thread-safe: holds lock for entire transaction duration.
        """
        with self._lock:
            self._in_transaction = True
            try:
                yield
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise
            finally:
                self._in_transaction = False

    def _create_tables(self):
        cursor = self.conn.cursor()

        # Cartomancy types (tarot, lenormand, oracle)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cartomancy_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        ''')

        # Decks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS decks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                cartomancy_type_id INTEGER NOT NULL,
                image_folder TEXT,
                suit_names TEXT,
                court_names TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cartomancy_type_id) REFERENCES cartomancy_types(id)
            )
        ''')

        # Migration: add suit_names and court_names columns if missing
        cursor.execute("PRAGMA table_info(decks)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'suit_names' not in columns:
            cursor.execute('ALTER TABLE decks ADD COLUMN suit_names TEXT')
        if 'court_names' not in columns:
            cursor.execute('ALTER TABLE decks ADD COLUMN court_names TEXT')
        # Migration: add deck metadata columns
        if 'date_published' not in columns:
            cursor.execute('ALTER TABLE decks ADD COLUMN date_published TEXT')
        if 'publisher' not in columns:
            cursor.execute('ALTER TABLE decks ADD COLUMN publisher TEXT')
        if 'credits' not in columns:
            cursor.execute('ALTER TABLE decks ADD COLUMN credits TEXT')
        if 'notes' not in columns:
            cursor.execute('ALTER TABLE decks ADD COLUMN notes TEXT')
        if 'card_back_image' not in columns:
            cursor.execute('ALTER TABLE decks ADD COLUMN card_back_image TEXT')
        if 'booklet_info' not in columns:
            cursor.execute('ALTER TABLE decks ADD COLUMN booklet_info TEXT')

        # Cards table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deck_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                image_path TEXT,
                card_order INTEGER DEFAULT 0,
                archetype TEXT,
                rank TEXT,
                suit TEXT,
                notes TEXT,
                custom_fields TEXT,
                FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE CASCADE
            )
        ''')

        # Migration: add new columns to cards table if missing
        cursor.execute("PRAGMA table_info(cards)")
        card_columns = [col[1] for col in cursor.fetchall()]
        if 'archetype' not in card_columns:
            cursor.execute('ALTER TABLE cards ADD COLUMN archetype TEXT')
        if 'rank' not in card_columns:
            cursor.execute('ALTER TABLE cards ADD COLUMN rank TEXT')
        if 'suit' not in card_columns:
            cursor.execute('ALTER TABLE cards ADD COLUMN suit TEXT')
        if 'notes' not in card_columns:
            cursor.execute('ALTER TABLE cards ADD COLUMN notes TEXT')
        if 'custom_fields' not in card_columns:
            cursor.execute('ALTER TABLE cards ADD COLUMN custom_fields TEXT')

        # Spreads table (saved spread layouts)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS spreads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                positions JSON NOT NULL,
                cartomancy_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Migration: add cartomancy_type column if missing
        cursor.execute("PRAGMA table_info(spreads)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'cartomancy_type' not in columns:
            cursor.execute('ALTER TABLE spreads ADD COLUMN cartomancy_type TEXT')

        # Migration: add allowed_deck_types column for multi-deck-type spreads
        if 'allowed_deck_types' not in columns:
            cursor.execute('ALTER TABLE spreads ADD COLUMN allowed_deck_types TEXT')

        # Migration: add default_deck_id column for spread-specific default deck
        if 'default_deck_id' not in columns:
            cursor.execute('ALTER TABLE spreads ADD COLUMN default_deck_id INTEGER REFERENCES decks(id)')

        # Migration: add deck_slots column for multi-deck spreads
        if 'deck_slots' not in columns:
            cursor.execute('ALTER TABLE spreads ADD COLUMN deck_slots TEXT')

        # Journal entries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS journal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reading_datetime TIMESTAMP,
                location_name TEXT,
                location_lat REAL,
                location_lon REAL
            )
        ''')

        # Migrate journal_entries table if needed
        cursor.execute('PRAGMA table_info(journal_entries)')
        columns = [col[1] for col in cursor.fetchall()]
        if 'reading_datetime' not in columns:
            cursor.execute('ALTER TABLE journal_entries ADD COLUMN reading_datetime TIMESTAMP')
        if 'location_name' not in columns:
            cursor.execute('ALTER TABLE journal_entries ADD COLUMN location_name TEXT')
        if 'location_lat' not in columns:
            cursor.execute('ALTER TABLE journal_entries ADD COLUMN location_lat REAL')
        if 'location_lon' not in columns:
            cursor.execute('ALTER TABLE journal_entries ADD COLUMN location_lon REAL')

        # Entry readings (links entries to spreads and cards used)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entry_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id INTEGER NOT NULL,
                spread_id INTEGER,
                spread_name TEXT,
                deck_id INTEGER,
                deck_name TEXT,
                cartomancy_type TEXT,
                cards_used JSON,
                position_order INTEGER DEFAULT 0,
                FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE,
                FOREIGN KEY (spread_id) REFERENCES spreads(id),
                FOREIGN KEY (deck_id) REFERENCES decks(id)
            )
        ''')

        # Tags table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                color TEXT DEFAULT '#6B5B95'
            )
        ''')

        # Entry tags junction table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entry_tags (
                entry_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (entry_id, tag_id),
                FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
        ''')

        # Deck tags table (separate from entry tags)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deck_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                color TEXT DEFAULT '#6B5B95'
            )
        ''')

        # Deck tag assignments junction table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deck_tag_assignments (
                deck_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (deck_id, tag_id),
                FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES deck_tags(id) ON DELETE CASCADE
            )
        ''')

        # Card tags table (separate from deck tags)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS card_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                color TEXT DEFAULT '#6B5B95'
            )
        ''')

        # Card tag assignments junction table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS card_tag_assignments (
                card_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (card_id, tag_id),
                FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES card_tags(id) ON DELETE CASCADE
            )
        ''')

        # Card groups (per-deck custom groupings)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS card_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deck_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                color TEXT DEFAULT '#6B5B95',
                FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE CASCADE,
                UNIQUE(deck_id, name)
            )
        ''')

        # Card group assignments junction table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS card_group_assignments (
                card_id INTEGER NOT NULL,
                group_id INTEGER NOT NULL,
                PRIMARY KEY (card_id, group_id),
                FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
                FOREIGN KEY (group_id) REFERENCES card_groups(id) ON DELETE CASCADE
            )
        ''')

        # Migration: add sort_order to card_groups
        cursor.execute('PRAGMA table_info(card_groups)')
        columns = [col[1] for col in cursor.fetchall()]
        if 'sort_order' not in columns:
            cursor.execute('ALTER TABLE card_groups ADD COLUMN sort_order INTEGER DEFAULT 0')
            # Initialize sort_order for existing groups based on name order
            cursor.execute('SELECT id, deck_id FROM card_groups ORDER BY deck_id, name')
            rows = cursor.fetchall()
            current_deck = None
            pos = 0
            for row in rows:
                if row[1] != current_deck:
                    current_deck = row[1]
                    pos = 0
                cursor.execute('UPDATE card_groups SET sort_order = ? WHERE id = ?', (pos, row[0]))
                pos += 1

        # Deck type assignments junction table (allows decks to have multiple types)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deck_type_assignments (
                deck_id INTEGER NOT NULL,
                type_id INTEGER NOT NULL,
                PRIMARY KEY (deck_id, type_id),
                FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE CASCADE,
                FOREIGN KEY (type_id) REFERENCES cartomancy_types(id) ON DELETE CASCADE
            )
        ''')

        # Settings table for app preferences
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # Profiles table (for querent and reader information)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                gender TEXT,
                birth_date DATE,
                birth_time TIME,
                birth_place_name TEXT,
                birth_place_lat REAL,
                birth_place_lon REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Migration: add querent_only column to profiles
        cursor.execute('PRAGMA table_info(profiles)')
        profile_columns = [col[1] for col in cursor.fetchall()]
        if 'querent_only' not in profile_columns:
            cursor.execute('ALTER TABLE profiles ADD COLUMN querent_only INTEGER DEFAULT 0')

        # Migration: add querent_id and reader_id to journal_entries
        cursor.execute('PRAGMA table_info(journal_entries)')
        columns = [col[1] for col in cursor.fetchall()]
        if 'querent_id' not in columns:
            cursor.execute('ALTER TABLE journal_entries ADD COLUMN querent_id INTEGER REFERENCES profiles(id)')
        if 'reader_id' not in columns:
            cursor.execute('ALTER TABLE journal_entries ADD COLUMN reader_id INTEGER REFERENCES profiles(id)')

        # Follow-up notes table (for adding notes to entries after the fact)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS follow_up_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE
            )
        ''')

        # Card archetypes table (predefined standard card archetypes by type)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS card_archetypes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                cartomancy_type TEXT NOT NULL,
                rank TEXT,
                suit TEXT,
                card_type TEXT,
                UNIQUE(name, cartomancy_type)
            )
        ''')

        # Deck custom fields table (define custom fields per deck)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deck_custom_fields (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deck_id INTEGER NOT NULL,
                field_name TEXT NOT NULL,
                field_type TEXT NOT NULL,
                field_options TEXT,
                field_order INTEGER DEFAULT 0,
                FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE CASCADE
            )
        ''')

        # Card custom fields table (card-specific custom fields)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS card_custom_fields (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER NOT NULL,
                field_name TEXT NOT NULL,
                field_type TEXT NOT NULL,
                field_options TEXT,
                field_value TEXT,
                field_order INTEGER DEFAULT 0,
                FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE
            )
        ''')

        # Insert default cartomancy types
        default_types = ['Tarot', 'Lenormand', 'Kipper', 'Playing Cards', 'Oracle', 'I Ching']
        for ct in default_types:
            cursor.execute(
                'INSERT OR IGNORE INTO cartomancy_types (name) VALUES (?)',
                (ct,)
            )

        # Migrate existing deck types to junction table
        cursor.execute('SELECT COUNT(*) FROM deck_type_assignments')
        if cursor.fetchone()[0] == 0:
            # Junction table is empty - populate from existing cartomancy_type_id
            cursor.execute('''
                INSERT OR IGNORE INTO deck_type_assignments (deck_id, type_id)
                SELECT id, cartomancy_type_id FROM decks
                WHERE cartomancy_type_id IS NOT NULL
            ''')

        # Seed card archetypes if table is empty
        cursor.execute('SELECT COUNT(*) FROM card_archetypes')
        if cursor.fetchone()[0] == 0:
            self._seed_card_archetypes(cursor)
        else:
            # Migration: Update Tarot archetypes to new numbering schema
            # Check if migration is needed by looking at Ace of Wands rank
            cursor.execute('''
                SELECT rank FROM card_archetypes
                WHERE name = 'Ace of Wands' AND cartomancy_type = 'Tarot'
            ''')
            row = cursor.fetchone()
            if row and row[0] == 'Ace':  # Old schema used 'Ace', new uses '101'
                self._migrate_tarot_numbering(cursor)

        self._commit()

    def _seed_card_archetypes(self, cursor):
        """Seed the card_archetypes table with standard archetypes for all types.

        Numbering schema for Tarot:
        - Major Arcana: 0-21
        - Wands: 101-114 (Ace=101, Two=102, ... King=114)
        - Cups: 201-214
        - Swords: 301-314
        - Pentacles: 401-414
        """
        archetypes = []

        # Tarot - Major Arcana (22): numbered 0-21
        major_arcana = [
            ('The Fool', '0'), ('The Magician', '1'), ('The High Priestess', '2'),
            ('The Empress', '3'), ('The Emperor', '4'), ('The Hierophant', '5'),
            ('The Lovers', '6'), ('The Chariot', '7'), ('Strength', '8'),
            ('The Hermit', '9'), ('Wheel of Fortune', '10'), ('Justice', '11'),
            ('The Hanged Man', '12'), ('Death', '13'), ('Temperance', '14'),
            ('The Devil', '15'), ('The Tower', '16'), ('The Star', '17'),
            ('The Moon', '18'), ('The Sun', '19'), ('Judgement', '20'),
            ('The World', '21')
        ]
        for name, rank in major_arcana:
            archetypes.append((name, 'Tarot', rank, 'Major Arcana', 'major'))

        # Tarot - Minor Arcana (56)
        # Suit base numbers: Wands=100, Cups=200, Swords=300, Pentacles=400
        tarot_rank_names = ['Ace', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven',
                            'Eight', 'Nine', 'Ten', 'Page', 'Knight', 'Queen', 'King']
        tarot_suits = [('Wands', 100), ('Cups', 200), ('Swords', 300), ('Pentacles', 400)]
        for suit_name, suit_base in tarot_suits:
            for i, rank_name in enumerate(tarot_rank_names):
                name = f"{rank_name} of {suit_name}"
                rank_num = str(suit_base + i + 1)  # 101, 102, ... 114 for Wands
                archetypes.append((name, 'Tarot', rank_num, suit_name, 'minor'))

        # Lenormand (36)
        lenormand_cards = [
            ('Rider', '1'), ('Clover', '2'), ('Ship', '3'), ('House', '4'),
            ('Tree', '5'), ('Clouds', '6'), ('Snake', '7'), ('Coffin', '8'),
            ('Bouquet', '9'), ('Scythe', '10'), ('Whip', '11'), ('Birds', '12'),
            ('Child', '13'), ('Fox', '14'), ('Bear', '15'), ('Stars', '16'),
            ('Stork', '17'), ('Dog', '18'), ('Tower', '19'), ('Garden', '20'),
            ('Mountain', '21'), ('Crossroads', '22'), ('Mice', '23'), ('Heart', '24'),
            ('Ring', '25'), ('Book', '26'), ('Letter', '27'), ('Man', '28'),
            ('Woman', '29'), ('Lily', '30'), ('Sun', '31'), ('Moon', '32'),
            ('Key', '33'), ('Fish', '34'), ('Anchor', '35'), ('Cross', '36')
        ]
        for name, rank in lenormand_cards:
            archetypes.append((name, 'Lenormand', rank, None, 'lenormand'))

        # Playing Cards (54)
        playing_ranks = ['Ace', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven',
                         'Eight', 'Nine', 'Ten', 'Jack', 'Queen', 'King']
        playing_suits = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
        for suit in playing_suits:
            for rank in playing_ranks:
                name = f"{rank} of {suit}"
                archetypes.append((name, 'Playing Cards', rank, suit, 'playing'))

        # Jokers
        archetypes.append(('Red Joker', 'Playing Cards', 'Joker', None, 'playing'))
        archetypes.append(('Black Joker', 'Playing Cards', 'Joker', None, 'playing'))

        # Insert all archetypes
        cursor.executemany('''
            INSERT OR IGNORE INTO card_archetypes (name, cartomancy_type, rank, suit, card_type)
            VALUES (?, ?, ?, ?, ?)
        ''', archetypes)

    def _migrate_tarot_numbering(self, cursor):
        """Migrate Tarot archetypes from old naming schema to new numbering schema.

        Old schema: rank was 'Ace', 'Two', etc. and Roman numerals for Major Arcana
        New schema:
        - Major Arcana: 0-21
        - Wands: 101-114
        - Cups: 201-214
        - Swords: 301-314
        - Pentacles: 401-414
        """
        # Major Arcana: Roman numerals -> Arabic numbers
        major_updates = [
            ('0', 'The Fool'), ('1', 'The Magician'), ('2', 'The High Priestess'),
            ('3', 'The Empress'), ('4', 'The Emperor'), ('5', 'The Hierophant'),
            ('6', 'The Lovers'), ('7', 'The Chariot'), ('8', 'Strength'),
            ('9', 'The Hermit'), ('10', 'Wheel of Fortune'), ('11', 'Justice'),
            ('12', 'The Hanged Man'), ('13', 'Death'), ('14', 'Temperance'),
            ('15', 'The Devil'), ('16', 'The Tower'), ('17', 'The Star'),
            ('18', 'The Moon'), ('19', 'The Sun'), ('20', 'Judgement'),
            ('21', 'The World')
        ]
        for new_rank, name in major_updates:
            cursor.execute('''
                UPDATE card_archetypes SET rank = ?
                WHERE name = ? AND cartomancy_type = 'Tarot'
            ''', (new_rank, name))

        # Minor Arcana: rank names -> numbers with suit prefix
        rank_name_to_num = {
            'Ace': 1, 'Two': 2, 'Three': 3, 'Four': 4, 'Five': 5,
            'Six': 6, 'Seven': 7, 'Eight': 8, 'Nine': 9, 'Ten': 10,
            'Page': 11, 'Knight': 12, 'Queen': 13, 'King': 14
        }
        suit_bases = {'Wands': 100, 'Cups': 200, 'Swords': 300, 'Pentacles': 400}

        for suit_name, suit_base in suit_bases.items():
            for rank_name, rank_num in rank_name_to_num.items():
                new_rank = str(suit_base + rank_num)
                card_name = f"{rank_name} of {suit_name}"
                cursor.execute('''
                    UPDATE card_archetypes SET rank = ?
                    WHERE name = ? AND cartomancy_type = 'Tarot'
                ''', (new_rank, card_name))

    def close(self):
        """Close the database connection (safe to call more than once)."""
        if self.conn:
            try:
                self.conn.close()
            except Exception as e:
                logger.debug("Error closing database connection: %s", e)
            self.conn = None
