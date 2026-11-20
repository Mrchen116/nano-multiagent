import Foundation
import Testing
@testable import NanoIM

struct AgentWorkParityTests {
    private func decode<T: Decodable>(_ json: String) throws -> T {
        try JSONDecoder().decode(T.self, from: Data(json.utf8))
    }

    @Test func combinedHistoryUsesServerSequenceAcrossMainAndMaintenance() throws {
        func page(_ session: String, seq: Int, next: Int?) throws -> AgentWorkPage {
            let nextField = next.map { ",\"next_turn_seq\":\($0),\"next_turn_id\":\"reused\"" } ?? ""
            return try decode("""
            {"timeline":"combined","turns":[{"session_id":"\(session)","turn_id":"reused","seq":\(seq),"status":"completed","items":[]}]\(nextField)}
            """)
        }
        var history = AgentWorkHistory()
        history.merge(try page("main", seq: 50, next: 42))
        history.merge(try page("cron", seq: 38, next: nil))
        #expect(history.hasGap(after: history.turns[0], before: history.turns[1]))
        history.merge(try page("maintenance", seq: 42, next: 38), after: history.turns[0])
        #expect(history.turns.map(\.session_id) == ["main", "maintenance", "cron"])
        #expect(!history.hasGap(after: history.turns[0], before: history.turns[1]))
        #expect(!history.hasGap(after: history.turns[1], before: history.turns[2]))
    }

    @Test func focusPreservesTheExactTurnAndItsUnloadedNeighbors() throws {
        let page: AgentWorkPage = try decode(#"{"turns":[{"session_id":"root","turn_id":"latest","seq":100,"status":"running","items":[]}],"next_turn_id":"middle"}"#)
        let focus: AgentWorkFocus = try decode(#"{"turn":{"session_id":"root","turn_id":"delivered","seq":3,"status":"completed","items":[]},"newer_turn_id":"old","older_turn_id":"older"}"#)
        var history = AgentWorkHistory()
        history.merge(page)
        history.merge(focus)
        history.merge(page)
        #expect(history.turns.map(\.turn_id) == ["latest", "delivered"])
        #expect(history.hasGap(after: history.turns[0], before: history.turns[1]))
        #expect(history.hasEarlier(after: history.turns[1]))
    }

    @Test func knownMainActivityDoesNotInventChildCountsDuringRecovery() throws {
        let activity: AgentActivityPage = try decode(#"{"revision":2,"node_connection_state":"online","record_sync_state":"catching_up","main_execution":"running","latest_tool":{"name":"search","status":"running"},"running_count":null,"waiting_permission_count":null,"sessions":[],"next_cursor":null}"#)
        #expect(activity.main_execution == "running")
        #expect(activity.latest_tool?.name == "search")
        #expect(!activity.confirmedChildren)
    }

    @Test func onlyConfirmedChatDeliveriesCanPreviewAnOriginalMessage() throws {
        func delivery(_ payload: String) throws -> WorkDelivery? {
            let item: AgentWorkItem = try decode("""
            {"item_id":"call","seq":1,"kind":"tool","payload":\(payload)}
            """)
            return WorkDelivery(item)
        }
        #expect(try delivery(#"{"name":"send_message","status":"completed","input":{"text":"draft"}}"#) == nil)
        #expect(try delivery(#"{"work_facts":[{"type":"draft_withheld","target":"chat","message_id":"draft"}]}"#) == nil)
        #expect(try delivery(#"{"name":"send_message","detail":{"status":"sent","target":"chat","message_id":"sent"}}"#)?.message == "sent")
        #expect(try delivery(#"{"work_facts":[{"type":"message_sent","conversation_id":"chat","message_id":"sent"}]}"#)?.conversation == "chat")
    }

    @Test func delegationKeepsUnreportedUsageDistinctFromZero() throws {
        let page: AgentDelegationPage = try decode(#"{"from":"2026-11-18","until":"2026-11-21","revision":5,"node_connection_state":"offline","record_sync_state":"unknown","main_session_id":"main","nodes":[{"session_id":"child","parent_session_id":"main","status":"completed","usage":{"total_tokens":null,"reported_turns":0,"missing_turns":1}},{"session_id":"main","status":"idle","ancestor_only":true,"usage":{"total_tokens":0,"reported_turns":1,"missing_turns":1}},{"session_id":"starting","scope":"worker","status":"starting","runtime":"codex"}],"next_cursor":"child"}"#)
        #expect(page.nodes[0].usage?.total_tokens == nil)
        #expect(page.nodes[0].parent_session_id == "main")
        #expect(page.nodes[1].usage?.total_tokens == 0)
        #expect(page.nodes[1].usage?.turns == 2)
        #expect(page.nodes[2].usage == nil)
        #expect(!page.nodes[2].canOpenRecords)
        #expect(page.next_cursor == "child")
    }
}
