import Foundation
import GRDB

/// Talks to the desktop app's /api/sync/ endpoints and mirrors the
/// results into the local database.
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

    /// Bumped whenever a phone-composed entry lands in the local
    /// journal, so list views refresh without waiting for a sync.
    @Published var localJournalEdits = 0

    /// Set by AppModel after construction; used to pre-download all
    /// favorite-deck card images so the phone works fully offline.
    weak var imageStore: ImageStore?

    /// Guards the image pre-download separately from `isSyncing` —
    /// a long download must never block data syncs.
    private var isPrefetching = false

    /// Data requests on a short leash: on the home LAN the Mac
    /// answers in well under a second, so a stalled connection
    /// should fail within seconds and let the outbox retry later —
    /// not hang for Apple's default minute-plus. The request timeout
    /// is between-bytes idle time, so a slow-but-moving transfer
    /// (a big first pull over a hotspot) still completes within the
    /// resource limit.
    static let dataSession: URLSession = {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 15
        config.timeoutIntervalForResource = 180
        return URLSession(configuration: config)
    }()

    /// The tables mirrored wholesale each sync, in dependency-free order.
    static let snapshotTables = [
        "decks", "cards", "spreads", "profiles", "tags",
        "reference_sources", "source_fields", "card_archetypes",
        "archetype_combinations", "combination_meanings",
        "entity_source_notes", "reference_entities",
        "correspondence_systems", "correspondence_assignments",
        "card_correspondence_overrides", "card_custom_fields",
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
        let (data, response) = try await Self.dataSession.data(for: req)
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

    /// A request to the Mac carrying this phone's pairing token.
    static func authorizedRequest(_ base: URL, path: String,
                                  query: [String: String] = [:]) -> URLRequest {
        var comps = URLComponents(
            url: base.appendingPathComponent(path), resolvingAgainstBaseURL: false)!
        if !query.isEmpty {
            comps.queryItems = query.map { URLQueryItem(name: $0.key, value: $0.value) }
        }
        var req = URLRequest(url: comps.url!)
        if let token = Keychain.token {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        return req
    }

    /// Naive local wall-clock time, the format the desktop stores.
    static let localTimestamp: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        return f
    }()

    /// A JSON array/object as text, or nil if it isn't one.
    static func jsonText(_ value: Any?) -> String? {
        guard let value, JSONSerialization.isValidJSONObject(value),
              let data = try? JSONSerialization.data(withJSONObject: value)
        else { return nil }
        return String(data: data, encoding: .utf8)
    }

    private func get(_ path: String, query: [String: String] = [:]) async throws -> Data {
        guard let base = serverURL else { throw SyncError.notConfigured }
        let req = Self.authorizedRequest(base, path: path, query: query)
        let (data, response) = try await Self.dataSession.data(for: req)
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
        let naiveNow = Self.localTimestamp.string(from: Date())
        do {
            try await database.writer.write { db in
                try db.execute(
                    sql: "INSERT INTO pending_entries (payload_json, created_at) VALUES (?, ?)",
                    arguments: [jsonString, now])
                // The entry appears in the phone's journal right
                // away, as a provisional row keyed by a NEGATIVE id
                // (desktop ids are positive, so no collision). Once
                // the push succeeds, the next pull brings the real
                // entry and the provisional twin — matched by
                // sync_uuid — is removed.
                try Self.insertProvisionalEntry(
                    db, payload: payload,
                    outboxId: db.lastInsertedRowID, now: naiveNow)
            }
        } catch {
            statusMessage = "Could not save the entry: \(error.localizedDescription)"
            return
        }
        localJournalEdits += 1
        await refreshPendingCount()
        // The save itself is the local write above; delivery happens
        // in the background. Awaiting the sync here froze the composer
        // for a minute whenever the Mac was unreachable — a connection
        // attempt to an absent host hangs until it times out, and the
        // Save button looked simply broken. Offline, the entry waits
        // safely in the outbox for the next successful sync — quietly:
        // an out-of-reach Mac is normal life, not an error to show.
        // (Quick pass: skip the image pre-download either way.)
        Task { await self.syncNow(includeImages: false, quiet: true) }
    }

    /// A local stand-in for a phone-composed entry, shaped exactly
    /// like a pulled desktop aggregate so every journal view renders
    /// it unchanged.
    private static func insertProvisionalEntry(
        _ db: Database, payload: [String: Any],
        outboxId: Int64, now: String) throws {
        var readings: [[String: Any]] = []
        for (index, r) in ((payload["readings"] as? [[String: Any]]) ?? []).enumerated() {
            var reading = r
            // The Reading decoder requires an id; any unique value works.
            reading["id"] = Int64(index + 1)
            readings.append(reading)
        }
        let querentIds = (payload["querent_ids"] as? [Int64]) ?? []
        var aggregate = payload
        aggregate["id"] = -outboxId
        aggregate["created_at"] = now
        aggregate["updated_at"] = now
        aggregate["readings"] = readings
        aggregate["querent_ids"] = querentIds
        aggregate["querent_id"] = querentIds.first
        aggregate["tag_ids"] = [Int64]()
        aggregate["follow_up_notes"] = [Any]()
        try upsertEntry(db, aggregate: aggregate)
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
            var req = Self.authorizedRequest(base, path: "api/sync/push-entry")
            req.httpMethod = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = payload.data(using: .utf8)
            let (_, response) = try await Self.dataSession.data(for: req)
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
                // forever would wedge the queue behind it. Drop it
                // (and its provisional journal row) and surface the
                // loss instead of failing silently.
                try await database.writer.write { db in
                    try db.execute(sql: "DELETE FROM pending_entries WHERE id = ?",
                                   arguments: [rowId])
                    try db.execute(sql: "DELETE FROM entries WHERE id = ?",
                                   arguments: [-rowId])
                }
                statusMessage = "One phone entry was rejected by the Mac and could not be delivered."
            default:
                throw SyncError.serverError(http.statusCode)
            }
        }
    }

    // MARK: - The pull

    @MainActor
    func syncNow(includeImages: Bool = true, quiet: Bool = false) async {
        guard !isSyncing else { return }
        isSyncing = true
        // A quiet pass (after saving an entry) neither announces
        // itself nor reports failure — an unreachable Mac is the
        // outbox's normal case, and the entry already shows locally.
        if !quiet { statusMessage = "Syncing…" }
        do {
            do {
                try await runSyncPass()
            } catch {
                // The Mac's address changes with every network setup —
                // home Wi-Fi, Personal Hotspot, USB tethering all give
                // it a different one. Ask Bonjour where it is now, and
                // if a fresh address answers, retry once.
                guard await rediscoverServer() else { throw error }
                try await runSyncPass()
            }
            lastSyncDate = Date()
            statusMessage = nil
            // Release the lock BEFORE the image pre-download below:
            // a long download once held it for minutes, during which
            // every other sync attempt (foreground, save, "Sync now")
            // silently no-oped on the guard above.
            isSyncing = false
        } catch {
            isSyncing = false
            if !quiet {
                statusMessage = "Sync failed: \(error.localizedDescription)"
            }
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

    /// One full data exchange: push first, so an entry logged at the
    /// table shows up in the pulled journal below in the same pass.
    @MainActor
    private func runSyncPass() async throws {
        try await pushPending()
        try await pullSnapshots()
        try await pullEntries()
        try await pullSourceEntries()
    }

    /// The stored address stopped answering — browse Bonjour for the
    /// Mac's advertisement (it lists one address per interface) and
    /// adopt the first one that actually responds. The pairing token
    /// stays valid; only the address moves.
    @MainActor
    private func rediscoverServer() async -> Bool {
        guard isPaired else { return false }
        let candidates = await ServerDiscovery().findServerURLs()
        let failing = serverURL
        for url in candidates where url != failing {
            if await respondsToProbe(url) {
                try? setServer(url: url)
                return true
            }
        }
        return false
    }

    private func respondsToProbe(_ url: URL) async -> Bool {
        var req = URLRequest(url: url.appendingPathComponent("api/sync/manifest"))
        req.timeoutInterval = 4
        guard let (_, response) = try? await Self.dataSession.data(for: req) else {
            return false
        }
        // Any HTTP answer proves the Mac is there (401 just means
        // this probe carried no token).
        return response is HTTPURLResponse
    }

    @MainActor
    private func prefetchImages() async {
        guard !isPrefetching else { return }
        isPrefetching = true
        defer { isPrefetching = false }
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
        try await pullDelta("entries", cursorKey: "entries_since") { db, ids, changed in
            // Prune local entries deleted on the desktop. Negative
            // ids are provisional phone-composed entries the desktop
            // doesn't know about yet — never prune those.
            try Self.prune(db, table: "entries", keeping: ids, scope: "id >= 0")
            for e in changed {
                try Self.upsertEntry(db, aggregate: e)
            }
            // A provisional entry whose real, desktop-assigned twin
            // has arrived (same sync_uuid) is now redundant.
            try db.execute(sql: """
                DELETE FROM entries WHERE id < 0 AND sync_uuid IN
                    (SELECT sync_uuid FROM entries
                     WHERE id >= 0 AND sync_uuid IS NOT NULL)
                """)
        }
    }

    private func pullSourceEntries() async throws {
        try await pullDelta("source-entries", cursorKey: "source_entries_since") { db, ids, changed in
            try Self.prune(db, table: "source_entries", keeping: ids)
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
            }
        }
    }

    /// An incremental pull: the Mac sends rows changed since our
    /// cursor plus the full list of ids it still has. `apply` prunes
    /// and upserts in one transaction; then the cursor advances to
    /// the newest `updated_at` seen.
    private func pullDelta(
        _ endpoint: String, cursorKey: String,
        apply: @escaping (Database, _ ids: [Int64], _ changed: [[String: Any]]) throws -> Void
    ) async throws {
        let since = (try? database.syncState(cursorKey)) ?? nil
        let data = try await get("api/sync/\(endpoint)",
                                 query: since.map { ["since": $0] } ?? [:])
        guard let body = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let ids = body["ids"] as? [Int64],
              let changed = body["changed"] as? [[String: Any]] else {
            throw SyncError.badPayload(endpoint)
        }
        try await database.writer.write { db in try apply(db, ids, changed) }
        let newest = ([since] + changed.map { $0["updated_at"] as? String })
            .compactMap { $0 }.max()
        if let newest { try database.setSyncState(cursorKey, newest) }
    }

    /// Delete rows (within `scope`) whose id the Mac no longer lists.
    private static func prune(_ db: Database, table: String,
                              keeping ids: [Int64], scope: String = "1") throws {
        if ids.isEmpty {
            try db.execute(sql: "DELETE FROM \(table) WHERE \(scope)")
        } else {
            let marks = ids.map { _ in "?" }.joined(separator: ",")
            try db.execute(
                sql: "DELETE FROM \(table) WHERE \(scope) AND id NOT IN (\(marks))",
                arguments: StatementArguments(ids))
        }
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
        func json(_ key: String) -> String? { jsonText(aggregate[key]) }
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
            return jsonText(value)
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
