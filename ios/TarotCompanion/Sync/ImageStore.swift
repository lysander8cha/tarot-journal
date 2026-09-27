import Foundation
import SwiftUI

/// Fetches phone-sized card images from the Mac and keeps them on
/// disk, so images load once over Wi-Fi and then work offline.
/// An actor: concurrent screens can request images safely.
actor ImageStore {
    private let cacheDir: URL
    private let serverURL: @Sendable () -> URL?
    private var inFlight: [Int64: Task<UIImage?, Never>] = [:]

    /// One image should arrive in seconds (the Mac may generate the
    /// derivative on first request); a stalled connection must fail
    /// fast rather than hold the pre-download queue for a minute.
    private static let session: URLSession = {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 20
        config.timeoutIntervalForResource = 60
        return URLSession(configuration: config)
    }()

    init(serverURL: @escaping @Sendable () -> URL?) {
        self.serverURL = serverURL
        let caches = FileManager.default.urls(
            for: .cachesDirectory, in: .userDomainMask)[0]
        cacheDir = caches.appendingPathComponent("card-images", isDirectory: true)
        try? FileManager.default.createDirectory(
            at: cacheDir, withIntermediateDirectories: true)
    }

    private func localURL(for cardId: Int64) -> URL {
        cacheDir.appendingPathComponent("card_\(cardId).png")
    }

    func isCached(_ cardId: Int64) -> Bool {
        FileManager.default.fileExists(atPath: localURL(for: cardId).path)
    }

    func image(for cardId: Int64) async -> UIImage? {
        if let cached = UIImage(contentsOfFile: localURL(for: cardId).path) {
            return cached
        }

        // Coalesce concurrent requests for the same card.
        if let task = inFlight[cardId] {
            return await task.value
        }
        let task = Task<UIImage?, Never> {
            await self.fetch(cardId: cardId)
        }
        inFlight[cardId] = task
        let result = await task.value
        inFlight[cardId] = nil
        return result
    }

    private func fetch(cardId: Int64) async -> UIImage? {
        guard let base = serverURL() else { return nil }
        var req = URLRequest(url: base.appendingPathComponent("api/sync/card-image/\(cardId)"))
        if let token = Keychain.token {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        guard let (data, response) = try? await Self.session.data(for: req),
              let http = response as? HTTPURLResponse, http.statusCode == 200,
              let image = UIImage(data: data) else { return nil }
        try? data.write(to: localURL(for: cardId))
        return image
    }
}

/// A card image that shows a themed placeholder until (or unless)
/// the real image is available.
struct CardImageView: View {
    let cardId: Int64?
    var reversed = false
    var contentMode: ContentMode = .fit

    @EnvironmentObject private var appModel: AppModel
    @State private var image: UIImage?

    var body: some View {
        Group {
            if let image {
                Image(uiImage: image)
                    .resizable()
                    .aspectRatio(contentMode: contentMode)
            } else {
                RoundedRectangle(cornerRadius: 4)
                    .fill(TJ.card)
                    .overlay(
                        RoundedRectangle(cornerRadius: 4)
                            .strokeBorder(TJ.hairline))
            }
        }
        .rotationEffect(reversed ? .degrees(180) : .zero)
        .task(id: cardId) {
            guard let cardId else { return }
            image = await appModel.images.image(for: cardId)
        }
    }
}
