import SwiftUI
import GRDB

/// The quick-entry composer: querents → one or more readings (each
/// with its own deck, spread, and cards, like the desktop) → notes.
/// Optimized for speed at the reading table; the entry pushes to the
/// Mac (or waits in the outbox when it's unreachable) and gets the
/// "logged on phone" tag there.
struct NewEntryView: View {
    @EnvironmentObject private var appModel: AppModel
    @Environment(\.dismiss) private var dismiss

    struct PickedCard: Identifiable, Equatable {
        let id = UUID()
        var cardId: Int64
        var name: String
        var reversed = false
    }

    struct SpreadOption: Identifiable, Hashable {
        let id: Int64
        let name: String
        let positions: [SpreadPosition]

        var positionLabels: [String] { positions.map { $0.label ?? "" } }

        static func == (lhs: SpreadOption, rhs: SpreadOption) -> Bool {
            lhs.id == rhs.id
        }
        func hash(into hasher: inout Hasher) { hasher.combine(id) }
    }

    /// One reading being composed: its deck, optional spread, and
    /// cards (per-position slots, or a freeform list without one).
    struct ComposedReading: Identifiable {
        let id = UUID()
        var deckId: Int64?
        var spread: SpreadOption?
        var cards: [PickedCard?] = []
        var freeformCards: [PickedCard] = []

        var chosenCards: [PickedCard?] {
            spread != nil ? cards : freeformCards
        }
        /// Card names placed more than once in this reading — almost
        /// certainly a mis-tap with a physical deck. Advisory only.
        var duplicateNames: [String] {
            var counts: [Int64: (name: String, n: Int)] = [:]
            for case let card? in chosenCards {
                var bucket = counts[card.cardId] ?? (card.name, 0)
                bucket.n += 1
                counts[card.cardId] = bucket
            }
            return counts.values.filter { $0.n > 1 }.map { $0.name }
        }
        var isValid: Bool {
            deckId != nil && chosenCards.contains { $0 != nil }
        }
    }

    enum ActivePicker: Identifiable {
        case querent
        case deck(Int)
        case spread(Int)

        var id: String {
            switch self {
            case .querent: return "querent"
            case .deck(let i): return "deck-\(i)"
            case .spread(let i): return "spread-\(i)"
            }
        }
    }

    @State private var title = ""
    @State private var notes = ""
    @State private var querentIds: [Int64] = []
    @State private var readingDate = Date()
    @State private var locationName = ""
    @State private var readings: [ComposedReading] = [ComposedReading()]

    @State private var profiles: [(id: Int64, name: String)] = []
    @State private var decks: [(id: Int64, name: String)] = []
    @State private var spreads: [SpreadOption] = []
    @State private var activePicker: ActivePicker?
    /// The slot the card picker is filling: (reading index, position
    /// index) — position nil means "append freeform".
    @State private var pickingCard: (reading: Int, slot: Int?)?
    @State private var saving = false

    private var canSave: Bool {
        readings.contains { $0.isValid } && !saving
    }

    var body: some View {
        NavigationStack {
            NocturneScreen {
                Form {
                    Group {
                        detailsSection
                        ForEach(readings.indices, id: \.self) { index in
                            readingSection(index)
                        }
                        Section {
                            Button {
                                readings.append(ComposedReading())
                            } label: {
                                Label("Add another reading", systemImage: "plus")
                                    .foregroundStyle(TJ.accent)
                            }
                        }
                        notesSection
                    }
                    .listRowBackground(TJ.panel)
                }
            }
            .navigationTitle("New Entry")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { Task { await save() } }
                        .disabled(!canSave)
                }
            }
            .sheet(isPresented: Binding(
                get: { pickingCard != nil },
                set: { if !$0 { pickingCard = nil } }
            )) {
                if let picking = pickingCard,
                   readings.indices.contains(picking.reading),
                   let deckId = readings[picking.reading].deckId {
                    CardPickerView(deckId: deckId) { picked in
                        place(picked)
                    }
                }
            }
            .sheet(item: $activePicker) { picker in
                optionPicker(for: picker)
            }
        }
        .task { load() }
    }

    private var querentSummary: String {
        let names = querentIds.compactMap { id in
            profiles.first { $0.id == id }?.name
        }
        return names.isEmpty ? "None" : names.joined(separator: ", ")
    }

    @ViewBuilder
    private func optionPicker(for picker: ActivePicker) -> some View {
        switch picker {
        case .querent:
            MultiPickerSheet(
                title: "Querents",
                options: profiles.map { ($0.id, $0.name) },
                selection: $querentIds)
        case .deck(let index):
            OptionPickerSheet(
                title: "Deck",
                options: decks.map { ($0.id, $0.name) },
                noneLabel: nil) { picked in
                if let picked, readings.indices.contains(index) {
                    readings[index].deckId = picked
                }
            }
        case .spread(let index):
            OptionPickerSheet(
                title: "Spread",
                options: spreads.map { ($0.id, $0.name) },
                noneLabel: "No spread") { picked in
                guard readings.indices.contains(index) else { return }
                let spread = spreads.first { $0.id == picked }
                readings[index].spread = spread
                readings[index].cards = Array(
                    repeating: nil, count: spread?.positions.count ?? 0)
            }
        }
    }

    /// A reading's picked cards shaped for the live spread preview.
    private func previewCards(_ reading: ComposedReading) -> [ReadingCard] {
        reading.cards.enumerated().compactMap { index, slot in
            guard let card = slot else { return nil }
            return ReadingCard(
                name: card.name, reversed: card.reversed,
                deckId: reading.deckId, deckName: nil,
                positionIndex: index, cardId: card.cardId, clarifies: nil)
        }
    }

    // MARK: - Sections

    private var detailsSection: some View {
        Section("Entry") {
            TextField("Title (optional)", text: $title)

            pickerRow("Querents", value: querentSummary) {
                activePicker = .querent
            }

            DatePicker("Date & time", selection: $readingDate)
                .tint(TJ.accent)

            TextField("Location (optional)", text: $locationName)
                .autocorrectionDisabled()
        }
    }

    @ViewBuilder
    private func readingSection(_ index: Int) -> some View {
        let reading = readings[index]
        Section {
            pickerRow("Deck",
                      value: decks.first { $0.id == reading.deckId }?.name ?? "Choose…") {
                activePicker = .deck(index)
            }
            pickerRow("Spread", value: reading.spread?.name ?? "No spread") {
                activePicker = .spread(index)
            }

            if !reading.duplicateNames.isEmpty {
                Label(
                    "\(reading.duplicateNames.joined(separator: ", ")) appears more than once in this reading",
                    systemImage: "exclamationmark.triangle")
                    .font(.caption)
                    .foregroundStyle(TJ.textAccent)
            }

            if reading.deckId == nil {
                Text("Choose a deck first.")
                    .font(.caption)
                    .foregroundStyle(TJ.textFaint)
            } else if let spread = reading.spread {
                if !spread.positions.isEmpty {
                    SpreadLayoutView(
                        cards: previewCards(reading),
                        positions: spread.positions,
                        onTapCard: { card in
                            if let slot = card.positionIndex {
                                pickingCard = (index, slot)
                            }
                        },
                        onTapEmptySlot: { pickingCard = (index, $0) },
                        onLongPressCard: { card in
                            if let slot = card.positionIndex,
                               readings[index].cards.indices.contains(slot) {
                                readings[index].cards[slot]?.reversed.toggle()
                            }
                        })
                        .padding(.vertical, 6)
                    Text("Tap a slot to set its card · long-press a card to reverse it")
                        .font(.caption2)
                        .foregroundStyle(TJ.textFaint)
                }
                ForEach(Array(spread.positionLabels.enumerated()),
                        id: \.offset) { slot, label in
                    slotRow(label: label.isEmpty ? "Position \(slot + 1)" : label,
                            card: reading.cards.indices.contains(slot)
                                ? reading.cards[slot] : nil) {
                        pickingCard = (index, slot)
                    } clear: {
                        if readings[index].cards.indices.contains(slot) {
                            readings[index].cards[slot] = nil
                        }
                    } toggleReversed: {
                        if readings[index].cards.indices.contains(slot) {
                            readings[index].cards[slot]?.reversed.toggle()
                        }
                    }
                }
            } else {
                ForEach(Array(reading.freeformCards.enumerated()),
                        id: \.element.id) { cardIndex, card in
                    slotRow(label: "Card \(cardIndex + 1)", card: card) {
                    } clear: {
                        readings[index].freeformCards.remove(at: cardIndex)
                    } toggleReversed: {
                        readings[index].freeformCards[cardIndex].reversed.toggle()
                    }
                }
                Button {
                    pickingCard = (index, nil)
                } label: {
                    Label("Add card", systemImage: "plus")
                }
            }
        } header: {
            HStack {
                Text(readings.count > 1 ? "Reading \(index + 1)" : "Reading")
                Spacer()
                if readings.count > 1 {
                    Button {
                        readings.remove(at: index)
                    } label: {
                        Image(systemName: "trash")
                            .font(.caption)
                            .foregroundStyle(TJ.textFaint)
                    }
                }
            }
        }
    }

    private func pickerRow(_ label: String, value: String,
                           action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack {
                Text(label).foregroundStyle(TJ.text)
                Spacer()
                Text(value)
                    .foregroundStyle(TJ.accent)
                    .lineLimit(1)
                Image(systemName: "chevron.up.chevron.down")
                    .font(.caption2)
                    .foregroundStyle(TJ.textFaint)
            }
        }
    }

    private func slotRow(label: String, card: PickedCard?,
                         pick: @escaping () -> Void,
                         clear: @escaping () -> Void,
                         toggleReversed: @escaping () -> Void) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(label).font(.caption).foregroundStyle(TJ.textMuted)
                if let card {
                    Text(card.name + (card.reversed ? "  ⟲ reversed" : ""))
                        .foregroundStyle(TJ.text)
                } else {
                    Button("Choose card…", action: pick)
                        .foregroundStyle(TJ.accent)
                }
            }
            Spacer()
            if let card {
                Button(action: toggleReversed) {
                    Image(systemName: "arrow.up.arrow.down")
                        .foregroundStyle(card.reversed ? TJ.accent : TJ.textFaint)
                }
                .buttonStyle(.borderless)
                .accessibilityLabel(card.reversed ? "Mark upright" : "Mark reversed")
                Button(action: clear) {
                    Image(systemName: "xmark.circle")
                }
                .buttonStyle(.borderless)
                .foregroundStyle(TJ.textFaint)
            }
        }
    }

    private var notesSection: some View {
        Section("Notes") {
            TextEditor(text: $notes)
                .frame(minHeight: 110)
                .scrollContentBackground(.hidden)
        }
    }

    // MARK: - Behavior

    private func place(_ picked: PickedCard) {
        guard let picking = pickingCard,
              readings.indices.contains(picking.reading) else { return }
        if let slot = picking.slot {
            if readings[picking.reading].cards.indices.contains(slot) {
                readings[picking.reading].cards[slot] = picked
            }
        } else {
            readings[picking.reading].freeformCards.append(picked)
        }
        pickingCard = nil
    }

    private func load() {
        try? appModel.database.writer.read { db in
            profiles = try Row.fetchAll(
                db, sql: "SELECT id, name FROM profiles WHERE hidden IS NOT 1 ORDER BY name")
                .map { ($0["id"], $0["name"]) }
            decks = try Row.fetchAll(
                db, sql: "SELECT id, name FROM decks ORDER BY name")
                .map { ($0["id"], $0["name"]) }
            let decoder = JSONDecoder()
            spreads = try Row.fetchAll(
                db, sql: """
                    SELECT id, name, positions FROM spreads
                    WHERE archived IS NOT 1 ORDER BY name
                    """)
                .map { row in
                    var positions: [SpreadPosition] = []
                    if let raw: String = row["positions"],
                       let data = raw.data(using: .utf8),
                       let decoded = try? decoder.decode([SpreadPosition].self, from: data) {
                        positions = decoded
                    }
                    return SpreadOption(id: row["id"], name: row["name"],
                                        positions: positions)
                }
        }
    }

    private func save() async {
        saving = true

        var readingPayloads: [[String: Any]] = []
        for reading in readings where reading.isValid {
            guard let deckId = reading.deckId else { continue }
            let deckName = decks.first { $0.id == deckId }?.name
            var cardsUsed: [[String: Any]] = []
            for (index, slot) in reading.chosenCards.enumerated() {
                guard let card = slot else { continue }
                cardsUsed.append([
                    "card_id": card.cardId,
                    "name": card.name,
                    "reversed": card.reversed,
                    "position_index": index,
                    "deck_id": deckId,
                    "deck_name": deckName ?? "",
                ])
            }
            readingPayloads.append([
                "deck_id": deckId,
                "spread_id": reading.spread?.id as Any,
                "spread_name": reading.spread?.name as Any,
                "deck_name": deckName ?? "",
                "cards_used": cardsUsed,
            ])
        }

        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"

        var payload: [String: Any] = [
            "sync_uuid": UUID().uuidString,
            "reading_datetime": formatter.string(from: readingDate),
            "querent_ids": querentIds,
            "readings": readingPayloads,
        ]
        if !title.trimmingCharacters(in: .whitespaces).isEmpty {
            payload["title"] = title
        }
        let trimmedLocation = locationName.trimmingCharacters(in: .whitespaces)
        if !trimmedLocation.isEmpty {
            // Name only — the Mac geocodes it into coordinates on arrival.
            payload["location_name"] = trimmedLocation
        }
        let trimmedNotes = notes.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedNotes.isEmpty {
            payload["content"] = Self.paragraphsToHTML(trimmedNotes)
        }

        await appModel.sync.submitEntry(payload)
        saving = false
        dismiss()
    }

    /// Plain text from the phone keyboard becomes the same simple
    /// HTML the desktop's rich-text editor produces.
    static func paragraphsToHTML(_ text: String) -> String {
        text.split(separator: "\n", omittingEmptySubsequences: true)
            .map { line -> String in
                let escaped = String(line)
                    .replacingOccurrences(of: "&", with: "&amp;")
                    .replacingOccurrences(of: "<", with: "&lt;")
                    .replacingOccurrences(of: ">", with: "&gt;")
                return "<p>\(escaped)</p>"
            }
            .joined()
    }
}

// MARK: - Multi-select picker (querents)

/// Searchable multi-select: tap to toggle, Done to finish. Selection
/// order is preserved — the first-tapped querent is the primary one,
/// matching the desktop's ordered querent list.
struct MultiPickerSheet: View {
    let title: String
    let options: [(id: Int64, label: String)]
    @Binding var selection: [Int64]

    @Environment(\.dismiss) private var dismiss
    @State private var searchText = ""

    var filtered: [(id: Int64, label: String)] {
        guard !searchText.isEmpty else { return options }
        return options.filter {
            $0.label.lowercased().contains(searchText.lowercased())
        }
    }

    var body: some View {
        NavigationStack {
            NocturneScreen {
                List(filtered, id: \.id) { option in
                    Button {
                        if let index = selection.firstIndex(of: option.id) {
                            selection.remove(at: index)
                        } else {
                            selection.append(option.id)
                        }
                    } label: {
                        HStack {
                            Text(option.label).foregroundStyle(TJ.text)
                            Spacer()
                            if selection.contains(option.id) {
                                Image(systemName: "checkmark")
                                    .foregroundStyle(TJ.accent)
                            }
                        }
                    }
                    .listRowBackground(TJ.panel)
                }
                .searchable(text: $searchText)
            }
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .preferredColorScheme(.dark)
    }
}

// MARK: - Searchable option picker

/// A searchable list sheet standing in for a dropdown — with dozens
/// of decks and spreads, scrolling a wheel picker doesn't scale.
struct OptionPickerSheet: View {
    let title: String
    let options: [(id: Int64, label: String)]
    let noneLabel: String?
    let onPick: (Int64?) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var searchText = ""

    var filtered: [(id: Int64, label: String)] {
        guard !searchText.isEmpty else { return options }
        return options.filter {
            $0.label.lowercased().contains(searchText.lowercased())
        }
    }

    var body: some View {
        NavigationStack {
            NocturneScreen {
                List {
                    if let noneLabel, searchText.isEmpty {
                        Button {
                            onPick(nil)
                            dismiss()
                        } label: {
                            Text(noneLabel).foregroundStyle(TJ.text3)
                        }
                        .listRowBackground(TJ.panel)
                    }
                    ForEach(filtered, id: \.id) { option in
                        Button {
                            onPick(option.id)
                            dismiss()
                        } label: {
                            Text(option.label).foregroundStyle(TJ.text)
                        }
                        .listRowBackground(TJ.panel)
                    }
                }
                .searchable(text: $searchText)
            }
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
        .preferredColorScheme(.dark)
    }
}

// MARK: - Card picker

struct CardPickerView: View {
    let deckId: Int64
    let onPick: (NewEntryView.PickedCard) -> Void

    @EnvironmentObject private var appModel: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var searchText = ""
    @State private var cards: [(id: Int64, name: String)] = []

    var filtered: [(id: Int64, name: String)] {
        guard !searchText.isEmpty else { return cards }
        return cards.filter { $0.name.lowercased().contains(searchText.lowercased()) }
    }

    var body: some View {
        NavigationStack {
            NocturneScreen {
                List(filtered, id: \.id) { card in
                    HStack(spacing: 10) {
                        Button {
                            onPick(.init(cardId: card.id, name: card.name))
                            dismiss()
                        } label: {
                            HStack(spacing: 10) {
                                CardImageView(cardId: card.id)
                                    .frame(width: 30, height: 46)
                                    .clipShape(RoundedRectangle(cornerRadius: 3))
                                Text(card.name).foregroundStyle(TJ.text)
                            }
                        }
                        .buttonStyle(.borderless)
                        Spacer()
                        Button {
                            onPick(.init(cardId: card.id, name: card.name,
                                         reversed: true))
                            dismiss()
                        } label: {
                            Text("⟲ rev")
                                .font(.caption)
                                .foregroundStyle(TJ.textAccent)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(Capsule().fill(TJ.tint))
                        }
                        .buttonStyle(.borderless)
                        .accessibilityLabel("Choose \(card.name) reversed")
                    }
                    .listRowBackground(TJ.panel)
                }
                .searchable(text: $searchText, prompt: "Card name…")
            }
            .navigationTitle("Choose a card")
            .navigationBarTitleDisplayMode(.inline)
        }
        .task {
            cards = (try? appModel.database.writer.read { db in
                try Row.fetchAll(
                    db, sql: "SELECT id, name FROM cards WHERE deck_id = ? ORDER BY card_order, id",
                    arguments: [deckId]).map { ($0["id"], $0["name"]) }
            }) ?? []
        }
    }
}
