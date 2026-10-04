import XCTest
@testable import NanoIM

final class TimelineTests: XCTestCase {
    func testOverlappingRecoveryPagesReplaceContentAndRespectDiscardedMessages() throws {
        let first = try item("one", content: "partial")
        let final = try item("one", content: "complete")
        let deleted = try item("discard", content: "provisional")
        let old = try item("older", content: "history")
        let merged = TimelineMerge.merge(current: [first, deleted], page: [final], older: false, discarded: ["discard"])
        let replay = TimelineMerge.merge(current: merged, page: [final], older: false, discarded: ["discard"])
        XCTAssertEqual(replay.map(\.id), ["one"])
        XCTAssertEqual(replay[0].message?.content, "complete")
        XCTAssertEqual(TimelineMerge.merge(current: replay, page: [old, final], older: true, discarded: []).map(\.id), ["older", "one"])
    }
    private func item(_ id: String, content: String) throws -> TimelineItem {
        let payload: [String: Any] = ["type":"message", "message":["id":id,"conversation_id":"chat","sender":["type":"agent","id":"agent"],"sender_user_id":"user","sender_type":"agent","content":content,"attachments":[],"delivery_status":"running","created_at":"2026-01-01"]]
        return try JSONDecoder().decode(TimelineItem.self, from: JSONSerialization.data(withJSONObject: payload))
    }
}
