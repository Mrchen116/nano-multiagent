import XCTest
@testable import NanoIM

@MainActor
final class SendRecoveryTests: XCTestCase {
    private let origin = URL(string: "https://im.example.test")!
    private let user = AuthUser(id: "user", username: "user", display_name: "User", owner_id: "user", locale: "en", membership_status: "active", is_company_admin: false, owned_node_ids: [], created_at: "now")
    private var directory: URL!
    private var disk: SendAttemptStore { SendAttemptStore(directory: directory) }

    override func setUpWithError() throws { directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString) }
    override func tearDownWithError() throws {
        if FileManager.default.fileExists(atPath: directory.path) { try FileManager.default.removeItem(at: directory) }
    }

    func testNewSessionAndStoreReadFrozenMentionAndAttachmentsBeforeExplicitRetry() async throws {
        let (first, transport, vault) = try await makeStore()
        await first.loadConversations()
        first.conversations[0].participants = [ActorRef(type: "agent", id: "agent", display_name: "Before", user_id: "agent-user")]
        first.drafts["chat"] = "@Before original"
        first.attachments["chat"] = [ChatAttachment(url: "/im/v1/uploads/kept", content_type: "image/png", file_name: "kept.png")]
        await first.send("chat")
        let key = try XCTUnwrap(first.pending["chat"]?.key)
        let original = try XCTUnwrap(first.pending["chat"]?.requestBody)
        first.stop(); first.clear()

        // A fresh transport owner restores credentials and reads disk, as after process termination.
        let session = Session(baseURL: origin, transport: transport, credentials: vault, sendAttempts: disk)
        _ = try await session.restore()
        let restored = ChatStore(client: IMClient(baseURL: origin, session: session), user: user)
        XCTAssertEqual(restored.pending["chat"]?.key, key)
        XCTAssertEqual(restored.attachments["chat"]?.first?.file_name, "kept.png")
        await restored.loadConversations()
        restored.conversations[0].participants = [ActorRef(type: "agent", id: "agent", display_name: "After", user_id: "different-user")]
        restored.drafts["chat"] = "new work"
        await restored.recoverPending()
        let beforeRetry = await transport.sent()
        XCTAssertEqual(beforeRetry.count, 1)
        XCTAssertNotNil(restored.pending["chat"])
        await restored.send("chat", retry: true)
        let sent = await transport.sent()
        XCTAssertEqual(sent.map(\.httpBody), [original, original])
        XCTAssertEqual(sent.map { $0.value(forHTTPHeaderField: "Idempotency-Key") }, [key, key])
        let payload = try JSONDecoder().decode(JSONValue.self, from: original)
        XCTAssertEqual(payload["content"].stringValue, "<mention type=\"user\" target_id=\"agent-user\"/> original")
        XCTAssertNil(restored.pending["chat"])
        XCTAssertEqual(restored.drafts["chat"], "new work")
        XCTAssertTrue(try disk.load(origin: origin, userID: user.id).isEmpty)
        XCTAssertEqual(restored.timelines["chat"]?.map(\.id), ["sent"])
        restored.clear()
    }

    func testRestoredCommittedCardUsesNamespacedLookupAndDoesNotResend() async throws {
        let (first, transport, vault) = try await makeStore()
        let input = InteractionReplyInput(source_message_id: "card", action_id: "continue", event: nil, state: ["minutes": .number(30)])
        do { _ = try await first.submitInteraction("chat", input: input, key: "card-key"); XCTFail("Expected lost acknowledgement") } catch {}
        XCTAssertNil(first.pending["chat"])
        XCTAssertEqual(first.interactionAttempt("chat", sourceMessageID: "card")?.key, "card-key")
        first.clear()
        await transport.setLookup(status: 200)
        let session = Session(baseURL: origin, transport: transport, credentials: vault, sendAttempts: disk)
        _ = try await session.restore()
        let restored = ChatStore(client: IMClient(baseURL: origin, session: session), user: user)
        restored.drafts["chat"] = "keep this unrelated text"
        await restored.recoverPending()
        let sent = await transport.sent(), lookups = await transport.lookupKeys()
        XCTAssertEqual(sent.count, 1)
        XCTAssertEqual(lookups, ["interaction:user:card-key"])
        XCTAssertNil(restored.interactionAttempt("chat", sourceMessageID: "card"))
        XCTAssertEqual(restored.drafts["chat"], "keep this unrelated text")
        XCTAssertEqual(restored.timelines["chat"]?.map(\.id), ["sent"])
        XCTAssertTrue(try disk.load(origin: origin, userID: user.id).isEmpty)
        restored.clear()
    }

    func testUnknownCardRetryKeepsOriginalBytesAndRawPostKey() async throws {
        let (first, transport, _) = try await makeStore()
        let input = InteractionReplyInput(source_message_id: "card", action_id: nil, event: .object(["type": .string("continue_conversation"), "message": .string("continue")]), state: ["choice": .string("A")])
        do { _ = try await first.submitInteraction("chat", input: input, key: "raw"); XCTFail("Expected lost acknowledgement") } catch {}
        let restored = ChatStore(client: first.client, user: user)
        await restored.recoverPending()
        let before = await transport.sent()
        XCTAssertEqual(before.count, 1)
        _ = try await restored.retryInteraction("chat", sourceMessageID: "card")
        let sent = await transport.sent(), lookups = await transport.lookupKeys()
        XCTAssertEqual(sent.map(\.httpBody), [before[0].httpBody, before[0].httpBody])
        XCTAssertEqual(sent.map { $0.value(forHTTPHeaderField: "Idempotency-Key") }, ["raw", "raw"])
        XCTAssertEqual(lookups, ["interaction:user:raw", "interaction:user:raw"])
        XCTAssertNil(restored.interactionPending["card"])
        first.clear(); restored.clear()
    }

    func testWriteFailureDoesNotPostAndConflictChecksAuthoritativeReceipt() async throws {
        // An unusable storage destination must fail before the first network write.
        try Data("occupied".utf8).write(to: directory)
        let (blocked, blockedTransport, _) = try await makeStore()
        blocked.drafts["chat"] = "do not lose"
        await blocked.send("chat")
        let blockedRequests = await blockedTransport.sent()
        XCTAssertTrue(blockedRequests.isEmpty)
        XCTAssertNil(blocked.pending["chat"])
        XCTAssertEqual(blocked.drafts["chat"], "do not lose")
        blocked.clear()
        try FileManager.default.removeItem(at: directory)

        let (store, transport, _) = try await makeStore(firstPostStatus: 409)
        await transport.setLookup(status: 200)
        store.drafts["chat"] = "already accepted"
        await store.send("chat")
        let sent = await transport.sent(), lookups = await transport.lookupKeys()
        XCTAssertEqual(sent.count, 1)
        XCTAssertEqual(lookups.count, 1)
        XCTAssertNil(store.pending["chat"])
        XCTAssertEqual(store.timelines["chat"]?.map(\.id), ["sent"])
        store.clear()
    }

    func testSignOutAndPermissionRevocationRemoveDiskAndRejectLateResult() async throws {
        let (store, transport, _) = try await makeStore(firstPostStatus: 200, gated: true)
        store.drafts["chat"] = "private"
        let send = Task { await store.send("chat") }
        await transport.waitForPost()
        XCTAssertEqual(try disk.load(origin: origin, userID: user.id).count, 1)
        _ = await store.client.session.signOut()
        store.clear()
        await transport.releasePost()
        await send.value
        XCTAssertTrue(store.timelines.isEmpty)
        XCTAssertTrue(store.pending.isEmpty)
        XCTAssertTrue(try disk.load(origin: origin, userID: user.id).isEmpty)

        let (revoked, _, _) = try await makeStore()
        revoked.drafts["chat"] = "remove with permission"
        await revoked.send("chat")
        XCTAssertEqual(try disk.load(origin: origin, userID: user.id).count, 1)
        await revoked.inspectConversation("chat")
        XCTAssertNil(revoked.pending["chat"])
        XCTAssertTrue(try disk.load(origin: origin, userID: user.id).isEmpty)
        revoked.clear()
    }

    func testOriginAndAccountIsolationAndAccountIneligibilityCleanup() async throws {
        let (store, transport, _) = try await makeStore()
        store.drafts["chat"] = "owner only"
        await store.send("chat")
        XCTAssertEqual(try disk.load(origin: origin, userID: user.id).count, 1)
        XCTAssertTrue(try disk.load(origin: URL(string: "https://other.example.test")!, userID: user.id).isEmpty)
        XCTAssertTrue(try disk.load(origin: origin, userID: "other").isEmpty)
        var disabled = user; disabled.membership_status = "suspended"
        await transport.setCurrentUser(try JSONEncoder().encode(disabled))
        _ = try await store.client.session.updateUser()
        XCTAssertTrue(try disk.load(origin: origin, userID: user.id).isEmpty)
        store.clear()
    }

    func testBackgroundStopKeepsUnknownAttemptAndLateConfirmationKeepsNewDraft() async throws {
        for status in [0, 200] {
            let (store, transport, _) = try await makeStore(firstPostStatus: status, gated: true)
            store.drafts["chat"] = "original"
            let send = Task { await store.send("chat") }
            await transport.waitForPost()
            store.drafts["chat"] = "new draft"
            store.stop()
            await transport.releasePost()
            await send.value
            XCTAssertEqual(store.drafts["chat"], "new draft")
            XCTAssertEqual(store.pending["chat"] != nil, status == 0)
            XCTAssertEqual(try disk.load(origin: origin, userID: user.id).count, status == 0 ? 1 : 0)
            store.clear()
            let reopened = ChatStore(client: store.client, user: user)
            XCTAssertEqual(reopened.pending["chat"] != nil, status == 0)
            reopened.clear()
            try disk.remove(origin: origin, userID: user.id)
        }
    }

    func testReauthenticationCannotResendAnOldStoresPendingRequest() async throws {
        let (store, transport, _) = try await makeStore()
        store.drafts["chat"] = "old identity generation"
        await store.send("chat")
        XCTAssertNotNil(store.pending["chat"])
        _ = try await store.client.session.login(username: "user", password: "test")
        await store.send("chat", retry: true)
        let sent = await transport.sent()
        XCTAssertEqual(sent.count, 1)
        XCTAssertTrue(try disk.load(origin: origin, userID: user.id).isEmpty)
        let next = ChatStore(client: store.client, user: user)
        XCTAssertTrue(next.pending.isEmpty)
        store.clear(); next.clear()
    }

    func testPrivateBackgroundFiltersHistoryAndFreezesLatestThreeSelections() async throws {
        for group in [false, true] {
            let (store, transport, _) = try await makeStore()
            await store.loadConversations()
            store.conversations[0].type = group ? "group" : "direct"
            let base = try JSONDecoder().decode(ChatMessage.self, from: transport.message)
            let cards = ["old", "a", "b", "c", "d", "read-only"]
            store.timelines["chat"] = cards.enumerated().map { index, id in
                var message = base; message.id = id
                message.interactive = MessageInteractive(format: "openuilang", catalog_version: "nano-1", source: "root = Text(\"example\")", read_only: id == "read-only", superseded_by: nil, supersedes_message_id: id == "d" ? "old" : nil)
                store.interactionSelections[id] = InteractionSelection(conversationID: "chat", source_message_id: id, state: ["value": .number(Double(index))], editedAt: Double(index))
                return TimelineItem(type: "message", message: message)
            }
            store.drafts["chat"] = "  preserve handwritten text  "
            await store.send("chat")
            let firstRequests = await transport.sent()
            let first = try XCTUnwrap(firstRequests.first?.httpBody)
            let body = try JSONDecoder().decode(JSONValue.self, from: first)
            XCTAssertEqual(body["content"].stringValue, "  preserve handwritten text  ")
            XCTAssertEqual(body["interaction_contexts"].arrayValue?.compactMap { $0["source_message_id"].stringValue } ?? [], group ? [] : ["d", "c", "b"])
            store.interactionSelections = [:]
            await store.send("chat", retry: true)
            let sent = await transport.sent()
            XCTAssertEqual(sent[1].httpBody, first)
            store.clear()
        }
    }

    private func makeStore(firstPostStatus: Int = 0, gated: Bool = false) async throws -> (ChatStore, RecoveryTransport, RecoveryCredentials) {
        let pair = try JSONEncoder().encode(TokenPair(access_token: "token", refresh_token: "refresh", user: user))
        let transport = RecoveryTransport(pair: pair, user: try JSONEncoder().encode(user), firstPostStatus: firstPostStatus, gated: gated)
        let vault = RecoveryCredentials()
        let session = Session(baseURL: origin, transport: transport, credentials: vault, sendAttempts: disk)
        _ = try await session.login(username: "user", password: "test")
        return (ChatStore(client: IMClient(baseURL: origin, session: session), user: user), transport, vault)
    }
}

private final class RecoveryCredentials: CredentialStore, @unchecked Sendable {
    private let lock = NSLock()
    private var stored: StoredSession?
    func load() throws -> StoredSession? { lock.lock(); defer { lock.unlock() }; return stored }
    func save(_ value: StoredSession) throws { lock.lock(); defer { lock.unlock() }; stored = value }
    func remove() throws { lock.lock(); defer { lock.unlock() }; stored = nil }
}

private actor RecoveryTransport: HTTPTransport {
    let pair: Data
    var user: Data
    let firstPostStatus: Int
    let gated: Bool
    var posts: [URLRequest] = []
    var lookups: [String] = []
    var lookupStatus = 404
    var postStarted = false
    var start: CheckedContinuation<Void, Never>?
    var release: CheckedContinuation<Void, Never>?
    let message = Data(#"{"id":"sent","conversation_id":"chat","sender":{"type":"user","id":"user"},"sender_user_id":"user","sender_type":"user","content":"confirmed","attachments":[],"delivery_status":"pending","created_at":"now"}"#.utf8)
    let list = Data(#"{"items":[{"id":"chat","title":"Chat","participants":[],"participant_ids":["user"],"type":"direct","owner_id":"user","creator_id":"user","is_pinned":false,"is_muted":false,"unread_count":0,"created_at":"now"}]}"#.utf8)
    init(pair: Data, user: Data, firstPostStatus: Int, gated: Bool) { self.pair = pair; self.user = user; self.firstPostStatus = firstPostStatus; self.gated = gated }
    func sent() -> [URLRequest] { posts }
    func lookupKeys() -> [String] { lookups }
    func setLookup(status: Int) { lookupStatus = status }
    func setCurrentUser(_ data: Data) { user = data }
    func waitForPost() async { if !postStarted { await withCheckedContinuation { start = $0 } } }
    func releasePost() { release?.resume(); release = nil }
    func data(for request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        let path = request.url!.path
        var status = 200
        let data: Data
        if path == "/im/v1/auth/me" { data = user }
        else if path.contains("/auth/") { data = pair }
        else if path.contains("/message-attempts/") {
            lookups.append(request.url!.lastPathComponent)
            status = lookupStatus; data = status == 200 ? message : Data(#"{"detail":"not found"}"#.utf8)
        } else if path.hasSuffix("/messages"), request.httpMethod == "POST" {
            posts.append(request)
            if gated { await withCheckedContinuation { release = $0; postStarted = true; start?.resume(); start = nil } }
            if posts.count == 1, firstPostStatus == 0 { throw URLError(.networkConnectionLost) }
            status = posts.count == 1 ? firstPostStatus : 200
            data = status == 200 ? message : Data(#"{"detail":{"code":"message_attempt_conflict","message":"conflict"}}"#.utf8)
        } else if path.hasSuffix("/messages") { data = Data(#"{"items":[]}"#.utf8) }
        else if path == "/im/v1/conversations" { data = list }
        else { status = 404; data = Data(#"{"detail":"not found"}"#.utf8) }
        return (data, HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: [:])!)
    }
}
