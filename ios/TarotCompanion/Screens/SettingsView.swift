import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var appModel: AppModel
    @StateObject private var discovery = ServerDiscovery()

    @State private var pairingCode = ""
    @State private var manualAddress = ""
    @State private var selectedURL: URL?
    @State private var selectedName: String?
    @State private var isPairing = false
    @State private var errorMessage: String?
    @State private var paired = false
    @State private var testing = false
    @State private var testResult: String?

    var body: some View {
        NavigationStack {
            NocturneScreen {
                Form {
                    Group {
                        if paired {
                            pairedSection
                        } else {
                            pairingSection
                        }
                    }
                    .listRowBackground(TJ.panel)
                }
            }
            .navigationTitle("Settings")
        }
        .onAppear {
            paired = appModel.sync.isPaired
            if !paired { discovery.start() }
        }
        .onDisappear { discovery.stop() }
    }

    // MARK: - Paired state

    private var pairedSection: some View {
        Section("Sync") {
            LabeledContent("Mac", value: appModel.sync.serverURL?.host() ?? "—")
            if let last = appModel.sync.lastSyncDate {
                LabeledContent("Last sync",
                               value: last.formatted(date: .omitted, time: .shortened))
            }
            // The journal shows phone entries immediately and no
            // longer announces the outbox; its state lives here.
            if appModel.sync.pendingCount > 0 {
                LabeledContent(
                    "Entries waiting to reach the Mac",
                    value: "\(appModel.sync.pendingCount)")
            }
            if let status = appModel.sync.statusMessage {
                Text(status).font(.caption).foregroundStyle(.secondary)
            }
            if let progress = appModel.sync.imageProgress {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Downloading card images — \(progress.done) of \(progress.total)")
                        .font(.caption)
                        .foregroundStyle(TJ.text3)
                    ProgressView(value: Double(progress.done),
                                 total: Double(max(progress.total, 1)))
                        .tint(TJ.accent)
                    Text("Keep the Mac awake with the desktop app open. If this is interrupted, the next sync picks up where it left off.")
                        .font(.caption2)
                        .foregroundStyle(TJ.textFaint)
                }
            }
            Button {
                Task { await appModel.sync.syncNow() }
            } label: {
                if appModel.sync.isSyncing {
                    HStack { ProgressView(); Text("Syncing…") }
                } else {
                    Text("Sync now")
                }
            }
            .disabled(appModel.sync.isSyncing)

            Button("Unpair from this Mac", role: .destructive) {
                appModel.sync.unpair()
                paired = false
                discovery.start()
            }
        }
    }

    // MARK: - Pairing flow

    @ViewBuilder
    private var pairingSection: some View {
        Section("Find your Mac") {
            if discovery.servers.isEmpty {
                HStack {
                    ProgressView()
                    Text("Looking for the Tarot Journal app on your Wi-Fi…")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            ForEach(discovery.servers) { server in
                Button {
                    discovery.resolveAll(server) { urls in
                        let url = urls.first
                        selectedURL = url
                        selectedName = server.name
                        if url == nil {
                            errorMessage = "Couldn't resolve \(server.name)'s address. "
                                + "Check that Local Network access is allowed "
                                + "(Settings → Apps → Tarot Companion), or enter "
                                + "the Mac's address below."
                        }
                    }
                } label: {
                    HStack {
                        Text(server.name)
                        Spacer()
                        if selectedName == server.name && selectedURL != nil {
                            Image(systemName: "checkmark")
                        }
                    }
                }
            }
        }

        Section("Or enter the address manually") {
            TextField("192.168.x.x", text: $manualAddress)
                .keyboardType(.numbersAndPunctuation)
                .autocorrectionDisabled()
                .textInputAutocapitalization(.never)
            Button("Test connection") {
                Task { await testConnection() }
            }
            .disabled(pairingHost == nil || testing)
            if let testResult {
                Text(testResult).font(.caption).foregroundStyle(TJ.text3)
            }
        }

        Section("Pairing code") {
            TextField("6-digit code from the Mac's Settings", text: $pairingCode)
                .keyboardType(.numberPad)
            Button {
                Task { await doPair() }
            } label: {
                if isPairing {
                    HStack { ProgressView(); Text("Pairing…") }
                } else {
                    Text("Pair")
                }
            }
            .disabled(pairingCode.count != 6 || isPairing
                      || (selectedURL == nil && manualAddress.isEmpty))
            if let errorMessage {
                Text(errorMessage).font(.caption).foregroundStyle(.red)
            }
            Text("On the Mac: Settings → General → Phone Sync → Show pairing code.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    /// A typed address always wins over an earlier tap in the
    /// discovery list — the manual field is the escape hatch, so it
    /// must never be silently ignored.
    private var pairingHost: URL? {
        let trimmed = manualAddress.trimmingCharacters(in: .whitespaces)
        if !trimmed.isEmpty {
            let raw = trimmed.contains("://") ? trimmed : "http://\(trimmed):5678"
            return URL(string: raw)
        }
        return selectedURL
    }

    private func doPair() async {
        errorMessage = nil
        guard let host = pairingHost else {
            errorMessage = "Pick your Mac from the list or enter its address."
            return
        }
        isPairing = true
        defer { isPairing = false }
        do {
            try await appModel.sync.pair(
                host: host, code: pairingCode,
                deviceName: UIDevice.current.name)
            paired = true
            discovery.stop()
            await appModel.sync.syncNow()
        } catch let error as URLError {
            errorMessage = "\(error.localizedDescription) (network code \(error.code.rawValue), trying \(host.absoluteString))"
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    /// Plain reachability check against the sync API — answers
    /// "can this phone see the Mac at that address?" with specifics,
    /// separate from any pairing-code concerns.
    private func testConnection() async {
        guard let host = pairingHost else { return }
        testing = true
        testResult = "Testing \(host.absoluteString)…"
        defer { testing = false }
        var req = URLRequest(url: host.appendingPathComponent("api/sync/manifest"))
        req.timeoutInterval = 6
        do {
            let (_, response) = try await URLSession.shared.data(for: req)
            let code = (response as? HTTPURLResponse)?.statusCode ?? 0
            if code == 200 || code == 401 {
                testResult = "✓ The Mac answered at \(host.absoluteString). Pairing should work."
            } else {
                testResult = "Reached \(host.absoluteString) but got HTTP \(code) — is the desktop app running with phone sync enabled?"
            }
        } catch let error as URLError {
            switch error.code {
            case .cannotConnectToHost, .timedOut, .cannotFindHost:
                testResult = "✗ Nothing answered at \(host.absoluteString) — wrong address, or the Mac isn't on this network. (code \(error.code.rawValue))"
            default:
                testResult = "✗ \(error.localizedDescription) (code \(error.code.rawValue)). If this happens on every network, check Local Network permission for this app in the phone's Settings."
            }
        } catch {
            testResult = "✗ \(error.localizedDescription)"
        }
    }
}
