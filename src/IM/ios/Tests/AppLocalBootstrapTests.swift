import XCTest
@testable import NanoIM

/// Exercises the real account owner rather than manually calling ChatStore.loadSeed().
@MainActor
final class AppLocalBootstrapTests: XCTestCase {
    private var root: URL!
    private let origin = URL(string: "https://im.example.test")!

    override func setUpWithError() throws {
        root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
    }
    override func tearDownWithError() throws {
        if let root, FileManager.default.fileExists(atPath: root.path) { try FileManager.default.removeItem(at: root) }
    }

    func testReadyPublishesCachedRowsWithoutAnyHTTPOrSecondSeedTask() async throws {
        let (model, transport) = try await makeModel()
        await model.bootstrapLocal()
        XCTAssertTrue(model.ready)
        XCTAssertEqual(model.user?.id, "alice")
        let chat = try XCTUnwrap(model.chat)
        XCTAssertEqual(chat.conversations.map(\.id), ["cached"])
        XCTAssertEqual(chat.listPhase, .loaded)
        XCTAssertEqual(chat.connection, .localOnly)
        let requests = await transport.requests
        XCTAssertEqual(requests, 0, "the entire first-paint stage is local, even when every HTTP request could hang")
        chat.stop()
    }

    func testSameAccountRefreshKeepsTheDisplayedStoreAndControllerRecipient() async throws {
        let (model, _) = try await makeModel()
        await model.bootstrapLocal()
        let displayed = try XCTUnwrap(model.chat)
        displayed.drafts["cached"] = "unsaved UI state survives an unrelated parent redraw"
        for _ in 0..<3 { await model.refreshUser() }
        XCTAssertTrue(model.chat === displayed, "publishing fresh account metadata must not create a temporary replacement")
        XCTAssertEqual(displayed.drafts["cached"], "unsaved UI state survives an unrelated parent redraw")
        await model.storage.purge(reason: .signedOut)
        XCTAssertTrue(displayed.conversations.isEmpty, "the controller still addresses the store the screen retained")
        XCTAssertNil(displayed.repository)
        displayed.stop()
    }

    func testSignOutFencesLegacyWithoutChangingItsBytesAtTheActualOwner() async throws {
        let (model, _) = try await makeModel()
        let legacy = SendAttemptStore(directory: root.appendingPathComponent("legacy"))
        let attempt = SendAttempt(conversationID: "cached", sourceMessageID: nil,
                                  draft: PendingSend(key: "old", content: "private", attachments: [], requestBody: Data("{}".utf8)))
        try legacy.save(attempt, origin: origin, userID: "alice")
        let file = try XCTUnwrap(legacy.attemptFiles(origin: origin, userID: "alice").first)
        let bytes = try Data(contentsOf: file)
        await model.bootstrapLocal()
        await model.signOut()
        XCTAssertNil(model.user)
        XCTAssertNil(model.chat)
        XCTAssertEqual(try Data(contentsOf: file), bytes)
        let reopened = try ChatRepository.open(ChatPartition(origin: origin, userID: "alice"),
                                               location: .directory(root.appendingPathComponent("partition")),
                                               legacyAttemptRoot: root.appendingPathComponent("legacy"))
        let pending = try await reopened.pendingAttempts()
        XCTAssertTrue(pending.isEmpty, "the surviving legacy file is not permission to undo sign-out")
        try await reopened.close()
    }

    func testLogoutWhileBootstrapOpensCannotPublishTheStoredAccountAfterward() async throws {
        let gate = BootstrapOpenGate()
        let (model, _) = try await makeModel(openGate: gate)
        let bootstrap = Task { await model.bootstrapLocal() }
        await gate.waitUntilEntered()
        _ = await model.client.session.signOut()
        await gate.release()
        await bootstrap.value
        await model.storage.purge(reason: .signedOut)
        XCTAssertTrue(model.ready)
        XCTAssertNil(model.user)
        XCTAssertNil(model.chat, "a stale local seed must not recreate the user/store after Session invalidation")
    }

    func testDisabledStoredOwnerPurgesItsUnopenedPartitionBeforeLaterReenable() async throws {
        let (model, transport) = try await makeModel(enabled: false)
        let partition = ChatPartition(origin: origin, userID: "alice")
        let location = ChatStorageLocation.directory(root.appendingPathComponent("partition"))
        let legacy = SendAttemptStore(directory: root.appendingPathComponent("legacy"))
        let attempt = SendAttempt(conversationID: "cached", sourceMessageID: nil,
                                  draft: PendingSend(key: "old", content: "private", attachments: [], requestBody: Data("{}".utf8)))
        try legacy.save(attempt, origin: origin, userID: "alice")
        let file = try XCTUnwrap(legacy.attemptFiles(origin: origin, userID: "alice").first)
        let original = try Data(contentsOf: file)
        XCTAssertNil(model.storage.partition, "this models a fresh process after disabled credentials were saved")
        await model.bootstrapLocal()
        XCTAssertTrue(model.ready)
        XCTAssertFalse(model.user?.accountEnabled ?? true)
        XCTAssertNil(model.chat)
        XCTAssertFalse(FileManager.default.fileExists(atPath: location.directoryURL.path))
        XCTAssertEqual(try Data(contentsOf: file), original, "legacy source remains read-only")
        let requests = await transport.requests
        XCTAssertEqual(requests, 0)
        await model.storage.activate(partition)
        let reopened = try XCTUnwrap(model.storage.repository)
        let rows = try await reopened.conversations()
        let pending = try await reopened.pendingAttempts()
        XCTAssertTrue(rows.isEmpty)
        XCTAssertTrue(pending.isEmpty, "reenable cannot import the disabled owner's old frozen request")
        XCTAssertNotNil(try reopened.attemptPersistence.policy().purgeGeneration)
        try await reopened.close()
    }

    private func makeModel(openGate: BootstrapOpenGate? = nil, enabled: Bool = true) async throws -> (AppModel, BootstrapTransport) {
        let base = try XCTUnwrap(root)
        let user = AuthUser(id: "alice", username: "alice", display_name: "Alice", owner_id: "alice", locale: "en",
                            membership_status: enabled ? "active" : "inactive", is_company_admin: false, owned_node_ids: [], created_at: "now")
        let location = ChatStorageLocation.directory(base.appendingPathComponent("partition"))
        let repository = try ChatRepository.open(ChatPartition(origin: origin, userID: user.id), location: location,
                                                 legacyAttemptRoot: base.appendingPathComponent("legacy"))
        let context = try await repository.writeContext()
        let row = try JSONDecoder().decode(Conversation.self, from: Data("""
            {"id":"cached","title":"Cached","participants":[],"participant_ids":["alice"],"type":"group",
             "owner_id":"alice","creator_id":"alice","is_pinned":false,"is_muted":false,"unread_count":0,"created_at":"now"}
            """.utf8))
        _ = try await repository.applySnapshot([row], maxEventID: 1, snapshotSeq: context.snapshotSeq + 1, write: context)
        try await repository.close()
        let transport = BootstrapTransport(user: user)
        let session = Session(baseURL: origin, transport: transport,
                              credentials: BootstrapCredentials(StoredSession(refresh_token: "test", user: user)),
                              sendAttempts: SendAttemptStore(directory: base.appendingPathComponent("legacy")))
        let client = IMClient(baseURL: origin, session: session)
        let controller = ChatStorageController(client: client, opener: { partition, location in
            if let openGate { await openGate.enter() }
            return try ChatRepository.open(partition, location: location, legacyAttemptRoot: base.appendingPathComponent("legacy"))
        }) { _ in location }
        return (AppModel(client: client, storage: controller), transport)
    }
}

private actor BootstrapOpenGate {
    private var entered = false
    private var released = false
    private var observer: CheckedContinuation<Void, Never>?
    private var opener: CheckedContinuation<Void, Never>?
    func enter() async {
        entered = true
        observer?.resume(); observer = nil
        if !released { await withCheckedContinuation { opener = $0 } }
    }
    func waitUntilEntered() async {
        if !entered { await withCheckedContinuation { observer = $0 } }
    }
    func release() {
        released = true
        opener?.resume(); opener = nil
    }
}

private final class BootstrapCredentials: CredentialStore, @unchecked Sendable {
    private let lock = NSLock()
    private var value: StoredSession?
    init(_ value: StoredSession?) { self.value = value }
    func load() throws -> StoredSession? { lock.lock(); defer { lock.unlock() }; return value }
    func save(_ session: StoredSession) throws { lock.lock(); defer { lock.unlock() }; value = session }
    func remove() throws { lock.lock(); defer { lock.unlock() }; value = nil }
}

private actor BootstrapTransport: HTTPTransport {
    private let user: AuthUser
    private(set) var requests = 0
    init(user: AuthUser) { self.user = user }
    func data(for request: URLRequest) async throws -> (Data, HTTPURLResponse) {
        requests += 1
        let data: Data
        if request.url!.path.hasSuffix("/refresh") {
            data = try JSONEncoder().encode(TokenPair(access_token: "test", refresh_token: "test", user: user))
        } else if request.url!.path.hasSuffix("/me") { data = try JSONEncoder().encode(user) }
        else { throw URLError(.notConnectedToInternet) }
        return (data, HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!)
    }
}
