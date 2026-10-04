import Foundation
import Network

/// Browses Bonjour for the desktop app's `_tarotjournal._tcp` service
/// so pairing doesn't require typing an IP address.
///
/// Browsing uses the modern NWBrowser; resolving a service to a
/// concrete IP uses Foundation's NetService, which (though marked
/// deprecated) reliably surfaces the address records, where
/// NWConnection's currentPath does not always.
@MainActor
final class ServerDiscovery: NSObject, ObservableObject {
    struct FoundServer: Identifiable, Hashable {
        let id = UUID()
        let name: String
    }

    @Published var servers: [FoundServer] = []
    private var browser: NWBrowser?
    private var resolvingService: NetService?
    private var resolveCompletion: (([URL]) -> Void)?
    private var resolveTimeout: Task<Void, Never>?

    func start() {
        stop()
        let browser = NWBrowser(
            for: .bonjour(type: "_tarotjournal._tcp", domain: nil),
            using: .tcp)
        browser.browseResultsChangedHandler = { [weak self] results, _ in
            let found = results.compactMap { result -> FoundServer? in
                if case let .service(name, _, _, _) = result.endpoint {
                    return FoundServer(name: name)
                }
                return nil
            }
            Task { @MainActor in self?.servers = found }
        }
        browser.start(queue: .main)
        self.browser = browser
    }

    func stop() {
        browser?.cancel()
        browser = nil
        cancelResolve()
    }

    private func cancelResolve() {
        resolvingService?.stop()
        resolvingService = nil
        resolveTimeout?.cancel()
        resolveTimeout = nil
        resolveCompletion = nil
    }

    /// Resolve a discovered service to EVERY address it advertises —
    /// the Mac announces one per interface (Wi-Fi, hotspot, USB
    /// tether), and only probing tells which one the phone can reach.
    /// Completion fires once, on the main actor.
    func resolveAll(_ server: FoundServer,
                    completion: @escaping ([URL]) -> Void) {
        cancelResolve()
        let service = NetService(domain: "local.",
                                 type: "_tarotjournal._tcp.",
                                 name: server.name)
        service.delegate = self
        resolvingService = service
        resolveCompletion = completion
        service.resolve(withTimeout: 8)
        resolveTimeout = Task { @MainActor [weak self] in
            try? await Task.sleep(for: .seconds(9))
            guard let self, self.resolveCompletion != nil else { return }
            self.finishResolve(urls: [])
        }
    }

    /// Browse briefly and return every candidate URL for the first
    /// Mac found. Used for automatic re-discovery when the stored
    /// address stops answering.
    func findServerURLs(browseDeadline: TimeInterval = 4) async -> [URL] {
        start()
        defer { stop() }
        let began = Date()
        while servers.isEmpty
                && Date().timeIntervalSince(began) < browseDeadline {
            try? await Task.sleep(for: .milliseconds(250))
        }
        guard let first = servers.first else { return [] }
        return await withCheckedContinuation { continuation in
            resolveAll(first) { continuation.resume(returning: $0) }
        }
    }

    private func finishResolve(urls: [URL]) {
        let completion = resolveCompletion
        cancelResolve()
        completion?(urls)
    }

    /// All usable addresses from the resolved records, IPv4 first.
    nonisolated private static func urls(from service: NetService) -> [URL] {
        var v4s: [String] = []
        var v6s: [String] = []
        for data in service.addresses ?? [] {
            data.withUnsafeBytes { (raw: UnsafeRawBufferPointer) in
                guard let base = raw.baseAddress else { return }
                let family = base.assumingMemoryBound(to: sockaddr.self).pointee.sa_family
                var host = [CChar](repeating: 0, count: Int(NI_MAXHOST))
                let ok = getnameinfo(
                    base.assumingMemoryBound(to: sockaddr.self),
                    socklen_t(data.count),
                    &host, socklen_t(host.count),
                    nil, 0, NI_NUMERICHOST) == 0
                guard ok else { return }
                let ip = String(cString: host)
                if family == sa_family_t(AF_INET) {
                    v4s.append(ip)
                } else if family == sa_family_t(AF_INET6) {
                    v6s.append(ip)
                }
            }
        }
        var urls = v4s.compactMap {
            URL(string: "http://\($0):\(service.port)")
        }
        urls += v6s.compactMap { v6 -> URL? in
            // Scoped link-local addresses need the zone percent-encoded.
            let escaped = v6.replacingOccurrences(of: "%", with: "%25")
            return URL(string: "http://[\(escaped)]:\(service.port)")
        }
        return urls
    }
}

extension ServerDiscovery: NetServiceDelegate {
    nonisolated func netServiceDidResolveAddress(_ sender: NetService) {
        let urls = Self.urls(from: sender)
        Task { @MainActor in self.finishResolve(urls: urls) }
    }

    nonisolated func netService(_ sender: NetService,
                                didNotResolve errorDict: [String: NSNumber]) {
        Task { @MainActor in self.finishResolve(urls: []) }
    }
}
