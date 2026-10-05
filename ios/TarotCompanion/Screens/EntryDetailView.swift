import SwiftUI
import GRDB

// MARK: - Models decoded from the entry aggregate's JSON

struct ReadingCard: Decodable, Identifiable, Hashable {
    let name: String?
    let reversed: Bool?
    let deckId: Int64?
    let deckName: String?
    let positionIndex: Int?
    let cardId: Int64?
    let clarifies: Int?

    var id: String { "\(cardId ?? 0)-\(positionIndex ?? -1)" }

    enum CodingKeys: String, CodingKey {
        case name, reversed, clarifies
        case deckId = "deck_id"
        case deckName = "deck_name"
        case positionIndex = "position_index"
        case cardId = "card_id"
    }
}

struct Reading: Decodable, Identifiable {
    let id: Int64
    let spreadId: Int64?
    let spreadName: String?
    let deckName: String?
    let cardsUsed: [ReadingCard]?
    let notes: String?
    let querentId: Int64?

    enum CodingKeys: String, CodingKey {
        case id, notes
        case querentId = "querent_id"
        case spreadId = "spread_id"
        case spreadName = "spread_name"
        case deckName = "deck_name"
        case cardsUsed = "cards_used"
    }

    /// Decode an entry's readings_json column; empty when absent or malformed.
    static func decodeList(_ raw: String?) -> [Reading] {
        guard let data = raw?.data(using: .utf8) else { return [] }
        return (try? JSONDecoder().decode([Reading].self, from: data)) ?? []
    }
}

struct SpreadPosition: Decodable {
    let x: Double
    let y: Double
    let width: Double
    let height: Double
    let label: String?
    let rotated: Bool?
    let zIndex: Int?

    enum CodingKeys: String, CodingKey {
        case x, y, width, height, label, rotated
        case zIndex = "z_index"
    }
}

struct FollowUpNote: Decodable, Identifiable {
    let id: Int64
    let content: String?
    let createdAt: String?

    enum CodingKeys: String, CodingKey {
        case id, content
        case createdAt = "created_at"
    }
}

// MARK: - Entry detail

struct EntryDetailView: View {
    let entryId: Int64

    @EnvironmentObject private var appModel: AppModel
    @State private var title: String?
    @State private var content: String?
    @State private var readingDatetime: String?
    @State private var locationName: String?
    @State private var readings: [Reading] = []
    @State private var followUps: [FollowUpNote] = []
    @State private var querentNames: [String] = []
    @State private var querentNameById: [Int64: String] = [:]
    @State private var readerName: String?
    @State private var tags: [(name: String, color: String?)] = []
    @State private var positionsBySpread: [Int64: [SpreadPosition]] = [:]
    @State private var viewingCard: ReadingCard?
    @State private var zoomedReading: Reading?

    var body: some View {
        NocturneScreen {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    header
                    ForEach(readings) { reading in
                        readingSection(reading)
                    }
                    if let content, !content.isEmpty {
                        notesPanel("Notes", html: content)
                    }
                    ForEach(followUps) { note in
                        notesPanel(
                            followUpTitle(note),
                            html: note.content ?? "")
                    }
                }
                .padding()
            }
        }
        .navigationTitle(title ?? "Reading")
        .navigationBarTitleDisplayMode(.inline)
        .task { load() }
        .sheet(item: $viewingCard) { card in
            CardInfoView(cardId: card.cardId, fallbackName: card.name,
                         reversed: card.reversed ?? false)
        }
        .sheet(item: $zoomedReading) { reading in
            NavigationStack {
                ZStack {
                    TJ.canvas.ignoresSafeArea()
                    ZoomableScrollView {
                        SpreadLayoutView(
                            cards: reading.cardsUsed ?? [],
                            positions: reading.spreadId.flatMap { positionsBySpread[$0] },
                            onTapCard: { viewingCard = $0 })
                            .padding(10)
                    }
                }
                .navigationTitle(reading.spreadName ?? "Spread")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Done") { zoomedReading = nil }
                    }
                }
            }
            .preferredColorScheme(.dark)
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            if let title {
                Text(title)
                    .font(TJ.displayFont(24))
                    .foregroundStyle(TJ.text2)
            }
            if let readingDatetime {
                Text(JournalListView.displayDate(readingDatetime))
                    .font(.subheadline)
                    .foregroundStyle(TJ.textMuted)
            }
            if let locationName, !locationName.isEmpty {
                Label(locationName, systemImage: "mappin.and.ellipse")
                    .font(.caption)
                    .foregroundStyle(TJ.text3)
            }
            if !querentNames.isEmpty || readerName != nil {
                HStack(spacing: 12) {
                    if !querentNames.isEmpty {
                        Label(querentNames.joined(separator: ", "),
                              systemImage: "person")
                    }
                    if let readerName {
                        Label(readerName, systemImage: "eye")
                    }
                }
                .font(.caption)
                .foregroundStyle(TJ.text3)
            }
            if !tags.isEmpty {
                HStack(spacing: 6) {
                    ForEach(tags, id: \.name) { tag in
                        Text(tag.name)
                            .font(.caption2)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 3)
                            .background(Capsule().fill(TJ.tint))
                            .foregroundStyle(TJ.textAccent)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func readingSection(_ reading: Reading) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                if let spreadName = reading.spreadName {
                    Text(spreadName)
                        .font(TJ.serifFont(17))
                        .foregroundStyle(TJ.text2)
                }
                Spacer()
                if let deckName = reading.deckName {
                    Text(deckName)
                        .font(.caption)
                        .foregroundStyle(TJ.textFaint)
                }
                if reading.cardsUsed?.isEmpty == false {
                    Button {
                        zoomedReading = reading
                    } label: {
                        Image(systemName: "arrow.up.left.and.arrow.down.right")
                            .font(.caption)
                    }
                    .accessibilityLabel("View spread full screen")
                }
            }
            if let id = reading.querentId, let name = querentNameById[id] {
                Text("For \(name)")
                    .font(.caption)
                    .foregroundStyle(TJ.textFaint)
            }
            if let cards = reading.cardsUsed, !cards.isEmpty {
                SpreadLayoutView(
                    cards: cards,
                    positions: reading.spreadId.flatMap { positionsBySpread[$0] },
                    onTapCard: { viewingCard = $0 })
            }
            if let notes = reading.notes, !notes.isEmpty {
                notesPanel("Reading notes", html: notes)
            }
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 10).fill(TJ.panel))
    }

    private func notesPanel(_ heading: String, html: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(heading)
                .font(.caption)
                .textCase(.uppercase)
                .foregroundStyle(TJ.textMuted)
            HTMLText(html: html)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 10).fill(TJ.panel))
    }

    private func followUpTitle(_ note: FollowUpNote) -> String {
        guard let created = note.createdAt else { return "Follow-up" }
        return "Follow-up · \(JournalListView.displayDate(created))"
    }

    private func load() {
        try? appModel.database.writer.read { db in
            guard let row = try Row.fetchOne(
                db, sql: "SELECT * FROM entries WHERE id = ?",
                arguments: [entryId]) else { return }
            title = row["title"]
            content = row["content"]
            readingDatetime = row["reading_datetime"]
            locationName = row["location_name"]

            let decoder = JSONDecoder()
            readings = Reading.decodeList(row["readings_json"])
            if let raw: String = row["follow_ups_json"],
               let data = raw.data(using: .utf8) {
                followUps = (try? decoder.decode([FollowUpNote].self, from: data)) ?? []
            }

            // Spread layouts for each reading
            for reading in readings {
                guard let spreadId = reading.spreadId else { continue }
                if let raw = try String.fetchOne(
                    db, sql: "SELECT positions FROM spreads WHERE id = ?",
                    arguments: [spreadId]),
                   let data = raw.data(using: .utf8) {
                    positionsBySpread[spreadId] =
                        try? decoder.decode([SpreadPosition].self, from: data)
                }
            }

            // Querent / reader names
            if let raw: String = row["querent_ids_json"],
               let data = raw.data(using: .utf8),
               let ids = try? decoder.decode([Int64].self, from: data),
               !ids.isEmpty {
                let marks = ids.map { _ in "?" }.joined(separator: ",")
                let rows = try Row.fetchAll(
                    db, sql: "SELECT id, name FROM profiles WHERE id IN (\(marks))",
                    arguments: StatementArguments(ids))
                for row in rows { querentNameById[row["id"]] = row["name"] }
                querentNames = ids.compactMap { querentNameById[$0] }
            }
            if let readerId: Int64 = row["reader_id"] {
                readerName = try String.fetchOne(
                    db, sql: "SELECT name FROM profiles WHERE id = ?",
                    arguments: [readerId])
            }

            // Tags
            if let raw: String = row["tag_ids_json"],
               let data = raw.data(using: .utf8),
               let ids = try? decoder.decode([Int64].self, from: data),
               !ids.isEmpty {
                let marks = ids.map { _ in "?" }.joined(separator: ",")
                tags = try Row.fetchAll(
                    db, sql: "SELECT name, color FROM tags WHERE id IN (\(marks))",
                    arguments: StatementArguments(ids))
                    .map { ($0["name"], $0["color"]) }
            }
        }
    }
}

// MARK: - The spread layout renderer

/// Draws a reading's cards in their spread's 2D arrangement, scaled
/// to fit the phone's width. Falls back to a flowing grid when the
/// spread has no stored layout.
struct SpreadLayoutView: View {
    let cards: [ReadingCard]
    let positions: [SpreadPosition]?
    var onTapCard: ((ReadingCard) -> Void)?
    var onTapEmptySlot: ((Int) -> Void)?
    var onLongPressCard: ((ReadingCard) -> Void)?

    var body: some View {
        if let positions, !positions.isEmpty {
            VStack(alignment: .leading, spacing: 0) {
                positionedLayout(positions)
                extrasSection(positions)
            }
        } else {
            gridLayout
        }
    }

    private func positionedLayout(_ positions: [SpreadPosition]) -> some View {
        // Bounding box of the design-time layout (desktop pixels).
        let minX = positions.map(\.x).min() ?? 0
        let minY = positions.map(\.y).min() ?? 0
        let maxX = positions.map { $0.x + $0.width }.max() ?? 1
        let maxY = positions.map { $0.y + $0.height }.max() ?? 1
        let designWidth = max(maxX - minX, 1)
        let designHeight = max(maxY - minY, 1)

        return GeometryReader { geo in
            let scale = geo.size.width / designWidth
            ZStack(alignment: .topLeading) {
                // Only the spread's own slots; extra/clarifier cards
                // (position_index beyond the layout) get their own
                // rows beneath, one per clarified card, like the
                // desktop journal.
                ForEach(Array(positions.enumerated()), id: \.offset) { index, pos in
                    let card = cards.first { ($0.positionIndex ?? -1) == index }
                    positionedCard(card, at: pos, index: index,
                                   minX: minX, minY: minY, scale: scale)
                }
            }
        }
        .aspectRatio(designWidth / designHeight, contentMode: .fit)
    }

    // MARK: Extra / clarifier rows

    @ViewBuilder
    private func extrasSection(_ positions: [SpreadPosition]) -> some View {
        let extras = cards.filter { ($0.positionIndex ?? -1) >= positions.count }
        if !extras.isEmpty {
            let targets = Array(Set(extras.compactMap { card -> Int? in
                guard let t = card.clarifies,
                      t >= 0, t < positions.count else { return nil }
                return t
            })).sorted()
            let unattached = extras.filter {
                guard let t = $0.clarifies else { return true }
                return t < 0 || t >= positions.count
            }
            VStack(alignment: .leading, spacing: 10) {
                ForEach(targets, id: \.self) { target in
                    extrasGroup(
                        title: clarifyingTitle(target, positions: positions),
                        groupCards: extras.filter { $0.clarifies == target })
                }
                if !unattached.isEmpty {
                    extrasGroup(title: "Extra cards", groupCards: unattached)
                }
            }
            .padding(.top, 12)
        }
    }

    private func clarifyingTitle(_ target: Int,
                                 positions: [SpreadPosition]) -> String {
        let label = positions[target].label
        let posLabel = (label?.isEmpty == false) ? label! : "position \(target + 1)"
        if let clarified = cards.first(where: { $0.positionIndex == target }),
           let name = clarified.name, !name.isEmpty {
            return "↳ Clarifying \(name) (\(posLabel))"
        }
        return "↳ Clarifying \(posLabel)"
    }

    private func extrasGroup(title: String,
                             groupCards: [ReadingCard]) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption2.weight(.semibold))
                .foregroundStyle(TJ.textMuted)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(alignment: .top, spacing: 8) {
                    ForEach(groupCards) { card in
                        VStack(spacing: 3) {
                            CardImageView(cardId: card.cardId,
                                          reversed: card.reversed ?? false)
                                .frame(height: 90)
                                .onTapGesture { onTapCard?(card) }
                                .onLongPressGesture { onLongPressCard?(card) }
                            Text(card.name ?? "")
                                .font(.system(size: 9))
                                .foregroundStyle(TJ.textFaint)
                                .lineLimit(1)
                                .frame(maxWidth: 70)
                        }
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func positionedCard(_ card: ReadingCard?, at pos: SpreadPosition,
                                index: Int, minX: Double, minY: Double,
                                scale: CGFloat) -> some View {
        let w = pos.width * scale
        let h = pos.height * scale
        VStack(spacing: 2) {
            Group {
                if let card {
                    CardImageView(cardId: card.cardId,
                                  reversed: card.reversed ?? false)
                        .onTapGesture { onTapCard?(card) }
                        .onLongPressGesture { onLongPressCard?(card) }
                } else {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(TJ.well)
                        .overlay(RoundedRectangle(cornerRadius: 4)
                            .strokeBorder(TJ.hairline, style: .init(dash: [4])))
                        .contentShape(Rectangle())
                        .onTapGesture { onTapEmptySlot?(index) }
                }
            }
            .frame(width: w, height: h)
            .rotationEffect((pos.rotated ?? false) ? .degrees(90) : .zero)

            // Labels only where there's room — in a tight cluster
            // (Celtic Cross center) they'd pile on each other.
            if let label = pos.label, !label.isEmpty, w >= 55 {
                Text(label)
                    .font(.system(size: 9))
                    .foregroundStyle(TJ.textFaint)
                    .lineLimit(1)
                    .frame(maxWidth: max(w, 60))
            }
        }
        .offset(x: (pos.x - minX) * scale, y: (pos.y - minY) * scale)
        .zIndex(Double(pos.zIndex ?? 0))
    }

    private var gridLayout: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 70), spacing: 8)],
                  spacing: 8) {
            ForEach(cards) { card in
                VStack(spacing: 3) {
                    CardImageView(cardId: card.cardId,
                                  reversed: card.reversed ?? false)
                        .frame(height: 110)
                        .onTapGesture { onTapCard?(card) }
                    Text(card.name ?? "")
                        .font(.system(size: 9))
                        .foregroundStyle(TJ.textFaint)
                        .lineLimit(1)
                }
            }
        }
    }
}
