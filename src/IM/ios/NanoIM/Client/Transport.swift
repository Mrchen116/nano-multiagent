import Foundation

protocol HTTPTransport: Sendable {
    func data(for request: URLRequest) async throws -> (Data, HTTPURLResponse)
}

/// A protected request must never follow an off-origin redirect with credentials.
final class OriginRedirectDelegate: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest,
                    completionHandler: @escaping (URLRequest?) -> Void) {
        guard let original = task.originalRequest?.url, let next = request.url,
              ServerOrigin.same(original, next) else { completionHandler(nil); return }
        completionHandler(request)
    }
}

final class LiveTransport: HTTPTransport, @unchecked Sendable {
    private let session: URLSession
    init() {
        let config = URLSessionConfiguration.ephemeral
        config.httpCookieStorage = nil
        config.urlCache = nil
        config.timeoutIntervalForRequest = 30
        session = URLSession(configuration: config, delegate: OriginRedirectDelegate(), delegateQueue: nil)
    }
    func data(for request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw URLError(.badServerResponse) }
        return (data, http)
    }
}

enum ServerOrigin {
    static func parse(_ text: String, allowLoopback: Bool = false) throws -> URL {
        guard var c = URLComponents(string: text.trimmingCharacters(in: .whitespacesAndNewlines)),
              let host = c.host, c.user == nil, c.password == nil, c.query == nil, c.fragment == nil,
              c.path.isEmpty || c.path == "/",
              c.scheme == "https" || (allowLoopback && c.scheme == "http" && ["localhost", "127.0.0.1", "::1"].contains(host))
        else { throw APIError(status: 0, detail: L("请输入完整 HTTPS 服务地址，不含路径。", "Enter an HTTPS server origin without a path.")) }
        c.path = ""
        guard let url = c.url else { throw URLError(.badURL) }
        return url
    }
    static func same(_ lhs: URL, _ rhs: URL) -> Bool {
        func port(_ url: URL) -> Int? { url.port ?? (url.scheme == "https" ? 443 : url.scheme == "http" ? 80 : nil) }
        return lhs.scheme?.lowercased() == rhs.scheme?.lowercased() && lhs.host?.lowercased() == rhs.host?.lowercased() && port(lhs) == port(rhs)
    }
    static func resource(_ text: String, base: URL) throws -> URL {
        guard let url = URL(string: text, relativeTo: base)?.absoluteURL,
              same(base, url), url.user == nil, url.password == nil,
              url.path.hasPrefix("/im/") else { throw APIError(status: 0, detail: L("无法读取非本服务的受保护资源。", "Protected resources must belong to this server.")) }
        return url
    }
}
