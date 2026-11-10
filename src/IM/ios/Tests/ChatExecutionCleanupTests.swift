import XCTest
@testable import NanoIM

private actor CleanupWriteOnce {
    private var available = true
    func take() -> Bool {
        guard available else { return false }
        available = false
        return true
    }
}

/// The SQLite and in-memory projections must agree about execution generations.
extension ChatLocalFirstTests {
    func testDurableCleanupKeepsReadingAnchorAndCannotReappearOnOfflineRestart() async throws {
        let (store, stub) = try await makeStore()
        await seed(store, conversations: ["a"], messages: 1)
        let repo = try XCTUnwrap(store.repository)
        var old = try message(1, conversation: "a")
        old.thinking = [ChatThinking(seq: 1, text: "obsolete execution")]
        let context = try await repo.writeContext()
        _ = try await repo.applyPage("a", items: [TimelineItem(type: "message", message: old)], write: context)
        store.timelines["a"] = [TimelineItem(type: "message", message: old)]
        store.before["a"] = "old-cursor"
        store.recordReadingPosition("m1", in: "a")
        var current = try conversation("a")
        current.execution_cleanup_revision = 2
        await stub.setList(try listData(current))
        await stub.setMessages(try JSONEncoder().encode(MessagePage(items: [TimelineItem(type: "message", message: try message(2, conversation: "a"))], next_before_message_id: "m2", execution_cleanup_revision: 2)))
        await stub.setMessages(try JSONEncoder().encode(MessagePage(items: [TimelineItem(type: "message", message: try message(1, conversation: "a"))], execution_cleanup_revision: 2)), before: "m2")

        await store.loadConversations()
        XCTAssertNil(store.timelines["a"])
        let invalidated = try await repo.timeline("a")
        XCTAssertTrue(invalidated.items.isEmpty)
        await store.loadChat("a")
        XCTAssertEqual(store.timelines["a"]?.map(\.id), ["m1", "m2"])
        XCTAssertNil(store.timelines["a"]?.first?.message?.thinking)
        XCTAssertEqual(store.restoreReadingPositions["a"], "m1")
        store.resetProjection()
        await store.loadSeed()
        await stub.failMessages(URLError(.notConnectedToInternet))
        await store.loadChat("a")
        XCTAssertEqual(store.timelines["a"]?.map(\.id), ["m1", "m2"])
        XCTAssertNil(store.timelines["a"]?.first?.message?.thinking)
        store.resetProjection()
        try await repo.close()
    }

    func testHeldLatestPageCannotRestoreExecutionAfterCleanupEvent() async throws {
        try await assertHeldPageRejected(older: false)
    }

    func testHeldOlderPageCannotRestoreExecutionAfterCleanupEvent() async throws {
        try await assertHeldPageRejected(older: true)
    }

    private func assertHeldPageRejected(older: Bool) async throws {
        let (store, stub) = try await makeStore()
        await seed(store, conversations: ["a"], messages: 1)
        let repo = try XCTUnwrap(store.repository)
        var obsolete = try message(2, conversation: "a")
        obsolete.thinking = [ChatThinking(seq: 1, text: "must not return")]
        let body = try JSONEncoder().encode(MessagePage(items: [TimelineItem(type: "message", message: obsolete)]))
        await stub.hold("/im/v1/conversations/a/messages", body: body)
        let task = Task { await store.loadChat("a", older: older) }
        await stub.waitUntilHeld()
        let event = try JSONDecoder().decode(UserEvent.self, from: Data(#"{"op":"event","event_type":"conversation.execution_cleanup","event_id":5,"data":{"conversation_id":"a","execution_cleanup_revision":2}}"#.utf8))
        await store.consume(event)
        await stub.release()
        await task.value
        XCTAssertTrue(store.timelines["a"]?.isEmpty ?? true)
        let page = try await repo.timeline("a")
        XCTAssertTrue(page.items.isEmpty, "a rejected response must not write SQL before its RAM check")
        XCTAssertEqual(page.executionCleanupRevision, 2)
        store.resetProjection()
        try await repo.close()
    }

    func testLateOtherConversationCannotUndoKnownDeletedActorInSQLOrVisibleDetail() async throws {
        let (store, stub) = try await makeStore()
        await seed(store, conversations: ["a", "b"], messages: 0)
        let repo = try XCTUnwrap(store.repository)
        var known = try conversation("a")
        known.participants = [ActorRef(type: "agent", id: "deleted-agent", is_deleted: true)]
        var late = try conversation("b")
        late.participants = [ActorRef(type: "agent", id: "deleted-agent", is_deleted: false)]
        let context = try await repo.writeContext()
        _ = try await repo.applyConversation(known, members: known.participants, write: context)
        await store.loadSeed()
        await stub.setDetail(try JSONEncoder().encode(late))
        await store.inspectConversation("b")
        XCTAssertEqual(store.inspectedConversation?.participants.first?.is_deleted, true)
        XCTAssertEqual(store.conversations.first { $0.id == "b" }?.participants.first?.is_deleted, true)
        let restored = try await repo.conversation("a")
        XCTAssertEqual(restored?.participants.first?.is_deleted, true)
        store.resetProjection()
        try await repo.close()
    }

    func testCleanupEventRetriesSupersededContextWithoutDegradingHealthyStorage() async throws {
        let (store, _) = try await makeStore()
        await seed(store, conversations: ["a"], messages: 1)
        let repo = try XCTUnwrap(store.repository)
        let chat = try conversation("a")
        let once = CleanupWriteOnce()
        await store.consume(try cleanupEvent()) { repository, event, context in
            if await once.take() {
                _ = try await repository.applySnapshot([chat], maxEventID: 5, snapshotSeq: context.snapshotSeq + 1, write: context)
            }
            return try await repository.applyEvent(event, write: context)
        }
        XCTAssertTrue(store.repository === repo, "normal stale qualification is not a storage failure")
        let page = try await repo.timeline("a")
        XCTAssertTrue(page.items.isEmpty)
        XCTAssertEqual(page.executionCleanupRevision, 2)
        store.resetProjection()
        try await repo.close()
    }

    func testOldCleanupFailureCannotDegradeResetOwner() async throws {
        let (store, _) = try await makeStore()
        await seed(store, conversations: ["a"], messages: 1)
        let repo = try XCTUnwrap(store.repository)
        await store.consume(try cleanupEvent()) { _, _, _ in
            await MainActor.run { store.resetProjection() }
            throw ChatRepositoryError.databaseUnavailable("old owner's controlled IO failure")
        }
        XCTAssertTrue(store.repository === repo, "a late failure must not publish into a new owner generation")
        try await repo.close()
    }

    func testListDeletionImmediatelyNormalizesAlreadyInspectedOtherChat() async throws {
        let (store, stub) = try await makeStore()
        await seed(store, conversations: ["a", "b"], messages: 0)
        let repo = try XCTUnwrap(store.repository)
        var opened = try conversation("b")
        opened.participants = [ActorRef(type: "agent", id: "deleted-agent", is_deleted: false)]
        await stub.setDetail(try JSONEncoder().encode(opened))
        await store.inspectConversation("b")
        var changed = try conversation("a")
        changed.participants = [ActorRef(type: "agent", id: "deleted-agent", is_deleted: true)]
        await stub.setList(try listData(changed))
        await store.loadConversations()
        XCTAssertEqual(store.inspectedConversation?.participants.first?.is_deleted, true)
        XCTAssertEqual(store.conversations.first { $0.id == "b" }?.participants.first?.is_deleted, true)
        let persisted = try await repo.conversation("b")
        XCTAssertEqual(persisted?.participants.first?.is_deleted, true)
        store.resetProjection()
        try await repo.close()
    }

    func testDegradedDeletionKnowledgeOutlivesProjectionAndResetsWithOwner() async throws {
        let (store, stub) = try await makeStore()
        let repo = try XCTUnwrap(store.repository)
        store.storage = .degraded(reason: "controlled unavailable partition")
        var known = try conversation("a")
        known.participants = [ActorRef(type: "agent", id: "deleted-agent", is_deleted: true)]
        await stub.setList(try listData(known))
        await store.loadConversations()
        await stub.setList(Data(#"{"items":[]}"#.utf8))
        await store.loadConversations()
        var late = try conversation("b")
        late.participants = [ActorRef(type: "agent", id: "deleted-agent", is_deleted: false)]
        await stub.setList(try listData(late))
        await store.loadConversations()
        XCTAssertEqual(store.conversations.first?.participants.first?.is_deleted, true)
        store.resetProjection()
        await store.loadConversations()
        XCTAssertEqual(store.conversations.first?.participants.first?.is_deleted, false, "a different owner must not inherit another owner's deletion facts")
        store.resetProjection()
        try await repo.close()
    }

    func testHeldPreDiscardListAndDetailCannotPublishInReadyOrDegradedStorage() async throws {
        var eventID = 100
        for degraded in [false, true] {
            for isList in [false, true] {
                eventID += 1
                let (store, stub) = try await makeStore()
                await seed(store, conversations: ["a"], messages: 2)
                let repo = try XCTUnwrap(store.repository)
                if degraded { store.storage = .degraded(reason: "controlled test") }
                var obsolete = try conversation("a")
                obsolete.last_message_preview = "discarded server preview"
                let body = isList ? try listData(obsolete) : try JSONEncoder().encode(obsolete)
                await stub.hold(isList ? "/im/v1/conversations" : "/im/v1/conversations/a", body: body)
                let request = Task { if isList { await store.loadConversations() } else { await store.inspectConversation("a") } }
                await stub.waitUntilHeld()
                // makeStore shares this test's partition; each accepted event must advance
                // its durable cursor rather than reuse a previously consumed event ID.
                let event = try JSONDecoder().decode(UserEvent.self, from: JSONSerialization.data(withJSONObject: [
                    "op": "event", "event_id": eventID, "event_type": "message.discarded",
                    "data": ["conversation_id": "a", "message_id": "m2"]
                ]))
                await store.consume(event)
                await stub.release()
                await request.value
                XCTAssertNotEqual(store.conversations.first?.last_message_preview, "discarded server preview")
                XCTAssertNotEqual(store.inspectedConversation?.last_message_preview, "discarded server preview")
                store.resetProjection()
                try await repo.close()
            }
        }
    }

    private func cleanupEvent() throws -> UserEvent {
        try JSONDecoder().decode(UserEvent.self, from: Data(#"{"op":"event","event_type":"conversation.execution_cleanup","event_id":5,"data":{"conversation_id":"a","execution_cleanup_revision":2}}"#.utf8))
    }

    private func listData(_ chat: Conversation) throws -> Data {
        let row = try JSONSerialization.jsonObject(with: JSONEncoder().encode(chat))
        return try JSONSerialization.data(withJSONObject: ["items": [row]])
    }
}
