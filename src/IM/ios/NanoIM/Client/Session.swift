import Foundation

/// Owns token rotation and prevents an old account's suspended requests from publishing.
actor Session {
    nonisolated let baseURL: URL
    private let transport: any HTTPTransport
    private let credentials: any CredentialStore
    private var stored: StoredSession?
    private var access: String?
    private var generation = 0
    private var refreshFlight: (id: UUID, task: Task<TokenPair, Error>)?
    private var requests: [UUID: Task<(Data, HTTPURLResponse), Error>] = [:]
    private var observers: [UUID: AsyncStream<AuthUser?>.Continuation] = [:]

    init(baseURL: URL, transport: any HTTPTransport = LiveTransport(), credentials: (any CredentialStore)? = nil) {
        self.baseURL = baseURL
        self.transport = transport
        self.credentials = credentials ?? KeychainCredentials(origin: baseURL)
    }

    func updates() -> AsyncStream<AuthUser?> {
        let id = UUID()
        return AsyncStream { continuation in
            observers[id] = continuation
            continuation.onTermination = { _ in Task { await self.removeObserver(id) } }
        }
    }
    private func removeObserver(_ id: UUID) { observers.removeValue(forKey: id) }
    private func publish(_ user: AuthUser?) { for observer in observers.values { observer.yield(user) } }

    func restore() async throws -> AuthUser? {
        if stored == nil { stored = try credentials.load() }
        guard stored != nil else { return nil }
        return try await refresh().user
    }
    func currentUser() -> AuthUser? { stored?.user }
    func revision() -> Int { generation }

    func login(username: String, password: String, displayName: String? = nil, locale: String = "zh") async throws -> AuthUser {
        invalidateRequests()
        let expected = generation
        stored = nil; access = nil
        try credentials.remove()
        var fields = ["username": username, "password": password]
        if let displayName { fields["display_name"] = displayName; fields["locale"] = locale }
        let path = displayName == nil ? "/im/v1/auth/login" : "/im/v1/auth/register"
        let request = try makeRequest(path: path, method: "POST", body: JSONEncoder().encode(fields))
        let (data, _) = try await tracked(request, expected: expected)
        let pair = try JSONDecoder().decode(TokenPair.self, from: data)
        try install(pair, expected: expected)
        return pair.user
    }

    /// Clears the local session immediately, then revokes the latest rotated credential.
    @discardableResult
    func signOut() async -> Bool {
        let old = stored?.refresh_token
        let flight = refreshFlight?.task
        invalidateRequests()
        stored = nil; access = nil; refreshFlight = nil
        let removed = (try? credentials.remove()) != nil
        publish(nil)
        let rotated = try? await flight?.value
        guard let refresh = rotated?.refresh_token ?? old else { return removed }
        do {
            let request = try makeRequest(path: "/im/v1/auth/logout", method: "POST", body: JSONEncoder().encode(["refresh_token": refresh]))
            _ = try await Self.perform(request, transport: transport)
            return removed
        } catch { return false }
    }

    func updateUser() async throws -> AuthUser {
        let expected = generation
        let (data, _) = try await request(path: "/im/v1/auth/me")
        let user = try JSONDecoder().decode(AuthUser.self, from: data)
        guard expected == generation, let previous = stored, user.id == previous.user.id else { throw CancellationError() }
        let next = StoredSession(refresh_token: previous.refresh_token, user: user)
        try credentials.save(next); stored = next; publish(user)
        return user
    }

    func request(path: String, method: String = "GET", body: Data? = nil,
                 query: [URLQueryItem] = [], headers: [String: String] = [:]) async throws -> (Data, HTTPURLResponse) {
        let expected = generation
        if stored == nil { stored = try credentials.load() }
        guard stored != nil else { throw APIError(status: 401, detail: L("请重新登录。", "Please sign in again.")) }
        if access == nil { _ = try await refresh() }
        guard generation == expected else { throw CancellationError() }
        var request = try makeRequest(path: path, method: method, body: body, query: query)
        for (key, value) in headers { request.setValue(value, forHTTPHeaderField: key) }
        request.setValue("Bearer \(access ?? "")", forHTTPHeaderField: "Authorization")
        do { return try await tracked(request, expected: expected) }
        catch let error as APIError where error.status == 401 {
            _ = try await refresh()
            guard generation == expected else { throw CancellationError() }
            request.setValue("Bearer \(access ?? "")", forHTTPHeaderField: "Authorization")
            return try await tracked(request, expected: expected)
        }
    }

    private func refresh() async throws -> TokenPair {
        let expected = generation
        guard let stored else { throw APIError(status: 401, detail: L("请重新登录。", "Please sign in again.")) }
        let flight: (id: UUID, task: Task<TokenPair, Error>)
        if let existing = refreshFlight { flight = existing }
        else {
            let request = try makeRequest(path: "/im/v1/auth/refresh", method: "POST", body: JSONEncoder().encode(["refresh_token": stored.refresh_token]))
            let transport = self.transport
            flight = (UUID(), Task {
                let (data, _) = try await Self.perform(request, transport: transport)
                return try JSONDecoder().decode(TokenPair.self, from: data)
            })
            refreshFlight = flight
        }
        defer { if refreshFlight?.id == flight.id { refreshFlight = nil } }
        do {
            let pair = try await flight.task.value
            try install(pair, expected: expected)
            return pair
        } catch {
            if generation != expected { throw CancellationError() }
            if (error as? APIError)?.status == 401 {
                invalidateRequests(); self.stored = nil; access = nil
                try? credentials.remove(); publish(nil)
            }
            throw error
        }
    }

    private func install(_ pair: TokenPair, expected: Int) throws {
        guard generation == expected else { throw CancellationError() }
        let next = StoredSession(refresh_token: pair.refresh_token, user: pair.user)
        try credentials.save(next)
        stored = next; access = pair.access_token; publish(pair.user)
    }
    private func invalidateRequests() {
        generation += 1
        requests.values.forEach { $0.cancel() }; requests.removeAll()
    }
    private func tracked(_ request: URLRequest, expected: Int) async throws -> (Data, HTTPURLResponse) {
        let id = UUID(), transport = self.transport
        let task = Task { try await Self.perform(request, transport: transport) }
        requests[id] = task
        defer { requests.removeValue(forKey: id) }
        let result = try await withTaskCancellationHandler { try await task.value } onCancel: { task.cancel() }
        guard expected == generation else { throw CancellationError() }
        return result
    }
    private func makeRequest(path: String, method: String, body: Data?, query: [URLQueryItem] = []) throws -> URLRequest {
        guard path.hasPrefix("/im/"), !path.hasPrefix("//"),
              var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false) else { throw URLError(.badURL) }
        // Feature paths are composed from server IDs; preserve explicit query strings for resource URLs.
        guard let relative = URLComponents(string: path), relative.scheme == nil, relative.host == nil else { throw URLError(.badURL) }
        components.percentEncodedPath = relative.percentEncodedPath
        components.queryItems = (relative.queryItems ?? []) + query
        if components.queryItems?.isEmpty == true { components.queryItems = nil }
        guard let url = components.url else { throw URLError(.badURL) }
        var request = URLRequest(url: url)
        request.httpMethod = method; request.httpBody = body
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if body != nil { request.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        return request
    }
    private static func perform(_ request: URLRequest, transport: any HTTPTransport) async throws -> (Data, HTTPURLResponse) {
        let (data, response) = try await transport.data(for: request)
        guard (200..<300).contains(response.statusCode) else {
            let payload = try? JSONDecoder().decode(JSONValue.self, from: data)
            let detail = payload?["detail"].stringValue ?? payload?["detail"]["message"].stringValue
                ?? HTTPURLResponse.localizedString(forStatusCode: response.statusCode)
            throw APIError(status: response.statusCode, detail: detail,
                           retryAfter: Double(response.value(forHTTPHeaderField: "Retry-After") ?? "") ?? 0,
                           code: payload?["code"].stringValue ?? payload?["detail"]["code"].stringValue)
        }
        return (data, response)
    }
}
