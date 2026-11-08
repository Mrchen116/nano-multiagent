import XCTest
import GRDB
@testable import NanoIM

/// Repository-level contracts: the store is the durable truth, so these tests talk to SQLite
/// through `ChatRepository` only (no stub transport) and assert what a restart would read.
final class ChatRepositoryTests: XCTestCase {
    private var root: URL!
    private let origin = URL(string: "https://im.example.test")!
    private var partition: ChatPartition { ChatPartition(origin: origin, userID: "user") }
    private var legacyRoot: URL { root.appendingPathComponent("legacy", isDirectory: true) }

    override func setUpWithError() throws {
        root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
    }
    override func tearDownWithError() throws {
        if let root, FileManager.default.fileExists(atPath: root.path) { try FileManager.default.removeItem(at: root) }
    }

    // MARK: - Migration

    func testSchemaMigrationIsIdempotent() async throws {
        let first = try open()
        let seed = try await first.bootstrapSeed()
        XCTAssertTrue(seed.conversations.isEmpty)
        XCTAssertEqual(seed.pendingCount, 0)
        XCTAssertEqual(seed.connection.snapshotSeq, 0)

        // Re-opening runs the same migrator again; it must be a no-op rather than a failure.
        let second = try open()
        let actual = try await second.connectionSeed().snapshotSeq
        XCTAssertEqual(actual, 0)
        let actual2 = try await second.conversations().isEmpty
        XCTAssertTrue(actual2)
    }

    func testMigrationImportsEveryAttemptByteExactlyOnce() async throws {
        let legacy = SendAttemptStore(directory: legacyRoot)
        let image = ChatAttachment(url: "/im/v1/uploads/1", content_type: "image/png", file_name: "a.png")
        let plain = Data(#"{"content":"hello","attachments":[]}"#.utf8)
        let withImage = Data(#"{"content":"second","attachments":[{"url":"/im/v1/uploads/1"}]}"#.utf8)
        try legacy.save(SendAttempt(conversationID: "a", sourceMessageID: nil,
                                    draft: PendingSend(key: "k1", content: "hello", attachments: [], requestBody: plain)),
                        origin: origin, userID: "user")
        try legacy.save(SendAttempt(conversationID: "b", sourceMessageID: "s1",
                                    draft: PendingSend(key: "k2", content: "second", attachments: [image], requestBody: withImage)),
                        origin: origin, userID: "user")

        let repo = try open()
        // The import happens before any `/sync`, so `conversations` is still empty here — the
        // migration must not depend on a conversation row (no foreign key on pending_sends).
        let actual = try await repo.conversations().isEmpty
        XCTAssertTrue(actual)
        let attempts = try await repo.pendingAttempts()
        XCTAssertEqual(attempts.count, 2)
        XCTAssertEqual(Set(attempts.map { $0.draft.requestBody! }), [plain, withImage])
        let restored = attempts.first { $0.conversationID == "b" }
        XCTAssertEqual(restored?.sourceMessageID, "s1")
        XCTAssertEqual(restored?.draft.attachments, [image])
        let actual2 = try await repo.migrationReport().allSatisfy { $0.outcome == "imported" }
        XCTAssertTrue(actual2)

        // A second open reads the in-database marker and does not import twice.
        let reopened = try open()
        let actual3 = try await reopened.pendingCount()
        XCTAssertEqual(actual3, 2)
        let actual4 = try await reopened.migrationReport().count
        XCTAssertEqual(actual4, 2)
    }

    func testOrphanedPendingConvergesWithFirstSnapshot() async throws {
        let legacy = SendAttemptStore(directory: legacyRoot)
        try legacy.save(SendAttempt(conversationID: "ghost", sourceMessageID: nil,
                                    draft: PendingSend(key: "k", content: "unsent", attachments: [], requestBody: Data("{}".utf8))),
                        origin: origin, userID: "user")
        let repo = try open()
        let actual = try await repo.pendingCount()
        XCTAssertEqual(actual, 1)

        let context = try await repo.writeContext()
        let result = try await repo.applySnapshot([conversation("a")], maxEventID: 3,
                                                 snapshotSeq: context.snapshotSeq + 1, write: context)
        XCTAssertEqual(result.pendingCount, 0)
        XCTAssertEqual(result.revoked, ["ghost"])
        let actual2 = try await repo.revokedConversations()
        XCTAssertEqual(actual2, ["ghost"])
        // No placeholder row: the list only contains what the server confirmed.
        let actual3 = try await repo.conversations().map(\.id)
        XCTAssertEqual(actual3, ["a"])
        let recorded = try await repo.migrationReport()
        XCTAssertTrue(recorded.contains { $0.outcome == "orphaned" })
    }

    // MARK: - Snapshot and revocation

    func testSnapshotReportsOnlyNewRevocations() async throws {
        let repo = try open()
        var context = try await repo.writeContext()
        _ = try await repo.applySnapshot([conversation("a"), conversation("b")], maxEventID: 1,
                                         snapshotSeq: context.snapshotSeq + 1, write: context)
        context = try await repo.writeContext()
        let second = try await repo.applySnapshot([conversation("a")], maxEventID: 2,
                                                  snapshotSeq: context.snapshotSeq + 1, write: context)
        XCTAssertEqual(second.revoked, ["b"], "a disappearing conversation is reported once")
        context = try await repo.writeContext()
        let third = try await repo.applySnapshot([conversation("a")], maxEventID: 3,
                                                 snapshotSeq: context.snapshotSeq + 1, write: context)
        XCTAssertEqual(third.revoked, [], "an existing tombstone must not be re-reported")
        XCTAssertEqual(third.conversations.map(\.id), ["a"])
    }

    func testStaleWriteContextAndOlderSnapshotAreRejected() async throws {
        let repo = try open()
        let stale = try await repo.writeContext()
        let fresh = try await repo.writeContext()
        _ = try await repo.applySnapshot([conversation("a")], maxEventID: 1,
                                         snapshotSeq: fresh.snapshotSeq + 1, write: fresh)
        do {
            _ = try await repo.applySnapshot([conversation("a")], maxEventID: 2,
                                             snapshotSeq: fresh.snapshotSeq + 1, write: stale)
            XCTFail("a write from the previous snapshot generation must be rejected")
        } catch { XCTAssertEqual(error as? ChatRepositoryError, .staleWrite) }
        do {
            _ = try await repo.applyPage("a", items: [item(try message(1))], write: stale)
            XCTFail("a late page must not be written back after a newer snapshot")
        } catch { XCTAssertEqual(error as? ChatRepositoryError, .staleWrite) }
        do {
            let current = try await repo.writeContext()
            _ = try await repo.applySnapshot([conversation("a")], maxEventID: 3,
                                             snapshotSeq: current.snapshotSeq, write: current)
            XCTFail("an older snapshot sequence must be rejected")
        } catch { XCTAssertEqual(error as? ChatRepositoryError, .staleWrite) }
    }

    func testRevokeDeletesRowsAndTombstoneBlocksLateWrites() async throws {
        let repo = try open()
        let context = try await repo.writeContext()
        _ = try await repo.applyConversation(conversation("a"), members: conversation("a").participants, write: context)
        _ = try await repo.applyPage("a", items: [item(try message(1))], write: context)
        try await repo.setDraft("a", body: "keep me")
        try await repo.upsertPending(SendAttempt(conversationID: "a", sourceMessageID: nil,
                                                 draft: PendingSend(key: "k", content: "x", attachments: [], requestBody: Data("{}".utf8))),
                                     write: context)

        try await repo.revoke("a", reason: .detailForbidden, write: context)
        let actual = try await repo.conversations().isEmpty
        XCTAssertTrue(actual)
        let actual2 = try await repo.timeline("a").items.isEmpty
        XCTAssertTrue(actual2)
        let actual3 = try await repo.draft("a")
        XCTAssertNil(actual3)
        let actual4 = try await repo.pendingCount()
        XCTAssertEqual(actual4, 0)
        let actual5 = try await repo.revokedConversations()
        XCTAssertEqual(actual5, ["a"])

        let revokedContext = try await repo.writeContext()
        do {
            _ = try await repo.applyPage("a", items: [item(try message(2))], write: revokedContext)
            XCTFail("a revoked conversation must refuse a late page")
        } catch { XCTAssertEqual(error as? ChatRepositoryError, .revokedConversation("a")) }
        do {
            try await repo.upsertPending(SendAttempt(conversationID: "a", sourceMessageID: nil,
                                                     draft: PendingSend(key: "k2", content: "y", attachments: [], requestBody: Data("{}".utf8))),
                                         write: revokedContext)
            XCTFail("a revoked conversation must refuse a new pending send")
        } catch { XCTAssertEqual(error as? ChatRepositoryError, .revokedConversation("a")) }

        // The server saying the conversation is accessible again clears the tombstone.
        let next = try await repo.writeContext()
        _ = try await repo.applySnapshot([conversation("a")], maxEventID: 4, snapshotSeq: next.snapshotSeq + 1, write: next)
        let actual6 = try await repo.revokedConversations().isEmpty
        XCTAssertTrue(actual6)
    }

    func testNonWritableConversationDropsOnlyPendingSends() async throws {
        let repo = try open()
        let context = try await repo.writeContext()
        // A migrated record for a conversation the snapshot then reports as read-only: the row
        // stays (the user can still read it), only the unconfirmed send loses its path.
        try await repo.upsertPending(attempt("a", "k1"), write: context)
        _ = try await repo.applySnapshot([conversation("a", canWrite: false)], maxEventID: 1,
                                         snapshotSeq: context.snapshotSeq + 1, write: context)
        let actual = try await repo.pendingCount()
        XCTAssertEqual(actual, 0)
        let actual2 = try await repo.conversations().map(\.id)
        XCTAssertEqual(actual2, ["a"])
        let actual3 = try await repo.revokedConversations().isEmpty
        XCTAssertTrue(actual3, "read-only is not a revocation")

        // The same primitive, called when the store discards attempts for a visible conversation.
        let second = try await repo.writeContext()
        _ = try await repo.applySnapshot([conversation("a", canWrite: false), conversation("b")], maxEventID: 2,
                                         snapshotSeq: second.snapshotSeq + 1, write: second)
        let write = try await repo.writeContext()
        try await repo.upsertPending(attempt("b", "k2"), write: write)
        try await repo.deletePending(conversationID: "b", write: write)
        let actual4 = try await repo.pendingCount()
        XCTAssertEqual(actual4, 0)
        let actual5 = try await repo.conversations().map(\.id).sorted()
        XCTAssertEqual(actual5, ["a", "b"])
    }

    func testDetailRevocationInvalidatesOlderSuccessfulListAndDetailContexts() async throws {
        let repo = try open()
        let old = try await repo.writeContext()
        _ = try await repo.applyConversation(conversation("a"), members: [], write: old)
        try await repo.revoke("a", reason: .detailForbidden, write: old)
        for isList in [true, false] {
            do {
                if isList { _ = try await repo.applyConversationList([conversation("a")], write: old) }
                else { _ = try await repo.applyConversation(conversation("a"), members: [], write: old) }
                XCTFail("an older HTTP 200 cannot undo a newer authoritative denial")
            } catch { XCTAssertEqual(error as? ChatRepositoryError, .staleWrite) }
        }
        let rows = try await repo.conversations()
        let revoked = try await repo.revokedConversations()
        XCTAssertTrue(rows.isEmpty)
        XCTAssertEqual(revoked, ["a"])
    }

    func testDiscardDeletesMessageAndBoundaryAndBlocksOlderPageAfterReopen() async throws {
        let repo = try open()
        let context = try await repo.writeContext()
        _ = try await repo.applyConversation(conversation("a"), members: [], write: context)
        let boundary = TimelineItem(type: "boundary", boundaryID: "b2", conversation_id: "a",
                                    agent_id: "agent", before_message_id: "m2", applied_at: "now")
        let page = [item(try message(1)), item(try message(2)), boundary]
        _ = try await repo.applyPage("a", items: page, write: context)
        let event = try JSONDecoder().decode(UserEvent.self, from: Data("""
            {"op":"event","event_id":20,"event_type":"message.discarded","data":{"conversation_id":"a","message_id":"m2"}}
            """.utf8))
        _ = try await repo.applyEvent(event, write: context)
        let cursor = try await repo.connectionSeed().maxEventID
        XCTAssertEqual(cursor, 20)
        let reopened = try open()
        let current = try await reopened.writeContext()
        _ = try await reopened.applyPage("a", items: page, write: current)
        let ids = try await reopened.timeline("a").items.map(\.id)
        XCTAssertEqual(ids, ["m1"], "a cached old page must not resurrect discarded content or its boundary")
    }

    func testSchemaFailureDoesNotQuarantineAValidDatabase() throws {
        let location = ChatStorageLocation.directory(root.appendingPathComponent("schema-error"))
        try location.prepare()
        let queue = try DatabaseQueue(path: location.databaseURL.path)
        try queue.write { db in
            try db.execute(sql: "CREATE TABLE cache_meta(unexpected TEXT)")
            try db.execute(sql: "INSERT INTO cache_meta(unexpected) VALUES('recoverable')")
        }
        try queue.close()
        XCTAssertThrowsError(try open(location))
        let preserved = try DatabaseQueue(path: location.databaseURL.path)
        let value = try preserved.read { db in try String.fetchOne(db, sql: "SELECT unexpected FROM cache_meta") }
        XCTAssertEqual(value, "recoverable")
        try preserved.close()
        let files = try FileManager.default.contentsOfDirectory(atPath: location.directoryURL.path)
        XCTAssertFalse(files.contains { $0.contains("corrupt") }, "schema/IO failures are not evidence of corruption")
    }

    func testCorruptDatabaseIsQuarantinedAndRebuilt() async throws {
        let location = ChatStorageLocation.directory(root.appendingPathComponent("corrupt"))
        try location.prepare()
        let original = Data("not a SQLite database".utf8)
        try original.write(to: location.databaseURL)
        let repo = try open(location)
        let seed = try await repo.bootstrapSeed()
        XCTAssertTrue(seed.conversations.isEmpty)
        let files = try FileManager.default.contentsOfDirectory(at: location.directoryURL, includingPropertiesForKeys: nil)
        let quarantine = try XCTUnwrap(files.first { $0.lastPathComponent.contains("corrupt-") })
        XCTAssertEqual(try Data(contentsOf: quarantine), original)
    }

    // MARK: - Timeline

    func testTrimKeepsWindowAndDropsAnchoredBoundary() async throws {
        let repo = try open()
        let context = try await repo.writeContext()
        _ = try await repo.applyConversation(conversation("a"), members: [], write: context)
        let first = try (1...300).map { item(try message($0)) }
        let boundary = TimelineItem(type: "boundary", boundaryID: "b-old", conversation_id: "a",
                                    agent_id: "agent", before_message_id: "m10", applied_at: "2026-11-01T00:00:00Z")
        _ = try await repo.applyPage("a", items: first + [boundary], write: context)
        let actual = try await repo.timeline("a").items.count
        XCTAssertEqual(actual, 301)

        let second = try (301...350).map { item(try message($0)) }
        let page = try await repo.applyPage("a", items: second, write: context)
        XCTAssertEqual(page.items.compactMap { $0.message?.id }.count, ChatRepository.retentionLimit)
        XCTAssertEqual(page.items.first?.message?.id, "m51")
        XCTAssertTrue(page.olderNeedsNetwork)
        XCTAssertFalse(page.isAtLocalStart)
        XCTAssertEqual(page.nextBefore, "m51", "the cursor points at the oldest retained row")
        XCTAssertFalse(page.items.contains { $0.boundaryID == "b-old" }, "a boundary whose anchor was trimmed is gone")
    }

    func testTimelineOrderingMatchesTimelineMerge() async throws {
        let repo = try open()
        let context = try await repo.writeContext()
        _ = try await repo.applyConversation(conversation("a"), members: [], write: context)
        let sameSecond = "2026-11-01T00:00:00Z"
        let items = [item(try message(2, createdAt: sameSecond)), item(try message(1, createdAt: sameSecond)),
                     item(try message(3, createdAt: "2026-11-01T00:00:01Z"))]
        _ = try await repo.applyPage("a", items: items, write: context)
        let stored = try await repo.timeline("a").items.map(\.id)
        let merged = TimelineMerge.merge(current: [], page: items, older: false, discarded: []).map(\.id)
        XCTAssertEqual(stored, merged)
        XCTAssertEqual(stored, ["m1", "m2", "m3"])
    }

    func testPayloadAndBoundaryRoundTrip() async throws {
        let repo = try open()
        let context = try await repo.writeContext()
        _ = try await repo.applyConversation(conversation("a"), members: conversation("a").participants, write: context)
        let rich = try message(1, extra: ["interactive": ["format": "openui", "catalog_version": "1",
                                                          "source": "agent", "read_only": true,
                                                          "superseded_by": "m9"],
                                        "tool_calls": [["id": "t1", "name": "search", "status": "completed",
                                                        "output": "ok", "duration_ms": 12.5]]])
        let boundary = TimelineItem(type: "boundary", boundaryID: "b1", conversation_id: "a",
                                    agent_id: "agent", before_message_id: "m1", applied_at: "2026-11-01T00:00:00Z")
        _ = try await repo.applyPage("a", items: [boundary, item(rich)], write: context)

        let page = try await repo.timeline("a")
        XCTAssertEqual(page.items.compactMap(\.boundaryID), ["b1"])
        XCTAssertEqual(page.items.first?.boundaryID, "b1", "the boundary stays attached above its message")
        let restored = try XCTUnwrap(page.items.last?.message)
        XCTAssertEqual(restored.interactive?.format, "openui")
        XCTAssertEqual(restored.interactive?.read_only, true)
        XCTAssertEqual(restored.interactive?.superseded_by, "m9")
        XCTAssertEqual(restored.tool_calls?.first?.duration_ms, 12.5)
    }

    func testDraftFlushKeepsLatestSnapshot() async throws {
        let repo = try open()
        let context = try await repo.writeContext()
        _ = try await repo.applyConversation(conversation("a"), members: [], write: context)
        try await repo.setDraft("a", body: "first")
        try await repo.setDraft("a", body: "second")
        let actual = try await repo.draft("a")
        XCTAssertEqual(actual, "second")
        try await repo.setDraft("a", body: "")
        let actual2 = try await repo.draft("a")
        XCTAssertNil(actual2)
    }

    func testReadBoundaryDoesNotChangeConversationProjection() async throws {
        let repo = try open()
        let context = try await repo.writeContext()
        _ = try await repo.applySnapshot([conversation("a", unread: 3)], maxEventID: 1,
                                         snapshotSeq: context.snapshotSeq + 1, write: context)
        try await repo.markReadBoundary("a", messageID: "m1")
        // U1 records the confirmed boundary but never derives unread from it (U3 owns that).
        let actual = try await repo.conversations().first?.unread_count
        XCTAssertEqual(actual, 3)
    }

    // MARK: - Partition lifecycle

    func testPurgeLeavesNothingToRead() async throws {
        let store = ChatStorageLocation.directory(root.appendingPathComponent("db", isDirectory: true))
        let repo = try open(store)
        let context = try await repo.writeContext()
        _ = try await repo.applySnapshot([conversation("a")], maxEventID: 1,
                                         snapshotSeq: context.snapshotSeq + 1, write: context)
        try await repo.setDraft("a", body: "draft")
        try await repo.purge()
        XCTAssertFalse(FileManager.default.fileExists(atPath: store.databaseURL.path))
        let reopened = try open(store)
        let actual = try await reopened.conversations().isEmpty
        XCTAssertTrue(actual)
        let actual2 = try await reopened.connectionSeed().snapshotSeq
        XCTAssertGreaterThan(actual2, 0, "the surviving purge intent is applied before a new cache can be read")
        let actual3 = try await reopened.draft("a")
        XCTAssertNil(actual3)
    }

    func testPolicyCommittedBeforeSQLRollbackIsAppliedBeforeTheNextRead() async throws {
        let repo = try open()
        let context = try await repo.writeContext()
        _ = try await repo.applyConversation(conversation("a"), members: [], write: context)
        let fixture = try DatabaseQueue(path: repo.location.databaseURL.path)
        try fixture.write { db in
            try db.execute(sql: "CREATE TRIGGER fail_cleanup BEFORE DELETE ON conversations BEGIN SELECT RAISE(ABORT, 'isolated cleanup failure'); END")
        }
        do {
            try await repo.revoke("a", reason: .detailForbidden, write: context)
            XCTFail("the isolated SQL trigger must abort the cleanup transaction")
        } catch {
            XCTAssertNotNil(try repo.attemptPersistence.policy().conversationCleanups["a"])
        }
        try fixture.write { db in try db.execute(sql: "DROP TRIGGER fail_cleanup") }
        try fixture.close()
        let afterRetry = try await repo.conversations()
        let tombstones = try await repo.revokedConversations()
        XCTAssertTrue(afterRetry.isEmpty, "even the same repository must replay the committed policy before reading old rows")
        XCTAssertEqual(tombstones, ["a"])
    }

    func testNewHandoffAfterReauthorizationSurvivesReplayedOldTombstone() async throws {
        let repo = try open()
        _ = try repo.attemptPersistence.recordCleanup("a", kind: .revokeAccess)
        let newAttempt = attempt("a", "new-after-network-regrant")
        try repo.attemptPersistence.save(newAttempt, stamp: repo.attemptPersistence.stamp(for: "a"))
        try await repo.close()
        let reopened = try open()
        let keys = try await reopened.pendingAttempts().map { $0.draft.key }
        let conversations = try await reopened.conversations()
        XCTAssertEqual(keys, [newAttempt.draft.key], "an old replayed tombstone is not a newer denial of the current-stamp request")
        XCTAssertTrue(conversations.isEmpty, "the orphan pending is not a fabricated conversation")
    }

    func testRepeatedReadonlyCleanupRotatesForAnUnhandedOffNewRequestEvenIfSQLFails() async throws {
        let repo = try open()
        var context = try await repo.writeContext()
        _ = try await repo.applyConversation(conversation("a", canWrite: false), members: [], write: context)
        let oldGeneration = try XCTUnwrap(repo.attemptPersistence.policy().conversationCleanups["a"]?.generation)
        context = try await repo.writeContext()
        _ = try await repo.applyConversation(conversation("a", canWrite: true), members: [], write: context)
        let pending = attempt("a", "new-between-readonly-events")
        try repo.attemptPersistence.save(pending, stamp: repo.attemptPersistence.stamp(for: "a"))
        let file = try XCTUnwrap(repo.attemptPersistence.loadHandoffs().first?.fileURL)
        let fixture = try DatabaseQueue(path: repo.location.databaseURL.path)
        try fixture.write { db in
            try db.execute(sql: "CREATE TRIGGER fail_receipt BEFORE INSERT ON cache_meta WHEN NEW.key='policy.conversation.a' BEGIN SELECT RAISE(ABORT, 'isolated receipt failure'); END")
        }
        do {
            _ = try await repo.applyConversation(conversation("a", canWrite: false), members: [], write: context)
            XCTFail("the isolated receipt failure must abort the SQL transaction")
        } catch {
            XCTAssertNotEqual(try repo.attemptPersistence.policy().conversationCleanups["a"]?.generation, oldGeneration)
            XCTAssertTrue(FileManager.default.fileExists(atPath: file.path), "the crash fixture retains the old handoff bytes")
        }
        try fixture.write { db in try db.execute(sql: "DROP TRIGGER fail_receipt") }
        try fixture.close()
        try await repo.close()
        let reopened = try open()
        let remaining = try await reopened.pendingAttempts()
        XCTAssertTrue(remaining.isEmpty, "the pre-cleanup file must be ineligible despite the older SQL receipt/state")
    }

    func testPurgeStillRemovesFilesWhenItsConnectionIsAlreadyClosed() async throws {
        let repo = try open()
        let directory = repo.location.directoryURL
        try await repo.close()
        // Deterministic residual-file fixture: this is also the state after a previous purge
        // closed SQLite but filesystem removal failed. Closed must not bypass that tail.
        XCTAssertTrue(FileManager.default.fileExists(atPath: directory.path))
        try await repo.purge()
        XCTAssertFalse(FileManager.default.fileExists(atPath: directory.path))
        XCTAssertNotNil(try repo.attemptPersistence.policy().purgeGeneration)
    }

    func testPurgeThenReopenCannotReimportLegacyButAcceptsANewRequest() async throws {
        let legacy = SendAttemptStore(directory: legacyRoot)
        try legacy.save(attempt("a", "legacy"), origin: origin, userID: partition.userID)
        let files = legacy.attemptFiles(origin: origin, userID: partition.userID)
        let original = try files.map { try Data(contentsOf: $0) }
        let repo = try open()
        let beforePurge = try await repo.pendingCount()
        XCTAssertEqual(beforePurge, 1)
        try await repo.purge()
        let reopened = try open()
        let afterPurge = try await reopened.pendingCount()
        XCTAssertEqual(afterPurge, 0)
        XCTAssertEqual(try files.map { try Data(contentsOf: $0) }, original, "legacy bytes remain read-only")
        let context = try await reopened.writeContext()
        _ = try await reopened.applyConversation(conversation("a"), members: [], write: context)
        try await reopened.upsertPending(attempt("a", "new"), write: context)
        let newKeys = try await reopened.pendingAttempts().map { $0.draft.key }
        XCTAssertEqual(newKeys, ["new"])
    }

    func testCommittedDiscardIntentBeforeDBCleanupPreservesReadableHistoryAndDraft() async throws {
        let legacy = SendAttemptStore(directory: legacyRoot)
        try legacy.save(attempt("a", "legacy"), origin: origin, userID: partition.userID)
        let repo = try open()
        let context = try await repo.writeContext()
        _ = try await repo.applyConversation(conversation("a"), members: [], write: context)
        _ = try await repo.applyPage("a", items: [item(try message(1))], write: context)
        try await repo.setDraft("a", body: "still editable local text")
        try await repo.close()
        // Isolated crash fixture: the external intent committed, the SQL transaction never ran.
        _ = try repo.attemptPersistence.recordCleanup("a", kind: .discardPending)
        let reopened = try open()
        let count = try await reopened.pendingCount()
        let conversations = try await reopened.conversations().map(\.id)
        let timeline = try await reopened.timeline("a").items.map(\.id)
        let draft = try await reopened.draft("a")
        let revoked = try await reopened.revokedConversations()
        XCTAssertEqual(count, 0)
        XCTAssertEqual(conversations, ["a"])
        XCTAssertEqual(timeline, ["m1"])
        XCTAssertEqual(draft, "still editable local text")
        XCTAssertTrue(revoked.isEmpty)
        XCTAssertEqual(try legacy.load(origin: origin, userID: partition.userID).count, 1)
    }

    func testCommittedAccessRevocationBeforeDBCleanupRemovesAllReadableContent() async throws {
        let repo = try open()
        let context = try await repo.writeContext()
        _ = try await repo.applyConversation(conversation("a"), members: [], write: context)
        _ = try await repo.applyPage("a", items: [item(try message(1))], write: context)
        try await repo.setDraft("a", body: "private")
        try await repo.upsertPending(attempt("a", "pending"), write: context)
        try await repo.close()
        _ = try repo.attemptPersistence.recordCleanup("a", kind: .revokeAccess)
        let reopened = try open()
        let conversations = try await reopened.conversations()
        let timeline = try await reopened.timeline("a").items
        let draft = try await reopened.draft("a")
        let count = try await reopened.pendingCount()
        let revoked = try await reopened.revokedConversations()
        XCTAssertTrue(conversations.isEmpty)
        XCTAssertTrue(timeline.isEmpty)
        XCTAssertNil(draft)
        XCTAssertEqual(count, 0)
        XCTAssertEqual(revoked, ["a"])
    }

    func testRevocationSurvivesCorruptionWithoutExcludingAnotherConversationLegacy() async throws {
        let legacy = SendAttemptStore(directory: legacyRoot)
        for id in ["a", "b"] { try legacy.save(attempt(id, "old-\(id)"), origin: origin, userID: partition.userID) }
        let repo = try open()
        let context = try await repo.writeContext()
        try await repo.revoke("a", reason: .detailForbidden, write: context)
        let location = repo.location
        try await repo.close()
        try Data("actual corrupt sqlite fixture".utf8).write(to: location.databaseURL)
        let rebuilt = try open()
        let restoredIDs = try await rebuilt.pendingAttempts().map(\.conversationID)
        XCTAssertEqual(restoredIDs, ["b"])
        XCTAssertEqual(try legacy.load(origin: origin, userID: partition.userID).count, 2)
        let newContext = try await rebuilt.writeContext()
        _ = try await rebuilt.applyConversation(conversation("a"), members: [], write: newContext)
        try await rebuilt.upsertPending(attempt("a", "new-after-regrant"), write: newContext)
        let restoredKeys = try await rebuilt.pendingAttempts().map { $0.draft.key }
        XCTAssertEqual(Set(restoredKeys), ["old-b", "new-after-regrant"])
    }

    func testPurgeWithCommittedReceiptAndResidualHandoffDoesNotResurrectIt() async throws {
        let repo = try open()
        let persistence = repo.attemptPersistence
        let old = attempt("a", "old-handoff")
        try persistence.save(old, stamp: persistence.stamp(for: "a"))
        let handoff = try XCTUnwrap(persistence.loadHandoffs().first)
        let bytes = try Data(contentsOf: handoff.fileURL)
        try await repo.purge()
        // Restore only the obsolete file, modelling a crash/file-deletion failure after the
        // policy and SQL receipt committed. The external policy remains the current one.
        try repo.location.prepare()
        try bytes.write(to: handoff.fileURL)
        let reopened = try open()
        let oldAttempts = try await reopened.pendingAttempts()
        XCTAssertTrue(oldAttempts.isEmpty)
        let fresh = attempt("a", "new-handoff")
        try persistence.save(fresh, stamp: persistence.stamp(for: "a"))
        let freshKeys = try await reopened.pendingAttempts().map { $0.draft.key }
        XCTAssertEqual(freshKeys, ["new-handoff"])
    }

    func testHandoffAfterOpenIsImportedOnceAndItsCommitMarkerSurvivesResolution() async throws {
        let repo = try open()
        let pending = attempt("a", "late-handoff")
        let persistence = repo.attemptPersistence
        try persistence.save(pending, stamp: persistence.stamp(for: "a"))
        let file = try XCTUnwrap(persistence.loadHandoffs().first?.fileURL)
        let bytes = try Data(contentsOf: file)
        let restoredBody = try await repo.pendingAttempts().first?.draft.requestBody
        XCTAssertEqual(restoredBody, pending.draft.requestBody)
        let context = try await repo.writeContext()
        try await repo.removePending(pending, write: context)
        try bytes.write(to: file)
        let remaining = try await repo.pendingAttempts()
        XCTAssertTrue(remaining.isEmpty, "a leftover handed-off file cannot recreate a resolved DB row")
    }

    // MARK: - Helpers

    private func open(_ location: ChatStorageLocation? = nil) throws -> ChatRepository {
        try ChatRepository.open(partition, location: location ?? ChatStorageLocation.directory(root.appendingPathComponent("db", isDirectory: true)),
                                legacyAttemptRoot: legacyRoot)
    }

    private func conversation(_ id: String, title: String = "Chat", canWrite: Bool = true,
                              dissolvedAt: String? = nil, unread: Int = 0) -> Conversation {
        let actor = ActorRef(type: "user", id: "u1", display_name: "U1", user_id: "u1", is_stale: nil)
        return Conversation(id: id, title: title, participants: [actor], participant_ids: ["u1"],
                            type: "direct", direct_kind: "user-user", owner_id: "user", creator_id: "user",
                            is_pinned: false, is_muted: false, unread_count: unread,
                            last_message_preview: nil, last_message_at: nil,
                            created_at: "2026-11-01T00:00:00Z", dissolved_at: dissolvedAt,
                            is_member: true, can_write: canWrite)
    }

    private func item(_ message: ChatMessage) -> TimelineItem { TimelineItem(type: "message", message: message) }

    private func attempt(_ conversationID: String, _ key: String) -> SendAttempt {
        SendAttempt(conversationID: conversationID, sourceMessageID: nil,
                    draft: PendingSend(key: key, content: "unsent", attachments: [], requestBody: Data("{}".utf8)))
    }

    private func message(_ n: Int, createdAt: String? = nil, conversation: String = "a",
                         extra: [String: Any] = [:]) throws -> ChatMessage {
        var payload: [String: Any] = ["id": "m\(n)", "conversation_id": conversation,
                                      "sender": ["type": "user", "id": "u1", "display_name": "U1"],
                                      "sender_user_id": "u1", "sender_type": "user",
                                      "content": "message \(n)", "attachments": [],
                                      "delivery_status": "completed",
                                      // Strictly increasing with `n`, so ordering assertions are
                                      // about the store, not about a wrapped clock.
                                      "created_at": createdAt ?? String(format: "2026-11-01T%02d:%02d:%02dZ", n / 3600, (n / 60) % 60, n % 60)]
        for (key, value) in extra { payload[key] = value }
        return try JSONDecoder().decode(ChatMessage.self, from: JSONSerialization.data(withJSONObject: payload))
    }
}
