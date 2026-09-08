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

    enum CodingKeys: String, CodingKey {
        case id, notes
        case spreadId = "spread_id"
        case spreadName = "spread_name"
        case deckName = "deck_name"
        case cardsUsed = "cards_used"
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
            if let raw: String = row["readings_json"],
               let data = raw.data(using: .utf8) {
                readings = (try? decoder.decode([Reading].self, from: data)) ?? []
            }
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
                querentNames = try String.fetchAll(
                    db, sql: "SELECT name FROM profiles WHERE id IN (\(marks))",
                    arguments: StatementArguments(ids))
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
            positionedLayout(positions)
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

        let mainCards = cards.filter { $0.clarifies == nil }
        let clarifiers = cards.filter { $0.clarifies != nil }

        return GeometryReader { geo in
            let scale = geo.size.width / designWidth
            ZStack(alignment: .topLeading) {
                ForEach(Array(positions.enumerated()), id: \.offset) { index, pos in
                    let card = mainCards.first { ($0.positionIndex ?? -1) == index }
                    positionedCard(card, at: pos, index: index,
                                   minX: minX, minY: minY, scale: scale)
                }
                // Clarifiers ride on their target's corner.
                ForEach(clarifiers) { card in
                    if let target = card.clarifies, target < positions.count {
                        let pos = positions[target]
                        clarifierCard(card, on: pos,
                                      minX: minX, minY: minY, scale: scale)
                    }
                }
            }
        }
        .aspectRatio(designWidth / designHeight, contentMode: .fit)
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

    private func clarifierCard(_ card: ReadingCard, on pos: SpreadPosition,
                               minX: Double, minY: Double,
                               scale: CGFloat) -> some View {
        let w = pos.width * scale * 0.6
        let h = pos.height * scale * 0.6
        return CardImageView(cardId: card.cardId, reversed: card.reversed ?? false)
            .onTapGesture { onTapCard?(card) }
            .frame(width: w, height: h)
            .shadow(radius: 3)
            .offset(x: (pos.x - minX + pos.width * 0.55) * scale,
                    y: (pos.y - minY + pos.height * 0.55) * scale)
            .zIndex(10)
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
