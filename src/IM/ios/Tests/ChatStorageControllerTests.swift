import XCTest
import Observation
@testable import NanoIM

/// Partition lifecycle. The controller is the only owner: these tests pin that `.opening` is
/// not a downgrade, that a failed open degrades instead of lying, and that a switch removes
/// the previous account's rows and files.
@MainActor
final class ChatStorageControllerTests: XCTestCase {
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

    func testOpeningIsNotDegraded() async throws {
        let controller = try makeController()
        let store = makeStore(controller)
        XCTAssertNil(store.storageDegradedReason, "a partition that is still opening is not a missing cache")
        XCTAssertEqual(store.listPhase, .loadingFirst)
        XCTAssertTrue(store.conversations.isEmpty)
    }

    func testReadyPaintsTheStoredPartition() async throws {
        let controller = try makeController()
        await controller.activate(makePartition("user"))
        let repository = try XCTUnwrap(controller.repository)
        var context = try await repository.writeContext()
        _ = try await repository.applySnapshot([try conversation("a")], maxEventID: 7,
                                               snapshotSeq: context.snapshotSeq + 1, write: context)
        context = try await repository.writeContext()
        try await repository.setDraft("a", body: "remembered text")
        _ = try await repository.applyPage("a", items: [TimelineItem(type: "message", message: try message(1))], write: context)

        let store = makeStore(controller)
        await store.loadSeed()
        XCTAssertEqual(store.conversations.map(\.id), ["a"])
        XCTAssertEqual(store.drafts["a"], "remembered text")
        XCTAssertEqual(store.listPhase, .loaded)
        XCTAssertEqual(store.connection, .localOnly, "local content is painted before any successful correction")
        // Invariant ③: the stamp is the recorded `sync.last_full_at`, including one written by
        // an earlier process — never "now".
        let recorded = try await repository.connectionSeed().lastFullAt
        XCTAssertEqual(store.lastFullAt, recorded)
        XCTAssertNotNil(recorded)
    }

    func testUnopenablePartitionDegradesInsteadOfPretending() async throws {
        // A regular file where the partition directory should be makes `prepare()` fail.
        let blocked = try XCTUnwrap(root).appendingPathComponent("blocked")
        try Data().write(to: blocked)
        let controller = ChatStorageController(client: makeClient()) { _ in
            ChatStorageLocation.directory(blocked.appendingPathComponent("db", isDirectory: true))
        }
        await controller.activate(makePartition("user"))
        guard case .degraded = controller.state else { return XCTFail("expected a degraded partition") }
        let store = makeStore(controller)
        XCTAssertNotNil(store.storageDegradedReason)
        XCTAssertNil(store.repository, "degraded means pure network mode, not a half-open store")
        store.resetProjection()
        XCTAssertEqual(store.listPhase, .loadingFirst, "no crash and no fake first paint")
    }

    func testActivatingAnotherPartitionPurgesThePreviousOne() async throws {
        let controller = try makeController()
        await controller.activate(makePartition("a"))
        let repository = try XCTUnwrap(controller.repository)
        let context = try await repository.writeContext()
        _ = try await repository.applySnapshot([try conversation("chat")], maxEventID: 1,
                                               snapshotSeq: context.snapshotSeq + 1, write: context)
        let firstDirectory = try location(makePartition("a")).directoryURL
        XCTAssertTrue(FileManager.default.fileExists(atPath: firstDirectory.path))

        await controller.activate(makePartition("b"))
        XCTAssertFalse(FileManager.default.fileExists(atPath: firstDirectory.path), "the previous account's partition is gone")
        let next = try XCTUnwrap(controller.repository)
        let remaining = try await next.conversations()
        XCTAssertTrue(remaining.isEmpty)
        XCTAssertEqual(controller.partition?.userID, "b")
    }

    func testPurgeClearsRowsAndFilesAndKeepsTheStateHonest() async throws {
        let controller = try makeController()
        await controller.activate(makePartition("user"))
        let directory = try location(makePartition("user")).directoryURL
        let repository = try XCTUnwrap(controller.repository)
        let context = try await repository.writeContext()
        _ = try await repository.applySnapshot([try conversation("a")], maxEventID: 1,
                                               snapshotSeq: context.snapshotSeq + 1, write: context)
        let store = makeStore(controller)
        await store.loadSeed()
        XCTAssertEqual(store.conversations.count, 1)

        await controller.purge(reason: .signedOut)
        XCTAssertFalse(FileManager.default.fileExists(atPath: directory.path))
        XCTAssertNil(controller.repository)
        XCTAssertNil(controller.partition)
        XCTAssertTrue(store.conversations.isEmpty)
        XCTAssertEqual(store.listPhase, .loadingFirst)
        XCTAssertNotNil(store.storageDegradedReason)
    }

    func testConcurrentActivationCoalescesTheSamePartitionOpen() async throws {
        let base = try XCTUnwrap(root)
        let gate = OpenGate()
        let controller = ChatStorageController(client: makeClient(), opener: { partition, location in
            await gate.enter()
            return try ChatRepository.open(partition, location: location, legacyAttemptRoot: base.appendingPathComponent("legacy"))
        }) { partition in ChatStorageLocation.directory(base.appendingPathComponent(partition.userID)) }
        let first = Task { await controller.activate(makePartition("user")) }
        await gate.waitUntilEntered()
        let second = Task { await controller.activate(makePartition("user")) }
        // This main-actor turn is a deterministic opportunity for the second caller to enter.
        await Task.yield()
        await gate.release()
        await first.value; await second.value
        let count = await gate.entries
        XCTAssertEqual(count, 1, "login and its session observer must share one open, not purge each other")
        XCTAssertEqual(controller.partition, makePartition("user"))
        XCTAssertNotNil(controller.repository)
    }

    func testPurgeDuringOpenDrainsAndRemovesTheStalePartition() async throws {
        let base = try XCTUnwrap(root)
        let gate = OpenGate()
        let controller = ChatStorageController(client: makeClient(), opener: { partition, location in
            await gate.enter()
            return try ChatRepository.open(partition, location: location, legacyAttemptRoot: base.appendingPathComponent("legacy"))
        }) { partition in ChatStorageLocation.directory(base.appendingPathComponent(partition.userID)) }
        let first = Task { await controller.activate(makePartition("user")) }
        await gate.waitUntilEntered()
        let purge = Task { await controller.purge(reason: .signedOut) }
        await Task.yield()
        await gate.release()
        await first.value; await purge.value
        XCTAssertNil(controller.partition)
        XCTAssertNil(controller.repository)
        XCTAssertFalse(FileManager.default.fileExists(atPath: base.appendingPathComponent("user").path),
                       "an opener that completed after logout must not leave readable data behind")
    }

    func testRetryPersistsAKnownFailedRevocationBeforePublishingAnyCachedSeed() async throws {
        let controller = try makeController()
        await controller.activate(makePartition("user"))
        let repository = try XCTUnwrap(controller.repository)
        let context = try await repository.writeContext()
        _ = try await repository.applyConversation(conversation("a"), members: [], write: context)
        _ = try await repository.applyPage("a", items: [TimelineItem(type: "message", message: try message(1))], write: context)
        let store = makeStore(controller)
        await store.loadSeed()
        XCTAssertEqual(store.conversations.map(\.id), ["a"])
        // The caller reports an actual cleanup-write failure through this interface. The old
        // readable policy is deliberately unchanged, exactly as after an atomic write failed.
        XCTAssertTrue(try repository.attemptPersistence.policy().conversationCleanups.isEmpty)
        controller.reportCleanupFailure("fixture: policy write failed", conversationID: "a", kind: .revokeAccess)
        XCTAssertTrue(store.conversations.isEmpty)
        XCTAssertNil(controller.repository)
        await controller.retryOpen()
        let retried = try XCTUnwrap(controller.repository)
        let conversations = try await retried.conversations()
        let tombstones = try await retried.revokedConversations()
        XCTAssertTrue(conversations.isEmpty)
        XCTAssertTrue(store.conversations.isEmpty, "retry cannot bootstrap the cache whose cleanup previously failed")
        XCTAssertEqual(tombstones, ["a"])
    }

    func testRetryOfFailedPendingDiscardKeepsReadableHistory() async throws {
        let controller = try makeController()
        await controller.activate(makePartition("user"))
        let repository = try XCTUnwrap(controller.repository)
        let context = try await repository.writeContext()
        _ = try await repository.applyConversation(conversation("a"), members: [], write: context)
        _ = try await repository.applyPage("a", items: [TimelineItem(type: "message", message: try message(1))], write: context)
        let pending = SendAttempt(conversationID: "a", sourceMessageID: nil,
                                  draft: PendingSend(key: "old", content: "uncertain", attachments: [], requestBody: Data("{}".utf8)))
        try await repository.upsertPending(pending, write: context)
        let store = makeStore(controller)
        controller.reportCleanupFailure("fixture: policy write failed", conversationID: "a", kind: .discardPending)
        await controller.retryOpen()
        let retried = try XCTUnwrap(controller.repository)
        let page = try await retried.timeline("a")
        let pendingCount = try await retried.pendingCount()
        let tombstones = try await retried.revokedConversations()
        XCTAssertEqual(store.conversations.map(\.id), ["a"])
        XCTAssertEqual(page.items.map(\.id), ["m1"])
        XCTAssertEqual(pendingCount, 0)
        XCTAssertTrue(tombstones.isEmpty)
    }

    func testFailedPartitionPurgeRetriesBeforeSameOwnerCanSeed() async throws {
        let controller = try makeController()
        let partition = makePartition("user")
        await controller.activate(partition)
        let repository = try XCTUnwrap(controller.repository)
        let context = try await repository.writeContext()
        _ = try await repository.applyConversation(conversation("a"), members: [], write: context)
        try await repository.setDraft("a", body: "old private draft")
        try await repository.upsertPending(SendAttempt(conversationID: "a", sourceMessageID: nil,
                                                       draft: PendingSend(key: "old", content: "private", attachments: [], requestBody: Data("{}".utf8))), write: context)
        let store = makeStore(controller)
        await store.loadSeed()
        let blocker = repository.attemptPersistence.policyURL.deletingLastPathComponent()
        XCTAssertFalse(FileManager.default.fileExists(atPath: blocker.path))
        try Data("fixture blocks policy IO".utf8).write(to: blocker)
        await controller.purge(reason: .signedOut)
        guard case .degraded = controller.state else { return XCTFail("purge IO must fail honestly") }
        XCTAssertNil(controller.partition)
        XCTAssertTrue(store.conversations.isEmpty)
        // This exact temporary fixture is the file created above, not production data.
        XCTAssertEqual(blocker.deletingLastPathComponent(), root)
        try FileManager.default.removeItem(at: blocker)
        await controller.activate(partition)
        let reopened = try XCTUnwrap(controller.repository)
        let rows = try await reopened.conversations()
        XCTAssertTrue(rows.isEmpty, "same-owner login must finish the failed purge before publishing a seed")
        let draft = try await reopened.draft("a")
        let attempts = try await reopened.pendingAttempts()
        XCTAssertNil(draft)
        XCTAssertTrue(attempts.isEmpty)
        XCTAssertTrue(store.conversations.isEmpty)
        XCTAssertNotNil(try reopened.attemptPersistence.policy().purgeGeneration)
        try await reopened.close()
    }

    func testFailedPurgeCanRetryWhileLogicalPartitionIsNil() async throws {
        let controller = try makeController()
        await controller.activate(makePartition("user"))
        let repository = try XCTUnwrap(controller.repository)
        let blocker = repository.attemptPersistence.policyURL.deletingLastPathComponent()
        XCTAssertFalse(FileManager.default.fileExists(atPath: blocker.path))
        try Data().write(to: blocker)
        await controller.purge(reason: .signedOut)
        XCTAssertNil(controller.partition)
        XCTAssertEqual(blocker.deletingLastPathComponent(), root)
        try FileManager.default.removeItem(at: blocker)
        await controller.retryOpen()
        let directory = try location(makePartition("user")).directoryURL
        XCTAssertFalse(FileManager.default.fileExists(atPath: directory.path), "nil partition is not evidence the failed cleanup completed")
        XCTAssertNotNil(try repository.attemptPersistence.policy().purgeGeneration)
    }

    func testQueuedSignOutCannotBeSupersededBySameOwnerActivation() async throws {
        let controller = try makeController()
        let partition = makePartition("user")
        await controller.activate(partition)
        let repository = try XCTUnwrap(controller.repository)
        let context = try await repository.writeContext()
        _ = try await repository.applyConversation(conversation("a"), members: [], write: context)
        // The partition's will-change callback enqueues login before move(nil) can create
        // its child operation. This covers accepted authority with an unstarted purge.
        let relogged = expectation(description: "same owner reactivated")
        withObservationTracking {
            _ = controller.partition
        } onChange: {
            Task { @MainActor in
                await controller.activate(partition)
                relogged.fulfill()
            }
        }
        await controller.purge(reason: .signedOut)
        await fulfillment(of: [relogged], timeout: 3)
        let reopened = try XCTUnwrap(controller.repository)
        let rows = try await reopened.conversations()
        XCTAssertTrue(rows.isEmpty)
        XCTAssertNotNil(try reopened.attemptPersistence.policy().purgeGeneration)
        try await reopened.close()
    }

    // MARK: - Helpers

    private func makeClient() -> IMClient { IMClient(baseURL: origin) }
    private func makePartition(_ userID: String) -> ChatPartition { ChatPartition(origin: origin, userID: userID) }
    private func location(_ partition: ChatPartition) throws -> ChatStorageLocation {
        ChatStorageLocation.directory(try XCTUnwrap(root).appendingPathComponent(partition.userID, isDirectory: true))
    }
    private func makeController() throws -> ChatStorageController {
        let base = try XCTUnwrap(root)
        return ChatStorageController(client: makeClient(), opener: { partition, location in
            try ChatRepository.open(partition, location: location, legacyAttemptRoot: base.appendingPathComponent("legacy"))
        }) { partition in
            ChatStorageLocation.directory(base.appendingPathComponent(partition.userID, isDirectory: true))
        }
    }
    private func makeStore(_ controller: ChatStorageController) -> ChatStore {
        ChatStore(client: makeClient(), user: user, controller: controller)
    }
    private func conversation(_ id: String) throws -> Conversation {
        try JSONDecoder().decode(Conversation.self, from: Data("""
            {"id":"\(id)","title":"\(id)","participants":[],"participant_ids":["user"],"type":"group",
             "owner_id":"user","creator_id":"user","is_pinned":false,"is_muted":false,"unread_count":0,"created_at":"now"}
            """.utf8))
    }
    private func message(_ n: Int) throws -> ChatMessage {
        try JSONDecoder().decode(ChatMessage.self, from: Data("""
            {"id":"m\(n)","conversation_id":"a","sender":{"type":"user","id":"user"},"sender_user_id":"user",
             "sender_type":"user","content":"message \(n)","attachments":[],"delivery_status":"completed",
             "created_at":"2026-11-01T00:00:0\(n)Z"}
            """.utf8))
    }
}

private actor OpenGate {
    private(set) var entries = 0
    private var released = false
    private var waiters: [CheckedContinuation<Void, Never>] = []
    private var observer: CheckedContinuation<Void, Never>?

    func enter() async {
        entries += 1
        observer?.resume(); observer = nil
        if released { return }
        await withCheckedContinuation { waiters.append($0) }
    }
    func waitUntilEntered() async {
        if entries > 0 { return }
        await withCheckedContinuation { observer = $0 }
    }
    func release() {
        released = true
        for waiter in waiters { waiter.resume() }
        waiters = []
    }
}
