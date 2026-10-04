import SwiftUI
import Charts
import GRDB

/// Read-only stats over the synced journal, computed on the phone.
/// Everything here derives from the entry aggregates alone (card
/// names, decks, reversals live inside readings_json), so it works
/// for cards from any deck, favorited or not.
struct InsightsView: View {
    @EnvironmentObject private var appModel: AppModel

    struct CardCount: Identifiable {
        let name: String
        let count: Int
        var id: String { name }
    }
    struct MonthCount: Identifiable {
        let month: String
        let count: Int
        var id: String { month }
    }
    struct DeckCount: Identifiable {
        let name: String
        let count: Int
        var id: String { name }
    }

    @State private var topCards: [CardCount] = []
    @State private var byMonth: [MonthCount] = []
    @State private var topDecks: [DeckCount] = []
    @State private var totalEntries = 0
    @State private var totalCards = 0
    @State private var reversalRate: Double = 0

    var body: some View {
        NavigationStack {
            NocturneScreen {
                if totalEntries == 0 {
                    ContentUnavailableView(
                        "No data yet",
                        systemImage: "chart.bar",
                        description: Text("Sync your journal to see trends."))
                } else {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 16) {
                            summaryRow
                            chartPanel("Readings per month") { monthChart }
                            chartPanel("Most drawn cards") { cardChart }
                            chartPanel("Most used decks") { deckChart }
                        }
                        .padding()
                    }
                }
            }
            .navigationTitle("Insights")
        }
        .task { load() }
        .onReceive(appModel.sync.$lastSyncDate) { _ in load() }
    }

    // MARK: - Pieces

    private var summaryRow: some View {
        HStack(spacing: 10) {
            summaryTile("\(totalEntries)", "entries")
            summaryTile("\(totalCards)", "cards drawn")
            summaryTile(reversalRate.formatted(.percent.precision(.fractionLength(0))),
                        "reversed")
        }
    }

    private func summaryTile(_ value: String, _ label: String) -> some View {
        VStack(spacing: 2) {
            Text(value)
                .font(TJ.displayFont(24))
                .foregroundStyle(TJ.textAccent)
            Text(label)
                .font(.caption2)
                .foregroundStyle(TJ.textMuted)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(RoundedRectangle(cornerRadius: 10).fill(TJ.panel))
    }

    private func chartPanel(_ title: String,
                            @ViewBuilder content: () -> some View) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title)
                .font(TJ.serifFont(17))
                .foregroundStyle(TJ.text2)
            content()
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 10).fill(TJ.panel))
    }

    private var monthChart: some View {
        Chart(byMonth) { item in
            BarMark(x: .value("Month", item.month),
                    y: .value("Readings", item.count))
                .foregroundStyle(TJ.accent.opacity(0.75))
        }
        .chartXAxis {
            AxisMarks { value in
                AxisValueLabel(orientation: .vertical)
                    .foregroundStyle(TJ.textFaint)
            }
        }
        .chartYAxis {
            AxisMarks { _ in
                AxisGridLine().foregroundStyle(TJ.hairline)
                AxisValueLabel().foregroundStyle(TJ.textFaint)
            }
        }
        .frame(height: 190)
    }

    private var cardChart: some View {
        Chart(topCards) { item in
            BarMark(x: .value("Times drawn", item.count),
                    y: .value("Card", item.name))
                .foregroundStyle(TJ.accent.opacity(0.75))
        }
        .chartXAxis {
            AxisMarks { _ in
                AxisGridLine().foregroundStyle(TJ.hairline)
                AxisValueLabel().foregroundStyle(TJ.textFaint)
            }
        }
        .chartYAxis {
            AxisMarks { _ in
                AxisValueLabel().foregroundStyle(TJ.text3)
            }
        }
        .frame(height: CGFloat(topCards.count) * 26 + 30)
    }

    private var deckChart: some View {
        Chart(topDecks) { item in
            BarMark(x: .value("Readings", item.count),
                    y: .value("Deck", item.name))
                .foregroundStyle(TJ.accent.opacity(0.55))
        }
        .chartXAxis {
            AxisMarks { _ in
                AxisGridLine().foregroundStyle(TJ.hairline)
                AxisValueLabel().foregroundStyle(TJ.textFaint)
            }
        }
        .chartYAxis {
            AxisMarks { _ in
                AxisValueLabel().foregroundStyle(TJ.text3)
            }
        }
        .frame(height: CGFloat(topDecks.count) * 26 + 30)
    }

    // MARK: - Aggregation

    private func load() {
        let rows = (try? appModel.database.writer.read { db in
            try Row.fetchAll(db, sql: """
                SELECT reading_datetime, readings_json FROM entries
                """)
        }) ?? []

        var cardCounts: [String: Int] = [:]
        var deckCounts: [String: Int] = [:]
        var monthCounts: [String: Int] = [:]
        var cards = 0
        var reversals = 0
        for row in rows {
            if let datetime: String = row["reading_datetime"],
               datetime.count >= 7 {
                let month = String(datetime.prefix(7))   // "2026-09"
                monthCounts[month, default: 0] += 1
            }
            for reading in Reading.decodeList(row["readings_json"]) {
                if let deck = reading.deckName {
                    deckCounts[deck, default: 0] += 1
                }
                for card in reading.cardsUsed ?? [] {
                    cards += 1
                    if card.reversed == true { reversals += 1 }
                    if let name = card.name {
                        cardCounts[name, default: 0] += 1
                    }
                }
            }
        }

        totalEntries = rows.count
        totalCards = cards
        reversalRate = cards > 0 ? Double(reversals) / Double(cards) : 0
        topCards = cardCounts
            .sorted { $0.value > $1.value }.prefix(10)
            .map { CardCount(name: $0.key, count: $0.value) }
        topDecks = deckCounts
            .sorted { $0.value > $1.value }.prefix(8)
            .map { DeckCount(name: $0.key, count: $0.value) }
        byMonth = monthCounts
            .sorted { $0.key < $1.key }.suffix(12)
            .map { MonthCount(month: $0.key, count: $0.value) }
    }
}
