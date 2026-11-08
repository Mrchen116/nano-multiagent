import XCTest
import Observation
@testable import NanoIM

/// The store on top of a real partition: local first paint, "network failure is not a sign-out",
/// and the targeted access check that replaced clearing the whole timeline.
@MainActor
final class ChatLocalFirstTests: XCTestCase {
    private var root: URL!
    private let origin = URL(string: "https://im.example.test")!
    private let user = AuthUser(id: "user", username: "user", display_name: "User", owner_id: "user", locale: "en",
                                membership_status: "active", is_company_admin: false, owned_node_ids: [], created_at: "now")

    override func setUpWithError() throws {
        root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
    }
    override func tearDownWithError() throws {
        if let root, FileManager.default.fileExists(atPath: root.path) { try FileManager.default.removeItem(at: root) }
    }

    func testOfflineColdStartPaintsStoredContentAndKeepsItOnFailure() async throws {
        let (store, stub) = try await makeStore()
        await seed(store, conversations: ["a", "b"], messages: 2)
        store.resetProjection()
        // The next launch has no process state; only the partition is available.
        await store.loadSeed()
        XCTAssertEqual(store.conversations.map(\.id).sorted(), ["a", "b"])
        XCTAssertEqual(store.listPhase, .loaded, "content comes from the store, not from a request")
        XCTAssertEqual(store.connection, .localOnly)
        XCTAssertFalse(store.connectionText.isEmpty, "an offline launch must say so")

        await stub.failList(URLError(.notConnectedToInternet))
        await store.loadConversations()
        XCTAssertEqual(store.conversations.count, 2, "a failed request keeps the local content")
        XCTAssertEqual(store.listPhase, .loaded, "and must not fall back to a full-screen loader")
        XCTAssertNotNil(store.listError)
    }

    func testFirstSnapshotIsTheOnlyAuthorityForAbsence() async throws {
        let (store, stub) = try await makeStore()
        await seed(store, conversations: ["a", "b"], messages: 0)
        // A `/conversations` page that omits `b` says nothing about access to `b`.
        // A real list response is `{"items": [...]}`; encode the row instead of inventing a page type.
        let row = try JSONSerialization.jsonObject(with: JSONEncoder().encode(try conversation("a")))
        await stub.setList(try JSONSerialization.data(withJSONObject: ["items": [row]]))
        await store.loadConversations()
        XCTAssertEqual(store.conversations.map(\.id).sorted(), ["a", "b"])
        XCTAssertTrue(store.revokedChats.isEmpty)
    }

    func testColdStartNeverResendsAPendingAttempt() async throws {
        let (store, stub) = try await makeStore()
        await seed(store, conversations: ["a"], messages: 0)
        try await seedPending(store)
        await store.recoverPending()
        let posts = await stub.postPaths()
        XCTAssertTrue(posts.isEmpty, "a restored attempt is only looked up, never re-POSTed")
        XCTAssertNotNil(store.errors["a"], "the attempt stays unconfirmed and visible")
        XCTAssertNotNil(store.pending["a"])
        XCTAssertEqual(store.pendingCount, 1)
    }

    func testMembershipRenameRechecksWithoutClearingTheTimeline() async throws {
        let (store, stub) = try await makeStore()
        await seed(store, conversations: ["chat"], messages: 3)
        await store.loadChat("chat")
        XCTAssertEqual(store.timelines["chat"]?.count, 3)
        await stub.setDetail(try JSONEncoder().encode(try conversation("chat", title: "Renamed")))

        await store.consume(try membershipEvent("chat"))
        XCTAssertEqual(store.timelines["chat"]?.map(\.id), ["m1", "m2", "m3"], "a rename must not empty the timeline")
        XCTAssertEqual(store.conversations.first?.title, "Renamed")
        XCTAssertTrue(store.revokedChats.isEmpty)

        let reads = await stub.messageReadCount()
        XCTAssertEqual(reads, 1, "opening the conversation was the only message read")
        let repository = try XCTUnwrap(store.repository)
        let actual = try await repository.timeline("chat").items.count
        XCTAssertEqual(actual, 3, "the rows were kept, not re-fetched")
    }

    func testMembershipRemovalRevokesAndWritesATombstone() async throws {
        let (store, stub) = try await makeStore()
        await seed(store, conversations: ["chat"], messages: 2)
        try await seedPending(store, conversation: "chat", key: "k")
        await store.loadChat("chat")
        await stub.setDetail(nil, status: 403)

        await store.consume(try membershipEvent("chat"))
        XCTAssertTrue(store.revokedChats.contains("chat"))
        XCTAssertNil(store.timelines["chat"])
        XCTAssertNil(store.pending["chat"])
        XCTAssertFalse(store.conversations.contains { $0.id == "chat" })

        let repository = try XCTUnwrap(store.repository)
        let actual = try await repository.conversations().isEmpty
        XCTAssertTrue(actual)
        let actual2 = try await repository.revokedConversations()
        XCTAssertEqual(actual2, ["chat"])
        let actual3 = try await repository.pendingCount()
        XCTAssertEqual(actual3, 0)
    }

    func testMembershipCheckFailureDecidesNothing() async throws {
        let (store, stub) = try await makeStore()
        await seed(store, conversations: ["chat"], messages: 1)
        await stub.failDetail(URLError(.timedOut))

        await store.consume(try membershipEvent("chat"))
        XCTAssertFalse(store.revokedChats.contains("chat"), "a transport failure is not a revocation")
        XCTAssertEqual(store.connection, .offline(attempt: 0, nextRetryAt: nil))
        let repository = try XCTUnwrap(store.repository)
        let actual = try await repository.conversations().map(\.id)
        XCTAssertEqual(actual, ["chat"])
        let actual2 = try await repository.revokedConversations().isEmpty
        XCTAssertTrue(actual2)
    }

    func testLateListAndDetailCannotUndoNewerSnapshotRevocation() async throws {
        for path in ["/im/v1/conversations", "/im/v1/conversations/chat"] {
            let (store, stub) = try await makeStore()
            await seed(store, conversations: ["chat"], messages: 1)
            let row = try JSONEncoder().encode(try conversation("chat", title: "Old"))
            let body = path.hasSuffix("/chat") ? row : Data("{\"items\":[\(String(decoding: row, as: UTF8.self))]}".utf8)
            await stub.hold(path, body: body)
            let request = Task {
                if path.hasSuffix("/chat") { await store.inspectConversation("chat") }
                else { await store.loadConversations() }
            }
            await stub.waitUntilHeld()
            let repository = try XCTUnwrap(store.repository)
            let context = try await repository.writeContext()
            _ = try await repository.applySnapshot([], maxEventID: 20, snapshotSeq: context.snapshotSeq + 1, write: context)
            await store.loadSeed()
            await stub.release()
            await request.value
            XCTAssertTrue(store.conversations.isEmpty, "late \(path) must not repaint revoked content")
            XCTAssertNil(store.inspectedConversation)
            let revoked = try await repository.revokedConversations()
            XCTAssertTrue(revoked.contains("chat"))
            store.resetProjection()
            await store.loadSeed()
            XCTAssertTrue(store.conversations.isEmpty, "offline restart cannot revive the row")
            try await repository.purge()
        }
    }

    func testLatePageCannotFallBackToMemoryAfterPartitionCloses() async throws {
        let (store, stub) = try await makeStore()
        await seed(store, conversations: ["chat"], messages: 0)
        let row = try JSONEncoder().encode(TimelineItem(type: "message", message: try message(1, conversation: "chat")))
        await stub.hold("/im/v1/conversations/chat/messages", body: Data("{\"items\":[\(String(decoding: row, as: UTF8.self))]}".utf8))
        let request = Task { await store.loadChat("chat") }
        await stub.waitUntilHeld()
        let repository = try XCTUnwrap(store.repository)
        try await repository.purge()
        await stub.release()
        await request.value
        XCTAssertTrue(store.timelines["chat"]?.isEmpty ?? true, "failed durable write is not permission to paint raw network data")
    }

    func testDiscardSurvivesProjectionResetAndRepositoryReopen() async throws {
        let (store, _) = try await makeStore()
        await seed(store, conversations: ["chat"], messages: 2)
        await store.consume(try JSONDecoder().decode(UserEvent.self, from: Data("""
            {"op":"event","event_id":10,"event_type":"message.discarded","data":{"conversation_id":"chat","message_id":"m2"}}
            """.utf8)))
        store.stop()
        store.resetProjection()
        let repository = try XCTUnwrap(store.repository)
        let reopened = try ChatRepository.open(repository.partition, location: repository.location)
        let ids = try await reopened.timeline("chat").items.map(\.id)
        XCTAssertEqual(ids, ["m1"], "discard must delete the durable row in the cursor transaction")
    }

    func testCachedChatEntryPaintsBeforeDetailResponse() async throws {
        let (store, stub) = try await makeStore()
        await seed(store, conversations: ["chat"], messages: 2)
        await stub.hold("/im/v1/conversations/chat", body: try JSONEncoder().encode(try conversation("chat")))
        let entry = Task { await store.openConversation("chat") }
        await stub.waitUntilHeld()
        XCTAssertEqual(store.timelines["chat"]?.map(\.id), ["m1", "m2"], "detail timeouts must not gate local history")
        await stub.release()
        await entry.value
    }

    func testMembershipFailureCanRetryWithoutReconnect() async throws {
        let (store, stub) = try await makeStore()
        await seed(store, conversations: ["chat"], messages: 1)
        await stub.setDetail(nil, status: 503)
        await store.consume(try membershipEvent("chat"))
        XCTAssertTrue(store.checkingAccess.contains("chat"))
        await stub.setDetail(try JSONEncoder().encode(try conversation("chat")))
        await store.retryAccess("chat")
        XCTAssertFalse(store.checkingAccess.contains("chat"))
        XCTAssertEqual(store.timelines["chat"]?.map(\.id), ["m1"])
        store.stop()
    }

    func testMembershipFailureAutomaticallyRecoversFromFullSyncWithoutReconnect() async throws {
        let (store, stub) = try await makeStore()
        await seed(store, conversations: ["chat"], messages: 1)
        store.selectedID = "chat"
        await stub.setDetail(nil, status: 503)
        let row = try JSONSerialization.jsonObject(with: JSONEncoder().encode(try conversation("chat")))
        await stub.hold("/im/v1/sync", body: try JSONSerialization.data(withJSONObject: ["items": [row], "max_event_id": 20]))
        await store.consume(try membershipEvent("chat"))
        await stub.waitUntilHeld()
        XCTAssertTrue(store.checkingAccess.contains("chat"))
        let recovered = expectation(description: "the full-sync result releases the access placeholder")
        let pageRestored = expectation(description: "the selected local page is projected again")
        withObservationTracking { _ = store.checkingAccess } onChange: { recovered.fulfill() }
        withObservationTracking { _ = store.timelines["chat"] } onChange: { pageRestored.fulfill() }
        await stub.release()
        await fulfillment(of: [recovered, pageRestored], timeout: 3)
        XCTAssertFalse(store.checkingAccess.contains("chat"))
        XCTAssertEqual(store.timelines["chat"]?.map(\.id), ["m1"])
        let reads = await stub.messageReadCount()
        XCTAssertEqual(reads, 0, "full sync restores the local page without fetching its history again")
        store.stop()
    }

    func testFullSyncPublishesOnlineBeforeASocketTicketReturns() async throws {
        let (store, stub) = try await makeStore()
        let row = try JSONSerialization.jsonObject(with: JSONEncoder().encode(try conversation("chat")))
        await stub.setSync(try JSONSerialization.data(withJSONObject: ["items": [row], "max_event_id": 20]))
        // Invalid ticket body ensures releasing the canceled task cannot open a real socket.
        await stub.hold("/im/v1/auth/ws-ticket", body: Data("{}".utf8))
        let run = Task { await store.run() }
        await stub.waitUntilHeld()
        XCTAssertEqual(store.connection, .online, "a successful durable sync is not gated by another connection stage")
        XCTAssertEqual(store.conversations.map(\.id), ["chat"])
        run.cancel(); store.stop()
        await stub.release()
        await run.value
    }

    // MARK: - Helpers

    private func makeStore() async throws -> (ChatStore, StubTransport) {
        let base = try XCTUnwrap(root)
        let partition = ChatPartition(origin: origin, userID: user.id)
        let controller = ChatStorageController(client: IMClient(baseURL: origin)) { _ in
            ChatStorageLocation.directory(base.appendingPathComponent("partition", isDirectory: true))
        }
        await controller.activate(partition)
        let pair = TokenPair(access_token: "access", refresh_token: "refresh", user: user)
        let transport = StubTransport(pair: try JSONEncoder().encode(pair))
        let session = Session(baseURL: origin, transport: transport, credentials: TestCredentials(),
                              sendAttempts: SendAttemptStore(directory: base.appendingPathComponent("legacy")))
        _ = try await session.login(username: "user", password: "test")
        let store = ChatStore(client: IMClient(baseURL: origin, session: session), user: user, controller: controller)
        return (store, transport)
    }

    private func seed(_ store: ChatStore, conversations: [String], messages: Int) async {
        guard let repository = store.repository else { return }
        guard var context = try? await repository.writeContext() else { return }
        _ = try? await repository.applySnapshot(conversations.map { try? conversation($0) }.compactMap { $0 },
                                                maxEventID: 4, snapshotSeq: context.snapshotSeq + 1, write: context)
        guard let fresh = try? await repository.writeContext() else { return }
        context = fresh
        for id in conversations where messages > 0 {
            let items = try? (1...messages).map { TimelineItem(type: "message", message: try message($0, conversation: id)) }
            if let items { _ = try? await repository.applyPage(id, items: items, write: context) }
        }
        await store.loadSeed()
    }

    private func seedPending(_ store: ChatStore, conversation: String = "a", key: String = "k") async throws {
        let repository = try XCTUnwrap(store.repository)
        let context = try await repository.writeContext()
        try await repository.upsertPending(SendAttempt(conversationID: conversation, sourceMessageID: nil,
                                                       draft: PendingSend(key: key, content: "unsent", attachments: [],
                                                                          requestBody: Data("{}".utf8))),
                                           write: context)
    }

    private func membershipEvent(_ id: String) throws -> UserEvent {
        try JSONDecoder().decode(UserEvent.self, from: Data("""
            {"op":"event","event_type":"conversation.membership_changed","data":{"conversation_id":"\(id)"}}
            """.utf8))
    }

    private func conversation(_ id: String, title: String? = nil) throws -> Conversation {
        try JSONDecoder().decode(Conversation.self, from: Data("""
            {"id":"\(id)","title":"\(title ?? id)","participants":[],"participant_ids":["user"],"type":"group",
             "owner_id":"user","creator_id":"user","is_pinned":false,"is_muted":false,"unread_count":0,"created_at":"now"}
            """.utf8))
    }

    private func message(_ n: Int, conversation: String) throws -> ChatMessage {
        try JSONDecoder().decode(ChatMessage.self, from: Data("""
            {"id":"m\(n)","conversation_id":"\(conversation)","sender":{"type":"user","id":"user"},
             "sender_user_id":"user","sender_type":"user","content":"message \(n)","attachments":[],
             "delivery_status":"completed","created_at":"2026-11-01T00:00:0\(n)Z"}
            """.utf8))
    }
}

private actor StubTransport: HTTPTransport {
    private let pair: Data
    private var listData = Data(#"{"items":[]}"#.utf8)
    private var syncData = Data(#"{"items":[],"max_event_id":0}"#.utf8)
    private var detailData: Data?
    private var detailStatus = 200
    private var detailFailure: URLError?
    private var listFailure: URLError?
    private var postRequests: [URLRequest] = []
    private var messageReads = 0
    private var heldPath: String?
    private var heldBody = Data()
    private var held: CheckedContinuation<Void, Never>?
    private var didHold = false
    private var waiting: CheckedContinuation<Void, Never>?

    func hold(_ path: String, body: Data) { heldPath = path; heldBody = body; didHold = false }
    func waitUntilHeld() async {
        if didHold { return }
        await withCheckedContinuation { waiting = $0 }
    }
    func release() { held?.resume(); held = nil }

    init(pair: Data) { self.pair = pair }

    func setList(_ data: Data) { listData = data }
    func setSync(_ data: Data) { syncData = data }
    func setDetail(_ data: Data?, status: Int = 200) { detailData = data; detailStatus = status }
    func failDetail(_ error: URLError?) { detailFailure = error }
    func failList(_ error: URLError?) { listFailure = error }
    func postPaths() -> [String] { postRequests.map { $0.url?.path ?? "" } }
    func messageReadCount() -> Int { messageReads }

    func data(for request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let url = request.url!
        if heldPath == url.path {
            let body = heldBody
            heldPath = nil; didHold = true
            waiting?.resume(); waiting = nil
            await withCheckedContinuation { held = $0 }
            return (body, response(url, 200))
        }
        if url.path == "/im/v1/auth/me" {
            return (try JSONEncoder().encode(JSONDecoder().decode(TokenPair.self, from: pair).user), response(url, 200))
        }
        if url.path.contains("/auth/") { return (pair, response(url, 200)) }
        if url.path == "/im/v1/sync" { return (syncData, response(url, 200)) }
        if url.path.hasSuffix("/messages") {
            if request.httpMethod == "GET" { messageReads += 1 } else { postRequests.append(request) }
            return (Data(#"{"items":[]}"#.utf8), response(url, 200))
        }
        if url.path.contains("/message-attempts/") {
            return (Data(#"{"detail":"not found"}"#.utf8), response(url, 404))
        }
        if url.path == "/im/v1/conversations" {
            if let listFailure { throw listFailure }
            return (listData, response(url, 200))
        }
        if url.path.hasPrefix("/im/v1/conversations/") {
            if let detailFailure { throw detailFailure }
            if let detailData, detailStatus == 200 { return (detailData, response(url, 200)) }
            return (Data(#"{"detail":"not found"}"#.utf8), response(url, detailStatus))
        }
        if request.httpMethod == "POST" { postRequests.append(request) }
        return (Data(#"{"detail":"unexpected"}"#.utf8), response(url, 404))
    }

    private func response(_ url: URL, _ status: Int) -> HTTPURLResponse {
        HTTPURLResponse(url: url, statusCode: status, httpVersion: nil, headerFields: [:])!
    }
}

private struct TestCredentials: CredentialStore {
    func load() throws -> StoredSession? { nil }
    func save(_ value: StoredSession) throws {}
    func remove() throws {}
}
