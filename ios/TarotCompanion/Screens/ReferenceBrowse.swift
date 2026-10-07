import SwiftUI
import GRDB

// MARK: - Categories

/// The non-card halves of the Reference section, mirroring the
/// desktop's tabs. Raw values are the entity kinds in the synced
/// catalog; combinations are their own thing.
enum ReferenceCategory: String, CaseIterable, Identifiable, Hashable {
    case combinations
    case sign, planet, sephira, path, chakra, number, suit, rank

    var id: String { rawValue }

    var label: String {
        switch self {
        case .combinations: return "Combinations"
        case .sign: return "Signs"
        case .planet: return "Planets"
        case .sephira: return "Sephiroth"
        case .path: return "Paths"
        case .chakra: return "Chakras"
        case .number: return "Numerology"
        case .suit: return "Suits"
        case .rank: return "Ranks"
        }
    }

    var icon: String {
        switch self {
        case .combinations: return "rectangle.on.rectangle"
        case .sign: return "sparkles"
        case .planet: return "circle.circle"
        case .sephira: return "point.3.connected.trianglepath.dotted"
        case .path: return "arrow.triangle.branch"
        case .chakra: return "circle.grid.3x3"
        case .number: return "number"
        case .suit: return "suit.club"
        case .rank: return "crown"
        }
    }
}

/// Top-level rows on the Reference front page. Groups bundle
/// related categories behind one row with a segmented switcher.
enum ReferenceGroup: String, CaseIterable, Identifiable, Hashable {
    case cards
    case astrology
    case kabbalah
    case numbersAndSuits
    case chakras

    var id: String { rawValue }

    var label: String {
        switch self {
        case .cards: return "Cards"
        case .astrology: return "Astrology"
        case .kabbalah: return "Kabbalah"
        case .numbersAndSuits: return "Numbers and Suits"
        case .chakras: return "Chakras"
        }
    }

    var icon: String {
        switch self {
        case .cards: return "rectangle.portrait.on.rectangle.portrait"
        case .astrology: return "sparkles"
        case .kabbalah: return "point.3.connected.trianglepath.dotted"
        case .numbersAndSuits: return "number"
        case .chakras: return "circle.grid.3x3"
        }
    }

    /// The entity categories inside this group (empty for cards,
    /// which has its own screen).
    var categories: [ReferenceCategory] {
        switch self {
        case .cards: return []
        case .astrology: return [.sign, .planet]
        case .kabbalah: return [.sephira, .path]
        case .numbersAndSuits: return [.number, .suit, .rank]
        case .chakras: return [.chakra]
        }
    }
}

/// A group's page: one category shows plainly; several get a
/// segmented switcher.
struct ReferenceGroupView: View {
    let group: ReferenceGroup
    @State private var selected: ReferenceCategory

    init(group: ReferenceGroup) {
        self.group = group
        _selected = State(initialValue: group.categories.first ?? .chakra)
    }

    var body: some View {
        NocturneScreen {
            VStack(spacing: 0) {
                if group.categories.count > 1 {
                    Picker("Section", selection: $selected) {
                        ForEach(group.categories) { category in
                            Text(category.label).tag(category)
                        }
                    }
                    .pickerStyle(.segmented)
                    .padding(.horizontal)
                    .padding(.top, 8)
                }
                EntityListView(category: selected)
                    .id(selected)
            }
        }
        .navigationTitle(group.label)
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct ReferenceEntity: Identifiable, Hashable {
    let id: Int64
    let kind: String
    let key: String
    let name: String
    let subtitle: String?
    let cartomancyType: String?
}

// MARK: - Entity list

struct EntityListView: View {
    let category: ReferenceCategory

    @EnvironmentObject private var appModel: AppModel
    @State private var entities: [ReferenceEntity] = []
    @State private var searchText = ""

    var filtered: [ReferenceEntity] {
        guard !searchText.isEmpty else { return entities }
        let q = searchText.lowercased()
        return entities.filter {
            $0.name.lowercased().contains(q)
                || ($0.cartomancyType ?? "").lowercased().contains(q)
        }
    }

    var body: some View {
        List(filtered) { entity in
            NavigationLink(value: entity) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(entity.name)
                        .font(TJ.serifFont(17))
                        .foregroundStyle(TJ.text)
                    if let subtitle = entity.subtitle, !subtitle.isEmpty {
                        Text(subtitle)
                            .font(.caption)
                            .foregroundStyle(TJ.textFaint)
                    }
                }
            }
            .listRowBackground(TJ.panel)
        }
        .scrollContentBackground(.hidden)
        .searchable(text: $searchText)
        .task { load() }
    }

    private func load() {
        entities = (try? appModel.database.writer.read { db in
            try Row.fetchAll(db, sql: """
                SELECT * FROM reference_entities WHERE kind = ?
                ORDER BY sort
                """, arguments: [category.rawValue]).map {
                ReferenceEntity(id: $0["id"], kind: $0["kind"],
                                key: $0["key"], name: $0["name"],
                                subtitle: $0["subtitle"],
                                cartomancyType: $0["cartomancy_type"])
            }
        }) ?? []
    }
}

// MARK: - Entity detail (source notes)

struct EntityDetailView: View {
    let entity: ReferenceEntity

    @EnvironmentObject private var appModel: AppModel
    @State private var notes: [(id: Int64, sourceName: String, content: String)] = []
    @State private var loaded = false

    var body: some View {
        NocturneScreen {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    if let subtitle = entity.subtitle, !subtitle.isEmpty {
                        Text(subtitle)
                            .font(.subheadline)
                            .foregroundStyle(TJ.textMuted)
                    }
                    if loaded && notes.isEmpty {
                        ContentUnavailableView(
                            "No reference text",
                            systemImage: "text.book.closed",
                            description: Text("No source has notes for this yet — import some with the Scribe on the Mac."))
                            .padding(.top, 40)
                    }
                    ForEach(notes, id: \.id) { note in
                        VStack(alignment: .leading, spacing: 8) {
                            Text(note.sourceName)
                                .font(TJ.serifFont(17))
                                .foregroundStyle(TJ.text2)
                            HTMLText(html: note.content)
                        }
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(RoundedRectangle(cornerRadius: 10).fill(TJ.panel))
                    }
                }
                .padding()
            }
        }
        .navigationTitle(entity.name)
        .navigationBarTitleDisplayMode(.inline)
        .task { load() }
    }

    private func load() {
        notes = (try? appModel.database.writer.read { db in
            try Row.fetchAll(db, sql: """
                SELECT n.id, n.content, rs.name AS source_name
                FROM entity_source_notes n
                LEFT JOIN reference_sources rs ON rs.id = n.source_id
                WHERE n.entity_kind = ? AND n.entity_key = ?
                ORDER BY rs.name
                """, arguments: [entity.kind, entity.key]).map {
                ($0["id"], $0["source_name"] ?? "Source", $0["content"] ?? "")
            }
        }) ?? []
        loaded = true
    }
}

// MARK: - The Cards group

enum CardsRoute: Hashable {
    case byDeckType
    case combinations
}

/// The Cards page: archetype search up top, plus structured browsing
/// (by deck type, like the desktop's Archetypes tab) and the
/// combinations lookup.
struct CardsGroupView: View {
    @EnvironmentObject private var appModel: AppModel
    @State private var searchText = ""
    @State private var hits: [ArchetypeHit] = []

    var body: some View {
        List {
            if searchText.isEmpty {
                NavigationLink(value: CardsRoute.byDeckType) {
                    Label {
                        Text("View by deck type")
                            .font(TJ.serifFont(17))
                            .foregroundStyle(TJ.text)
                    } icon: {
                        Image(systemName: "square.stack.3d.up")
                            .foregroundStyle(TJ.accent)
                    }
                }
                .listRowBackground(TJ.panel)
                NavigationLink(value: CardsRoute.combinations) {
                    Label {
                        Text("Combinations")
                            .font(TJ.serifFont(17))
                            .foregroundStyle(TJ.text)
                    } icon: {
                        Image(systemName: "rectangle.on.rectangle")
                            .foregroundStyle(TJ.accent)
                    }
                }
                .listRowBackground(TJ.panel)
            } else {
                ForEach(hits) { hit in
                    NavigationLink(value: hit) {
                        VStack(alignment: .leading) {
                            Text(hit.name)
                                .font(TJ.serifFont(17))
                                .foregroundStyle(TJ.text)
                            if let type = hit.cartomancyType {
                                Text(type).font(.caption).foregroundStyle(TJ.textFaint)
                            }
                        }
                    }
                    .listRowBackground(TJ.panel)
                }
            }
        }
        .scrollContentBackground(.hidden)
        .searchable(text: $searchText, prompt: "Card name…")
        .onChange(of: searchText) { _, _ in search() }
        .navigationTitle("Cards")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func search() {
        guard !searchText.isEmpty else { hits = []; return }
        hits = (try? appModel.database.writer.read { db in
            try Row.fetchAll(db, sql: """
                SELECT id, name, cartomancy_type FROM card_archetypes
                WHERE name LIKE ? ORDER BY name LIMIT 50
                """, arguments: ["%\(searchText)%"]).map {
                ArchetypeHit(id: $0["id"], name: $0["name"],
                             cartomancyType: $0["cartomancy_type"])
            }
        }) ?? []
    }
}

/// Deck types with the preferred builtins first, like the desktop.
func orderedDeckTypes(_ types: [String]) -> [String] {
    let preferred = ["Tarot", "Petit Lenormand", "Playing Cards",
                     "Playing Cards (Latin-suited)", "Playing Cards (German-suited)", "Oracle"]
    let head = preferred.filter { types.contains($0) }
    let tail = types.filter { !preferred.contains($0) }.sorted()
    return head + tail
}

struct DeckTypeSelection: Hashable {
    let type: String
}

/// Step one of by-type browsing: pick the deck type.
struct DeckTypeListView: View {
    @EnvironmentObject private var appModel: AppModel
    @State private var types: [String] = []

    var body: some View {
        List(types, id: \.self) { type in
            NavigationLink(value: DeckTypeSelection(type: type)) {
                Text(type)
                    .font(TJ.serifFont(17))
                    .foregroundStyle(TJ.text)
            }
            .listRowBackground(TJ.panel)
        }
        .scrollContentBackground(.hidden)
        .navigationTitle("Deck Types")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            let raw = (try? appModel.database.writer.read { db in
                try String.fetchAll(db, sql: """
                    SELECT DISTINCT cartomancy_type FROM card_archetypes
                    WHERE cartomancy_type IS NOT NULL AND cartomancy_type != ''
                    """)
            }) ?? []
            types = orderedDeckTypes(raw)
        }
    }
}

/// Step two: the type's archetypes, in canonical (seed) order.
struct TypeArchetypesView: View {
    let type: String

    @EnvironmentObject private var appModel: AppModel
    @State private var archetypes: [ArchetypeHit] = []
    @State private var searchText = ""

    var filtered: [ArchetypeHit] {
        guard !searchText.isEmpty else { return archetypes }
        return archetypes.filter {
            $0.name.lowercased().contains(searchText.lowercased())
        }
    }

    var body: some View {
        List(filtered) { hit in
            NavigationLink(value: hit) {
                Text(hit.name)
                    .font(TJ.serifFont(17))
                    .foregroundStyle(TJ.text)
            }
            .listRowBackground(TJ.panel)
        }
        .scrollContentBackground(.hidden)
        .searchable(text: $searchText)
        .navigationTitle(type)
        .navigationBarTitleDisplayMode(.inline)
        .task {
            archetypes = (try? appModel.database.writer.read { db in
                try Row.fetchAll(db, sql: """
                    SELECT id, name, cartomancy_type FROM card_archetypes
                    WHERE cartomancy_type = ? ORDER BY id
                    """, arguments: [type]).map {
                    ArchetypeHit(id: $0["id"], name: $0["name"],
                                 cartomancyType: $0["cartomancy_type"])
                }
            }) ?? []
        }
    }
}

// MARK: - Combinations

struct CombinationRow: Identifiable {
    let id: Int64
    let title: String
    let meanings: [(id: Int64, sourceName: String, text: String)]
}

/// Structured combination lookup, like the desktop: deck type →
/// two or three cards → the cards themselves → every stored
/// combination of exactly those cards (any order, any reversals),
/// with meanings grouped by source.
struct CombinationsView: View {
    @EnvironmentObject private var appModel: AppModel

    @State private var types: [String] = []
    @State private var type: String?
    @State private var cardCount = 2
    @State private var picks: [(id: Int64, name: String)?] = [nil, nil, nil]
    @State private var pickingSlot: Int?
    @State private var combos: [CombinationRow] = []
    @State private var searched = false

    private var ready: Bool {
        type != nil && (0..<cardCount).allSatisfy { picks[$0] != nil }
    }

    var body: some View {
        List {
            Section {
                Picker("Deck type", selection: $type) {
                    Text("Choose…").tag(String?.none)
                    ForEach(types, id: \.self) { t in
                        Text(t).tag(String?.some(t))
                    }
                }
                .onChange(of: type) { _, _ in resetPicks() }

                Picker("Cards", selection: $cardCount) {
                    Text("Two cards").tag(2)
                    Text("Three cards").tag(3)
                }
                .pickerStyle(.segmented)
                .onChange(of: cardCount) { _, _ in refresh() }
            }
            .listRowBackground(TJ.panel)

            if type != nil {
                Section {
                    ForEach(0..<cardCount, id: \.self) { slot in
                        Button {
                            pickingSlot = slot
                        } label: {
                            HStack {
                                Text("Card \(slot + 1)")
                                    .foregroundStyle(TJ.textMuted)
                                Spacer()
                                Text(picks[slot]?.name ?? "Choose…")
                                    .foregroundStyle(picks[slot] == nil ? TJ.accent : TJ.text)
                            }
                        }
                    }
                }
                .listRowBackground(TJ.panel)
            }

            if searched {
                if combos.isEmpty {
                    Text("No stored combination for these cards.")
                        .font(.caption)
                        .foregroundStyle(TJ.textFaint)
                        .listRowBackground(TJ.panel)
                }
                ForEach(combos) { combo in
                    VStack(alignment: .leading, spacing: 6) {
                        Text(combo.title)
                            .font(TJ.serifFont(17))
                            .foregroundStyle(TJ.text)
                        ForEach(combo.meanings, id: \.id) { meaning in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(meaning.sourceName)
                                    .font(.caption)
                                    .textCase(.uppercase)
                                    .foregroundStyle(TJ.textMuted)
                                HTMLText(html: meaning.text)
                            }
                        }
                    }
                    .padding(.vertical, 4)
                    .listRowBackground(TJ.panel)
                }
            }
        }
        .scrollContentBackground(.hidden)
        .navigationTitle("Combinations")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            types = (try? appModel.database.writer.read { db in
                orderedDeckTypes(try String.fetchAll(db, sql: """
                    SELECT DISTINCT cartomancy_type FROM archetype_combinations
                    WHERE cartomancy_type IS NOT NULL
                    """))
            }) ?? []
            if types.count == 1 { type = types.first }
        }
        .sheet(isPresented: Binding(
            get: { pickingSlot != nil },
            set: { if !$0 { pickingSlot = nil } }
        )) {
            if let type {
                ArchetypePickerSheet(type: type) { picked in
                    if let slot = pickingSlot { picks[slot] = picked }
                    pickingSlot = nil
                    refresh()
                }
            }
        }
    }

    private func resetPicks() {
        picks = [nil, nil, nil]
        combos = []
        searched = false
    }

    private func refresh() {
        guard ready, let type else { combos = []; searched = false; return }
        let wanted = (0..<cardCount).compactMap { picks[$0]?.id }
        combos = (try? appModel.database.writer.read { db in
            let marks = wanted.map { _ in "?" }.joined(separator: ",")
            let rows = try Row.fetchAll(db, sql: """
                SELECT c.id,
                       a1.name AS n1, c.archetype_1_reversed AS r1,
                       a2.name AS n2, c.archetype_2_reversed AS r2,
                       a3.name AS n3, c.archetype_3_reversed AS r3,
                       c.archetype_1_id AS i1, c.archetype_2_id AS i2,
                       c.archetype_3_id AS i3
                FROM archetype_combinations c
                JOIN card_archetypes a1 ON a1.id = c.archetype_1_id
                JOIN card_archetypes a2 ON a2.id = c.archetype_2_id
                LEFT JOIN card_archetypes a3 ON a3.id = c.archetype_3_id
                WHERE c.cartomancy_type = ?
                  AND c.archetype_1_id IN (\(marks))
                  AND c.archetype_2_id IN (\(marks))
                ORDER BY c.id
                """, arguments: StatementArguments([type] + wanted + wanted))
            return try rows.compactMap { row -> CombinationRow? in
                // Exact multiset match on the chosen cards
                var ids: [Int64] = [row["i1"], row["i2"]]
                if let i3: Int64 = row["i3"] { ids.append(i3) }
                guard ids.count == wanted.count,
                      ids.sorted() == wanted.sorted() else { return nil }
                func part(_ name: String?, _ reversed: Int?) -> String? {
                    guard let name else { return nil }
                    return reversed == 1 ? "\(name) (rev)" : name
                }
                let title = [part(row["n1"], row["r1"]),
                             part(row["n2"], row["r2"]),
                             part(row["n3"], row["r3"])]
                    .compactMap { $0 }
                    .joined(separator: " + ")
                let comboId: Int64 = row["id"]
                let meanings = try Row.fetchAll(db, sql: """
                    SELECT m.id, m.meaning, rs.name AS source_name
                    FROM combination_meanings m
                    LEFT JOIN reference_sources rs ON rs.id = m.source_id
                    WHERE m.combination_id = ? ORDER BY m.sort_order
                    """, arguments: [comboId]).map { mrow ->
                        (id: Int64, sourceName: String, text: String) in
                    (id: mrow["id"],
                     sourceName: mrow["source_name"] ?? "Source",
                     text: mrow["meaning"] ?? "")
                }
                return CombinationRow(id: comboId, title: title, meanings: meanings)
            }
        }) ?? []
        searched = true
    }
}

/// Searchable archetype picker for one combination slot.
struct ArchetypePickerSheet: View {
    let type: String
    let onPick: ((id: Int64, name: String)) -> Void

    @EnvironmentObject private var appModel: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var searchText = ""
    @State private var archetypes: [(id: Int64, name: String)] = []

    var filtered: [(id: Int64, name: String)] {
        guard !searchText.isEmpty else { return archetypes }
        return archetypes.filter {
            $0.name.lowercased().contains(searchText.lowercased())
        }
    }

    var body: some View {
        NavigationStack {
            NocturneScreen {
                List(filtered, id: \.id) { archetype in
                    Button {
                        onPick(archetype)
                        dismiss()
                    } label: {
                        Text(archetype.name).foregroundStyle(TJ.text)
                    }
                    .listRowBackground(TJ.panel)
                }
                .scrollContentBackground(.hidden)
                .searchable(text: $searchText)
            }
            .navigationTitle("Choose a card")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
        .preferredColorScheme(.dark)
        .task {
            archetypes = (try? appModel.database.writer.read { db in
                try Row.fetchAll(db, sql: """
                    SELECT id, name FROM card_archetypes
                    WHERE cartomancy_type = ? ORDER BY id
                    """, arguments: [type]).map { ($0["id"], $0["name"]) }
            }) ?? []
        }
    }
}
