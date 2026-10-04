import XCTest
@testable import NanoIM

@MainActor
final class ChatStateTests: XCTestCase {
    private let user = AuthUser(id: "user", username: "user", display_name: "User", owner_id: "user", locale: "en", membership_status: "active", is_company_admin: false, owned_node_ids: [], created_at: "now")

    func testMembershipControlWithoutCursorRemovesCachedContentAndDraft() async throws {
        let store = try await makeStore()
        store.timelines["chat"] = [try message(1)]
        store.drafts["chat"] = "private draft"
        store.attachments["chat"] = [ChatAttachment(url: "/im/v1/uploads/private")]
        store.pending["chat"] = PendingSend(content: "unsent", attachments: [])
        let event = try JSONDecoder().decode(UserEvent.self, from: Data(#"{"op":"event","event_type":"conversation.membership_changed","data":{"conversation_id":"chat"}}"#.utf8))
        store.consume(event)
        XCTAssertNil(store.timelines["chat"])
        await store.loadConversations()
        XCTAssertNil(store.timelines["chat"])
        XCTAssertNil(store.drafts["chat"])
        XCTAssertNil(store.attachments["chat"])
        XCTAssertNil(store.pending["chat"])
        store.clear()
    }

    func testMembershipRenameKeepsDraftAndRestoresAuthorizedConversation() async throws {
        let list = Data(#"{"items":[{"id":"chat","title":"Renamed","participants":[],"participant_ids":["user"],"type":"group","owner_id":"user","creator_id":"user","is_pinned":false,"is_muted":false,"unread_count":0,"created_at":"now"}]}"#.utf8)
        let store = try await makeStore(list: list)
        store.timelines["chat"] = [try message(1)]
        store.drafts["chat"] = "keep this draft"
        store.attachments["chat"] = [ChatAttachment(url: "/im/v1/uploads/own")]
        let event = try JSONDecoder().decode(UserEvent.self, from: Data(#"{"op":"event","event_type":"conversation.membership_changed","data":{"conversation_id":"chat"}}"#.utf8))
        store.consume(event)
        await store.loadConversations()
        XCTAssertEqual(store.drafts["chat"], "keep this draft")
        XCTAssertEqual(store.attachments["chat"]?.count, 1)
        XCTAssertEqual(store.conversations.first?.title, "Renamed")
        await store.loadChat("chat")
        XCTAssertEqual(store.timelines["chat"]?.map(\.id), ["m1"])
        store.clear()
    }

    private func makeStore(list: Data = Data(#"{"items":[]}"#.utf8)) async throws -> ChatStore {
        let pair = TokenPair(access_token: "test", refresh_token: "test", user: user)
        let page = try JSONEncoder().encode(MessagePage(items: [try message(1)]))
        let transport = HistoryTransport(pair: try JSONEncoder().encode(pair), latest: page, bridge: page, list: list)
        let session = Session(baseURL: URL(string: "https://im.example.test")!, transport: transport, credentials: ChatTestCredentials())
        _ = try await session.login(username: "user", password: "test")
        return ChatStore(client: IMClient(baseURL: session.baseURL, session: session), user: user)
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

    func testLostSendResponseRequiresExplicitRetryWithSameKeyAndNoDuplicateHistory() async throws {
        let pair = TokenPair(access_token: "test", refresh_token: "test", user: user)
        let received = try message(1)
        let list = Data(#"{"items":[{"id":"chat","title":"Chat","participants":[],"participant_ids":["user"],"type":"group","owner_id":"user","creator_id":"user","is_pinned":false,"is_muted":false,"unread_count":0,"created_at":"now"}]}"#.utf8)
        let transport = LostSendTransport(pair: try JSONEncoder().encode(pair), message: try JSONEncoder().encode(received.message!), page: try JSONEncoder().encode(MessagePage(items: [received])), list: list)
        let session = Session(baseURL: URL(string: "https://im.example.test")!, transport: transport, credentials: ChatTestCredentials())
        _ = try await session.login(username: "user", password: "test")
        let store = ChatStore(client: IMClient(baseURL: session.baseURL, session: session), user: user)
        store.drafts["chat"] = "message 1"
        await store.send("chat")
        XCTAssertNotNil(store.pending["chat"])
        XCTAssertNotNil(store.errors["chat"])
        XCTAssertEqual(store.timelines["chat"]?.map(\.id), ["m1"])

        // History recovery and the normal send action must not silently resend.
        await store.loadChat("chat")
        await store.send("chat")
        let initialKeys = await transport.keys
        XCTAssertEqual(initialKeys.count, 1)
        XCTAssertFalse(initialKeys[0].isEmpty)
        await store.send("chat", retry: true)
        let retryKeys = await transport.keys
        XCTAssertEqual(retryKeys, [initialKeys[0], initialKeys[0]])
        XCTAssertNil(store.pending["chat"])
        XCTAssertEqual(store.drafts["chat"], "")
        XCTAssertEqual(store.timelines["chat"]?.map(\.id), ["m1"])
        store.clear()
    }

    private func message(_ n: Int) throws -> TimelineItem {
        let payload: [String: Any] = ["type":"message", "message":["id":"m\(n)","conversation_id":"chat","sender":["type":"agent","id":"agent"],"sender_user_id":"agent-user","sender_type":"agent","content":"message \(n)","attachments":[],"delivery_status":"completed","created_at":"2026-01-01"]]
        return try JSONDecoder().decode(TimelineItem.self, from: JSONSerialization.data(withJSONObject: payload))
    }
}

private actor LostSendTransport: HTTPTransport {
    let pair: Data; let message: Data; let page: Data; let list: Data
    var keys: [String] = []
    init(pair: Data, message: Data, page: Data, list: Data) { self.pair = pair; self.message = message; self.page = page; self.list = list }
    func data(for request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let url = request.url!
        let body: Data
        if url.path.contains("/auth/") { body = pair }
        else if request.httpMethod == "POST", url.path.hasSuffix("/messages") {
            keys.append(request.value(forHTTPHeaderField: "Idempotency-Key") ?? "")
            if keys.count == 1 { throw URLError(.networkConnectionLost) }
            body = message
        } else if url.path == "/im/v1/conversations" { body = list }
        else { body = page }
        return (body, HTTPURLResponse(url: url, statusCode: 200, httpVersion: nil, headerFields: [:])!)
    }
}
private struct ChatTestCredentials: CredentialStore {
    func load() throws -> StoredSession? { nil }
    func save(_ value: StoredSession) throws {}
    func remove() throws {}
}
private actor HistoryTransport: HTTPTransport {
    let pair: Data; let latest: Data; let bridge: Data; let list: Data
    var cursors: [String?] = []
    init(pair: Data, latest: Data, bridge: Data, list: Data = Data(#"{"items":[]}"#.utf8)) { self.pair = pair; self.latest = latest; self.bridge = bridge; self.list = list }
    func data(for request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let url = request.url!
        let body: Data
        if url.path.contains("/auth/") { body = pair }
        else if url.path == "/im/v1/conversations" { body = list }
        else {
            let cursor = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems?.first { $0.name == "before_message_id" }?.value
            cursors.append(cursor); body = cursor == nil ? latest : bridge
        }
        return (body, HTTPURLResponse(url: url, statusCode: 200, httpVersion: nil, headerFields: [:])!)
    }
}
