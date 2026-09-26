import Combine
import SwiftUI

@main
struct TarotCompanionApp: App {
    // One shared database and sync engine for the whole app.
    @StateObject private var appModel = AppModel()

    init() {
        TJ.applyAppearance()
    }

    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appModel)
                .preferredColorScheme(.dark)
                .tint(TJ.accent)
        }
        .onChange(of: scenePhase) { _, phase in
            // Opening the app on home Wi-Fi is the sync moment: pull
            // quietly whenever we come to the foreground while paired.
            if phase == .active && appModel.sync.isPaired {
                Task { await appModel.sync.syncNow() }
            }
        }
    }
}

/// App-wide state: the local database, the sync connection, and
/// whatever the UI needs to observe about them.
@MainActor
final class AppModel: ObservableObject {
    let database: AppDatabase
    let sync: SyncEngine
    let images: ImageStore

    @Published var lastSyncError: String?
    private var cancellables = Set<AnyCancellable>()

    init() {
        do {
            database = try AppDatabase.open()
        } catch {
            // A companion app with no database can't do anything useful;
            // crashing early with a clear message beats limping along.
            fatalError("Could not open the local database: \(error)")
        }
        sync = SyncEngine(database: database)
        let engine = sync
        images = ImageStore(serverURL: { engine.serverURL })
        sync.imageStore = images

        // Views observe AppModel (the environment object); the sync
        // engine's own published changes (progress, status, pending
        // count) must flow through it or the UI silently goes stale —
        // which is exactly what happened to the first progress bar.
        sync.objectWillChange
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in self?.objectWillChange.send() }
            .store(in: &cancellables)

        #if DEBUG && targetEnvironment(simulator)
        if ProcessInfo.processInfo.arguments.contains("-seedComposerTest") {
            // UI-test mode: plant fixtures and point sync at the UI
            // test's tar-pit server (accepts connections, never
            // replies — what an asleep Mac looks like from the
            // phone), so saving must not wait on the network and
            // nothing can touch the real desktop app.
            try? database.seedForComposerUITest()
            try? database.setSyncState(
                "server_url", "http://127.0.0.1:5998")
        } else {
            // Development convenience: in the simulator, talk to the
            // desktop app on this Mac without pairing (loopback is
            // trusted by the desktop), and pull on every launch so the
            // simulator always shows live data. Never compiled into
            // device builds.
            if engine.serverURL == nil {
                try? database.setSyncState(
                    "server_url", "http://127.0.0.1:5678")
            } else if engine.serverURL?.port == 5998 {
                // A UI-test run left the tar-pit configured. Point the
                // simulator back at the desktop app and drop the test
                // outbox (only "ZZ" fixtures can be queued in that
                // state — they must never push to the real journal).
                try? database.setSyncState(
                    "server_url", "http://127.0.0.1:5678")
                try? database.writer.write { db in
                    try db.execute(sql: "DELETE FROM pending_entries")
                }
            }
            Task { await engine.syncNow() }
        }
        #endif
    }
}
