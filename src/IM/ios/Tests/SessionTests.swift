import XCTest
@testable import NanoIM

final class SessionTests: XCTestCase {
    private let origin = URL(string: "https://im.example.test")!
    private func user(_ id: String = "alice") -> AuthUser {
        AuthUser(id: id, username: id, display_name: id, owner_id: id, locale: "en", membership_status: "active", is_company_admin: false, default_entry_node_id: nil, owned_node_ids: [], created_at: "2026-01-01")
    }
    private func pair(_ user: AuthUser, token: String = "rotated") throws -> Data {
        try JSONEncoder().encode(TokenPair(access_token: "access-" + token, refresh_token: token, user: user))
    }
    func testConcurrentRequestsShareRefreshAndUseBearerWithoutBrowserCookies() async throws {
        let data = try pair(user())
        let transport = SessionTestTransport(refreshData: data, held: ["/im/v1/auth/refresh"])
        let vault = SessionTestCredentials(StoredSession(refresh_token: "old", user: user()))
        let session = Session(baseURL: origin, transport: transport, credentials: vault)
        let first = Task { try await session.request(path: "/im/v1/policies") }
        await transport.waitFor("/im/v1/auth/refresh")
        let second = Task { try await session.request(path: "/im/v1/nodes") }
        await transport.release("/im/v1/auth/refresh")
        _ = try await first.value; _ = try await second.value
        let requests = await transport.recorded()
        XCTAssertEqual(requests.filter { $0.url?.path == "/im/v1/auth/refresh" }.count, 1)
        for request in requests where request.url?.path != "/im/v1/auth/refresh" {
            XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer access-rotated")
            XCTAssertNil(request.value(forHTTPHeaderField: "X-IM-Session"))
            XCTAssertNil(request.value(forHTTPHeaderField: "Cookie"))
        }
        XCTAssertEqual(try vault.load()?.refresh_token, "rotated")
    }
    func testLateAccountResponseCannotReturnAfterSignOut() async throws {
        let transport = SessionTestTransport(refreshData: try pair(user()), held: ["/im/v1/policies"])
        let vault = SessionTestCredentials(StoredSession(refresh_token: "old", user: user()))
        let session = Session(baseURL: origin, transport: transport, credentials: vault)
        let request = Task { try await session.request(path: "/im/v1/policies") }
        await transport.waitFor("/im/v1/policies")
        let revoked = await session.signOut()
        await transport.release("/im/v1/policies")
        do { _ = try await request.value; XCTFail("Old account response was returned") } catch is CancellationError {} catch { XCTFail("Unexpected: \(error)") }
        XCTAssertTrue(revoked)
        XCTAssertNil(try vault.load())
    }
    func testSignOutRevokesCredentialRotatedByInFlightRefresh() async throws {
        let transport = SessionTestTransport(refreshData: try pair(user(), token: "newest"), held: ["/im/v1/auth/refresh"])
        let vault = SessionTestCredentials(StoredSession(refresh_token: "old", user: user()))
        let session = Session(baseURL: origin, transport: transport, credentials: vault)
        let restore = Task { try await session.restore() }
        await transport.waitFor("/im/v1/auth/refresh")
        let updates = await session.updates()
        let localSignOut = Task { for await user in updates { if user == nil { return } } }
        let logout = Task { await session.signOut() }
        await localSignOut.value
        await transport.release("/im/v1/auth/refresh")
        _ = await logout.value
        do { _ = try await restore.value; XCTFail("Restore must not reauthenticate after sign-out") } catch is CancellationError {} catch { XCTFail("Unexpected: \(error)") }
        let requests = await transport.recorded()
        let body = try XCTUnwrap(requests.first { $0.url?.path == "/im/v1/auth/logout" }?.httpBody)
        XCTAssertEqual(try JSONDecoder().decode([String: String].self, from: body)["refresh_token"], "newest")
        XCTAssertNil(try vault.load())
    }
    func testTransientRefreshFailureKeepsCredentialButUnauthorizedClearsIt() async throws {
        for status in [503, 401] {
            let vault = SessionTestCredentials(StoredSession(refresh_token: "old", user: user()))
            let transport = SessionTestTransport(refreshData: Data("{\"detail\":\"unavailable\"}".utf8), refreshStatus: status)
            let session = Session(baseURL: origin, transport: transport, credentials: vault)
            do { _ = try await session.restore(); XCTFail("Expected error") } catch let error as APIError { XCTAssertEqual(error.status, status) }
            XCTAssertEqual(try vault.load() != nil, status == 503)
        }
    }
    func testProtectedResourceRejectsForeignOriginBeforeTransport() throws {
        XCTAssertThrowsError(try ServerOrigin.resource("https://evil.test/im/v1/uploads/x", base: origin))
        XCTAssertThrowsError(try ServerOrigin.resource("https://im.example.test:9443/im/v1/uploads/x", base: origin))
        XCTAssertEqual(try ServerOrigin.resource("/im/v1/conversations/c/images/i", base: origin).host, origin.host)
        XCTAssertThrowsError(try ServerOrigin.parse("http://im.example.test", allowLoopback: true))
        XCTAssertNoThrow(try ServerOrigin.parse("http://127.0.0.1:19443", allowLoopback: true))
        XCTAssertThrowsError(try ServerOrigin.parse("http://127.0.0.1:19443"))
    }
}

private final class SessionTestCredentials: CredentialStore, @unchecked Sendable {
    private let lock = NSLock()
    private var value: StoredSession?
    init(_ value: StoredSession?) { self.value = value }
    func load() throws -> StoredSession? { lock.lock(); defer { lock.unlock() }; return value }
    func save(_ value: StoredSession) throws { lock.lock(); defer { lock.unlock() }; self.value = value }
    func remove() throws { lock.lock(); defer { lock.unlock() }; value = nil }
}

private actor SessionTestTransport: HTTPTransport {
    let refreshData: Data
    let refreshStatus: Int
    var held: Set<String>
    var requests: [URLRequest] = []
    var waiters: [String: [CheckedContinuation<Void, Never>]] = [:]
    var paused: [String: [CheckedContinuation<Void, Never>]] = [:]
    init(refreshData: Data, refreshStatus: Int = 200, held: Set<String> = []) { self.refreshData = refreshData; self.refreshStatus = refreshStatus; self.held = held }
    func recorded() -> [URLRequest] { requests }
    func waitFor(_ path: String) async {
        if requests.contains(where: { $0.url?.path == path }) { return }
        await withCheckedContinuation { waiters[path, default: []].append($0) }
    }
    func release(_ path: String) {
        held.remove(path)
        for waiter in paused.removeValue(forKey: path) ?? [] { waiter.resume() }
    }
    func data(for request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let path = request.url!.path
        requests.append(request)
        for waiter in waiters.removeValue(forKey: path) ?? [] { waiter.resume() }
        if held.contains(path) { await withCheckedContinuation { paused[path, default: []].append($0) } }
        let isRefresh = path == "/im/v1/auth/refresh"
        return (isRefresh ? refreshData : Data("{}".utf8), HTTPURLResponse(url: request.url!, statusCode: isRefresh ? refreshStatus : 200, httpVersion: nil, headerFields: [:])!)
    }
}
