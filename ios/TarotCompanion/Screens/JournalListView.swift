import SwiftUI
import GRDB

struct EntryRow: Identifiable, Hashable {
    let id: Int64
    let title: String?
    let readingDatetime: String?
    let content: String?
    let subtitle: String?        // spread · deck summary
    let querentIds: Set<Int64>
}

struct JournalListView: View {
    @EnvironmentObject private var appModel: AppModel
    @State private var entries: [EntryRow] = []
    @State private var searchText = ""
    @State private var querents: [(id: Int64, name: String)] = []
    @State private var querentFilter: Int64?
    @State private var composing = false

    var filtered: [EntryRow] {
        var result = entries
        if let querentFilter {
            result = result.filter { $0.querentIds.contains(querentFilter) }
        }
        if !searchText.isEmpty {
            let q = searchText.lowercased()
            result = result.filter {
                ($0.title ?? "").lowercased().contains(q)
                    || ($0.content ?? "").lowercased().contains(q)
                    || ($0.subtitle ?? "").lowercased().contains(q)
            }
        }
        return result
    }

    var body: some View {
        NavigationStack {
            NocturneScreen {
                if entries.isEmpty {
                    ContentUnavailableView(
                        "No entries yet",
                        systemImage: "book.closed",
                        description: Text("Pair with your Mac in Settings, then sync."))
                } else {
                    List(filtered) { entry in
                        NavigationLink(value: entry.id) {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(entry.title ?? "Untitled reading")
                                    .font(TJ.serifFont(17))
                                    .foregroundStyle(TJ.text)
                                if let subtitle = entry.subtitle {
                                    Text(subtitle)
                                        .font(.caption)
                                        .foregroundStyle(TJ.text3)
                                        .lineLimit(1)
                                }
                                if let date = entry.readingDatetime {
                                    Text(Self.displayDate(date))
                                        .font(.caption2)
                                        .foregroundStyle(TJ.textFaint)
                                }
                            }
                        }
                        .listRowBackground(TJ.panel)
                    }
                    .searchable(text: $searchText)
                    .refreshable { await appModel.sync.syncNow() }
                    .navigationDestination(for: Int64.self) { entryId in
                        EntryDetailView(entryId: entryId)
                    }
                }
            }
            .navigationTitle("Journal")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        composing = true
                    } label: {
                        Image(systemName: "plus")
                    }
                    .accessibilityLabel("New entry")
                }
                if !querents.isEmpty {
                    ToolbarItem(placement: .topBarTrailing) {
                        querentMenu
                    }
                }
            }
            .safeAreaInset(edge: .bottom) {
                statusStrip
            }
        }
        .sheet(isPresented: $composing) {
            NewEntryView()
        }
        .task {
            load()
            await appModel.sync.refreshPendingCount()
        }
        .onReceive(appModel.sync.$lastSyncDate) { _ in load() }
    }

    /// Sync activity where the user actually is — pending pushes,
    /// active sync, image downloads, and failures all announce
    /// themselves here rather than only deep in Settings.
    @ViewBuilder
    private var statusStrip: some View {
        VStack(spacing: 4) {
            if appModel.sync.pendingCount > 0 {
                stripCapsule(
                    "\(appModel.sync.pendingCount) entr\(appModel.sync.pendingCount == 1 ? "y" : "ies") waiting to reach the Mac")
            }
            if let progress = appModel.sync.imageProgress {
                stripCapsule("Downloading card images — \(progress.done) of \(progress.total)")
            } else if appModel.sync.isSyncing {
                stripCapsule("Syncing…")
            }
            if let message = appModel.sync.statusMessage, !appModel.sync.isSyncing {
                stripCapsule(message)
            }
        }
        .padding(.bottom, 4)
    }

    private func stripCapsule(_ text: String) -> some View {
        Text(text)
            .font(.caption)
            .foregroundStyle(TJ.textOnTint)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(Capsule().fill(TJ.tintStrong))
    }

    private var querentMenu: some View {
        Menu {
            Button("All querents") { querentFilter = nil }
            Divider()
            ForEach(querents, id: \.id) { querent in
                Button {
                    querentFilter = querent.id
                } label: {
                    if querentFilter == querent.id {
                        Label(querent.name, systemImage: "checkmark")
                    } else {
                        Text(querent.name)
                    }
                }
            }
        } label: {
            Image(systemName: querentFilter == nil
                  ? "person.crop.circle" : "person.crop.circle.fill")
        }
    }

    private func load() {
        let decoder = JSONDecoder()
        entries = (try? appModel.database.writer.read { db in
            try Row.fetchAll(db, sql: """
                SELECT id, title, reading_datetime, content,
                       readings_json, querent_ids_json
                FROM entries ORDER BY reading_datetime DESC
                """).map { row -> EntryRow in
                var subtitle: String?
                if let raw: String = row["readings_json"],
                   let data = raw.data(using: .utf8),
                   let readings = try? decoder.decode([Reading].self, from: data),
                   !readings.isEmpty {
                    let spreads = readings.compactMap(\.spreadName)
                    let decks = readings.compactMap(\.deckName)
                    let parts = [
                        Set(spreads).sorted().joined(separator: ", "),
                        Set(decks).sorted().joined(separator: ", "),
                    ].filter { !$0.isEmpty }
                    subtitle = parts.joined(separator: " · ")
                }
                var querentIds: Set<Int64> = []
                if let raw: String = row["querent_ids_json"],
                   let data = raw.data(using: .utf8),
                   let ids = try? decoder.decode([Int64].self, from: data) {
                    querentIds = Set(ids)
                }
                return EntryRow(id: row["id"], title: row["title"],
                                readingDatetime: row["reading_datetime"],
                                content: row["content"],
                                subtitle: subtitle,
                                querentIds: querentIds)
            }
        }) ?? []

        // Filter menu lists only querents who actually have entries.
        let used = entries.reduce(into: Set<Int64>()) { $0.formUnion($1.querentIds) }
        if !used.isEmpty {
            let marks = used.map { _ in "?" }.joined(separator: ",")
            querents = (try? appModel.database.writer.read { db in
                try Row.fetchAll(
                    db, sql: "SELECT id, name FROM profiles WHERE id IN (\(marks)) ORDER BY name",
                    arguments: StatementArguments(Array(used)))
                    .map { ($0["id"], $0["name"]) }
            }) ?? []
        }
    }

    /// The desktop stores naive local timestamps (no timezone), e.g.
    /// "2026-09-01T00:45:12.345" — try its variants oldest-first.
    static func displayDate(_ iso: String) -> String {
        let patterns = [
            "yyyy-MM-dd'T'HH:mm:ss.SSSSSS",
            "yyyy-MM-dd'T'HH:mm:ss",
            "yyyy-MM-dd'T'HH:mm",
            "yyyy-MM-dd",
        ]
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        for pattern in patterns {
            formatter.dateFormat = pattern
            if let date = formatter.date(from: iso) {
                return date.formatted(date: .abbreviated, time: .shortened)
            }
        }
        return iso
    }
}
