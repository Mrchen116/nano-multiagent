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
    func testLateConfigurationBoundaryPrecedesItsAlreadyCachedRequest() throws {
        let firstReply = try item("m1-reply", content: "42", createdAt: "2026-10-05T07:40:00Z")
        let secondRequest = try item("m2-request", content: "19 + 23", createdAt: "2026-10-05T07:41:00Z")
        let secondReply = try item("m2-reply", content: "42", createdAt: "2026-10-05T07:42:05Z")
        let boundary = TimelineItem(type: "agent_config_changed", boundaryID: "config-v10", before_message_id: secondRequest.id, applied_at: "2026-10-05T07:42:04Z")
        let merged = TimelineMerge.merge(current: [firstReply, secondRequest], page: [firstReply, boundary, secondRequest, secondReply], older: false, discarded: [])
        XCTAssertEqual(merged.map(\.id), ["m1-reply", "config-v10", "m2-request", "m2-reply"])
        let replay = TimelineMerge.merge(current: merged, page: [boundary, secondRequest, secondReply], older: false, discarded: [])
        XCTAssertEqual(replay.map(\.id), merged.map(\.id))
    }
    private func item(_ id: String, content: String, createdAt: String = "2026-01-01") throws -> TimelineItem {
        let payload: [String: Any] = ["type":"message", "message":["id":id,"conversation_id":"chat","sender":["type":"agent","id":"agent"],"sender_user_id":"user","sender_type":"agent","content":content,"attachments":[],"delivery_status":"running","created_at":createdAt]]
        return try JSONDecoder().decode(TimelineItem.self, from: JSONSerialization.data(withJSONObject: payload))
    }
}
