import SwiftUI
import GRDB

/// The phone's card page: image up top (tap for the full-screen
/// zoomable view), then three tabs — Classification (deck, archetype,
/// rank, suit, card notes), Correspondences (per-system assignments
/// for the card's archetype), and Custom Fields (the deck's own
/// fields) — plus a link into the Reference page for the archetype's
/// source texts.
struct CardInfoView: View {
    let cardId: Int64?
    let fallbackName: String?
    var reversed = false

    enum Tab: String, CaseIterable, Identifiable {
        case classification = "Classification"
        case correspondences = "Correspondences"
        case fields = "Custom Fields"
        var id: String { rawValue }
    }

    struct SystemAssignments: Identifiable {
        let id: Int64
        let name: String
        let values: [(field: String, value: String)]
    }

    @EnvironmentObject private var appModel: AppModel
    @Environment(\.dismiss) private var dismiss

    @State private var tab: Tab = {
        #if DEBUG
        let args = ProcessInfo.processInfo.arguments
        if let i = args.firstIndex(of: "-cardTab"), i + 1 < args.count,
           let t = Tab.allCases.first(where: { $0.rawValue.lowercased().hasPrefix(args[i + 1].lowercased()) }) {
            return t
        }
        #endif
        return .classification
    }()
    @State private var name: String?
    @State private var deckName: String?
    @State private var archetype: String?
    @State private var rank: String?
    @State private var suit: String?
    @State private var cardType: String?
    @State private var notes: String?
    @State private var customFields: [(name: String, value: String)] = []
    @State private var systems: [SystemAssignments] = []
    @State private var archetypeId: Int64?
    @State private var showingImage = false

    var body: some View {
        NavigationStack {
            NocturneScreen {
                ScrollView {
                    VStack(alignment: .leading, spacing: 14) {
                        imageHeader

                        Picker("Section", selection: $tab) {
                            ForEach(Tab.allCases) { t in
                                Text(t.rawValue).tag(t)
                            }
                        }
                        .pickerStyle(.segmented)

                        switch tab {
                        case .classification: classificationTab
                        case .correspondences: correspondencesTab
                        case .fields: fieldsTab
                        }

                        if let archetypeId {
                            NavigationLink {
                                ReferenceDetailView(
                                    archetypeId: archetypeId,
                                    archetypeName: archetype ?? name ?? "Archetype")
                            } label: {
                                HStack {
                                    Image(systemName: "text.book.closed")
                                    Text("Reference notes for \(archetype ?? name ?? "this card")")
                                    Spacer()
                                    Image(systemName: "chevron.right")
                                        .font(.caption)
                                        .foregroundStyle(TJ.textMuted)
                                }
                                .foregroundStyle(TJ.textAccent)
                                .padding(12)
                                .background(RoundedRectangle(cornerRadius: 10).fill(TJ.tint))
                            }
                        }
                    }
                    .padding()
                }
            }
            .navigationTitle((name ?? fallbackName ?? "Card")
                             + (reversed ? " (reversed)" : ""))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .preferredColorScheme(.dark)
        .task { load() }
        .sheet(isPresented: $showingImage) {
            CardViewerView(cardId: cardId, name: name ?? fallbackName,
                           reversed: reversed)
        }
    }

    private var imageHeader: some View {
        HStack {
            Spacer()
            CardImageView(cardId: cardId, reversed: reversed)
                .frame(height: 240)
                .clipShape(RoundedRectangle(cornerRadius: 8))
                .onTapGesture { showingImage = true }
            Spacer()
        }
    }

    // MARK: - Tabs

    @ViewBuilder
    private var classificationTab: some View {
        panel {
            infoRow("Deck", deckName)
            infoRow("Archetype", archetype)
            infoRow("Rank", rank)
            infoRow("Suit", suit)
            infoRow("Type", cardType)
        }
        if let notes, !HTMLText.strippedPlainText(notes).isEmpty {
            titledPanel("Card notes") { HTMLText(html: notes) }
        }
    }

    @ViewBuilder
    private var correspondencesTab: some View {
        if systems.isEmpty {
            emptyNote("No correspondences for this card — choose a correspondence system for the deck in the Mac's deck editor.")
        }
        ForEach(systems) { system in
            titledPanel(system.name) {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(system.values, id: \.field) { pair in
                        infoRow(pair.field.replacingOccurrences(of: "_", with: " ").capitalized, pair.value)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var fieldsTab: some View {
        if customFields.isEmpty {
            emptyNote("This deck has no custom fields filled in for this card.")
        }
        ForEach(customFields, id: \.name) { field in
            titledPanel(field.name) { HTMLText(html: field.value) }
        }
    }

    // MARK: - Pieces

    private func infoRow(_ label: String, _ value: String?) -> some View {
        Group {
            if let value, !value.isEmpty {
                HStack(alignment: .firstTextBaseline) {
                    Text(label)
                        .font(.caption)
                        .foregroundStyle(TJ.textMuted)
                        .frame(width: 92, alignment: .leading)
                    Text(value)
                        .font(.callout)
                        .foregroundStyle(TJ.text)
                    Spacer(minLength: 0)
                }
            }
        }
    }

    private func panel(@ViewBuilder content: () -> some View) -> some View {
        VStack(alignment: .leading, spacing: 8) { content() }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(12)
            .background(RoundedRectangle(cornerRadius: 10).fill(TJ.panel))
    }

    private func titledPanel(_ heading: String,
                             @ViewBuilder content: () -> some View) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(heading)
                .font(TJ.serifFont(16))
                .foregroundStyle(TJ.text2)
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 10).fill(TJ.panel))
    }

    private func emptyNote(_ text: String) -> some View {
        Text(text)
            .font(.caption)
            .foregroundStyle(TJ.textFaint)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(12)
            .background(RoundedRectangle(cornerRadius: 10).fill(TJ.panel))
    }

    // MARK: - Data

    /// Field values may be small HTML snippets (the desktop's rich
    /// editor saves "<p>…</p>"); show their text with paragraph
    /// breaks preserved.
    private static func plainText(_ html: String) -> String {
        var text = html
        for lineBreak in ["</p>", "<br>", "<br/>", "<br />"] {
            text = text.replacingOccurrences(of: lineBreak, with: "\n")
        }
        text = text.replacingOccurrences(
            of: "<[^>]+>", with: "", options: .regularExpression)
        let entities = [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                        ("&nbsp;", " "), ("&#39;", "'"), ("&quot;", "\"")]
        for (entity, plain) in entities {
            text = text.replacingOccurrences(of: entity, with: plain)
        }
        return text.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func load() {
        try? appModel.database.writer.read { db in
            var archetypeName: String? = fallbackName
            var deckSystemId: Int64?
            var deckType: String?
            if let cardId,
               let row = try Row.fetchOne(db, sql: """
                   SELECT c.name, c.archetype, c.rank, c.suit, c.notes,
                          c.custom_fields, d.name AS deck_name,
                          d.correspondence_system_id AS system_id,
                          d.cartomancy_type AS deck_type
                   FROM cards c LEFT JOIN decks d ON d.id = c.deck_id
                   WHERE c.id = ?
                   """, arguments: [cardId]) {
                deckSystemId = row["system_id"]
                deckType = row["deck_type"]
                name = row["name"]
                archetype = row["archetype"]
                rank = row["rank"]
                suit = row["suit"]
                notes = row["notes"]
                deckName = row["deck_name"]
                archetypeName = archetype ?? name
                // Custom fields merge two desktop stores, matching
                // the desktop's own rule: the newer per-field table
                // wins over the legacy JSON blob on a name collision
                // (case-insensitive); empty values and the I Ching
                // language keys (shown elsewhere) are skipped.
                var legacy: [(String, String)] = []
                if let raw: String = row["custom_fields"],
                   let data = raw.data(using: .utf8),
                   let dict = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    legacy = dict
                        .compactMap { key, value in
                            let text = Self.plainText(value as? String ?? "")
                            return text.isEmpty ? nil : (key, text)
                        }
                        .sorted { $0.0 < $1.0 }
                }
                let tableRows: [(String, String)] = try Row.fetchAll(
                    db, sql: """
                        SELECT field_name, field_value FROM card_custom_fields
                        WHERE card_id = ?
                        ORDER BY COALESCE(field_order, 0), id
                        """, arguments: [cardId])
                    .compactMap { fieldRow in
                        let name: String = fieldRow["field_name"] ?? ""
                        let text = Self.plainText(fieldRow["field_value"] ?? "")
                        return text.isEmpty ? nil : (name, text)
                    }
                let hidden: Set<String> = ["traditional_chinese", "simplified_chinese"]
                let shadowed = Set(tableRows.map { $0.0.lowercased() })
                var merged: [(name: String, value: String)] = []
                for (fieldName, value) in legacy {
                    let lower = fieldName.lowercased()
                    guard !hidden.contains(lower), !shadowed.contains(lower) else { continue }
                    merged.append((fieldName, value))
                }
                for (fieldName, value) in tableRows
                where !hidden.contains(fieldName.lowercased()) {
                    merged.append((fieldName, value))
                }
                customFields = merged
            }
            // Resolve the archetype (for correspondences and the
            // reference link). Names are matched as-is; when several
            // types share a name, prefer the deck's own type, then the
            // one with source texts.
            if let archetypeName {
                if let row = try Row.fetchOne(db, sql: """
                    SELECT ca.id, ca.cartomancy_type FROM card_archetypes ca
                    LEFT JOIN source_entries se ON se.archetype_id = ca.id
                    WHERE ca.name = ? COLLATE NOCASE
                    GROUP BY ca.id
                    ORDER BY ca.cartomancy_type IS ? DESC, COUNT(se.id) DESC LIMIT 1
                    """, arguments: [archetypeName, deckType]) {
                    archetypeId = row["id"]
                    cardType = row["cartomancy_type"]
                }
            }
            // Only the deck's chosen system, resolved the desktop's
            // way: per-card overrides win over system values.
            if let deckSystemId {
                var values: [String: String] = [:]
                var order: [String] = []
                if let archetypeId {
                    let rows = try Row.fetchAll(db, sql: """
                        SELECT field_name, field_value
                        FROM correspondence_assignments
                        WHERE system_id = ? AND archetype_id = ?
                          AND field_value IS NOT NULL AND field_value != ''
                        ORDER BY field_name
                        """, arguments: [deckSystemId, archetypeId])
                    for row in rows {
                        let field: String = row["field_name"] ?? ""
                        if values[field] == nil { order.append(field) }
                        values[field] = row["field_value"]
                    }
                }
                if let cardId {
                    let overrides = try Row.fetchAll(db, sql: """
                        SELECT field_name, field_value
                        FROM card_correspondence_overrides
                        WHERE card_id = ? AND field_value != ''
                        """, arguments: [cardId])
                    for row in overrides {
                        let field: String = row["field_name"] ?? ""
                        if values[field] == nil { order.append(field) }
                        values[field] = row["field_value"]
                    }
                }
                let systemName = try String.fetchOne(
                    db, sql: "SELECT name FROM correspondence_systems WHERE id = ?",
                    arguments: [deckSystemId]) ?? "Correspondences"
                if !order.isEmpty {
                    systems = [SystemAssignments(
                        id: deckSystemId, name: systemName,
                        values: order.map { ($0, values[$0] ?? "") })]
                }
            }
        }
    }
}
