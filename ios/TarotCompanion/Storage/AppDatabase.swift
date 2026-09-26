import Foundation
import GRDB

/// The phone's local mirror of the synced subset of the desktop
/// database. Schema names match the desktop tables so the sync code
/// can write snapshot rows straight in.
struct AppDatabase {
    let writer: DatabaseWriter

    static func open() throws -> AppDatabase {
        let folder = try FileManager.default.url(
            for: .applicationSupportDirectory, in: .userDomainMask,
            appropriateFor: nil, create: true)
        let dbURL = folder.appendingPathComponent("companion.sqlite")
        let writer = try DatabasePool(path: dbURL.path)
        let db = AppDatabase(writer: writer)
        try db.migrate()
        return db
    }

    /// In-memory database for previews and tests.
    static func empty() throws -> AppDatabase {
        let db = AppDatabase(writer: try DatabaseQueue())
        try db.migrate()
        return db
    }

    private func migrate() throws {
        var migrator = DatabaseMigrator()

        migrator.registerMigration("v1") { db in
            // ── Snapshot tables (mirrored wholesale each sync) ──
            try db.create(table: "decks") { t in
                t.primaryKey("id", .integer)
                t.column("name", .text).notNull()
                t.column("favorite", .integer).notNull().defaults(to: 0)
            }
            try db.create(table: "cards") { t in
                t.primaryKey("id", .integer)
                t.column("deck_id", .integer).notNull().indexed()
                t.column("name", .text).notNull()
                t.column("archetype", .text)
                t.column("rank", .text)
                t.column("suit", .text)
                t.column("card_order", .integer)
            }
            try db.create(table: "spreads") { t in
                t.primaryKey("id", .integer)
                t.column("name", .text).notNull()
                t.column("description", .text)
                t.column("positions", .text)          // JSON, as on desktop
                t.column("deck_slots", .text)
                t.column("allowed_deck_types", .text)
                t.column("archived", .integer)
            }
            try db.create(table: "profiles") { t in
                t.primaryKey("id", .integer)
                t.column("name", .text).notNull()
                t.column("hidden", .integer)
            }
            try db.create(table: "tags") { t in
                t.primaryKey("id", .integer)
                t.column("name", .text).notNull()
                t.column("color", .text)
            }
            try db.create(table: "reference_sources") { t in
                t.primaryKey("id", .integer)
                t.column("name", .text).notNull()
                t.column("cartomancy_type", .text)
            }
            try db.create(table: "source_fields") { t in
                t.primaryKey("id", .integer)
                t.column("source_id", .integer).indexed()
                t.column("cartomancy_type", .text)
                t.column("name", .text)
                t.column("sort_order", .integer)
                t.column("collapsible", .integer)
            }
            try db.create(table: "card_archetypes") { t in
                t.primaryKey("id", .integer)
                t.column("name", .text).notNull()
                t.column("cartomancy_type", .text)
                t.column("rank", .text)
                t.column("suit", .text)
            }

            // ── Delta tables (entry aggregates, source texts) ──
            try db.create(table: "entries") { t in
                t.primaryKey("id", .integer)
                t.column("title", .text)
                t.column("content", .text)
                t.column("created_at", .text)
                t.column("updated_at", .text).indexed()
                t.column("reading_datetime", .text)
                t.column("location_name", .text)
                t.column("querent_id", .integer)
                t.column("reader_id", .integer)
                t.column("sync_uuid", .text)
                // Children of the aggregate, stored as JSON blobs —
                // the phone only reads them, so relational child
                // tables would be complexity without payoff.
                t.column("readings_json", .text)
                t.column("tag_ids_json", .text)
                t.column("querent_ids_json", .text)
                t.column("follow_ups_json", .text)
            }
            try db.create(table: "source_entries") { t in
                t.primaryKey("id", .integer)
                t.column("archetype_id", .integer).indexed()
                t.column("field_id", .integer).indexed()
                t.column("content", .text)
                t.column("updated_at", .text)
            }

            // ── Sync bookkeeping ──
            try db.create(table: "sync_state") { t in
                t.primaryKey("key", .text)
                t.column("value", .text)
            }
        }

        migrator.registerMigration("v2-outbox") { db in
            // Entries composed on the phone wait here until the Mac
            // is reachable; each row is one push-entry payload.
            try db.create(table: "pending_entries") { t in
                t.autoIncrementedPrimaryKey("id")
                t.column("payload_json", .text).notNull()
                t.column("created_at", .text)
            }
        }

        migrator.registerMigration("v3-card-info") { db in
            // Card notes + per-deck custom fields now sync so the
            // card-info screen can show them. Registered after
            // v2-outbox: phones in the field have already applied it,
            // and migrations must only ever be appended.
            try db.alter(table: "cards") { t in
                t.add(column: "notes", .text)
                t.add(column: "custom_fields", .text)
            }
        }

        migrator.registerMigration("v4-whole-reference") { db in
            // The rest of the desktop's Reference section: card
            // combinations, entity notes (signs, sephiroth, suits…),
            // and the server-built entity catalog for browsing.
            try db.create(table: "archetype_combinations") { t in
                t.primaryKey("id", .integer)
                t.column("cartomancy_type", .text)
                t.column("archetype_1_id", .integer).indexed()
                t.column("archetype_1_reversed", .integer)
                t.column("archetype_2_id", .integer).indexed()
                t.column("archetype_2_reversed", .integer)
                t.column("archetype_3_id", .integer)
                t.column("archetype_3_reversed", .integer)
            }
            try db.create(table: "combination_meanings") { t in
                t.primaryKey("id", .integer)
                t.column("combination_id", .integer).indexed()
                t.column("meaning", .text)
                t.column("source_id", .integer)
                t.column("sort_order", .integer)
            }
            try db.create(table: "entity_source_notes") { t in
                t.primaryKey("id", .integer)
                t.column("entity_kind", .text).indexed()
                t.column("entity_key", .text)
                t.column("source_id", .integer)
                t.column("content", .text)
            }
            try db.create(table: "reference_entities") { t in
                t.primaryKey("id", .integer)
                t.column("kind", .text).indexed()
                t.column("key", .text)
                t.column("name", .text)
                t.column("subtitle", .text)
                t.column("cartomancy_type", .text)
                t.column("sort", .integer)
            }
        }

        migrator.registerMigration("v5-correspondences") { db in
            try db.create(table: "correspondence_systems") { t in
                t.primaryKey("id", .integer)
                t.column("name", .text)
                t.column("cartomancy_type", .text)
            }
            try db.create(table: "correspondence_assignments") { t in
                t.primaryKey("id", .integer)
                t.column("system_id", .integer).indexed()
                t.column("archetype_id", .integer).indexed()
                t.column("field_name", .text)
                t.column("field_value", .text)
            }
        }

        migrator.registerMigration("v6-deck-system") { db in
            // The card page shows only the deck's chosen system
            // (plus per-card overrides), matching the desktop's
            // resolution: override → deck's system → nothing.
            try db.alter(table: "decks") { t in
                t.add(column: "correspondence_system_id", .integer)
            }
            try db.create(table: "card_correspondence_overrides") { t in
                t.primaryKey("id", .integer)
                t.column("card_id", .integer).indexed()
                t.column("field_name", .text)
                t.column("field_value", .text)
            }
        }

        migrator.registerMigration("v7-reader") { db in
            // Readers exclude querent-only profiles, so the flag
            // syncs along for the composer's Reader picker.
            try db.alter(table: "profiles") { t in
                t.add(column: "querent_only", .integer)
            }
        }

        try migrator.migrate(writer)
    }

    #if DEBUG
    /// Deterministic "ZZ" fixtures for the composer UI test: a small
    /// deck, a three-card spread, and two profiles replace whatever
    /// synced data the simulator holds (the next normal launch just
    /// re-syncs it). Never compiled into release builds.
    func seedForComposerUITest() throws {
        try writer.write { db in
            try db.execute(sql: """
                DELETE FROM pending_entries;
                DELETE FROM decks;
                DELETE FROM cards;
                DELETE FROM spreads;
                DELETE FROM profiles;
                INSERT INTO decks (id, name, favorite)
                    VALUES (9001, 'ZZ UITest Deck', 0);
                INSERT INTO cards (id, deck_id, name, card_order) VALUES
                    (9101, 9001, 'ZZ Card One', 1),
                    (9102, 9001, 'ZZ Card Two', 2),
                    (9103, 9001, 'ZZ Card Three', 3);
                INSERT INTO spreads (id, name, positions, archived) VALUES (9201,
                    'ZZ Three Card',
                    '[{"x":0,"y":0,"width":100,"height":160,"label":"Past"},
                      {"x":110,"y":0,"width":100,"height":160,"label":"Present"},
                      {"x":220,"y":0,"width":100,"height":160,"label":"Future"}]',
                    0);
                INSERT INTO profiles (id, name, hidden, querent_only) VALUES
                    (9301, 'ZZ Querent', 0, 1),
                    (9302, 'ZZ Reader', 0, 0);
                """)
        }
    }
    #endif

    // MARK: - Sync-state helpers

    func syncState(_ key: String) throws -> String? {
        try writer.read { db in
            try String.fetchOne(
                db, sql: "SELECT value FROM sync_state WHERE key = ?",
                arguments: [key])
        }
    }

    func setSyncState(_ key: String, _ value: String?) throws {
        try writer.write { db in
            if let value {
                try db.execute(
                    sql: "INSERT OR REPLACE INTO sync_state (key, value) VALUES (?, ?)",
                    arguments: [key, value])
            } else {
                try db.execute(
                    sql: "DELETE FROM sync_state WHERE key = ?",
                    arguments: [key])
            }
        }
    }
}
