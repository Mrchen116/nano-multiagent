import XCTest
@testable import NanoIM

extension InteractionDraftLifecycleTests {
    func testClearingStoreAlsoFencesExplicitSubmissionWaitingForDraftFlush() async throws {
        let (runtime, transport) = try await fixture()
        await transport.gateNextSave(timestamp: "2026-11-01T10:00:00.002Z")
        try await edit(runtime, "thu")
        let submission = Task {
            try await runtime.chat.submitInteraction("chat", input: InteractionReplyInput(source_message_id: runtime.message.id, state: runtime.state), key: "cleared-attempt")
        }
        let started = await transport.waitForGatedSave(); XCTAssertTrue(started)
        runtime.chat.clear()
        await transport.releaseSave()
        do { _ = try await submission.value; XCTFail("Cleared interaction submission resumed") }
        catch { XCTAssertTrue(error is CancellationError) }
        let posts = await transport.posts
        XCTAssertTrue(posts.isEmpty)
        XCTAssertTrue(runtime.chat.interactionPending.isEmpty)
        XCTAssertTrue(try runtime.client.session.sendAttempts.load(origin: runtime.client.baseURL, userID: "viewer").isEmpty)
    }
}
