import XCTest
@testable import NanoIM

@MainActor
final class ChatStateTests: XCTestCase {
    private let user = AuthUser(id: "user", username: "user", display_name: "User", owner_id: "user", locale: "en", membership_status: "active", is_company_admin: false, owned_node_ids: [], created_at: "now")

    func testForegroundRemindersHandleHumanSentWithoutRepeatingCreation() async throws {
        let key = "nano.foregroundReminders"
        let previous = UserDefaults.standard.object(forKey: key)
        UserDefaults.standard.set(true, forKey: key)
        defer { if let previous { UserDefaults.standard.set(previous, forKey: key) } else { UserDefaults.standard.removeObject(forKey: key) } }
        let list = Data(#"{"items":[{"id":"chat","title":"Chat","participants":[],"participant_ids":["user"],"type":"group","owner_id":"user","creator_id":"user","is_pinned":false,"is_muted":false,"unread_count":0,"created_at":"now"}]}"#.utf8)
        let store = try await makeStore(list: list)
        await store.loadConversations()
        func event(_ type: String, _ id: Int, sender: String = "peer", kind: String = "user") throws -> UserEvent {
            let data: [String: Any] = ["op": "event", "event_type": type, "event_id": id, "data": ["conversation_id": "chat", "message_id": "message", "sender_user_id": sender, "sender_type": kind]]
            return try JSONDecoder().decode(UserEvent.self, from: JSONSerialization.data(withJSONObject: data))
        }
        store.consume(try event("message.sent", 1))
        XCTAssertEqual(store.banner?.conversationID, "chat")
        store.banner = nil
        store.consume(try event("message.created", 2))
        XCTAssertNil(store.banner)
        store.consume(try event("message.created", 3, kind: "agent"))
        XCTAssertEqual(store.banner?.conversationID, "chat")
        store.banner = nil
        store.consume(try event("message.sent", 4, kind: "agent"))
        store.consume(try event("message.sent", 5, sender: "user"))
        XCTAssertNil(store.banner)
        store.conversations[0].is_muted = true
        store.consume(try event("message.sent", 6))
        XCTAssertNil(store.banner)
        store.conversations[0].is_muted = false; store.selectedID = "chat"
        store.consume(try event("message.sent", 7))
        XCTAssertNil(store.banner)
        store.selectedID = nil
        store.consume(try event("message.sent", 7))
        XCTAssertNil(store.banner)
        store.clear()
    }

    func testMembershipControlWithoutCursorRemovesCachedContentAndDraft() async throws {
        let store = try await makeStore()
        store.timelines["chat"] = [try message(1)]
        store.drafts["chat"] = "private draft"
        store.attachments["chat"] = [ChatAttachment(url: "/im/v1/uploads/private")]
        store.uploadDrafts["chat"] = [AttachmentUpload(data: Data("private".utf8), fileName: "private.txt", contentType: "text/plain", error: "failed")]
        store.pending["chat"] = PendingSend(content: "unsent", attachments: [])
        let event = try JSONDecoder().decode(UserEvent.self, from: Data(#"{"op":"event","event_type":"conversation.membership_changed","data":{"conversation_id":"chat"}}"#.utf8))
        store.consume(event)
        XCTAssertNil(store.timelines["chat"])
        await store.loadConversations()
        XCTAssertNil(store.timelines["chat"])
        XCTAssertNil(store.drafts["chat"])
        XCTAssertNil(store.attachments["chat"])
        XCTAssertNil(store.uploadDrafts["chat"])
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

    func testFailedUploadBlocksNormalSendAndTextOnlyKeepsEveryAttachment() async throws {
        let (store, transport) = try await makeUploadStore(statuses: [503, 200])
        store.drafts["chat"] = "text stays available"
        store.attachments["chat"] = [ChatAttachment(url: "/im/v1/uploads/already-uploaded")]
        await store.addUpload("chat", data: Data("retry me".utf8), name: "failed.txt", type: "text/plain")
        let uploadID = try XCTUnwrap(store.uploadDrafts["chat"]?.first?.id)
        XCTAssertNotNil(store.uploadDrafts["chat"]?.first?.error)
        await store.send("chat")
        let blocked = await transport.sentFiles
        XCTAssertTrue(blocked.isEmpty)
        XCTAssertEqual(store.drafts["chat"], "text stays available")
        await store.send("chat", textOnly: true)
        let textOnly = await transport.sentFiles
        XCTAssertEqual(textOnly, [[]])
        XCTAssertEqual(store.drafts["chat"], "")
        XCTAssertEqual(store.attachments["chat"]?.map(\.id), ["/im/v1/uploads/already-uploaded"])
        XCTAssertEqual(store.uploadDrafts["chat"]?.first?.id, uploadID)
        await store.retryUpload("chat", uploadID: uploadID)
        XCTAssertTrue(store.uploadDrafts["chat"]?.isEmpty == true)
        XCTAssertEqual(store.attachments["chat"]?.count, 2)
        let bytes = await transport.uploadBodies
        XCTAssertEqual(bytes, [Data("retry me".utf8), Data("retry me".utf8)])
        store.clear()
    }

    func testUploadRetryWaitsForRetryAfterThenKeepsFileUntilSuccess() async throws {
        let (store, transport) = try await makeUploadStore(statuses: [429, 200])
        await store.addUpload("chat", data: Data("cooldown".utf8), name: "cooldown.txt", type: "text/plain")
        let uploadID = try XCTUnwrap(store.uploadDrafts["chat"]?.first?.id)
        let retryAt = try XCTUnwrap(store.uploadDrafts["chat"]?.first?.retryAt)
        XCTAssertGreaterThan(retryAt.timeIntervalSinceNow, 15)
        await store.retryUpload("chat", uploadID: uploadID)
        let waiting = await transport.uploadBodies
        XCTAssertEqual(waiting.count, 1)
        store.uploadDrafts["chat"]?[0].retryAt = .distantPast
        await store.retryUpload("chat", uploadID: uploadID)
        let retried = await transport.uploadBodies
        XCTAssertEqual(retried.count, 2)
        XCTAssertTrue(store.uploadDrafts["chat"]?.isEmpty == true)
        XCTAssertEqual(store.attachments["chat"]?.count, 1)
        store.clear()
    }

    func testUploadFinishedAfterStoreClearCannotRestorePrivateDraft() async throws {
        let (store, transport) = try await makeUploadStore(statuses: [200], gated: true)
        let task = Task { await store.addUpload("chat", data: Data("private".utf8), name: "private.txt", type: "text/plain") }
        await transport.waitForUpload()
        store.clear()
        await transport.releaseUpload()
        await task.value
        XCTAssertTrue(store.attachments.isEmpty)
        XCTAssertTrue(store.uploadDrafts.isEmpty)
        XCTAssertTrue(store.conversations.isEmpty)
    }

    func testUploadCompletesWhenRealtimeStopsForBackground() async throws {
        for status in [200, 503] {
            let (store, transport) = try await makeUploadStore(statuses: [status], gated: true)
            let task = Task { await store.addUpload("chat", data: Data("background".utf8), name: "background.txt", type: "text/plain") }
            await transport.waitForUpload()
            store.stop()
            await transport.releaseUpload()
            await task.value
            if status == 200 {
                XCTAssertTrue(store.uploadDrafts["chat"]?.isEmpty == true)
                XCTAssertEqual(store.attachments["chat"]?.count, 1)
            } else {
                XCTAssertEqual(store.uploadDrafts["chat"]?.first?.uploading, false)
                XCTAssertNotNil(store.uploadDrafts["chat"]?.first?.error)
            }
            store.clear()
        }
    }

    private func makeUploadStore(statuses: [Int], gated: Bool = false) async throws -> (ChatStore, UploadTransport) {
        let pair = TokenPair(access_token: "test", refresh_token: "test", user: user)
        let list = Data(#"{"items":[{"id":"chat","title":"Chat","participants":[],"participant_ids":["user"],"type":"group","owner_id":"user","creator_id":"user","is_pinned":false,"is_muted":false,"unread_count":0,"created_at":"now"}]}"#.utf8)
        let transport = UploadTransport(pair: try JSONEncoder().encode(pair), message: try JSONEncoder().encode(message(1).message!), list: list, statuses: statuses, gated: gated)
        let session = Session(baseURL: URL(string: "https://im.example.test")!, transport: transport, credentials: ChatTestCredentials())
        _ = try await session.login(username: "user", password: "test")
        let store = ChatStore(client: IMClient(baseURL: session.baseURL, session: session), user: user)
        await store.loadConversations()
        return (store, transport)
    }

    private func message(_ n: Int) throws -> TimelineItem {
        let createdAt = ISO8601DateFormatter().string(from: Date(timeIntervalSince1970: TimeInterval(n)))
        let payload: [String: Any] = ["type":"message", "message":["id":"m\(n)","conversation_id":"chat","sender":["type":"agent","id":"agent"],"sender_user_id":"agent-user","sender_type":"agent","content":"message \(n)","attachments":[],"delivery_status":"completed","created_at":createdAt]]
        return try JSONDecoder().decode(TimelineItem.self, from: JSONSerialization.data(withJSONObject: payload))
    }
}

private actor UploadTransport: HTTPTransport {
    let pair: Data; let message: Data; let list: Data
    var statuses: [Int]
    let gated: Bool
    var uploadBodies: [Data] = []
    var sentFiles: [[String]] = []
    private var started = false
    private var startWaiter: CheckedContinuation<Void, Never>?
    private var release: CheckedContinuation<Void, Never>?
    init(pair: Data, message: Data, list: Data, statuses: [Int], gated: Bool) {
        self.pair = pair; self.message = message; self.list = list; self.statuses = statuses; self.gated = gated
    }
    func waitForUpload() async {
        if !started { await withCheckedContinuation { startWaiter = $0 } }
    }
    func releaseUpload() { release?.resume(); release = nil }
    func data(for request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let url = request.url!
        var status = 200
        let body: Data
        if url.path.contains("/auth/") { body = pair }
        else if url.path == "/im/v1/uploads" {
            uploadBodies.append(request.httpBody ?? Data())
            if gated { await withCheckedContinuation { release = $0; started = true; startWaiter?.resume(); startWaiter = nil } }
            status = statuses.removeFirst()
            body = status == 200 ? Data(#"{"url":"/im/v1/uploads/new","file_name":"uploaded.txt","content_type":"text/plain"}"#.utf8) : Data(#"{"detail":"fixture failure"}"#.utf8)
        } else if request.httpMethod == "POST", url.path.hasSuffix("/messages") {
            let payload = try JSONSerialization.jsonObject(with: request.httpBody!) as! [String: Any]
            sentFiles.append((payload["attachments"] as! [[String: Any]]).map { $0["url"] as! String })
            body = message
        } else { body = list }
        return (body, HTTPURLResponse(url: url, statusCode: status, httpVersion: nil, headerFields: status == 429 ? ["Retry-After":"20"] : [:])!)
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
