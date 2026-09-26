import Foundation
import GRDB

/// Talks to the desktop app's /api/sync/ endpoints and mirrors the
/// results into the local database.
///
/// Protocol (Phase 0, desktop side):
///   GET  /api/sync/manifest          — counts + max timestamps
///   GET  /api/sync/snapshot/<table>  — full rows for small tables
///   GET  /api/sync/entries?since=    — changed aggregates + full ID list
///   GET  /api/sync/source-entries?since=
///   GET  /api/sync/card-image/<id>   — phone-sized image
///   POST /api/sync/pair              — pairing code -> bearer token
final class SyncEngine: ObservableObject {
    private let database: AppDatabase

    @Published var isSyncing = false
    @Published var lastSyncDate: Date?
    @Published var statusMessage: String?

    /// Progress of the image pre-download that follows each data sync.
    struct ImageProgress: Equatable {
        var done: Int
        var total: Int
    }
    @Published var imageProgress: ImageProgress?

    /// Entries composed on the phone, waiting to reach the Mac.
    @Published var pendingCount = 0

    /// Set by AppModel after construction; used to pre-download all
    /// favorite-deck card images so the phone works fully offline.
    weak var imageStore: ImageStore?

    /// The tables mirrored wholesale each sync, in dependency-free order.
    static let snapshotTables = [
        "decks", "cards", "spreads", "profiles", "tags",
        "reference_sources", "source_fields", "card_archetypes",
        "archetype_combinations", "combination_meanings",
        "entity_source_notes", "reference_entities",
        "correspondence_systems", "correspondence_assignments",
        "card_correspondence_overrides",
    ]

    init(database: AppDatabase) {
        self.database = database
    }

    // MARK: - Connection details

    var serverURL: URL? {
        guard let raw = try? database.syncState("server_url") else { return nil }
        return URL(string: raw)
    }

    func setServer(url: URL) throws {
        try database.setSyncState("server_url", url.absoluteString)
    }

    var isPaired: Bool { Keychain.token != nil }

    // MARK: - Pairing

    struct PairResponse: Decodable { let token: String }

    func pair(host: URL, code: String, deviceName: String) async throws {
        var req = URLRequest(url: host.appendingPathComponent("api/sync/pair"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(
            ["code": code, "device_name": deviceName])
        let (data, response) = try await URLSession.shared.data(for: req)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw SyncError.pairingRejected
        }
        let decoded = try JSONDecoder().decode(PairResponse.self, from: data)
        Keychain.token = decoded.token
        try setServer(url: host)
    }

    func unpair() {
        Keychain.token = nil
    }

    // MARK: - Requests

    private func get(_ path: String, query: [String: String] = [:]) async throws -> Data {
        guard let base = serverURL else { throw SyncError.notConfigured }
        var comps = URLComponents(
            url: base.appendingPathComponent(path), resolvingAgainstBaseURL: false)!
        if !query.isEmpty {
            comps.queryItems = query.map { URLQueryItem(name: $0.key, value: $0.value) }
        }
        var req = URLRequest(url: comps.url!)
        if let token = Keychain.token {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let (data, response) = try await URLSession.shared.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw SyncError.network }
        switch http.statusCode {
        case 200: return data
        case 401: throw SyncError.unauthorized
        default: throw SyncError.serverError(http.statusCode)
        }
    }

    // MARK: - The outbox (phone-composed entries)

    /// Queue a composed entry for delivery, then try to deliver
    /// immediately. Safe offline: the payload waits in the outbox.
    @MainActor
    func submitEntry(_ payload: [String: Any]) async {
        guard let data = try? JSONSerialization.data(withJSONObject: payload),
              let jsonString = String(data: data, encoding: .utf8) else {
            statusMessage = "Could not save the entry — please try again."
            return
        }
        let now = ISO8601DateFormatter().string(from: Date())
        do {
            try await database.writer.write { db in
                try db.execute(
                    sql: "INSERT INTO pending_entries (payload_json, created_at) VALUES (?, ?)",
                    arguments: [jsonString, now])
            }
        } catch {
            statusMessage = "Could not save the entry: \(error.localizedDescription)"
            return
        }
        await refreshPendingCount()
        // The save itself is the local write above; delivery happens
        // in the background. Awaiting the sync here froze the composer
        // for a minute whenever the Mac was unreachable — a connection
        // attempt to an absent host hangs until it times out, and the
        // Save button looked simply broken. Offline, the entry waits
        // safely in the outbox for the next successful sync.
        // (Quick pass: skip the image pre-download either way.)
        Task { await self.syncNow(includeImages: false) }
    }

    @MainActor
    func refreshPendingCount() async {
        pendingCount = (try? await database.writer.read { db in
            try Int.fetchOne(db, sql: "SELECT COUNT(*) FROM pending_entries") ?? 0
        }) ?? 0
    }

    @MainActor
    private func pushPending() async throws {
        let rows: [(Int64, String)] = try await database.writer.read { db in
            try Row.fetchAll(
                db, sql: "SELECT id, payload_json FROM pending_entries ORDER BY id")
                .map { ($0["id"], $0["payload_json"]) }
        }
        defer { Task { await refreshPendingCount() } }
        guard !rows.isEmpty else { return }
        guard let base = serverURL else { throw SyncError.notConfigured }
        for (rowId, payload) in rows {
            var req = URLRequest(url: base.appendingPathComponent("api/sync/push-entry"))
            req.httpMethod = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            if let token = Keychain.token {
                req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            }
            req.httpBody = payload.data(using: .utf8)
            let (_, response) = try await URLSession.shared.data(for: req)
            guard let http = response as? HTTPURLResponse else { throw SyncError.network }
            switch http.statusCode {
            case 200, 201:
                try await database.writer.write { db in
                    try db.execute(sql: "DELETE FROM pending_entries WHERE id = ?",
                                   arguments: [rowId])
                }
            case 401:
                throw SyncError.unauthorized
            case 400:
                // The Mac rejected this payload outright — retrying
                // forever would wedge the queue behind it. Drop it and
                // surface the loss instead of failing silently.
                try await database.writer.write { db in
                    try db.execute(sql: "DELETE FROM pending_entries WHERE id = ?",
                                   arguments: [rowId])
                }
                statusMessage = "One phone entry was rejected by the Mac and could not be delivered."
            default:
                throw SyncError.serverError(http.statusCode)
            }
        }
    }

    // MARK: - The pull

    @MainActor
    func syncNow(includeImages: Bool = true) async {
        guard !isSyncing else { return }
        isSyncing = true
        statusMessage = "Syncing…"
        defer { isSyncing = false }
        do {
            // Push first, so an entry logged at the table shows up in
            // the pulled journal below in the same pass.
            try await pushPending()
            try await pullSnapshots()
            try await pullEntries()
            try await pullSourceEntries()
            lastSyncDate = Date()
            statusMessage = nil
        } catch {
            statusMessage = "Sync failed: \(error.localizedDescription)"
            return
        }
        // Data is safely home; now pre-download any card images we
        // don't have yet, so every favorite deck works offline. This
        // is interruption-friendly: whatever fails or gets cut off
        // (Mac asleep, app backgrounded) is simply retried next sync.
        // Skipped for quick passes (saving an entry) so the save
        // never waits behind a long image download.
        if includeImages {
            await prefetchImages()
        }
    }

    @MainActor
    private func prefetchImages() async {
        guard let store = imageStore else { return }
        let ids: [Int64] = (try? await database.writer.read { db in
            try Int64.fetchAll(db, sql: "SELECT id FROM cards ORDER BY deck_id, card_order")
        }) ?? []
        var missing: [Int64] = []
        for id in ids where !(await store.isCached(id)) {
            missing.append(id)
        }
        guard !missing.isEmpty else { imageProgress = nil; return }

        var progress = ImageProgress(done: 0, total: missing.count)
        imageProgress = progress
        var failures = 0

        // A few at a time: fast on Wi-Fi without hammering the Mac,
        // which may be generating each derivative on first request.
        for batch in stride(from: 0, to: missing.count, by: 4).map({
            Array(missing[$0..<min($0 + 4, missing.count)])
        }) {
            await withTaskGroup(of: Bool.self) { group in
                for id in batch {
                    group.addTask { await store.image(for: id) != nil }
                }
                for await ok in group {
                    progress.done += 1
                    if !ok { failures += 1 }
                }
            }
            imageProgress = progress
            // The Mac has stopped answering (asleep, app closed) —
            // give up quietly; the next sync resumes from here.
            if failures >= 8 && failures == progress.done { break }
        }
        imageProgress = nil
        if failures > 0 {
            statusMessage = "\(failures) images couldn't be fetched — they'll retry on the next sync."
        }
    }

    private func pullSnapshots() async throws {
        for table in Self.snapshotTables {
            let data: Data
            do {
                data = try await get("api/sync/snapshot/\(table)")
            } catch SyncError.serverError(404) {
                // The Mac is running an older app version that doesn't
                // know this table yet — skip it, keep syncing the rest.
                continue
            }
            guard let body = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let rows = body["rows"] as? [[String: Any]] else {
                throw SyncError.badPayload(table)
            }
            try await database.writer.write { db in
                try db.execute(sql: "DELETE FROM \(table)")
                for row in rows {
                    try Self.insert(db, table: table, row: row)
                }
            }
        }
    }

    private func pullEntries() async throws {
        let since = (try? database.syncState("entries_since")) ?? nil
        let data = try await get("api/sync/entries",
                                 query: since.map { ["since": $0] } ?? [:])
        guard let body = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let ids = body["ids"] as? [Int64],
              let changed = body["changed"] as? [[String: Any]] else {
            throw SyncError.badPayload("entries")
        }
        let maxUpdated: String? = try await database.writer.write { db in
            var newest = since
            // Prune local entries deleted on the desktop.
            if ids.isEmpty {
                try db.execute(sql: "DELETE FROM entries")
            } else {
                let marks = ids.map { _ in "?" }.joined(separator: ",")
                try db.execute(
                    sql: "DELETE FROM entries WHERE id NOT IN (\(marks))",
                    arguments: StatementArguments(ids))
            }
            for e in changed {
                try Self.upsertEntry(db, aggregate: e)
                if let u = e["updated_at"] as? String, u > (newest ?? "") {
                    newest = u
                }
            }
            return newest
        }
        if let maxUpdated { try database.setSyncState("entries_since", maxUpdated) }
    }

    private func pullSourceEntries() async throws {
        let since = (try? database.syncState("source_entries_since")) ?? nil
        let data = try await get("api/sync/source-entries",
                                 query: since.map { ["since": $0] } ?? [:])
        guard let body = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let ids = body["ids"] as? [Int64],
              let changed = body["changed"] as? [[String: Any]] else {
            throw SyncError.badPayload("source-entries")
        }
        let maxUpdated: String? = try await database.writer.write { db in
            var newest = since
            if ids.isEmpty {
                try db.execute(sql: "DELETE FROM source_entries")
            } else {
                let marks = ids.map { _ in "?" }.joined(separator: ",")
                try db.execute(
                    sql: "DELETE FROM source_entries WHERE id NOT IN (\(marks))",
                    arguments: StatementArguments(ids))
            }
            for row in changed {
                try db.execute(
                    sql: """
                        INSERT OR REPLACE INTO source_entries
                        (id, archetype_id, field_id, content, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                    arguments: [
                        row["id"] as? Int64,
                        row["archetype_id"] as? Int64,
                        row["field_id"] as? Int64,
                        row["content"] as? String,
                        row["updated_at"] as? String,
                    ])
                if let u = row["updated_at"] as? String, u > (newest ?? "") {
                    newest = u
                }
            }
            return newest
        }
        if let maxUpdated { try database.setSyncState("source_entries_since", maxUpdated) }
    }

    // MARK: - Row plumbing

    /// Insert a snapshot row using only the columns the local table has.
    private static func insert(_ db: Database, table: String, row: [String: Any]) throws {
        let localColumns = try db.columns(in: table).map(\.name)
        let present = localColumns.filter { row[$0] != nil && !($0.isEmpty) }
        guard !present.isEmpty else { return }
        let marks = present.map { _ in "?" }.joined(separator: ",")
        let sql = "INSERT OR REPLACE INTO \(table) (\(present.joined(separator: ","))) VALUES (\(marks))"
        let values = present.map { toDatabaseValue(row[$0]) }
        try db.execute(sql: sql, arguments: StatementArguments(values))
    }

    private static func upsertEntry(_ db: Database, aggregate: [String: Any]) throws {
        func json(_ key: String) -> String? {
            guard let value = aggregate[key],
                  JSONSerialization.isValidJSONObject(value),
                  let data = try? JSONSerialization.data(withJSONObject: value)
            else { return nil }
            return String(data: data, encoding: .utf8)
        }
        try db.execute(
            sql: """
                INSERT OR REPLACE INTO entries
                (id, title, content, created_at, updated_at, reading_datetime,
                 location_name, querent_id, reader_id, sync_uuid,
                 readings_json, tag_ids_json, querent_ids_json, follow_ups_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
            arguments: [
                aggregate["id"] as? Int64,
                aggregate["title"] as? String,
                aggregate["content"] as? String,
                aggregate["created_at"] as? String,
                aggregate["updated_at"] as? String,
                aggregate["reading_datetime"] as? String,
                aggregate["location_name"] as? String,
                aggregate["querent_id"] as? Int64,
                aggregate["reader_id"] as? Int64,
                aggregate["sync_uuid"] as? String,
                json("readings"),
                json("tag_ids"),
                json("querent_ids"),
                json("follow_up_notes"),
            ])
    }

    private static func toDatabaseValue(_ value: Any?) -> DatabaseValueConvertible? {
        switch value {
        case let v as Int64: return v
        case let v as Int: return v
        case let v as Double: return v
        case let v as String: return v
        case let v as Bool: return v
        case is NSNull, nil: return nil
        default:
            // Nested JSON (e.g. spread positions arrive as parsed
            // objects if the server ever inlines them) — store as text.
            if let value,
               JSONSerialization.isValidJSONObject(value),
               let data = try? JSONSerialization.data(withJSONObject: value) {
                return String(data: data, encoding: .utf8)
            }
            return nil
        }
    }
}

enum SyncError: LocalizedError {
    case notConfigured
    case pairingRejected
    case unauthorized
    case network
    case badPayload(String)
    case serverError(Int)

    var errorDescription: String? {
        switch self {
        case .notConfigured: return "No Mac has been paired yet."
        case .pairingRejected: return "The pairing code was not accepted. Codes expire after 5 minutes — show a fresh one on the Mac and try again."
        case .unauthorized: return "The Mac no longer accepts this phone's pairing. Re-pair from the Mac's Settings."
        case .network: return "Could not reach the Mac. Make sure both devices are on the same Wi-Fi and the desktop app is open."
        case .badPayload(let what): return "Unexpected response from the Mac (\(what))."
        case .serverError(let code): return "The Mac returned an error (HTTP \(code))."
        }
    }
}
