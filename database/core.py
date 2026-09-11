"""
Database core: initialization, migrations, and transaction management.
"""

import atexit
import os
import re
import sqlite3
import threading
from contextlib import contextmanager

from logger_config import get_logger
from app_config import get_config

# Built-in cartomancy types, re-seeded (INSERT OR IGNORE) on every
# startup. Because deleting or renaming one would just resurrect it on
# the next launch, the in-app Deck Types manager only allows renaming
# and deleting types NOT in this list.
DEFAULT_TYPE_NAMES = [
    'Tarot', 'Petit Lenormand', 'Kipper', 'Playing Cards', 'Oracle', 'I Ching',
    'Playing Cards (Spanish)', 'Oracle Belline',
    'Vera Sibilla Italiana / Sibilla della Zingara',
    'Sibylle des Salons / Sibilla Indovina',
]

logger = get_logger('database')
_cfg = get_config()


_DIGITS_ONLY = re.compile(r'^\d+$')


def _numerology_reductions(value: str) -> list:
    """Mirror of frontend/src/utils/numerology.ts:numerologyReductions.

    Returns the digit-sum reduction chain for a numeric string (e.g.
    "156" -> ["12", "3"]). Non-numeric values return []. Single-digit
    inputs return [] since they're already irreducible.
    """
    if not value or not _DIGITS_ONLY.match(value) or len(value) <= 1:
        return []
    out = []
    current = value
    while len(current) > 1:
        current = str(sum(int(c) for c in current))
        out.append(current)
    return out


class CoreMixin:
    """Base mixin providing database initialization and transaction support."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = _cfg.get("paths", "database", "tarot_journal.db")
        self.db_path = db_path

        # Each Flask request thread gets its own sqlite3 connection.
        # A single shared connection across the threadpool causes
        # cursors and pending transactions from one request to bleed
        # into another, which manifested as "after using the app for
        # a while, entries and card-info pages start failing to load
        # until the app is restarted" — restart cleared the leaked
        # transaction state. With one connection per thread, sqlite's
        # own file-level locking + WAL handles concurrent access
        # safely, no cross-thread interference is possible.
        self._thread_state = threading.local()
        self._connection_registry: list[sqlite3.Connection] = []
        self._connection_registry_lock = threading.Lock()
        # Incremented when the DB file is swapped out from under us
        # (e.g. after a restore). Each per-thread connection caches
        # the epoch it was opened at; a mismatch invalidates the
        # cached connection so the next access opens a fresh one.
        self._connection_epoch = 0

        # Kept for the transaction() context manager, which is still
        # convenient for grouping multi-statement writes on the same
        # thread. SQLite handles cross-thread serialization itself.
        self._lock = threading.RLock()

        # Held (via db_swap_guard) while the .db file on disk is being
        # replaced during a backup restore. New per-thread connections
        # briefly acquire it before opening, so no thread can connect
        # to a half-copied database file mid-swap.
        self._db_swap_lock = threading.Lock()

        # Bootstrap the main thread's connection now so _create_tables
        # runs synchronously here (and any later background thread
        # opens its own connection on first access).
        _ = self.conn
        self._create_tables()

        # Ensure all per-thread connections are closed on exit.
        atexit.register(self.close)

    # === Per-thread connection management ===

    @property
    def conn(self) -> sqlite3.Connection:
        """Current thread's sqlite3 connection, lazily opened on
        first access. Each thread keeps its own; sqlite handles
        cross-connection coordination via WAL + busy_timeout."""
        existing = getattr(self._thread_state, 'conn', None)
        epoch = getattr(self._thread_state, 'epoch', -1)
        if existing is not None and epoch == self._connection_epoch:
            return existing
        return self._open_thread_connection()

    @conn.setter
    def conn(self, value: sqlite3.Connection) -> None:
        """Legacy assignment path used by import_export's restore
        flow. Registers the new connection so close() reaches it,
        and bumps the epoch so every other thread re-opens too."""
        self._thread_state.conn = value
        self._thread_state.epoch = self._connection_epoch
        if value is not None:
            with self._connection_registry_lock:
                if value not in self._connection_registry:
                    self._connection_registry.append(value)

    def _open_thread_connection(self) -> sqlite3.Connection:
        # Wait out any in-progress DB file swap (backup restore) so we
        # never open a connection against a half-copied file.
        with self._db_swap_lock:
            c = sqlite3.connect(self.db_path, check_same_thread=False)
        c.row_factory = sqlite3.Row
        # WAL is a database-level setting (persists once enabled), but
        # each fresh connection still needs FK enforcement + a sensible
        # busy_timeout so concurrent writers wait instead of erroring.
        try:
            c.execute('PRAGMA journal_mode=WAL')
        except sqlite3.DatabaseError:
            pass
        c.execute('PRAGMA foreign_keys = ON')
        c.execute('PRAGMA busy_timeout = 5000')
        self._thread_state.conn = c
        self._thread_state.epoch = self._connection_epoch
        with self._connection_registry_lock:
            self._connection_registry.append(c)
        return c

    @property
    def _in_transaction(self) -> bool:
        """Per-thread flag — each thread tracks its own transaction
        state since each thread has its own connection."""
        return getattr(self._thread_state, 'in_transaction', False)

    @_in_transaction.setter
    def _in_transaction(self, value: bool) -> None:
        self._thread_state.in_transaction = value

    def reopen_after_db_swap(self) -> None:
        """Call after the underlying .db file has been replaced (e.g.
        by a backup restore). Closes every per-thread connection that
        points at the old file and bumps the epoch so any thread that
        still holds a reference will lazy-reopen on next access. The
        caller does NOT need to reassign self.conn — the property
        will return a freshly-opened connection."""
        with self._connection_registry_lock:
            registered = list(self._connection_registry)
            self._connection_registry.clear()
        for c in registered:
            try:
                c.close()
            except Exception as e:
                logger.debug("Error closing pre-swap connection: %s", e)
        # Drop this thread's reference too.
        try:
            del self._thread_state.conn
        except AttributeError:
            pass
        self._connection_epoch += 1

    @contextmanager
    def db_swap_guard(self):
        """Serialize replacing the .db file on disk (backup restore).

        While the `with` block runs: every existing per-thread
        connection is closed, the epoch is bumped so other threads
        lazily reopen afterwards, and any thread trying to open a NEW
        connection blocks until the swap finishes — so nothing can
        connect to a half-copied database file.

        Stale -wal/-shm sidecars are also removed. They belong to the
        OLD database; if left behind, sqlite would try to replay the
        old write-ahead log against the newly restored file, which is
        a recipe for corruption.

        IMPORTANT: the body must only manipulate files on disk. It
        must not touch self.conn — that would try to open a connection
        and deadlock on this same lock.
        """
        with self._db_swap_lock:
            self.reopen_after_db_swap()
            self._remove_wal_sidecars()
            yield

    def _remove_wal_sidecars(self) -> None:
        """Delete leftover -wal/-shm files next to the database.

        Only call while all connections are closed (inside
        db_swap_guard) — deleting them under a live connection would
        itself corrupt the database.
        """
        for suffix in ('-wal', '-shm'):
            sidecar = f"{self.db_path}{suffix}"
            try:
                if os.path.exists(sidecar):
                    os.unlink(sidecar)
                    logger.info("Removed stale sidecar: %s", sidecar)
            except OSError as e:
                logger.warning("Could not remove sidecar %s: %s", sidecar, e)

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
                image_folder TEXT,
                suit_names TEXT,
                court_names TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        if 'favorite' not in columns:
            # Phone-sync prep: favorited decks are the subset whose
            # images sync to the iOS companion.
            cursor.execute('ALTER TABLE decks ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0')
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
        if 'variant_order' not in card_columns:
            # Optional within-name-group ordering used by the entry editor's
            # variant picker. Lets users reorder same-name cards (Terra
            # Volatile et al.) without touching card_order, which controls
            # deck display position.
            cursor.execute('ALTER TABLE cards ADD COLUMN variant_order INTEGER')

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

        # Migration: attribute a spread to a reference source
        if 'source_id' not in columns:
            cursor.execute('ALTER TABLE spreads ADD COLUMN source_id INTEGER')

        # Migration: add default_deck_id column for spread-specific default deck
        if 'default_deck_id' not in columns:
            cursor.execute('ALTER TABLE spreads ADD COLUMN default_deck_id INTEGER REFERENCES decks(id)')

        # Migration: archive flag — archived spreads are hidden from
        # the pickers and (by default) the spreads list, but never
        # deleted, so older entries that used them keep working.
        if 'archived' not in columns:
            cursor.execute('ALTER TABLE spreads ADD COLUMN archived INTEGER NOT NULL DEFAULT 0')

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
        if 'sync_uuid' not in columns:
            # Phone-sync prep: phone-created entries carry a client
            # UUID so offline pushes are idempotent. Desktop-created
            # entries leave it NULL.
            cursor.execute('ALTER TABLE journal_entries ADD COLUMN sync_uuid TEXT')
        if 'location_lon' not in columns:
            cursor.execute('ALTER TABLE journal_entries ADD COLUMN location_lon REAL')
        if 'breakdown_settings' not in columns:
            # Per-entry settings JSON for the Reading Breakdown panel:
            # { open: bool, last_tab: 'all' | <reading_id>,
            #   visible: { <field_name>: bool, ... } }
            cursor.execute('ALTER TABLE journal_entries ADD COLUMN breakdown_settings TEXT')

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
                notes TEXT,
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

        # Prompt presets: user-authored versions of the AI assistants'
        # system prompts (active choice lives in settings)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prompt_presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feature TEXT NOT NULL,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Spread tags table (separate namespace, like deck tags)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS spread_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                color TEXT DEFAULT '#6B5B95'
            )
        ''')

        # Spread tag assignments junction table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS spread_tag_assignments (
                spread_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (spread_id, tag_id),
                FOREIGN KEY (spread_id) REFERENCES spreads(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES spread_tags(id) ON DELETE CASCADE
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

        # Migration: add querent_only and hidden columns to profiles
        cursor.execute('PRAGMA table_info(profiles)')
        profile_columns = [col[1] for col in cursor.fetchall()]
        if 'querent_only' not in profile_columns:
            cursor.execute('ALTER TABLE profiles ADD COLUMN querent_only INTEGER DEFAULT 0')
        if 'hidden' not in profile_columns:
            cursor.execute('ALTER TABLE profiles ADD COLUMN hidden INTEGER DEFAULT 0')
        # Migration: full birth name (feeds name cards) + the user's
        # saved name-card adjustments (parts/roles/Y overrides, JSON)
        if 'full_name' not in profile_columns:
            cursor.execute('ALTER TABLE profiles ADD COLUMN full_name TEXT')
        if 'name_cards_config' not in profile_columns:
            cursor.execute('ALTER TABLE profiles ADD COLUMN name_cards_config TEXT')

        # Alternate names per profile (chosen names, nicknames) — each
        # runs through the name-cards calculator with its own parts and
        # Y adjustments. The birth name stays on profiles.full_name.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profile_names (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                name_kind TEXT NOT NULL DEFAULT 'other',
                display_name TEXT NOT NULL,
                parts TEXT,
                roles TEXT,
                y_mode TEXT DEFAULT 'heuristic',
                y_overrides TEXT,
                drop_suffixes INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            )
        ''')

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

        # Entry querents junction table (allows entries to have multiple querents)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entry_querents (
                entry_id INTEGER NOT NULL,
                profile_id INTEGER NOT NULL,
                position INTEGER DEFAULT 0,
                PRIMARY KEY (entry_id, profile_id),
                FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE,
                FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
            )
        ''')

        # Migrate existing querent_id values to entry_querents table
        cursor.execute('SELECT COUNT(*) FROM entry_querents')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT OR IGNORE INTO entry_querents (entry_id, profile_id, position)
                SELECT id, querent_id, 0 FROM journal_entries
                WHERE querent_id IS NOT NULL
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

        # One-time rename: "Spanish Playing Cards" → "Playing Cards (Spanish)".
        # The cartomancy type name is stored as a string in every table
        # that references it, so we update the cartomancy_types row plus
        # every other column that carries the name. Runs BEFORE the
        # default_types insert below so the new name's INSERT OR IGNORE
        # doesn't collide on UNIQUE (we'd end up with both rows). Each
        # UPDATE is wrapped in try/except OperationalError so tables that
        # don't exist on older schemas (e.g. source_fields was added
        # later) don't crash init. Idempotent — re-running on a DB that
        # never had the old name is a no-op.
        if self.get_setting('spanish_playing_cards_rename_done') != 'true':
            renames = [
                ('cartomancy_types', 'name'),
                ('card_archetypes', 'cartomancy_type'),
                ('spreads', 'cartomancy_type'),
                ('correspondence_systems', 'cartomancy_type'),
                ('reference_sources', 'cartomancy_type'),
                ('source_cartomancy_types', 'cartomancy_type'),
                ('source_fields', 'cartomancy_type'),
                ('archetype_combinations', 'cartomancy_type'),
            ]
            for table, column in renames:
                try:
                    cursor.execute(
                        f"UPDATE {table} SET {column} = 'Playing Cards (Spanish)' "
                        f"WHERE {column} = 'Spanish Playing Cards'"
                    )
                except sqlite3.OperationalError:
                    pass
            self.set_setting('spanish_playing_cards_rename_done', 'true')

        # One-time rename: "Vera Sibilla Italiana" → "Vera Sibilla
        # Italiana / Sibilla della Zingara". The Vera Sibilla and
        # Sibilla della Zingara decks share the same card structure
        # and divinatory names, so they're folded under a single
        # cartomancy type. Same shape as the rename block above —
        # runs BEFORE the default_types insert to avoid a UNIQUE
        # collision, idempotent across re-runs.
        if self.get_setting('vera_sibilla_zingara_rename_done') != 'true':
            renames = [
                ('cartomancy_types', 'name'),
                ('card_archetypes', 'cartomancy_type'),
                ('spreads', 'cartomancy_type'),
                ('correspondence_systems', 'cartomancy_type'),
                ('reference_sources', 'cartomancy_type'),
                ('source_cartomancy_types', 'cartomancy_type'),
                ('source_fields', 'cartomancy_type'),
                ('archetype_combinations', 'cartomancy_type'),
            ]
            for table, column in renames:
                try:
                    cursor.execute(
                        f"UPDATE {table} SET {column} = "
                        f"'Vera Sibilla Italiana / Sibilla della Zingara' "
                        f"WHERE {column} = 'Vera Sibilla Italiana'"
                    )
                except sqlite3.OperationalError:
                    pass
            self.set_setting('vera_sibilla_zingara_rename_done', 'true')

        # One-time rename: "Lenormand" → "Petit Lenormand" (distinguishes
        # the classic 36-card deck from Grand Jeu Lenormand). Same shape
        # as the rename blocks above. Afterwards, the archetypes' 1-36
        # card number in the rank field gives way to the playing-card
        # inset rank + suit (the number stays recoverable from the
        # curated inset table and the seeded id order).
        if self.get_setting('petit_lenormand_rename_done') != 'true':
            renames = [
                ('cartomancy_types', 'name'),
                ('card_archetypes', 'cartomancy_type'),
                ('spreads', 'cartomancy_type'),
                ('entries', 'cartomancy_type'),
                ('correspondence_systems', 'cartomancy_type'),
                ('reference_sources', 'cartomancy_type'),
                ('source_cartomancy_types', 'cartomancy_type'),
                ('source_fields', 'cartomancy_type'),
                ('archetype_combinations', 'cartomancy_type'),
            ]
            for table, column in renames:
                try:
                    cursor.execute(
                        f"UPDATE {table} SET {column} = 'Petit Lenormand' "
                        f"WHERE {column} = 'Lenormand'"
                    )
                except sqlite3.OperationalError:
                    pass
            # The default-deck setting is keyed by the type name.
            cursor.execute(
                "UPDATE settings SET key = 'default_deck_petit lenormand' "
                "WHERE key = 'default_deck_lenormand' AND NOT EXISTS "
                "(SELECT 1 FROM settings WHERE key = 'default_deck_petit lenormand')"
            )
            # Backfill inset rank + suit onto archetypes still carrying
            # their card number in rank.
            import reference_content as _rc
            for number, (rank_word, suit) in _rc.LENORMAND_INSETS.items():
                cursor.execute(
                    "UPDATE card_archetypes SET rank = ?, suit = ? "
                    "WHERE cartomancy_type = 'Petit Lenormand' AND rank = ?",
                    (rank_word, suit, str(number))
                )
            self.set_setting('petit_lenormand_rename_done', 'true')

        # One-time removal: the "Grand Etteilla Tarot" cartomancy type
        # was retired. Its import preset now lives under the Tarot
        # type. Clean up the seeded archetypes, the cartomancy_types
        # row, and any string references. If any decks were tagged
        # with the retired type (via deck_type_assignments), move
        # them to the Tarot row so no deck is left orphaned.
        # Idempotent — safe to re-run after the flag is set (the
        # queries all become no-ops).
        if self.get_setting('grand_etteilla_type_removal_done') != 'true':
            # Look up the source + target type ids up front.
            src_row = cursor.execute(
                "SELECT id FROM cartomancy_types WHERE name = 'Grand Etteilla Tarot'"
            ).fetchone()
            tar_row = cursor.execute(
                "SELECT id FROM cartomancy_types WHERE name = 'Tarot'"
            ).fetchone()
            src_id = src_row[0] if src_row else None
            tar_id = tar_row[0] if tar_row else None

            # Reassign the deck_type junction. INSERT OR IGNORE so a
            # deck already tagged Tarot doesn't hit the PK; then drop
            # any leftover Etteilla-tagged rows.
            if src_id is not None and tar_id is not None:
                try:
                    cursor.execute(
                        'INSERT OR IGNORE INTO deck_type_assignments '
                        '(deck_id, type_id) '
                        'SELECT deck_id, ? FROM deck_type_assignments '
                        'WHERE type_id = ?',
                        (tar_id, src_id)
                    )
                    cursor.execute(
                        'DELETE FROM deck_type_assignments WHERE type_id = ?',
                        (src_id,)
                    )
                except sqlite3.OperationalError:
                    pass

            # Rename any remaining string references in tables that
            # carry the type name as plain text. Wrapped in
            # try/except so schemas missing a table (older installs)
            # don't crash init.
            rename_targets = [
                ('spreads', 'cartomancy_type'),
                ('correspondence_systems', 'cartomancy_type'),
                ('reference_sources', 'cartomancy_type'),
                ('source_cartomancy_types', 'cartomancy_type'),
                ('source_fields', 'cartomancy_type'),
                ('archetype_combinations', 'cartomancy_type'),
            ]
            for table, column in rename_targets:
                try:
                    cursor.execute(
                        f"UPDATE {table} SET {column} = 'Tarot' "
                        f"WHERE {column} = 'Grand Etteilla Tarot'"
                    )
                except sqlite3.OperationalError:
                    pass

            # Delete the seeded archetype rows. Any authored source
            # entries or combinations FK'd to these rows cascade via
            # ON DELETE CASCADE. In the shipping DB this was 78 rows
            # with zero authored entries.
            cursor.execute(
                "DELETE FROM card_archetypes "
                "WHERE cartomancy_type = 'Grand Etteilla Tarot'"
            )
            # Finally drop the type row itself.
            cursor.execute(
                "DELETE FROM cartomancy_types WHERE name = 'Grand Etteilla Tarot'"
            )
            self.set_setting('grand_etteilla_type_removal_done', 'true')

        # Insert default cartomancy types
        for ct in DEFAULT_TYPE_NAMES:
            cursor.execute(
                'INSERT OR IGNORE INTO cartomancy_types (name) VALUES (?)',
                (ct,)
            )

        # Migration: populate junction table from legacy cartomancy_type_id, then drop column
        cursor.execute("PRAGMA table_info(decks)")
        deck_columns = [col[1] for col in cursor.fetchall()]
        if 'cartomancy_type_id' in deck_columns:
            # Ensure all decks have junction table entries before dropping
            cursor.execute('''
                INSERT OR IGNORE INTO deck_type_assignments (deck_id, type_id)
                SELECT id, cartomancy_type_id FROM decks
                WHERE cartomancy_type_id IS NOT NULL
            ''')
            # Can't use ALTER TABLE DROP COLUMN because the column has a FK constraint.
            # Rebuild the table without the column instead.
            cursor.execute('''
                CREATE TABLE decks_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    image_folder TEXT,
                    suit_names TEXT,
                    court_names TEXT,
                    date_published TEXT,
                    publisher TEXT,
                    credits TEXT,
                    notes TEXT,
                    card_back_image TEXT,
                    booklet_info TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Copy all non-legacy columns
            cursor.execute('''
                INSERT INTO decks_new (id, name, image_folder, suit_names, court_names,
                    date_published, publisher, credits, notes, card_back_image, booklet_info, created_at)
                SELECT id, name, image_folder, suit_names, court_names,
                    date_published, publisher, credits, notes, card_back_image, booklet_info, created_at
                FROM decks
            ''')
            # Must disable FK checks to drop a table referenced by other tables.
            # PRAGMA foreign_keys only takes effect outside transactions.
            self.conn.commit()
            self.conn.execute('PRAGMA foreign_keys = OFF')
            cursor.execute('DROP TABLE decks')
            cursor.execute('ALTER TABLE decks_new RENAME TO decks')
            self.conn.commit()
            self.conn.execute('PRAGMA foreign_keys = ON')

        # Migration: recreate correspondence tables when the CHECK constraint
        # is missing a newer field, or when source_group / unique-index changes
        # are needed for multi-value support.
        cursor.execute("SELECT sql FROM sqlite_master WHERE name='correspondence_assignments'")
        row = cursor.fetchone()
        needs_recreate = False
        if row:
            existing_sql = row[0] or ''
            if ('chakra' not in existing_sql
                    or 'source_group' not in existing_sql
                    or 'modality' not in existing_sql
                    or 'astrological_house' not in existing_sql):
                needs_recreate = True

        # Also check card_correspondence_overrides — drop the old UNIQUE(card_id, field_name)
        # constraint so card overrides can be multi-value, and add astrological_house.
        cursor.execute("SELECT sql FROM sqlite_master WHERE name='card_correspondence_overrides'")
        cco_row = cursor.fetchone()
        if cco_row:
            cco_sql = cco_row[0] or ''
            if ('UNIQUE(card_id, field_name)' in cco_sql
                    or 'astrological_house' not in cco_sql):
                needs_recreate = True

        # And deck_correspondence_overrides — needs to learn astrological_house too.
        cursor.execute("SELECT sql FROM sqlite_master WHERE name='deck_correspondence_overrides'")
        dco_row = cursor.fetchone()
        deck_overrides_needs_recreate = bool(
            dco_row and 'astrological_house' not in (dco_row[0] or '')
        )

        if needs_recreate:
            cursor.execute('SELECT * FROM correspondence_assignments')
            saved_assignments = [dict(r) for r in cursor.fetchall()]
            cursor.execute('SELECT * FROM card_correspondence_overrides')
            saved_overrides = [dict(r) for r in cursor.fetchall()]
            cursor.execute('DROP TABLE IF EXISTS correspondence_assignments')
            cursor.execute('DROP TABLE IF EXISTS card_correspondence_overrides')
            self._needs_corr_restore = (saved_assignments, saved_overrides)

        if deck_overrides_needs_recreate:
            cursor.execute('SELECT * FROM deck_correspondence_overrides')
            self._needs_deck_overrides_restore = [dict(r) for r in cursor.fetchall()]
            cursor.execute('DROP TABLE IF EXISTS deck_correspondence_overrides')

        # Correspondence systems (RWS, Thoth, Golden Dawn, user-defined)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS correspondence_systems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                is_builtin INTEGER DEFAULT 0,
                cartomancy_type TEXT DEFAULT 'Tarot',
                naming_style TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Migration: add columns if they're missing on older databases
        cursor.execute('PRAGMA table_info(correspondence_systems)')
        cs_cols = [c[1] for c in cursor.fetchall()]
        if 'cartomancy_type' not in cs_cols:
            cursor.execute("ALTER TABLE correspondence_systems ADD COLUMN cartomancy_type TEXT DEFAULT 'Tarot'")
        if 'naming_style' not in cs_cols:
            cursor.execute('ALTER TABLE correspondence_systems ADD COLUMN naming_style TEXT')

        # System-level correspondence assignments.
        # Multiple rows per (system, archetype, field) allowed — each tagged with
        # source_group so a card can have multiple values contributed by different
        # bulk groups (e.g. Page of Wands gets Fire from "Wands" and Earth from "Pages").
        # source_group IS NULL means an individual cell edit (not from a bulk group).
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS correspondence_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id INTEGER NOT NULL,
                archetype_id INTEGER NOT NULL,
                field_name TEXT NOT NULL CHECK(field_name IN (
                    'element', 'planet', 'zodiac_sign', 'decan',
                    'hebrew_letter', 'numerology', 'rune', 'i_ching_hexagram',
                    'chakra', 'modality', 'astrological_house'
                )),
                field_value TEXT NOT NULL,
                source_group TEXT,
                FOREIGN KEY (system_id) REFERENCES correspondence_systems(id) ON DELETE CASCADE,
                FOREIGN KEY (archetype_id) REFERENCES card_archetypes(id) ON DELETE CASCADE
            )
        ''')
        # Both NULL and non-NULL source groups can contribute multiple values
        # per cell (e.g. a manual edit can pick multiple zodiac signs). Unique
        # indexes include field_value so we only prevent exact duplicates.
        cursor.execute('DROP INDEX IF EXISTS idx_corr_assignments_unique_manual')
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_corr_assignments_unique_manual_value
            ON correspondence_assignments(system_id, archetype_id, field_name, field_value)
            WHERE source_group IS NULL
        ''')
        cursor.execute('DROP INDEX IF EXISTS idx_corr_assignments_unique_group')
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_corr_assignments_unique_group_value
            ON correspondence_assignments(system_id, archetype_id, field_name, source_group, field_value)
            WHERE source_group IS NOT NULL
        ''')

        # Card-level correspondence overrides (individual cards deviating from deck's system)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS card_correspondence_overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER NOT NULL,
                field_name TEXT NOT NULL CHECK(field_name IN (
                    'element', 'planet', 'zodiac_sign', 'decan',
                    'hebrew_letter', 'numerology', 'rune', 'i_ching_hexagram',
                    'chakra', 'modality', 'astrological_house'
                )),
                field_value TEXT,
                FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE
            )
        ''')
        # Unique constraint on (card, field, value) — card overrides can be
        # multi-value (e.g. Ace of Wands = Aries, Leo, Sagittarius); each
        # distinct value is its own row.
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_card_corr_overrides_unique_value
            ON card_correspondence_overrides(card_id, field_name, field_value)
        ''')

        # Deck-level correspondence overrides: sit between card overrides and
        # system assignments in the resolution order. Applied to all cards in
        # the deck with the given archetype.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deck_correspondence_overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deck_id INTEGER NOT NULL,
                archetype_id INTEGER NOT NULL,
                field_name TEXT NOT NULL CHECK(field_name IN (
                    'element', 'planet', 'zodiac_sign', 'decan',
                    'hebrew_letter', 'numerology', 'rune', 'i_ching_hexagram',
                    'chakra', 'modality', 'astrological_house'
                )),
                field_value TEXT,
                source_group TEXT,
                FOREIGN KEY (deck_id) REFERENCES decks(id) ON DELETE CASCADE,
                FOREIGN KEY (archetype_id) REFERENCES card_archetypes(id) ON DELETE CASCADE
            )
        ''')
        # Add source_group column if upgrading from a pre-source_group schema.
        # Drop any NULL-sourced legacy rows at the same time — pre-feature
        # individual-archetype overrides that the new UI can't surface.
        cursor.execute("PRAGMA table_info(deck_correspondence_overrides)")
        deck_ovr_cols = [r[1] for r in cursor.fetchall()]
        if 'source_group' not in deck_ovr_cols:
            cursor.execute(
                'ALTER TABLE deck_correspondence_overrides ADD COLUMN source_group TEXT'
            )
            cursor.execute(
                'DELETE FROM deck_correspondence_overrides WHERE source_group IS NULL'
            )
        # Unique index includes source_group so the same value from different
        # groups (e.g. Wands and Aces both setting Fire on Ace of Wands) can
        # coexist as independent contributions.
        cursor.execute('DROP INDEX IF EXISTS idx_deck_corr_overrides_unique_value')
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_deck_corr_overrides_unique_value
            ON deck_correspondence_overrides(deck_id, archetype_id, field_name, field_value, source_group)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_deck_corr_overrides_deck
            ON deck_correspondence_overrides(deck_id)
        ''')

        # Migration: recreate field options table when the CHECK constraint
        # is missing a newer field.
        cursor.execute("SELECT sql FROM sqlite_master WHERE name='correspondence_field_options'")
        fo_row = cursor.fetchone()
        if fo_row:
            fo_sql = fo_row[0] or ''
            if ('modality' not in fo_sql
                    or 'astrological_house' not in fo_sql):
                cursor.execute('SELECT * FROM correspondence_field_options')
                saved_options = [dict(r) for r in cursor.fetchall()]
                cursor.execute('DROP TABLE IF EXISTS correspondence_field_options')
                self._needs_options_restore = saved_options

        # Correspondence field options: the allowed values for each correspondence field
        # (Element, Planet, Zodiac, etc). Global list, shared across all systems.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS correspondence_field_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                field_name TEXT NOT NULL CHECK(field_name IN (
                    'element', 'planet', 'zodiac_sign', 'decan',
                    'hebrew_letter', 'numerology', 'rune', 'i_ching_hexagram',
                    'chakra', 'modality', 'astrological_house'
                )),
                option_value TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0,
                UNIQUE(field_name, option_value)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_corr_field_options_field ON correspondence_field_options(field_name, sort_order)')

        # Reference sources — shared across all Reference features (Lenormand
        # combinations, archetype notes, etc). Originally introduced as
        # `lenormand_sources` for the Lenormand combinations feature; renamed
        # in place so older databases pick up the new shape on next startup.
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lenormand_sources'")
        has_old_sources = cursor.fetchone() is not None
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reference_sources'")
        has_new_sources = cursor.fetchone() is not None
        if has_old_sources and not has_new_sources:
            cursor.execute('ALTER TABLE lenormand_sources RENAME TO reference_sources')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reference_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Add cartomancy_type column for the source-as-typed-field model.
        # NULL is allowed at the column level (older sources predate the
        # column) but the application layer requires it on new sources.
        cursor.execute('PRAGMA table_info(reference_sources)')
        rs_cols = [c[1] for c in cursor.fetchall()]
        if 'cartomancy_type' not in rs_cols:
            cursor.execute(
                'ALTER TABLE reference_sources ADD COLUMN cartomancy_type TEXT'
            )

        # Authors per source. Free-text names so a single registry isn't
        # required up front — duplicate names across sources are matched
        # by string equality if/when we want global author rollups later.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS source_authors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0,
                FOREIGN KEY (source_id) REFERENCES reference_sources(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_source_authors_source '
            'ON source_authors(source_id, sort_order)'
        )

        # Sources can cover multiple cartomancy types. The many-to-many
        # lives in source_cartomancy_types; reference_sources.cartomancy_type
        # is the pre-junction legacy column kept around so older code
        # paths don't crash mid-migration.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS source_cartomancy_types (
                source_id INTEGER NOT NULL,
                cartomancy_type TEXT NOT NULL,
                PRIMARY KEY (source_id, cartomancy_type),
                FOREIGN KEY (source_id) REFERENCES reference_sources(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_source_cartomancy_types_type '
            'ON source_cartomancy_types(cartomancy_type)'
        )

        # Fields defined within a source. Each field is scoped to a
        # specific cartomancy type so a book covering Tarot + Lenormand
        # can use different field sets per deck type. UNIQUE allows the
        # same field name (e.g. "Meaning") to repeat across types
        # within one source, but not within the same (source, type).
        # If the old (source_id, name) UNIQUE is on disk it's recreated
        # below in a one-shot migration.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS source_fields (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                cartomancy_type TEXT,
                name TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0,
                collapsible INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES reference_sources(id) ON DELETE CASCADE,
                UNIQUE (source_id, cartomancy_type, name)
            )
        ''')
        # Older DBs (this branch's prior commits) may be missing the
        # cartomancy_type or collapsible columns — add either before
        # the index/upserts later in this method reference them.
        cursor.execute('PRAGMA table_info(source_fields)')
        sf_cols = {c[1] for c in cursor.fetchall()}
        if 'cartomancy_type' not in sf_cols:
            cursor.execute('ALTER TABLE source_fields ADD COLUMN cartomancy_type TEXT')
        if 'collapsible' not in sf_cols:
            cursor.execute(
                'ALTER TABLE source_fields ADD COLUMN '
                'collapsible INTEGER NOT NULL DEFAULT 0'
            )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_source_fields_source '
            'ON source_fields(source_id, cartomancy_type, sort_order)'
        )

        # Per-(archetype, field) content. Rows exist only when the user
        # has authored something — empty content is the same as no row,
        # which is what the viewer's "absent = hidden" rule keys off of.
        # If an older single-source schema is on disk (field_id was
        # source_id), drop the table first so the new layout takes
        # effect. The dropping migration further down handles preserved
        # rows where possible.
        cursor.execute("PRAGMA table_info(archetype_source_entries)")
        existing_cols = {c[1] for c in cursor.fetchall()}
        if existing_cols and 'field_id' not in existing_cols:
            cursor.execute('DROP TABLE IF EXISTS archetype_source_entries')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS archetype_source_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                archetype_id INTEGER NOT NULL,
                field_id INTEGER NOT NULL,
                content TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (archetype_id) REFERENCES card_archetypes(id) ON DELETE CASCADE,
                FOREIGN KEY (field_id) REFERENCES source_fields(id) ON DELETE CASCADE,
                UNIQUE (archetype_id, field_id)
            )
        ''')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_archetype_source_entries_arch '
            'ON archetype_source_entries(archetype_id)'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_archetype_source_entries_field '
            'ON archetype_source_entries(field_id)'
        )

        # Per-(reference entity, source) notes: source texts attached
        # to non-card reference entities — signs, planets, sephiroth,
        # tree paths, chakras, numerology numbers. One content blob
        # per source per entity; blank content = no row (same
        # "absent = hidden" rule as archetype source entries).
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entity_source_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_kind TEXT NOT NULL,
                entity_key TEXT NOT NULL,
                source_id INTEGER NOT NULL,
                content TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES reference_sources(id) ON DELETE CASCADE,
                UNIQUE (entity_kind, entity_key, source_id)
            )
        ''')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_entity_source_notes_entity '
            'ON entity_source_notes(entity_kind, entity_key)'
        )

        # Combinations of two archetypes (any cartomancy type), each with
        # a list of authored meanings. Replaces the older Lenormand-only
        # tables (lenormand_combinations + lenormand_meanings). card_1 /
        # card_2 are archetype FKs; cartomancy_type is denormalized for
        # fast filtering in the picker UI. Rows are created on demand
        # when the first meaning is added to a pair.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS archetype_combinations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cartomancy_type TEXT NOT NULL,
                archetype_1_id INTEGER NOT NULL,
                archetype_1_reversed INTEGER NOT NULL DEFAULT 0,
                archetype_2_id INTEGER NOT NULL,
                archetype_2_reversed INTEGER NOT NULL DEFAULT 0,
                archetype_3_id INTEGER,
                archetype_3_reversed INTEGER NOT NULL DEFAULT 0,
                CHECK (archetype_1_id != archetype_2_id),
                CHECK (archetype_3_id IS NULL OR
                       (archetype_3_id != archetype_1_id AND archetype_3_id != archetype_2_id)),
                FOREIGN KEY (archetype_1_id) REFERENCES card_archetypes(id) ON DELETE CASCADE,
                FOREIGN KEY (archetype_2_id) REFERENCES card_archetypes(id) ON DELETE CASCADE,
                FOREIGN KEY (archetype_3_id) REFERENCES card_archetypes(id) ON DELETE CASCADE
            )
        ''')
        # Uniqueness split across partial indexes: NULLs are pairwise
        # distinct in SQLite unique constraints, so a single 7-column
        # UNIQUE would let duplicate two-card rows slip through.
        # Guarded on the column: an existing pre-three-card table lacks
        # archetype_3_id until its migration below rebuilds it (which
        # also creates these indexes).
        _combo_cols_now = [r[1] for r in cursor.execute(
            'PRAGMA table_info(archetype_combinations)').fetchall()]
        if 'archetype_3_id' in _combo_cols_now:
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS uq_combo_two
                ON archetype_combinations
                   (cartomancy_type, archetype_1_id, archetype_1_reversed,
                    archetype_2_id, archetype_2_reversed)
                WHERE archetype_3_id IS NULL
            ''')
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS uq_combo_three
                ON archetype_combinations
                   (cartomancy_type, archetype_1_id, archetype_1_reversed,
                    archetype_2_id, archetype_2_reversed,
                    archetype_3_id, archetype_3_reversed)
                WHERE archetype_3_id IS NOT NULL
            ''')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_archetype_combinations_type '
            'ON archetype_combinations(cartomancy_type)'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_archetype_combinations_pair '
            'ON archetype_combinations(archetype_1_id, archetype_2_id)'
        )

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS combination_meanings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                combination_id INTEGER NOT NULL,
                meaning TEXT NOT NULL,
                source_id INTEGER,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (combination_id) REFERENCES archetype_combinations(id) ON DELETE CASCADE,
                FOREIGN KEY (source_id) REFERENCES reference_sources(id) ON DELETE SET NULL
            )
        ''')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_combination_meanings_combination '
            'ON combination_meanings(combination_id, sort_order)'
        )

        # Migration: reversal flags join the combination key (a pair
        # with a reversed card is a different combination). SQLite
        # can't widen a UNIQUE constraint in place, so rebuild the
        # table. FK checks must be off while the old table drops —
        # combination_meanings cascades on delete, and with FKs on the
        # drop would take every authored meaning with it.
        combo_cols = [r[1] for r in cursor.execute(
            'PRAGMA table_info(archetype_combinations)').fetchall()]

        # Migration: third-card slot (three-card combinations). Another
        # rebuild — the inline five-column UNIQUE must give way to the
        # partial indexes above. Same FK-off dance as the reversal
        # migration (combination_meanings cascades on delete).
        if combo_cols and 'archetype_1_reversed' in combo_cols \
                and 'archetype_3_id' not in combo_cols:
            cursor.execute('''
                CREATE TABLE archetype_combinations_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cartomancy_type TEXT NOT NULL,
                    archetype_1_id INTEGER NOT NULL,
                    archetype_1_reversed INTEGER NOT NULL DEFAULT 0,
                    archetype_2_id INTEGER NOT NULL,
                    archetype_2_reversed INTEGER NOT NULL DEFAULT 0,
                    archetype_3_id INTEGER,
                    archetype_3_reversed INTEGER NOT NULL DEFAULT 0,
                    CHECK (archetype_1_id != archetype_2_id),
                    CHECK (archetype_3_id IS NULL OR
                           (archetype_3_id != archetype_1_id AND archetype_3_id != archetype_2_id)),
                    FOREIGN KEY (archetype_1_id) REFERENCES card_archetypes(id) ON DELETE CASCADE,
                    FOREIGN KEY (archetype_2_id) REFERENCES card_archetypes(id) ON DELETE CASCADE,
                    FOREIGN KEY (archetype_3_id) REFERENCES card_archetypes(id) ON DELETE CASCADE
                )
            ''')
            cursor.execute('''
                INSERT INTO archetype_combinations_new
                    (id, cartomancy_type, archetype_1_id, archetype_1_reversed,
                     archetype_2_id, archetype_2_reversed)
                SELECT id, cartomancy_type, archetype_1_id, archetype_1_reversed,
                       archetype_2_id, archetype_2_reversed
                FROM archetype_combinations
            ''')
            self.conn.commit()
            self.conn.execute('PRAGMA foreign_keys = OFF')
            cursor.execute('DROP TABLE archetype_combinations')
            cursor.execute(
                'ALTER TABLE archetype_combinations_new RENAME TO archetype_combinations')
            self.conn.commit()
            self.conn.execute('PRAGMA foreign_keys = ON')
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS uq_combo_two
                ON archetype_combinations
                   (cartomancy_type, archetype_1_id, archetype_1_reversed,
                    archetype_2_id, archetype_2_reversed)
                WHERE archetype_3_id IS NULL
            ''')
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS uq_combo_three
                ON archetype_combinations
                   (cartomancy_type, archetype_1_id, archetype_1_reversed,
                    archetype_2_id, archetype_2_reversed,
                    archetype_3_id, archetype_3_reversed)
                WHERE archetype_3_id IS NOT NULL
            ''')
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_archetype_combinations_type '
                'ON archetype_combinations(cartomancy_type)'
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_archetype_combinations_pair '
                'ON archetype_combinations(archetype_1_id, archetype_2_id)'
            )

        if combo_cols and 'archetype_1_reversed' not in combo_cols:
            cursor.execute('''
                CREATE TABLE archetype_combinations_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cartomancy_type TEXT NOT NULL,
                    archetype_1_id INTEGER NOT NULL,
                    archetype_1_reversed INTEGER NOT NULL DEFAULT 0,
                    archetype_2_id INTEGER NOT NULL,
                    archetype_2_reversed INTEGER NOT NULL DEFAULT 0,
                    CHECK (archetype_1_id != archetype_2_id),
                    UNIQUE (cartomancy_type, archetype_1_id, archetype_1_reversed,
                            archetype_2_id, archetype_2_reversed),
                    FOREIGN KEY (archetype_1_id) REFERENCES card_archetypes(id) ON DELETE CASCADE,
                    FOREIGN KEY (archetype_2_id) REFERENCES card_archetypes(id) ON DELETE CASCADE
                )
            ''')
            cursor.execute('''
                INSERT INTO archetype_combinations_new
                    (id, cartomancy_type, archetype_1_id, archetype_1_reversed,
                     archetype_2_id, archetype_2_reversed)
                SELECT id, cartomancy_type, archetype_1_id, 0, archetype_2_id, 0
                FROM archetype_combinations
            ''')
            # PRAGMA foreign_keys only takes effect outside transactions.
            self.conn.commit()
            self.conn.execute('PRAGMA foreign_keys = OFF')
            cursor.execute('DROP TABLE archetype_combinations')
            cursor.execute(
                'ALTER TABLE archetype_combinations_new RENAME TO archetype_combinations')
            self.conn.commit()
            self.conn.execute('PRAGMA foreign_keys = ON')
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_archetype_combinations_type '
                'ON archetype_combinations(cartomancy_type)'
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_archetype_combinations_pair '
                'ON archetype_combinations(archetype_1_id, archetype_2_id)'
            )

        # === Archetypes feature: per-archetype reference content ===
        # User-defined languages list (display order via sort_order).
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS archetype_language_languages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_archetype_languages_sort '
            'ON archetype_language_languages(sort_order)'
        )

        # Card names per (archetype, language). Multi-row per pair allowed —
        # romanization and ipa are optional metadata for each name.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS archetype_language_names (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                archetype_id INTEGER NOT NULL,
                language_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                romanization TEXT,
                ipa TEXT,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (archetype_id) REFERENCES card_archetypes(id) ON DELETE CASCADE,
                FOREIGN KEY (language_id) REFERENCES archetype_language_languages(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_archetype_lang_names_arch '
            'ON archetype_language_names(archetype_id, language_id, sort_order)'
        )

        # (Legacy archetype_notes_field_defs + archetype_notes_entries
        # tables were retired in favor of the source-as-typed-field model;
        # see the one-shot drop migration above.)

        # Astrological chart cache. One row per (profile|entry) source —
        # the SVG and structured chart_data are recomputed when input_hash
        # (date/time/lat/lon/house_system) changes, so changes to a profile's
        # birth fields automatically invalidate the cache on next view.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chart_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL CHECK (source_type IN ('profile', 'entry')),
                source_id INTEGER NOT NULL,
                house_system TEXT NOT NULL,
                chart_svg TEXT,
                chart_data TEXT,
                input_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (source_type, source_id)
            )
        ''')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_chart_cache_source '
            'ON chart_cache(source_type, source_id)'
        )

        # (Legacy lenormand_meanings restore step retired — both old
        # tables are dropped by the migration below in favor of the
        # generalized archetype_combinations / combination_meanings.)

        # Migration: add correspondence_system_id to decks
        cursor.execute("PRAGMA table_info(decks)")
        deck_cols = [col[1] for col in cursor.fetchall()]
        if 'correspondence_system_id' not in deck_cols:
            cursor.execute('''
                ALTER TABLE decks ADD COLUMN correspondence_system_id
                INTEGER REFERENCES correspondence_systems(id)
            ''')

        # Indexes for commonly queried foreign keys and search columns.
        # These speed up filtering, joining, and sorting as data grows.
        # "IF NOT EXISTS" means they're safe to run every startup.
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cards_deck_id ON cards(deck_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cards_card_order ON cards(deck_id, card_order)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_entry_readings_entry_id ON entry_readings(entry_id)')

        # Migration: per-reading notes (multi-spread entries get a
        # notes field per reading alongside the entry-level notes)
        reading_columns = [r[1] for r in cursor.execute(
            'PRAGMA table_info(entry_readings)').fetchall()]
        if reading_columns and 'notes' not in reading_columns:
            cursor.execute('ALTER TABLE entry_readings ADD COLUMN notes TEXT')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_entry_tags_entry_id ON entry_tags(entry_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_entry_tags_tag_id ON entry_tags(tag_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_deck_tag_assignments_deck_id ON deck_tag_assignments(deck_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_card_tag_assignments_card_id ON card_tag_assignments(card_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_card_group_assignments_card_id ON card_group_assignments(card_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_card_group_assignments_group_id ON card_group_assignments(group_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_card_groups_deck_id ON card_groups(deck_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_deck_type_assignments_deck_id ON deck_type_assignments(deck_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_follow_up_notes_entry_id ON follow_up_notes(entry_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_entry_querents_entry_id ON entry_querents(entry_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_journal_entries_created_at ON journal_entries(created_at DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_card_custom_fields_card_id ON card_custom_fields(card_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_deck_custom_fields_deck_id ON deck_custom_fields(deck_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_corr_assignments_system ON correspondence_assignments(system_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_corr_assignments_archetype ON correspondence_assignments(archetype_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_corr_assignments_field ON correspondence_assignments(field_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_card_corr_overrides_card ON card_correspondence_overrides(card_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_decks_corr_system ON decks(correspondence_system_id)')

        # Restore correspondence data after CHECK constraint migration
        if hasattr(self, '_needs_corr_restore'):
            saved_assignments, saved_overrides = self._needs_corr_restore
            # Temporarily disable FK checks — the referenced rows exist but
            # the table was just recreated so SQLite needs this
            self.conn.commit()
            self.conn.execute('PRAGMA foreign_keys = OFF')
            for a in saved_assignments:
                # Preserve existing source_group if present, else default to NULL
                source_group = a.get('source_group')
                cursor.execute('''
                    INSERT OR IGNORE INTO correspondence_assignments
                        (system_id, archetype_id, field_name, field_value, source_group)
                    VALUES (?, ?, ?, ?, ?)
                ''', (a['system_id'], a['archetype_id'], a['field_name'], a['field_value'], source_group))
            for o in saved_overrides:
                cursor.execute('''
                    INSERT OR IGNORE INTO card_correspondence_overrides
                        (card_id, field_name, field_value)
                    VALUES (?, ?, ?)
                ''', (o['card_id'], o['field_name'], o['field_value']))
            self.conn.commit()
            self.conn.execute('PRAGMA foreign_keys = ON')
            del self._needs_corr_restore

        # Restore field options after CHECK constraint migration
        if hasattr(self, '_needs_options_restore'):
            for o in self._needs_options_restore:
                cursor.execute('''
                    INSERT OR IGNORE INTO correspondence_field_options
                        (field_name, option_value, sort_order)
                    VALUES (?, ?, ?)
                ''', (o['field_name'], o['option_value'], o['sort_order']))
            del self._needs_options_restore

        # Restore deck-level overrides after CHECK constraint migration
        if hasattr(self, '_needs_deck_overrides_restore'):
            self.conn.commit()
            self.conn.execute('PRAGMA foreign_keys = OFF')
            for o in self._needs_deck_overrides_restore:
                cursor.execute('''
                    INSERT OR IGNORE INTO deck_correspondence_overrides
                        (deck_id, archetype_id, field_name, field_value, source_group)
                    VALUES (?, ?, ?, ?, ?)
                ''', (o['deck_id'], o['archetype_id'], o['field_name'],
                      o['field_value'], o.get('source_group')))
            self.conn.commit()
            self.conn.execute('PRAGMA foreign_keys = ON')
            del self._needs_deck_overrides_restore

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

            # Top-up: if a cartomancy type's archetypes were never seeded
            # (older DBs predate I Ching, Kipper, or Playing Cards (Spanish)),
            # run the seeder to add the missing ones. INSERT OR IGNORE
            # skips existing rows.
            cursor.execute(
                "SELECT COUNT(*) FROM card_archetypes WHERE cartomancy_type "
                "IN ('I Ching', 'Kipper', 'Playing Cards (Spanish)', "
                "    'Oracle Belline', 'Vera Sibilla Italiana / Sibilla della Zingara', "
                "    'Sibylle des Salons / Sibilla Indovina')"
            )
            # 64 I Ching + 36 Kipper + 49 Spanish + 53 Belline + 52 Sibilla
            # + 52 Sibylle = 306
            if cursor.fetchone()[0] < 306:
                self._seed_card_archetypes(cursor)

        # Seed correspondence systems if table is empty
        cursor.execute('SELECT COUNT(*) FROM correspondence_systems')
        if cursor.fetchone()[0] == 0:
            from database.correspondence_seed import seed_default_correspondences
            seed_default_correspondences(cursor)

        # One-time seed: built-in "I Ching Default" system mapping each
        # archetype to its hexagram. Guard with a setting so we don't
        # re-create it after a user deletes it.
        if self.get_setting('i_ching_default_seeded') != 'true':
            cursor.execute(
                "SELECT 1 FROM correspondence_systems WHERE name = 'I Ching Default'"
            )
            if not cursor.fetchone():
                from database.correspondence_seed import seed_i_ching_correspondences
                seed_i_ching_correspondences(cursor)
            self.set_setting('i_ching_default_seeded', 'true')

        # One-time repair: the original Lenormand -> Petit Lenormand
        # rename (above) worked from a hardcoded table list that
        # missed entry_readings and never looked inside spreads' JSON
        # columns (allowed_deck_types, deck_slots). Re-run the full
        # reference rename once with the complete machinery; exact
        # matching keeps 'Grand Jeu Lenormand' untouched, and on
        # already-clean databases this is a no-op.
        if self.get_setting('petit_lenormand_reference_repair_done') != 'true':
            self._rename_type_name_references(
                cursor, 'Lenormand', 'Petit Lenormand')
            self.set_setting('petit_lenormand_reference_repair_done', 'true')

        # One-time migration: rename legacy source_group labels (remove "All " prefix)
        if self.get_setting('source_group_label_migration_done') != 'true':
            legacy_rename = {
                'All Minor Arcana': 'Minor Arcana',
                'All Pages': 'Pages',
                'All Knights': 'Knights',
                'All Queens': 'Queens',
                'All Kings': 'Kings',
                'All Aces': 'Aces',
                'All Twos': 'Twos',
                'All Threes': 'Threes',
                'All Fours': 'Fours',
                'All Fives': 'Fives',
                'All Sixes': 'Sixes',
                'All Sevens': 'Sevens',
                'All Eights': 'Eights',
                'All Nines': 'Nines',
                'All Tens': 'Tens',
                'All Pips (Ace-10)': 'Pips (Ace-10)',
                'All Court Cards': 'Court Cards',
            }
            for old, new in legacy_rename.items():
                cursor.execute(
                    'UPDATE correspondence_assignments SET source_group = ? WHERE source_group = ?',
                    (new, old)
                )
            self.set_setting('source_group_label_migration_done', 'true')

        # Seed correspondence field options if table is empty, or if a newer
        # field's options haven't been added yet. INSERT OR IGNORE in the
        # seeder makes it safe to re-run.
        cursor.execute('SELECT COUNT(*) FROM correspondence_field_options')
        total_options = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM correspondence_field_options WHERE field_name = 'modality'")
        modality_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM correspondence_field_options WHERE field_name = 'astrological_house'")
        house_count = cursor.fetchone()[0]
        if total_options == 0 or modality_count == 0 or house_count == 0:
            from database.correspondence_seed import seed_field_options
            seed_field_options(cursor)

        # One-time migration: upgrade plain-numeric I Ching options to "N ䷀ Name" format.
        # Renames cascade to correspondence_assignments / card_correspondence_overrides.
        if self.get_setting('i_ching_hexagram_format_migration_done') != 'true':
            from database.correspondence_seed import I_CHING_HEXAGRAMS
            for i, new_value in enumerate(I_CHING_HEXAGRAMS, start=1):
                old_value = str(i)
                # Skip if the option is already in the new format
                cursor.execute(
                    "SELECT id, option_value FROM correspondence_field_options WHERE field_name = 'i_ching_hexagram' AND option_value = ?",
                    (old_value,)
                )
                row = cursor.fetchone()
                if not row:
                    continue
                opt_id = row['id']
                # Rename the option
                cursor.execute(
                    'UPDATE correspondence_field_options SET option_value = ? WHERE id = ?',
                    (new_value, opt_id)
                )
                # Cascade to assignments + overrides
                cursor.execute(
                    "UPDATE correspondence_assignments SET field_value = ? WHERE field_name = 'i_ching_hexagram' AND field_value = ?",
                    (new_value, old_value)
                )
                cursor.execute(
                    "UPDATE card_correspondence_overrides SET field_value = ? WHERE field_name = 'i_ching_hexagram' AND field_value = ?",
                    (new_value, old_value)
                )
            self.set_setting('i_ching_hexagram_format_migration_done', 'true')

        # One-time migration: collapse dual-named Tarot archetypes to canonical
        # RWS names so they match the card_archetypes table (the Thoth/Marseille
        # display name is applied at render time via naming_style).
        if self.get_setting('tarot_dual_archetype_migration_done') != 'true':
            dual_to_canonical = {
                'The Magician / The Magus': 'The Magician',
                'The High Priestess / The Priestess': 'The High Priestess',
                'Strength / Lust': 'Strength',
                'Wheel of Fortune / Fortune': 'Wheel of Fortune',
                'Justice / Adjustment': 'Justice',
                'Temperance / Art': 'Temperance',
                'Judgement / The Aeon': 'Judgement',
                'The World / The Universe': 'The World',
            }
            for old, new in dual_to_canonical.items():
                cursor.execute(
                    'UPDATE cards SET archetype = ? WHERE archetype = ?',
                    (new, old)
                )
            self.set_setting('tarot_dual_archetype_migration_done', 'true')

        # One-time migration: rewrite Thoth-suffixed minor-arcana archetypes
        # to their canonical RWS slot equivalents so they share an archetype
        # row with the same slot in any RWS deck. (See _get_tarot_metadata
        # for the matching slot mapping in newly-imported decks.)
        # Slot mapping: Princess→Page (11), Prince→Knight (12),
        #   Queen→Queen (13), Knight (Thoth)→King (14).
        # The card's display name (cards.name) is unchanged — it keeps the
        # Thoth label like "Prince of Wands". Only the archetype linkage is
        # canonicalized.
        if self.get_setting('tarot_thoth_archetype_canonical_migration_done') != 'true':
            thoth_rank_to_canonical = {
                'Princess': 'Page',
                'Prince': 'Knight',
                'Queen': 'Queen',
                'Knight': 'King',
            }
            suits = ['Wands', 'Cups', 'Swords', 'Pentacles']
            for thoth_rank, canonical_rank in thoth_rank_to_canonical.items():
                for suit in suits:
                    old_name = f'{thoth_rank} of {suit} (Thoth)'
                    new_name = f'{canonical_rank} of {suit}'
                    cursor.execute(
                        'UPDATE cards SET archetype = ? WHERE archetype = ?',
                        (new_name, old_name)
                    )
            self.set_setting('tarot_thoth_archetype_canonical_migration_done', 'true')

        # One-time migration: normalize Kipper archetypes to canonical names.
        # Some imported decks (Seaborn Kipper, Wahrsage Karten Original Kipper)
        # use slight variants of the standard Kipper card names — typos
        # ("High Honors" vs "High Honours"), synonyms ("Meeting" vs
        # "Rendezvous"), or shorter forms ("Court" vs "Judiciary"). The card's
        # display name (cards.name) is untouched; only the archetype linkage
        # column is canonicalized. Scoped to decks tagged as Kipper so a
        # similarly-spelled string in another cartomancy type isn't touched.
        if self.get_setting('kipper_archetype_normalization_done') != 'true':
            kipper_renames = {
                'Meeting': 'Rendezvous',
                'Gain Money': 'Lots of Money',
                'Rich Man': 'Rich Good Gentleman',
                'Official Person': 'Military Person',
                'High Honors': 'High Honours',
                'Expectation': 'Expectations',
                'Court': 'Judiciary',
                'Short Illness': 'Illness',
                'Work': 'Occupation',
            }
            for old_name, new_name in kipper_renames.items():
                cursor.execute(
                    '''
                    UPDATE cards SET archetype = ?
                    WHERE archetype = ?
                      AND deck_id IN (
                        SELECT d.id FROM decks d
                        JOIN deck_type_assignments dta ON dta.deck_id = d.id
                        JOIN cartomancy_types ct ON ct.id = dta.type_id
                        WHERE ct.name = 'Kipper'
                      )
                    ''',
                    (new_name, old_name)
                )
            self.set_setting('kipper_archetype_normalization_done', 'true')

        # One-time migration: normalize Playing Cards joker archetypes to
        # canonical Red Joker / Black Joker. Most decks store both jokers
        # with the bare archetype string "Joker", which matches neither
        # seeded row. Disambiguation rules, in order:
        #   1) display name contains "Red"   -> Red Joker
        #   2) display name contains "Black" -> Black Joker
        #   3) card_order = 1 -> Red Joker, card_order = 2 -> Black Joker
        # Scoped to Playing Cards decks. Man/Woman extras (Cartomancer
        # Clarity card_order 501/502) are left dangling — they're outside
        # the canonical 54-card vocabulary.
        if self.get_setting('playing_cards_joker_normalization_done') != 'true':
            cursor.execute(
                '''
                UPDATE cards SET archetype = 'Red Joker'
                WHERE archetype = 'Joker'
                  AND LOWER(name) LIKE '%red%'
                  AND deck_id IN (
                    SELECT d.id FROM decks d
                    JOIN deck_type_assignments dta ON dta.deck_id = d.id
                    JOIN cartomancy_types ct ON ct.id = dta.type_id
                    WHERE ct.name = 'Playing Cards'
                  )
                '''
            )
            cursor.execute(
                '''
                UPDATE cards SET archetype = 'Black Joker'
                WHERE archetype = 'Joker'
                  AND LOWER(name) LIKE '%black%'
                  AND deck_id IN (
                    SELECT d.id FROM decks d
                    JOIN deck_type_assignments dta ON dta.deck_id = d.id
                    JOIN cartomancy_types ct ON ct.id = dta.type_id
                    WHERE ct.name = 'Playing Cards'
                  )
                '''
            )
            # Positional fallback for color-neutral names (e.g. "Joker 1",
            # "Joker 2", or thematic replacements like Cartomancer Clarity's
            # Unconsciousness/Consciousness).
            for order, canonical in ((1, 'Red Joker'), (2, 'Black Joker')):
                cursor.execute(
                    '''
                    UPDATE cards SET archetype = ?
                    WHERE archetype = 'Joker'
                      AND card_order = ?
                      AND deck_id IN (
                        SELECT d.id FROM decks d
                        JOIN deck_type_assignments dta ON dta.deck_id = d.id
                        JOIN cartomancy_types ct ON ct.id = dta.type_id
                        WHERE ct.name = 'Playing Cards'
                      )
                    ''',
                    (canonical, order)
                )
            self.set_setting('playing_cards_joker_normalization_done', 'true')

        # One-time migration: consolidate separate Red Joker / Black Joker
        # archetypes into a single canonical "Joker" with variant_order
        # distinguishing them (1 = Red, 2 = Black). Transfers any FK
        # references (notes / correspondences / languages / deck overrides)
        # from the old archetype rows onto the new one, then deletes the
        # old rows. Same-name variants share an archetype's
        # notes/correspondences but can still be visually reordered via
        # the deck edit modal's Variants section.
        if self.get_setting('playing_cards_joker_consolidation_done') != 'true':
            cursor.execute(
                "INSERT OR IGNORE INTO card_archetypes (name, cartomancy_type, rank, suit, card_type) "
                "VALUES ('Joker', 'Playing Cards', 'Joker', NULL, 'playing')"
            )
            joker_id = cursor.execute(
                "SELECT id FROM card_archetypes WHERE name='Joker' AND cartomancy_type='Playing Cards'"
            ).fetchone()
            joker_id = joker_id[0] if joker_id else None

            old_ids = [
                r[0] for r in cursor.execute(
                    "SELECT id FROM card_archetypes "
                    "WHERE name IN ('Red Joker', 'Black Joker') "
                    "  AND cartomancy_type='Playing Cards'"
                ).fetchall()
            ]
            if joker_id is not None and old_ids:
                placeholders = ','.join('?' * len(old_ids))
                # Transfer FKs. INSERT OR IGNORE handles UNIQUE collisions
                # by keeping the existing (Joker) row, then we delete the
                # leftover old rows.
                for table in (
                    'correspondence_assignments',
                    'deck_correspondence_overrides',
                    'archetype_language_names',
                    # archetype_notes_field_defs was a target until the table
                    # was retired; the only DBs that ever ran this migration
                    # already finished with the flag set, so removing the
                    # entry can't strand existing data.
                ):
                    cursor.execute(
                        f'UPDATE OR IGNORE {table} SET archetype_id = ? '
                        f'WHERE archetype_id IN ({placeholders})',
                        [joker_id, *old_ids]
                    )
                    cursor.execute(
                        f'DELETE FROM {table} WHERE archetype_id IN ({placeholders})',
                        old_ids
                    )

            # Cards: Red Joker -> Joker var 1, Black Joker -> Joker var 2.
            cursor.execute(
                '''
                UPDATE cards SET archetype = 'Joker', variant_order = 1
                WHERE archetype = 'Red Joker'
                  AND deck_id IN (
                    SELECT d.id FROM decks d
                    JOIN deck_type_assignments dta ON dta.deck_id = d.id
                    JOIN cartomancy_types ct ON ct.id = dta.type_id
                    WHERE ct.name = 'Playing Cards'
                  )
                '''
            )
            cursor.execute(
                '''
                UPDATE cards SET archetype = 'Joker', variant_order = 2
                WHERE archetype = 'Black Joker'
                  AND deck_id IN (
                    SELECT d.id FROM decks d
                    JOIN deck_type_assignments dta ON dta.deck_id = d.id
                    JOIN cartomancy_types ct ON ct.id = dta.type_id
                    WHERE ct.name = 'Playing Cards'
                  )
                '''
            )

            if old_ids:
                placeholders = ','.join('?' * len(old_ids))
                cursor.execute(
                    f'DELETE FROM card_archetypes WHERE id IN ({placeholders})',
                    old_ids
                )

            self.set_setting('playing_cards_joker_consolidation_done', 'true')

        # One-time migration: stamp cartomancy_type on pre-existing
        # reference_sources rows (which predate the column). Best-effort
        # name-guessing — Lenormand if the name contains "lenormand",
        # Tarot otherwise. Users can re-assign in Settings if needed.
        if self.get_setting('reference_sources_cartomancy_type_backfill_done') != 'true':
            cursor.execute(
                "SELECT id, name FROM reference_sources WHERE cartomancy_type IS NULL"
            )
            for row in cursor.fetchall():
                name = (row['name'] or '').lower()
                if 'lenormand' in name or 'kipper' in name:
                    ctype = 'Petit Lenormand' if 'lenormand' in name else 'Kipper'
                elif 'iching' in name or 'i ching' in name or 'hexagram' in name:
                    ctype = 'I Ching'
                elif 'playing card' in name:
                    ctype = 'Playing Cards'
                else:
                    ctype = 'Tarot'
                cursor.execute(
                    'UPDATE reference_sources SET cartomancy_type = ? WHERE id = ?',
                    (ctype, row['id']),
                )
            self.set_setting('reference_sources_cartomancy_type_backfill_done', 'true')

        # One-time migration: drop the legacy archetype_notes_field_defs +
        # archetype_notes_entries tables. They've been replaced by the
        # source-as-typed-field model (archetype_source_entries). The user
        # had 0 authored entries when the change shipped — the only loss is
        # the two field-name placeholders that aliased the corresponding
        # reference_sources row.
        if self.get_setting('archetype_notes_tables_dropped') != 'true':
            cursor.execute('DROP TABLE IF EXISTS archetype_notes_entries')
            cursor.execute('DROP TABLE IF EXISTS archetype_notes_field_defs')
            self.set_setting('archetype_notes_tables_dropped', 'true')

        # One-time migration: sources go many-to-many with cartomancy types
        # via source_cartomancy_types, and source_fields get a per-field
        # cartomancy_type. Backfill both from the legacy single column on
        # reference_sources; any source/field stamped before this migration
        # gets exactly one type.
        if self.get_setting('source_multi_type_backfill_done') != 'true':
            cursor.execute('PRAGMA table_info(reference_sources)')
            rs_cols_now = {c[1] for c in cursor.fetchall()}
            if 'cartomancy_type' in rs_cols_now:
                cursor.execute(
                    'INSERT OR IGNORE INTO source_cartomancy_types '
                    '(source_id, cartomancy_type) '
                    "SELECT id, cartomancy_type FROM reference_sources "
                    'WHERE cartomancy_type IS NOT NULL AND TRIM(cartomancy_type) != ""'
                )
                cursor.execute(
                    'UPDATE source_fields SET cartomancy_type = ('
                    '  SELECT cartomancy_type FROM reference_sources '
                    '  WHERE reference_sources.id = source_fields.source_id'
                    ') WHERE cartomancy_type IS NULL'
                )
            self.set_setting('source_multi_type_backfill_done', 'true')

        # One-time migration: the old source_fields UNIQUE (source_id, name)
        # blocks the new (source_id, cartomancy_type, name) form. Rebuild
        # the table if the legacy constraint is still on disk.
        if self.get_setting('source_fields_unique_relaxed') != 'true':
            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='source_fields'"
            )
            sf_sql = cursor.fetchone()
            if sf_sql and 'UNIQUE (source_id, cartomancy_type, name)' not in (sf_sql[0] or ''):
                cursor.executescript('''
                    CREATE TABLE source_fields_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_id INTEGER NOT NULL,
                        cartomancy_type TEXT,
                        name TEXT NOT NULL,
                        sort_order INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (source_id) REFERENCES reference_sources(id) ON DELETE CASCADE,
                        UNIQUE (source_id, cartomancy_type, name)
                    );
                    INSERT INTO source_fields_new (id, source_id, cartomancy_type, name, sort_order, created_at)
                        SELECT id, source_id, cartomancy_type, name, sort_order, created_at
                        FROM source_fields;
                    DROP TABLE source_fields;
                    ALTER TABLE source_fields_new RENAME TO source_fields;
                    CREATE INDEX IF NOT EXISTS idx_source_fields_source
                        ON source_fields(source_id, cartomancy_type, sort_order);
                ''')
            self.set_setting('source_fields_unique_relaxed', 'true')

        # One-time migration: switch Belline compound names from period-
        # to comma-separated ("Thought. Friendship" -> "Thought, Friendship").
        # Both card_archetypes (so the viewer shows the new form) and
        # cards.archetype (so any imported deck cards stay linked) are
        # updated. Scoped to the Oracle Belline type to avoid touching
        # similarly-spelled names in other decks.
        if self.get_setting('belline_compound_name_rename_done') != 'true':
            belline_renames = {
                'Thought. Friendship': 'Thought, Friendship',
                'Countryside. Health': 'Countryside, Health',
                'Theft. Loss': 'Theft, Loss',
            }
            for old, new in belline_renames.items():
                cursor.execute(
                    'UPDATE OR IGNORE card_archetypes SET name = ? '
                    "WHERE name = ? AND cartomancy_type = 'Oracle Belline'",
                    (new, old)
                )
                cursor.execute(
                    'UPDATE cards SET archetype = ? WHERE archetype = ? '
                    'AND deck_id IN ('
                    '  SELECT d.id FROM decks d '
                    '  JOIN deck_type_assignments dta ON dta.deck_id = d.id '
                    '  JOIN cartomancy_types ct ON ct.id = dta.type_id '
                    "  WHERE ct.name = 'Oracle Belline'"
                    ')',
                    (new, old)
                )
            self.set_setting('belline_compound_name_rename_done', 'true')

        # One-time migration: drop the legacy Lenormand-only combinations
        # tables. Both were empty when the multi-type rewrite shipped (the
        # feature only ever surfaced UI for Lenormand and nobody authored
        # rows), so nothing user-facing is lost. The replacement tables
        # (archetype_combinations + combination_meanings) are created
        # unconditionally above.
        if self.get_setting('lenormand_combinations_tables_dropped') != 'true':
            cursor.execute('DROP TABLE IF EXISTS lenormand_meanings')
            cursor.execute('DROP TABLE IF EXISTS lenormand_combinations')
            self.set_setting('lenormand_combinations_tables_dropped', 'true')

        # One-time backfill: every existing numerology value should also have
        # its digit-sum reductions present (so "156" gains "12" and "3").
        # Going forward, the UI auto-expands new entries; this catches values
        # entered before that behavior existed. INSERT OR IGNORE relies on the
        # uniqueness constraints to skip reductions that already exist.
        if self.get_setting('numerology_reductions_backfill_done') != 'true':
            cursor.execute('''
                SELECT system_id, archetype_id, source_group, field_value
                FROM correspondence_assignments
                WHERE field_name = 'numerology'
            ''')
            for r in cursor.fetchall():
                for reduction in _numerology_reductions(r['field_value']):
                    cursor.execute('''
                        INSERT OR IGNORE INTO correspondence_assignments
                            (system_id, archetype_id, field_name, field_value, source_group)
                        VALUES (?, ?, 'numerology', ?, ?)
                    ''', (r['system_id'], r['archetype_id'], reduction, r['source_group']))
            cursor.execute('''
                SELECT deck_id, archetype_id, source_group, field_value
                FROM deck_correspondence_overrides
                WHERE field_name = 'numerology'
            ''')
            for r in cursor.fetchall():
                for reduction in _numerology_reductions(r['field_value']):
                    cursor.execute('''
                        INSERT OR IGNORE INTO deck_correspondence_overrides
                            (deck_id, archetype_id, field_name, field_value, source_group)
                        VALUES (?, ?, 'numerology', ?, ?)
                    ''', (r['deck_id'], r['archetype_id'], reduction, r['source_group']))
            cursor.execute('''
                SELECT card_id, field_value
                FROM card_correspondence_overrides
                WHERE field_name = 'numerology'
            ''')
            for r in cursor.fetchall():
                for reduction in _numerology_reductions(r['field_value']):
                    cursor.execute('''
                        INSERT OR IGNORE INTO card_correspondence_overrides
                            (card_id, field_name, field_value)
                        VALUES (?, 'numerology', ?)
                    ''', (r['card_id'], reduction))
            self.set_setting('numerology_reductions_backfill_done', 'true')

        self._commit()

        # Run one-time correspondence field migration (after commit so tables exist)
        from database.correspondence_migration import run_correspondence_migration
        run_correspondence_migration(self)

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
        # Rank/suit hold the traditional playing-card inset; the 1-36
        # number is the seeded order (and the inset table's key).
        import reference_content as _rc
        for name, number in lenormand_cards:
            inset_rank, inset_suit = _rc.LENORMAND_INSETS[int(number)]
            archetypes.append(
                (name, 'Petit Lenormand', inset_rank, inset_suit, 'lenormand'))

        # Playing Cards (54)
        playing_ranks = ['Ace', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven',
                         'Eight', 'Nine', 'Ten', 'Jack', 'Queen', 'King']
        playing_suits = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
        for suit in playing_suits:
            for rank in playing_ranks:
                name = f"{rank} of {suit}"
                archetypes.append((name, 'Playing Cards', rank, suit, 'playing'))

        # Jokers
        # One Joker archetype rather than separate Red/Black rows; deck-
        # specific cards distinguish themselves via variant_order
        # (1 = traditionally Red, 2 = traditionally Black).
        archetypes.append(('Joker', 'Playing Cards', 'Joker', None, 'playing'))

        # Playing Cards (Spanish) (50): 4 suits × 12 ranks + 1 Comodín
        # archetype (the deck's 2 physical Comodines share the slot via
        # variant_order, same pattern as the consolidated Joker above).
        spanish_ranks = [
            'As', 'Dos', 'Tres', 'Cuatro', 'Cinco', 'Seis', 'Siete',
            'Ocho', 'Nueve', 'Sota', 'Caballo', 'Rey',
        ]
        spanish_suits = ['Oros', 'Copas', 'Espadas', 'Bastos']
        for suit in spanish_suits:
            for rank in spanish_ranks:
                name = f'{rank} de {suit}'
                archetypes.append((name, 'Playing Cards (Spanish)', rank, suit, 'spanish-playing'))
        archetypes.append(('Comodín', 'Playing Cards (Spanish)', 'Comodín', None, 'spanish-playing'))

        # Oracle Belline (53). Position is the card's traditional number,
        # used as the rank string.
        belline_cards = [
            'Destiny', "The Man's Star", "The Woman's Star", 'Nativity',
            'Success', 'Elevation', 'Honours',
            'Thought, Friendship', 'Countryside, Health', 'Gifts',
            'Betrayal', 'Departure', 'Inconstancy', 'Discovery', 'Water',
            'The Home', 'Disease', 'Change', 'Money', 'Intelligence',
            'Theft, Loss', 'Undertakings', 'Trading', 'News', 'Pleasures',
            'Peace', 'Union', 'Family', 'Love', 'The Table',
            'Passions', 'Wickedness', 'Proceedings', 'Despotism',
            'Enemies', 'Negotiations', 'Fire', 'Accident', 'Support',
            'Beauty', 'Inheritance', 'Wisdom', 'Fame', 'Chance',
            'Happiness', 'Misfortune', 'Sterility', 'Fate', 'Gracefulness',
            'Ruin', 'Delay', 'Cloister', 'Blue Card',
        ]
        for i, name in enumerate(belline_cards, start=1):
            archetypes.append((name, 'Oracle Belline', str(i), None, 'belline'))

        # Vera Sibilla Italiana / Sibilla della Zingara (52). Each card is a standard playing-card
        # position (suit + rank) with a divinatory name. Suit/rank match
        # the Playing Cards convention so the underlying card structure
        # is preserved for sorting and any future correspondence sharing;
        # the archetype name is the divinatory term.
        sibilla_cards = [
            # Hearts
            ('Conversation', 'Hearts', 'Ace'),
            ('House', 'Hearts', 'Two'),
            ('Viewpoint', 'Hearts', 'Three'),
            ('Love', 'Hearts', 'Four'),
            ('Gladness of Heart', 'Hearts', 'Five'),
            ('Money', 'Hearts', 'Six'),
            ('Scholar', 'Hearts', 'Seven'),
            ('Hope', 'Hearts', 'Eight'),
            ('Loyalty', 'Hearts', 'Nine'),
            ('Constancy', 'Hearts', 'Ten'),
            ('Lover', 'Hearts', 'Jack'),
            ('Beloved', 'Hearts', 'Queen'),
            ('Gentleman', 'Hearts', 'King'),
            # Clubs
            ('Marriage', 'Clubs', 'Ace'),
            ('Pride', 'Clubs', 'Two'),
            ('Journey', 'Clubs', 'Three'),
            ('Friend', 'Clubs', 'Four'),
            ('Fortune', 'Clubs', 'Five'),
            ('Comforting Surprise', 'Clubs', 'Six'),
            ('Great Consolation', 'Clubs', 'Seven'),
            ('Reunion', 'Clubs', 'Eight'),
            ('Merriment', 'Clubs', 'Nine'),
            ('Levity', 'Clubs', 'Ten'),
            ('Servant', 'Clubs', 'Jack'),
            ('Young Woman', 'Clubs', 'Queen'),
            ('Doctor', 'Clubs', 'King'),
            # Diamonds
            ('Room', 'Diamonds', 'Ace'),
            ('Letter', 'Diamonds', 'Two'),
            ('Gift of Jewelry', 'Diamonds', 'Three'),
            ('Falsehood', 'Diamonds', 'Four'),
            ('Melancholy', 'Diamonds', 'Five'),
            ('Thoughts', 'Diamonds', 'Six'),
            ('Child', 'Diamonds', 'Seven'),
            ('Maid', 'Diamonds', 'Eight'),
            ('Madmen', 'Diamonds', 'Nine'),
            ('Thief', 'Diamonds', 'Ten'),
            ('Messenger', 'Diamonds', 'Jack'),
            ('Lady', 'Diamonds', 'Queen'),
            ('Merchant', 'Diamonds', 'King'),
            # Spades
            ('Sorrow', 'Spades', 'Ace'),
            ('Old Lady', 'Spades', 'Two'),
            ('Widower', 'Spades', 'Three'),
            ('Sickness', 'Spades', 'Four'),
            ('Death', 'Spades', 'Five'),
            ('Sighs', 'Spades', 'Six'),
            ('Misfortune', 'Spades', 'Seven'),
            ('Despair', 'Spades', 'Eight'),
            ('Prison', 'Spades', 'Nine'),
            ('Soldier', 'Spades', 'Ten'),
            ('Enemy', 'Spades', 'Jack'),
            ('Rival', 'Spades', 'Queen'),
            ('Priest', 'Spades', 'King'),
        ]
        for name, suit, rank in sibilla_cards:
            archetypes.append((name, 'Vera Sibilla Italiana / Sibilla della Zingara', rank, suit, 'sibilla'))

        # Sibylle des Salons / Sibilla Indovina (52). Same playing-card
        # structure as the Vera Sibilla but a different name-to-card
        # mapping and a different card ordering: each suit runs
        # King → Ace (not Ace → King), and the suits go
        # Clubs, Diamonds, Hearts, Spades. Divinatory names come from
        # the standard Grimaud / Lo Scarabeo Sibilla Indovina reading.
        sibylle_salons_cards = [
            # Clubs (1-13, King through Ace)
            ('Protector', 'Clubs', 'King'),
            ('A Sincere Friend', 'Clubs', 'Queen'),
            ('Flatterer', 'Clubs', 'Jack'),
            ('Success', 'Clubs', 'Ten'),
            ('Presents', 'Clubs', 'Nine'),
            ('Anger', 'Clubs', 'Eight'),
            ('Some Money/Small Gains', 'Clubs', 'Seven'),
            ('Enemy', 'Clubs', 'Six'),
            ('Victory', 'Clubs', 'Five'),
            ('Trip To The Country', 'Clubs', 'Four'),
            ('Hope', 'Clubs', 'Three'),
            ('Faithfulness, Affection', 'Clubs', 'Two'),
            ('A Lot Of Money', 'Clubs', 'Ace'),
            # Diamonds (14-26)
            ('Soldier', 'Diamonds', 'King'),
            ('Angry Woman', 'Diamonds', 'Queen'),
            ('Thief', 'Diamonds', 'Jack'),
            ('Journey', 'Diamonds', 'Ten'),
            ('Contrariety, Displeasure', 'Diamonds', 'Nine'),
            ('Impediment', 'Diamonds', 'Eight'),
            ('Chattering', 'Diamonds', 'Seven'),
            ('Absence', 'Diamonds', 'Six'),
            ('Reconciliation', 'Diamonds', 'Five'),
            ('Important Revelation', 'Diamonds', 'Four'),
            ('Consultant (M)', 'Diamonds', 'Three'),
            ('Pleasure, Pastime', 'Diamonds', 'Two'),
            ('A Letter', 'Diamonds', 'Ace'),
            # Hearts (27-39)
            ('Pensioner', 'Hearts', 'King'),
            ('Tenderness', 'Hearts', 'Queen'),
            ('Visit', 'Hearts', 'Jack'),
            ('Waiting', 'Hearts', 'Ten'),
            ('Surprise', 'Hearts', 'Nine'),
            ('A Blonde Woman', 'Hearts', 'Eight'),
            ('Thought/Reverie', 'Hearts', 'Seven'),
            ('Love', 'Hearts', 'Six'),
            ('Wedding', 'Hearts', 'Five'),
            ('City House', 'Hearts', 'Four'),
            ('Consultant (F)', 'Hearts', 'Three'),
            ('Country House', 'Hearts', 'Two'),
            ('Sweet Card', 'Hearts', 'Ace'),
            # Spades (40-52)
            ('Lawyer', 'Spades', 'King'),
            ('A Widow/Solitude', 'Spades', 'Queen'),
            ('Dark-Haired Man', 'Spades', 'Jack'),
            ('Infantilism/Sorrow', 'Spades', 'Ten'),
            ('Fright/Death', 'Spades', 'Nine'),
            ('Weakness', 'Spades', 'Eight'),
            ('Quarrel', 'Spades', 'Seven'),
            ('Inconstancy', 'Spades', 'Six'),
            ('Loss of Money', 'Spades', 'Five'),
            ('Dark-Haired Woman', 'Spades', 'Four'),
            ('Trap', 'Spades', 'Three'),
            ('Gamblers', 'Spades', 'Two'),
            ('Delay', 'Spades', 'Ace'),
        ]
        for name, suit, rank in sibylle_salons_cards:
            archetypes.append((
                name, 'Sibylle des Salons / Sibilla Indovina',
                rank, suit, 'sibylle-salons',
            ))

        # Kipper (36). Names match the import preset's
        # _get_kipper_metadata_by_position list so cards imported via that
        # preset find matching archetypes.
        kipper_cards = [
            'Main Male', 'Main Female', 'Marriage', 'Rendezvous', 'Good Gentleman',
            'Good Lady', 'Pleasant Letter', 'False Person', 'A Change', 'A Journey',
            'Lots of Money', 'Rich Girl', 'Rich Good Gentleman', 'Sad News',
            'Success in Love', 'His Thoughts', 'A Gift', 'A Small Child', 'A Funeral',
            'House', 'Living Room', 'Military Person', 'Court House', 'Theft',
            'High Honours', 'Great Fortune', 'Unexpected Money', 'Expectations',
            'Prison', 'Judiciary', 'Illness', 'Grief and Adversity', 'Gloomy Thoughts',
            'Occupation', 'A Long Way', 'Hope, Great Water',
        ]
        for i, name in enumerate(kipper_cards, start=1):
            archetypes.append((name, 'Kipper', str(i), None, 'kipper'))

        # I Ching (64 hexagrams). English names match the import preset's
        # short Wilhelm-Baynes form so cards imported via that preset find
        # matching archetypes.
        i_ching_names = [
            'The Creative', 'The Receptive', 'Difficulty at the Beginning',
            'Youthful Folly', 'Waiting', 'Conflict', 'The Army',
            'Holding Together', 'Small Taming', 'Treading', 'Peace',
            'Standstill', 'Fellowship', 'Great Possession', 'Modesty',
            'Enthusiasm', 'Following', 'Work on the Decayed', 'Approach',
            'Contemplation', 'Biting Through', 'Grace', 'Splitting Apart',
            'Return', 'Innocence', 'Great Taming', 'Nourishment',
            'Great Excess', 'The Abysmal', 'The Clinging', 'Influence',
            'Duration', 'Retreat', 'Great Power', 'Progress',
            'Darkening of the Light', 'The Family', 'Opposition',
            'Obstruction', 'Deliverance', 'Decrease', 'Increase',
            'Breakthrough', 'Coming to Meet', 'Gathering Together',
            'Pushing Upward', 'Oppression', 'The Well', 'Revolution',
            'The Cauldron', 'The Arousing', 'Keeping Still', 'Development',
            'The Marrying Maiden', 'Abundance', 'The Wanderer', 'The Gentle',
            'The Joyous', 'Dispersion', 'Limitation', 'Inner Truth',
            'Small Excess', 'After Completion', 'Before Completion',
        ]
        for i, name in enumerate(i_ching_names, start=1):
            archetypes.append((name, 'I Ching', str(i), None, 'i_ching'))

        # (Grand Etteilla archetypes intentionally NOT seeded — the
        # "Grand Etteilla Tarot" cartomancy type was retired; the
        # Grand Etteilla preset now lives under the Tarot type. See
        # the `grand_etteilla_type_removal_done` migration below,
        # which cleans up the seeded rows from earlier DB versions.)

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
        """Close every per-thread sqlite3 connection this Database
        has opened. Safe to call more than once. Runs a WAL
        checkpoint on the current thread's connection so the .db
        file is left in a clean, fully-merged state."""
        # Checkpoint via this thread's connection if we have one,
        # before closing anything.
        own_conn = getattr(self._thread_state, 'conn', None)
        if own_conn is not None:
            try:
                own_conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            except Exception as e:
                logger.debug("Error checkpointing WAL on close: %s", e)
        with self._connection_registry_lock:
            registered = list(self._connection_registry)
            self._connection_registry.clear()
        for c in registered:
            try:
                c.close()
            except Exception as e:
                logger.debug("Error closing a per-thread connection: %s", e)
        # Drop this thread's reference too so a later call doesn't
        # try to use the now-closed connection.
        try:
            del self._thread_state.conn
        except AttributeError:
            pass
