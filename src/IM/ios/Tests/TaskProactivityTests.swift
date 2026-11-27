import XCTest
import GRDB
@testable import NanoIM

/// Verifies chat `task_cards` persistence, v7 SQLite migration backfill, offline card summary caching,
/// timeline reconciliation, and PA proactive-planning presentation helpers.
extension ChatRepositoryTests {
    func testMessageTaskCardsAndSummaryCacheSurviveReopenAndMigrationBackfill() async throws {
        let repo = try open()
        let context = try await repo.writeContext()
        _ = try await repo.applyConversation(conversation("a"), members: [], write: context)

        let cardRefs: [[String: String]] = [
            ["graph_id": "tg_kyoto", "node_id": "stage_hotel"],
            ["graph_id": "tg_kyoto", "node_id": "stage_train"]
        ]
        let cardMessage = try message(1, extra: ["content": "Here are two candidate steps:", "task_cards": cardRefs])
        let cardOnlyMessage = try message(2, extra: ["content": "", "task_cards": [["graph_id": "tg_solo", "node_id": "n1"]]])
        _ = try await repo.applyPage("a", items: [item(cardMessage), item(cardOnlyMessage)], write: context)

        let cachedSummary = try JSONDecoder().decode(
            TaskCardNodeSummary.self,
            from: Data(#"{"graph_id":"tg_kyoto","node_id":"stage_hotel","root_node_id":"root","revision":3,"title":"Shortlist Kyoto hotels","description":"Dates confirmed; compare 3 options on approval","mode":"explore","status":"proposed"}"#.utf8)
        )
        try await repo.cacheTaskCards([cachedSummary])
        let databaseURL = repo.location.databaseURL
        try await repo.close()

        // Reopen 1: message task_cards, card-only preview, and cached TaskCardNodeSummary survive restart.
        let reopened = try open()
        let timeline1 = try await reopened.timeline("a")
        XCTAssertEqual(timeline1.items.first?.message?.task_cards, [
            TaskCardRef(graph_id: "tg_kyoto", node_id: "stage_hotel"),
            TaskCardRef(graph_id: "tg_kyoto", node_id: "stage_train")
        ])
        let preview = try await reopened.conversation("a")?.last_message_preview
        XCTAssertEqual(preview, L("[任务卡片]", "[Task card]"))
        let restoredSummaries = try await reopened.cachedTaskCards([
            TaskCardRef(graph_id: "tg_kyoto", node_id: "stage_hotel")
        ])
        XCTAssertEqual(restoredSummaries["tg_kyoto:stage_hotel"]?.status, "proposed")
        XCTAssertEqual(restoredSummaries["tg_kyoto:stage_hotel"]?.description, "Dates confirmed; compare 3 options on approval")

        // A sparse message update omitting task_cards preserves stored task_cards_json.
        let fresh = try await reopened.writeContext()
        let sparseCorrection = try message(1, extra: ["content": "Updated intro text"])
        let afterSparse = try await reopened.applyPage("a", items: [item(sparseCorrection)], write: fresh)
        XCTAssertEqual(afterSparse.items.first?.message?.content, "Updated intro text")
        XCTAssertEqual(afterSparse.items.first?.message?.task_cards?.count, 2)
        try await reopened.close()

        // Simulate upgrading an older v6 SQLite database whose payload_json already contained task_cards.
        let queue = try DatabaseQueue(path: databaseURL.path)
        try await queue.write { db in
            try db.execute(sql: """
                ALTER TABLE messages DROP COLUMN task_cards_json;
                DROP TABLE task_card_cache;
                DELETE FROM grdb_migrations WHERE identifier='v7_message_task_cards';
                """)
        }
        try queue.close()

        let migrated = try open()
        let timelineAfterBackfill = try await migrated.timeline("a")
        XCTAssertEqual(timelineAfterBackfill.items.last?.message?.task_cards, [
            TaskCardRef(graph_id: "tg_solo", node_id: "n1")
        ])
        try await migrated.close()
    }

    func testTimelineMergeAndFeatureLabelsSupportProactivePlanning() throws {
        let withCards = try message(1, extra: [
            "content": "Initial",
            "task_cards": [["graph_id": "tg_1", "node_id": "n_1"]]
        ])
        let sparseUpdate = try message(1, extra: ["content": "Final streamed text"])
        let merged = TimelineMerge.merge(current: [item(withCards)], page: [item(sparseUpdate)], older: false, discarded: [])
        XCTAssertEqual(merged.first?.message?.content, "Final streamed text")
        XCTAssertEqual(merged.first?.message?.task_cards, [TaskCardRef(graph_id: "tg_1", node_id: "n_1")])

        let label = agentFeatureName("proactive_planning")
        XCTAssertTrue(label == "主动筹划" || label == "Proactive planning")
        XCTAssertNotNil(agentFeatureSubtitle("proactive_planning", personal: true))

        let proactiveFeature = AgentFeature(
            key: "proactive_planning",
            label_i18n: "agent.features.proactive_planning.label",
            help_i18n: "agent.features.proactive_planning.help",
            default_on: true,
            available: true,
            requires: .init(features: ["task_graph"], tools: ["task_graph"], skills: [])
        )
        var legacyDraft = AgentDraft()
        legacyDraft.tool_allowlist = ["read", "bash"]
        XCTAssertFalse(legacyDraft.isFeatureEnabled(proactiveFeature))
        legacyDraft.tool_allowlist = ["read", "task_graph"]
        XCTAssertTrue(legacyDraft.isFeatureEnabled(proactiveFeature))

        let focusJSON = Data(#"""
        {
          "needs_you": [],
          "stashed": [],
          "active": [],
          "goals": [],
          "completed": [{"graph_id":"tg_done","root_node_id":"n1","node_id":"n2","revision":4,"title":"Completed Substage","mode":"none","status":"done","conversation":{"id":"c1","title":"PA","visibility":"private","is_member":true,"can_write":true}}],
          "completed_count": 1,
          "counts": {"needs_you":0,"stashed":0,"active":0,"goals":0,"completed":1},
          "next_cursors": {"completed":"cursor-next"}
        }
        """#.utf8)
        let decodedFocus = try JSONDecoder().decode(TaskFocusResponse.self, from: focusJSON)
        XCTAssertEqual(decodedFocus.completed.count, 1)
        XCTAssertEqual(decodedFocus.completed.first?.node_id, "n2")
        XCTAssertEqual(decodedFocus.next_cursors.completed, "cursor-next")
    }
}
