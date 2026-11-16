import XCTest
@testable import NanoIM

/// Business-action recovery belongs to the action, not a successful background list read.
extension ChatLocalFirstTests {
    func testSuccessfulPreferenceRetryConsumesItsFailureWithoutClearingAnotherBusinessError() async throws {
        for key in ["is_pinned", "is_muted"] {
            let (store, stub) = try await makeStore()
            await seed(store, conversations: ["a"], messages: 0)
            let row = try JSONEncoder().encode(try conversation("a"))
            await stub.setDetail(nil, status: 503)
            await store.updateConversationPreference("a", key: key, value: true)
            XCTAssertNotNil(store.listError)
            await stub.setDetail(row)
            await store.retryListError()
            XCTAssertNil(store.listError, "The notice must retry and consume this preference's own failure")

            await stub.setDetail(nil, status: 503)
            await store.updateConversationPreference("a", key: key, value: true)
            let otherKey = key == "is_pinned" ? "is_muted" : "is_pinned"
            await stub.setDetail(row)
            await store.updateConversationPreference("a", key: otherKey, value: true)
            XCTAssertNotNil(store.listError, "A successful Mute is not recovery of a failed Pin, or vice versa")
            await store.updateConversationPreference("a", key: key, value: true)
            XCTAssertNil(store.listError)

            await stub.hold("/im/v1/conversations/a", body: row)
            let inFlight = Task { await store.updateConversationPreference("a", key: key, value: false) }
            await stub.waitUntilHeld()
            store.listError = "unrelated local draft could not be saved"
            await stub.release()
            await inFlight.value
            XCTAssertEqual(store.listError, "unrelated local draft could not be saved", "An older action completing must not consume another operation's failure")
            store.resetProjection()
            try await store.repository?.close()
        }
    }
}
