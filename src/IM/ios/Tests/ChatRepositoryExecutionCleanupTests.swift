import XCTest
import GRDB
@testable import NanoIM

/// Durable projection compatibility with execution cleanup and list-preview DTOs.
extension ChatRepositoryTests {
    func testExecutionCleanupSurvivesReopenWithoutLosingDraftOrPending() async throws {
        let repo = try open()
        let context = try await repo.writeContext()
        _ = try await repo.applyConversation(conversation("a"), members: [], write: context)
        _ = try await repo.applyPage("a", items: [item(try message(1, extra: ["thinking": [["seq": 1, "text": "obsolete execution"]]]))], write: context)
        try await repo.setDraft("a", body: "newer ordinary draft")
        try await repo.upsertPending(attempt("a", "pending"), write: context)
        let event = try JSONDecoder().decode(UserEvent.self, from: Data(#"{"op":"event","event_type":"conversation.execution_cleanup","event_id":5,"data":{"conversation_id":"a","execution_cleanup_revision":2}}"#.utf8))
        _ = try await repo.applyEvent(event, write: context)
        try await repo.close()
        let reopened = try open()
        let page = try await reopened.timeline("a")
        XCTAssertTrue(page.items.isEmpty, "old execution must not reappear on offline restart")
        let draft = try await reopened.draft("a")
        let pending = try await reopened.pendingAttempts()
        XCTAssertEqual(draft, "newer ordinary draft")
        XCTAssertEqual(pending.map { $0.draft.key }, ["pending"])
        let fresh = try await reopened.writeContext()
        do {
            _ = try await reopened.applyPage("a", items: [item(try message(1))], write: fresh)
            XCTFail("a revision-zero page must not revive the old execution generation")
        } catch ChatRepositoryError.staleWrite { }
        let recovered = try await reopened.applyPage("a", items: [item(try message(1))], executionCleanupRevision: 2, write: fresh)
        XCTAssertEqual(recovered.items.first?.id, "m1", "cleanup must not discard ordinary IM message identities")
        XCTAssertNil(recovered.items.first?.message?.thinking)
        XCTAssertEqual(recovered.items.first?.message?.content, "message 1")
        XCTAssertEqual(recovered.executionCleanupRevision, 2)
        try await reopened.close()
    }

    func testConversationPreviewFieldsRoundTripAcrossReopen() async throws {
        let repo = try open()
        var chat = conversation("a")
        chat.last_message_sender_name = "Casey"
        chat.last_message_card = ChatCardPreview(title: "Review choices")
        chat.participants[0].is_deleted = true
        chat.execution_cleanup_revision = 2
        let context = try await repo.writeContext()
        _ = try await repo.applyConversation(chat, members: chat.participants, write: context)
        try await repo.close()
        let reopened = try open()
        let restored = try await reopened.conversation("a")
        XCTAssertEqual(restored?.last_message_sender_name, "Casey")
        XCTAssertEqual(restored?.last_message_card?.title, "Review choices")
        XCTAssertEqual(restored?.participants.first?.is_deleted, true)
        XCTAssertEqual(restored?.execution_cleanup_revision, 2)
        let fresh = try await reopened.writeContext()
        _ = try await reopened.applyPage("a", items: [item(try message(1))], executionCleanupRevision: 2, write: fresh)
        let corrected = try await reopened.conversation("a")
        XCTAssertNil(corrected?.last_message_card, "a plain latest message must not retain the previous card title")
        XCTAssertEqual(corrected?.last_message_sender_name, "U1")
        XCTAssertEqual(corrected?.last_message_preview, "message 1")
        try await reopened.close()
    }

    func testSnapshotMapListAndDetailShareMonotonicCleanupFence() async throws {
        let repo = try open()
        var context = try await repo.writeContext()
        _ = try await repo.applyConversation(conversation("a"), members: [], write: context)
        _ = try await repo.applyPage("a", items: [item(try message(1))], write: context)
        _ = try await repo.applySnapshot([conversation("a")], maxEventID: 2, snapshotSeq: context.snapshotSeq + 1,
                                         executionCleanupRevisions: ["a": 2], write: context)
        var page = try await repo.timeline("a")
        XCTAssertTrue(page.items.isEmpty)
        XCTAssertEqual(page.executionCleanupRevision, 2)
        context = try await repo.writeContext()
        _ = try await repo.applyPage("a", items: [item(try message(1))], executionCleanupRevision: 2, write: context)
        for revision in [3, 4] {
            var chat = conversation("a")
            chat.execution_cleanup_revision = revision
            if revision == 3 { _ = try await repo.applyConversationList([chat], write: context) }
            else { _ = try await repo.applyConversation(chat, members: chat.participants, write: context) }
            page = try await repo.timeline("a")
            XCTAssertTrue(page.items.isEmpty)
            XCTAssertEqual(page.executionCleanupRevision, revision)
            _ = try await repo.applyPage("a", items: [item(try message(1))], executionCleanupRevision: revision, write: context)
        }
        let older = try JSONDecoder().decode(UserEvent.self, from: Data(#"{"op":"event","event_type":"conversation.execution_cleanup","data":{"conversation_id":"a","execution_cleanup_revision":2}}"#.utf8))
        _ = try await repo.applyEvent(older, write: context)
        let retained = try await repo.timeline("a")
        XCTAssertEqual(retained.items.map(\.id), ["m1"], "older or duplicate cleanup is idempotent")
        XCTAssertEqual(retained.executionCleanupRevision, 4)
        try await repo.close()
    }

    func testOlderOrAmbiguousMessageWindowCannotReplaceLatestCardProjection() async throws {
        let repo = try open()
        var chat = conversation("a")
        chat.last_message_at = "2026-11-01T00:00:03Z"
        chat.last_message_sender_name = "Latest sender"
        chat.last_message_card = ChatCardPreview(title: "Latest review")
        let context = try await repo.writeContext()
        _ = try await repo.applyConversation(chat, members: chat.participants, write: context)
        for n in [1, 3] {
            _ = try await repo.applyPage("a", items: [item(try message(n))], write: context)
            let retained = try await repo.conversation("a")
            XCTAssertEqual(retained?.last_message_at, chat.last_message_at)
            XCTAssertEqual(retained?.last_message_sender_name, "Latest sender")
            XCTAssertEqual(retained?.last_message_card?.title, "Latest review")
        }
        _ = try await repo.applyPage("a", items: [item(try message(4))], write: context)
        let latest = try await repo.conversation("a")
        XCTAssertEqual(latest?.last_message_preview, "message 4")
        XCTAssertEqual(latest?.last_message_sender_name, "U1")
        XCTAssertNil(latest?.last_message_card)
        try await repo.close()
    }

    func testDiscardLatestRebuildsPreviewAndSortFromRemainingMessageAcrossReopen() async throws {
        let repo = try open()
        let context = try await repo.writeContext()
        _ = try await repo.applyConversation(conversation("a"), members: [], write: context)
        let first = try message(1, extra: ["content": "", "interactive": ["format": "openui", "catalog_version": "1", "source": "agent", "read_only": true]])
        _ = try await repo.applyPage("a", items: [item(first), item(try message(2))], write: context)
        _ = try await repo.applyEvent(discardEvent("m2"), write: context)
        let databaseURL = repo.location.databaseURL
        try await repo.close()
        let reopened = try open()
        let restored = try await reopened.conversation("a")
        XCTAssertNil(restored?.last_message_preview)
        XCTAssertNotNil(restored?.last_message_card)
        XCTAssertEqual(restored?.last_message_sender_name, "U1")
        XCTAssertEqual(restored?.last_message_at, first.created_at)
        let queue = try DatabaseQueue(path: databaseURL.path)
        let sortAt = try await queue.read { try String.fetchOne($0, sql: "SELECT sort_at FROM conversations WHERE id='a'") }
        XCTAssertEqual(sortAt, first.created_at)
        try queue.close()
        try await reopened.close()
    }

    func testDiscardNonLatestRetainsQualifiedPreview() async throws {
        let repo = try open()
        let context = try await repo.writeContext()
        _ = try await repo.applyConversation(conversation("a"), members: [], write: context)
        _ = try await repo.applyPage("a", items: [item(try message(1)), item(try message(2))], write: context)
        _ = try await repo.applyEvent(discardEvent("m1"), write: context)
        let retained = try await repo.conversation("a")
        XCTAssertEqual(retained?.last_message_preview, "message 2")
        XCTAssertEqual(retained?.last_message_at, try message(2).created_at)
        try await repo.close()
    }

    func testDiscardWithUnknownServerPreviewClearsRatherThanPromotesOlderWindow() async throws {
        let repo = try open()
        let context = try await repo.writeContext()
        var chat = conversation("a")
        chat.last_message_preview = "message 2"
        chat.last_message_at = try message(2).created_at
        chat.last_message_sender_name = "Server sender"
        _ = try await repo.applyConversation(chat, members: [], write: context)
        _ = try await repo.applyPage("a", items: [item(try message(1))], write: context)
        _ = try await repo.applyEvent(discardEvent("m2"), write: context)
        // A later older-window fetch must not accidentally qualify the cleared preview.
        let current = try await repo.writeContext()
        _ = try await repo.applyPage("a", items: [item(try message(1))], write: current)
        let cleared = try await repo.conversation("a")
        XCTAssertNil(cleared?.last_message_preview)
        XCTAssertNil(cleared?.last_message_at)
        XCTAssertNil(cleared?.last_message_sender_name)
        _ = try await repo.applyConversation(conversation("a"), members: [], write: current)
        _ = try await repo.applyPage("a", items: [item(try message(3))], write: current)
        let recovered = try await repo.conversation("a")
        XCTAssertEqual(recovered?.last_message_preview, "message 3", "a fresh server projection restores ordinary page qualification")
        try await repo.close()
    }

    func testPreDiscardListAndDetailContextsCannotRestoreInvalidatedPreview() async throws {
        let repo = try open()
        let context = try await repo.writeContext()
        var old = conversation("a")
        old.last_message_preview = "discarded server preview"
        old.last_message_at = try message(2).created_at
        _ = try await repo.applyConversation(old, members: [], write: context)
        _ = try await repo.applyPage("a", items: [item(try message(1))], write: context)
        _ = try await repo.applyEvent(discardEvent("m2"), write: context)
        for source in ["list", "detail", "snapshot"] {
            do {
                if source == "list" { _ = try await repo.applyConversationList([old], write: context) }
                else if source == "detail" { _ = try await repo.applyConversation(old, members: [], write: context) }
                else { _ = try await repo.applySnapshot([old], maxEventID: 0, snapshotSeq: context.snapshotSeq + 1, write: context) }
                XCTFail("a list/detail/snapshot started before discard cannot restore its preview")
            } catch ChatRepositoryError.staleWrite { }
        }
        let retained = try await repo.conversation("a")
        XCTAssertNil(retained?.last_message_preview)
        let current = try await repo.writeContext()
        var fresh = conversation("a")
        fresh.last_message_preview = "current server preview"
        _ = try await repo.applySnapshot([fresh], maxEventID: 20, snapshotSeq: current.snapshotSeq + 1, write: current)
        let corrected = try await repo.conversation("a")
        XCTAssertEqual(corrected?.last_message_preview, "current server preview")
        try await repo.close()
    }

    private func discardEvent(_ messageID: String) throws -> UserEvent {
        let body: [String: Any] = ["op": "event", "event_type": "message.discarded", "data": ["conversation_id": "a", "message_id": messageID]]
        return try JSONDecoder().decode(UserEvent.self, from: JSONSerialization.data(withJSONObject: body))
    }

    func testPreviewMigrationPreservesExistingV2DraftPendingAndMessages() async throws {
        let repo = try open()
        let context = try await repo.writeContext()
        _ = try await repo.applyConversation(conversation("a"), members: [], write: context)
        _ = try await repo.applyPage("a", items: [item(try message(1))], write: context)
        try await repo.setDraft("a", body: "existing v2 draft")
        try await repo.upsertPending(attempt("a", "v2-pending"), write: context)
        let databaseURL = repo.location.databaseURL
        try await repo.close()
        // Model an existing v2 partition, not a fresh database on every test launch.
        let queue = try DatabaseQueue(path: databaseURL.path)
        try await queue.write { db in
            try db.execute(sql: """
                ALTER TABLE conversations DROP COLUMN last_message_sender_name;
                ALTER TABLE conversations DROP COLUMN last_message_card_json;
                ALTER TABLE actors DROP COLUMN is_deleted;
                DELETE FROM grdb_migrations WHERE identifier='v3_execution_cleanup_and_previews';
                """)
        }
        try queue.close()
        let reopened = try open()
        let draft = try await reopened.draft("a")
        let pending = try await reopened.pendingAttempts()
        let page = try await reopened.timeline("a")
        XCTAssertEqual(draft, "existing v2 draft")
        XCTAssertEqual(pending.map { $0.draft.key }, ["v2-pending"])
        XCTAssertEqual(page.items.first?.message?.content, "message 1")
        try await reopened.close()
    }
}
