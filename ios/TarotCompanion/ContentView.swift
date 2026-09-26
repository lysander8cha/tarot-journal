import SwiftUI

struct ContentView: View {
    @State private var selectedTab = ContentView.initialTab()
    #if DEBUG
    // A real @State, not .constant — the routed screen must be able
    // to dismiss itself (Cancel/Save in the composer, for instance).
    @State private var debugRoute = DebugRoute.fromLaunchArguments()
    #endif

    static func initialTab() -> Int {
        #if DEBUG
        let args = ProcessInfo.processInfo.arguments
        if let index = args.firstIndex(of: "-openTab"), index + 1 < args.count {
            switch args[index + 1] {
            case "reference": return 1
            case "decks": return 2
            case "insights": return 3
            case "settings": return 4
            default: return 0
            }
        }
        #endif
        return 0
    }

    var body: some View {
        TabView(selection: $selectedTab) {
            JournalListView()
                .tabItem { Label("Journal", systemImage: "book.closed") }
                .tag(0)
            ReferenceView()
                .tabItem { Label("Reference", systemImage: "text.magnifyingglass") }
                .tag(1)
            DecksView()
                .tabItem { Label("Decks", systemImage: "rectangle.portrait.on.rectangle.portrait") }
                .tag(2)
            InsightsView()
                .tabItem { Label("Insights", systemImage: "chart.bar") }
                .tag(3)
            SettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape") }
                .tag(4)
        }
        #if DEBUG
        .sheet(item: $debugRoute) { route in
            // Launch-argument deep links so screens can be opened from
            // `simctl launch` during development, e.g.
            //   ... com.aslyon.TarotCompanion -openEntry 323
            NavigationStack {
                switch route {
                case .entry(let id): EntryDetailView(entryId: id)
                case .deck(let id): DeckDetailView(deckId: id, deckName: "Deck")
                case .archetype(let id):
                    ReferenceDetailView(archetypeId: id, archetypeName: "Archetype")
                case .compose: NewEntryView()
                case .refCombos: CombinationsView()
                case .refByType: DeckTypeListView()
                case .card(let id): CardInfoView(cardId: id, fallbackName: nil)
                }
            }
            .preferredColorScheme(.dark)
        }
        #endif
    }
}

#if DEBUG
enum DebugRoute: Identifiable {
    case entry(Int64)
    case deck(Int64)
    case archetype(Int64)
    case card(Int64)
    case compose
    case refCombos
    case refByType

    var id: String {
        switch self {
        case .entry(let id): return "entry-\(id)"
        case .deck(let id): return "deck-\(id)"
        case .archetype(let id): return "archetype-\(id)"
        case .card(let id): return "card-\(id)"
        case .compose: return "compose"
        case .refCombos: return "refCombos"
        case .refByType: return "refByType"
        }
    }

    static func fromLaunchArguments() -> DebugRoute? {
        let args = ProcessInfo.processInfo.arguments
        func value(after flag: String) -> Int64? {
            guard let index = args.firstIndex(of: flag),
                  index + 1 < args.count else { return nil }
            return Int64(args[index + 1])
        }
        if let id = value(after: "-openEntry") { return .entry(id) }
        if let id = value(after: "-openDeck") { return .deck(id) }
        if let id = value(after: "-openArchetype") { return .archetype(id) }
        if let id = value(after: "-openCard") { return .card(id) }
        if args.contains("-compose") { return .compose }
        if args.contains("-refCombos") { return .refCombos }
        if args.contains("-refByType") { return .refByType }
        return nil
    }
}
#endif

#Preview {
    ContentView()
        .environmentObject(AppModel())
}
