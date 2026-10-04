import XCTest
@testable import NanoIM

@MainActor
final class ChatStateTests: XCTestCase {
    private let user = AuthUser(id: "user", username: "user", display_name: "User", owner_id: "user", locale: "en", membership_status: "active", is_company_admin: false, owned_node_ids: [], created_at: "now")

    func testMembershipControlWithoutCursorRemovesCachedContentAndDraft() throws {
        let store = ChatStore(client: IMClient(baseURL: URL(string: "https://im.example.test")!), user: user)
        store.timelines["chat"] = [try message(1)]
        store.drafts["chat"] = "private draft"
        store.attachments["chat"] = [ChatAttachment(url: "/im/v1/uploads/private")]
        store.pending["chat"] = PendingSend(content: "unsent", attachments: [])
        let event = try JSONDecoder().decode(UserEvent.self, from: Data(#"{"op":"event","event_type":"conversation.membership_changed","data":{"conversation_id":"chat"}}"#.utf8))
        store.consume(event)
        XCTAssertNil(store.timelines["chat"])
        XCTAssertNil(store.drafts["chat"])
        XCTAssertNil(store.attachments["chat"])
        XCTAssertNil(store.pending["chat"])
        store.clear()
    }

    func testReconnectFillsMoreThanOnePageGapBeforeKeepingOlderCursor() async throws {
        let latest = try (62...121).map { try message($0) }
        let bridge = try (2...61).map { try message($0) }
        let pair = TokenPair(access_token: "test-access", refresh_token: "test-refresh", user: user)
        let transport = HistoryTransport(pair: try JSONEncoder().encode(pair), latest: try JSONEncoder().encode(MessagePage(items: latest, next_before_message_id: "m62")), bridge: try JSONEncoder().encode(MessagePage(items: bridge, next_before_message_id: "m2")))
        let session = Session(baseURL: URL(string: "https://im.example.test")!, transport: transport, credentials: ChatTestCredentials())
        _ = try await session.login(username: "user", password: "test")
        let store = ChatStore(client: IMClient(baseURL: session.baseURL, session: session), user: user)
        store.timelines["chat"] = try (1...60).map { try message($0) }
        store.before["chat"] = "m1"
        await store.loadChat("chat")
        XCTAssertEqual(store.timelines["chat"]?.map(\.id), (1...121).map { "m\($0)" })
        XCTAssertEqual(store.before["chat"], "m1")
        let cursors = await transport.cursors
        XCTAssertEqual(cursors, [nil, "m62"])
        store.clear()
    }

    private func message(_ n: Int) throws -> TimelineItem {
        let payload: [String: Any] = ["type":"message", "message":["id":"m\(n)","conversation_id":"chat","sender":["type":"agent","id":"agent"],"sender_user_id":"agent-user","sender_type":"agent","content":"message \(n)","attachments":[],"delivery_status":"completed","created_at":"2026-01-01"]]
        return try JSONDecoder().decode(TimelineItem.self, from: JSONSerialization.data(withJSONObject: payload))
    }
}
private struct ChatTestCredentials: CredentialStore {
    func load() throws -> StoredSession? { nil }
    func save(_ value: StoredSession) throws {}
    func remove() throws {}
}
private actor HistoryTransport: HTTPTransport {
    let pair: Data; let latest: Data; let bridge: Data
    var cursors: [String?] = []
    init(pair: Data, latest: Data, bridge: Data) { self.pair = pair; self.latest = latest; self.bridge = bridge }
    func data(for request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let url = request.url!
        let body: Data
        if url.path.contains("/auth/") { body = pair }
        else {
            let cursor = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems?.first { $0.name == "before_message_id" }?.value
            cursors.append(cursor); body = cursor == nil ? latest : bridge
        }
        return (body, HTTPURLResponse(url: url, statusCode: 200, httpVersion: nil, headerFields: [:])!)
    }
}
