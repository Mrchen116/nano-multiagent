import Foundation

/// Typed feature operations share this authenticated transport rather than managing tokens.
actor IMClient {
    nonisolated let baseURL: URL
    nonisolated let session: Session
    init(baseURL: URL, session: Session? = nil) {
        self.baseURL = baseURL
        self.session = session ?? Session(baseURL: baseURL)
    }
    func serverURL() -> URL { baseURL }
    func get<T: Decodable & Sendable>(_ path: String, query: [URLQueryItem] = []) async throws -> T {
        try await request(path, query: query)
    }
    func send<T: Decodable & Sendable, B: Encodable & Sendable>(_ path: String, method: String = "POST", body: B) async throws -> T {
        try await request(path, method: method, body: JSONEncoder().encode(body))
    }
    func delete<T: Decodable & Sendable>(_ path: String, query: [URLQueryItem] = []) async throws -> T {
        try await request(path, method: "DELETE", query: query)
    }
    func request<T: Decodable & Sendable>(_ path: String, method: String = "GET", body: Data? = nil,
                                         query: [URLQueryItem] = [], headers: [String: String] = [:]) async throws -> T {
        let (data, _) = try await session.request(path: path, method: method, body: body, query: query, headers: headers)
        return try JSONDecoder().decode(T.self, from: data.isEmpty ? Data("{}".utf8) : data)
    }
    func contacts(kind: String? = nil, search: String = "") async throws -> [Contact] {
        var result: [Contact] = [], cursor: String?
        repeat {
            var query = [URLQueryItem(name: "q", value: search)]
            if let kind { query.append(.init(name: "kind", value: kind)) }
            if let cursor { query.append(.init(name: "cursor", value: cursor)) }
            let page: ItemsPage<Contact> = try await get("/im/v1/contacts", query: query)
            result += page.items; cursor = page.next_cursor
        } while cursor != nil
        return result
    }
    func protectedResource(_ source: String) async throws -> (Data, String) {
        let url = try ServerOrigin.resource(source, base: baseURL)
        let (data, response) = try await session.request(path: url.path + (url.query.map { "?" + $0 } ?? ""))
        return (data, response.mimeType ?? "application/octet-stream")
    }
}
