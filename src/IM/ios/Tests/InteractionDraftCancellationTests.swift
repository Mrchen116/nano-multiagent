import XCTest
@testable import NanoIM

extension InteractionDraftLifecycleTests {
    func testImmediateDepartureRestoresStartupOwnershipBeforeDiscardWithoutForeground() async throws {
        let (runtime, transport) = try await fixture()
        try await edit(runtime, "thu"); _ = await runtime.flush()
        let reopened = ChatStore(client: runtime.client, user: runtime.chat.user)
        XCTAssertTrue(reopened.interactionDrafts.watermarks.isEmpty)
        reopened.selectedID = "chat"; reopened.selectedID = "other"
        await reopened.interactionDrafts.awaitPendingDiscard("chat")
        let through = await transport.discards
        XCTAssertEqual(through, ["2026-11-01T10:00:00.001Z"], "The leave barrier must restore ownership even before a foreground recovery pass")
        reopened.resetProjection(); runtime.chat.resetProjection()
    }

    func testClearingStoreAlsoFencesExplicitSubmissionWaitingForDraftFlush() async throws {
        let (runtime, transport) = try await fixture()
        await transport.gateNextSave(timestamp: "2026-11-01T10:00:00.002Z")
        try await edit(runtime, "thu")
        let submission = Task {
            try await runtime.chat.submitInteraction("chat", input: InteractionReplyInput(source_message_id: runtime.message.id, state: runtime.state), key: "cleared-attempt")
        }
        let started = await transport.waitForGatedSave(); XCTAssertTrue(started)
        runtime.chat.resetProjection()
        await transport.releaseSave()
        do { _ = try await submission.value; XCTFail("Cleared interaction submission resumed") }
        catch { XCTAssertTrue(error is CancellationError) }
        let posts = await transport.posts
        XCTAssertTrue(posts.isEmpty)
        XCTAssertTrue(runtime.chat.interactionPending.isEmpty)
        XCTAssertTrue(try runtime.client.session.sendAttempts.load(origin: runtime.client.baseURL, userID: "viewer").isEmpty)
    }
}
