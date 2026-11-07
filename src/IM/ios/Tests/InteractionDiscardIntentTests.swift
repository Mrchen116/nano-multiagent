import XCTest
@testable import NanoIM

final class InteractionDiscardIntentTests: XCTestCase {
    func testOlderConfirmationPreservesNewerIntentAndConfirmedIntentStopsRetrying() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        let disk = SendAttemptStore(directory: directory), origin = URL(string: "https://draft.example.test")!
        try disk.updateDraftDiscard("chat", through: "2026-11-01T10:00:00.001Z", confirmed: false, origin: origin, userID: "viewer")
        try disk.updateDraftDiscard("chat", through: "2026-11-01T10:00:00.002Z", confirmed: false, origin: origin, userID: "viewer")
        try disk.updateDraftDiscard("chat", through: "2026-11-01T10:00:00.001Z", confirmed: true, origin: origin, userID: "viewer")
        XCTAssertEqual(try disk.loadDraftDiscards(origin: origin, userID: "viewer")["chat"], "2026-11-01T10:00:00.002Z")
        try disk.updateDraftDiscard("chat", through: "2026-11-01T10:00:00.002Z", confirmed: true, origin: origin, userID: "viewer")
        XCTAssertTrue(try disk.loadDraftDiscards(origin: origin, userID: "viewer").isEmpty)
    }

    func testPendingDiscardsAreCappedOwnerIsolatedAndRemovedWithConversationOrAccount() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        let disk = SendAttemptStore(directory: directory), origin = URL(string: "https://draft.example.test")!
        for index in 0..<130 {
            try disk.updateDraftDiscard("chat-\(index)", through: String(format: "2026-11-01T10:00:00.%03dZ", index), confirmed: false, origin: origin, userID: "viewer")
        }
        let pending = try disk.loadDraftDiscards(origin: origin, userID: "viewer")
        XCTAssertEqual(pending.count, 128); XCTAssertNil(pending["chat-0"]); XCTAssertNil(pending["chat-1"])
        XCTAssertTrue(try disk.loadDraftDiscards(origin: origin, userID: "other").isEmpty)
        XCTAssertTrue(try disk.loadDraftDiscards(origin: URL(string: "https://other.example.test")!, userID: "viewer").isEmpty)
        XCTAssertTrue(try disk.load(origin: origin, userID: "viewer").isEmpty, "Discard metadata is not a frozen send attempt")
        try disk.remove(origin: origin, userID: "viewer", conversationID: "chat-129")
        XCTAssertNil(try disk.loadDraftDiscards(origin: origin, userID: "viewer")["chat-129"])
        try disk.remove(origin: origin, userID: "viewer")
        XCTAssertTrue(try disk.loadDraftDiscards(origin: origin, userID: "viewer").isEmpty)
    }
}
