import Foundation
import Testing
@testable import NanoIM

struct TaskContractsTests {
    @Test func sevenStatesKeepWaitingOngoingAndClosedDistinctFromCompletion() throws {
        #expect(taskStatus("in_review") != "in_review")
        #expect(taskStatus("closed") != "closed")
        #expect(taskGroupContains("todo", status: "paused"))
        #expect(taskGroupContains("doing", status: "waiting"))
        #expect(taskStatus("waiting") != "waiting")
        #expect(!taskGroupContains("done", status: "closed"))
        let graph = try fixture()
        let root = try #require(graph.nodes.first)
        #expect(root.status == "waiting")
        #expect(root.wait?.reason == "Await approval, then resume purchase")
        #expect(root.wait_health?.state == "unknown")
        let patch = TaskDraft(node: root).operations(node: root, parentID: nil)[0]["patch"]
        #expect(patch["status"] == .string("waiting"))
        #expect(patch["wait"] == .null)
        #expect(root.direct_counts?.done == 1)
        #expect(root.direct_counts?.closed == 1)
        #expect(root.direct_counts?.total == 3)
        #expect(graph.conversation.can_write == false)
        #expect(root.can_edit == false)
        #expect(root.created_by?.id == "creator")
        #expect(root.assignee?.type == "agent")
    }

    @Test func editingAndUnassigningUsesMutationOperationsWithoutChangingCreator() throws {
        let node = try #require(fixture().nodes.first)
        var draft = TaskDraft(node: node)
        draft.title = "Edited"; draft.result = "Full result\n\nSecond paragraph"; draft.status = "in_review"; draft.assignee = nil
        let operations = draft.operations(node: node, parentID: nil)
        #expect(operations.count == 2)
        #expect(operations[0]["patch"]["result"] == .string("Full result\n\nSecond paragraph"))
        #expect(operations[0]["patch"]["created_by"] == .null)
        #expect(operations[1]["op"] == .string("set_assignee"))
        #expect(operations[1]["assignee"] == .null)
        let child = TaskDraft().operations(node: nil, parentID: node.id)
        #expect(child[0]["container_id"] == .string(node.id))
        #expect(child[0]["assignee"] == .null)
        #expect(child[0]["client_ref"] == .string("new"))
    }

    @Test func crossLevelSummaryKeepsNodeIdentityAndParentPath() throws {
        let json = #"{"items":[{"graph_id":"tg_one","root_node_id":"n1","node_id":"n4","scope_id":"n2","revision":3,"updated_at":"now","updated_by":"User","relative_url":"/tasks/tg_one?scope=n2&node=n4","title":"Deep work","mode":"dag","status":"paused","parent_path":[{"id":"n1","title":"Root"},{"id":"n2","title":"Branch"}],"conversation":{"id":"chat","title":"Group","visibility":"public","is_member":false,"can_write":false}}],"total":1,"next_cursor":null}"#
        let page = try JSONDecoder().decode(TaskGraphPage.self, from: Data(json.utf8))
        #expect(page.items.first?.id == "tg_one:n4")
        #expect(page.items.first?.scope_id == "n2")
        #expect(page.items.first?.parent_path?.map(\.id) == ["n1", "n2"])
    }

    @Test func retryPreservesRemoteDescriptionAndLocalResult() throws {
        let original = try #require(fixture().nodes.first)
        var latest = original
        latest.description = "Remote clarification"
        var draft = TaskDraft(node: original)
        draft.result = "My full result"
        let reconciled = try #require(TaskConflict(baseline: original, draft: draft, latest: latest).resolved(keepingMine: [:]))
        let patch = reconciled.operations(node: latest, parentID: nil)[0]["patch"]
        #expect(patch["description"] == .string(latest.description))
        #expect(patch["result"] == .string("My full result"))
    }

    @Test func competingEditsRequireExplicitChoicesAndKeepTheRestOfTheDraft() throws {
        let original = try #require(fixture().nodes.first)
        var latest = original
        latest.description = "Remote description"
        latest.assignee = nil
        var mine = TaskDraft(node: original)
        mine.description = "My description"; mine.result = "Full local result"
        mine.assignee = ActorRef(type: "user", id: "peer"); mine.changeNote = "Reason"
        let conflict = TaskConflict(baseline: original, draft: mine, latest: latest)
        #expect(Set(conflict.fields) == [.description, .assignee])
        #expect(conflict.resolved(keepingMine: [:]) == nil)
        #expect(conflict.resolved(keepingMine: [.description: true]) == nil)
        let resolved = try #require(conflict.resolved(keepingMine: [.description: false, .assignee: false]))
        #expect(resolved.description == "Remote description")
        #expect(resolved.assignee == nil)
        #expect(resolved.result == "Full local result")
        #expect(resolved.changeNote == "Reason")
        let kept = try #require(conflict.resolved(keepingMine: [.description: true, .assignee: true]))
        #expect(kept.description == mine.description)
        #expect(kept.assignee?.taskKey == mine.assignee?.taskKey)
    }

    @Test func successiveConflictsCompareWithLastReviewedVersion() throws {
        let original = try #require(fixture().nodes.first)
        var mine = TaskDraft(node: original)
        mine.result = "My result"; mine.assignee = nil
        var latest = original
        latest.result = "My result"; latest.assignee = nil
        let first = TaskConflict(baseline: original, draft: mine, latest: latest)
        #expect(first.fields.isEmpty)
        var resolved = try #require(first.resolved(keepingMine: [:]))
        resolved.result = "My newer result"
        var newer = latest
        newer.result = "Remote newer result"; newer.description = "New clarification"; newer.status = "done"
        let next = TaskConflict(baseline: latest, draft: resolved, latest: newer)
        #expect(next.fields == [.result])
        var final = try #require(next.resolved(keepingMine: [.result: true]))
        #expect(final.result == "My newer result")
        #expect(final.description == "New clarification")
        #expect(final.status == "done")
        final.status = "doing"
        #expect(final.needsReworkReason(after: newer))
        final.changeNote = "Additional work identified"
        #expect(!final.needsReworkReason(after: newer))
    }

    @Test func nineCanonicalStatusesAndUnknownStatusFallbackDecodeSafely() throws {
        let expectedPairs: [(String, String, String)] = [
            ("proposed", "待拍板", "Proposed"),
            ("todo", "待办", "To do"),
            ("doing", "推进中", "Advancing"),
            ("waiting", "等待中", "Waiting"),
            ("in_review", "待确认", "In review"),
            ("done", "已完成", "Done"),
            ("paused", "已暂缓", "Paused"),
            ("backlog", "先存着", "Backlog"),
            ("closed", "已关闭", "Closed")
        ]
        #expect(taskStatuses == expectedPairs.map(\.0))
        for (raw, zh, en) in expectedPairs {
            #expect(isKnownTaskStatus(raw))
            let badge = taskStatus(raw)
            #expect(badge == zh || badge == en)
        }
        #expect(!isKnownTaskStatus("future_stage_state"))
        #expect(taskStatus("future_stage_state") == "future_stage_state")
        #expect(!taskStatus("   ").isEmpty)
        #expect(taskEditableStatuses("future_stage_state").contains("future_stage_state"))

        let unknownNodeJSON = #"{"id":"n_future","container_id":null,"title":"Future card","description":"","mode":"none","status":"future_stage_state","result":"","selection_reason":"","links":[],"order":0,"created_at":"now","updated_at":"now","updated_by":"PA"}"#
        let unknownNode = try JSONDecoder().decode(TaskNode.self, from: Data(unknownNodeJSON.utf8))
        #expect(unknownNode.status == "future_stage_state")

        let unknownSummaryJSON = #"{"graph_id":"tg_f","root_node_id":"n_future","node_id":"n_future","revision":1,"updated_at":"now","updated_by":"PA","relative_url":"/tasks/tg_f","title":"Future summary","mode":"none","status":"future_stage_state","conversation":{"id":"c1","title":"PA","visibility":"private","is_member":true,"can_write":true}}"#
        let unknownSummary = try JSONDecoder().decode(TaskSummary.self, from: Data(unknownSummaryJSON.utf8))
        #expect(unknownSummary.status == "future_stage_state")
    }

    @Test func silentWaitWithoutScheduleAndNineStateCountsDecodeCleanly() throws {
        let waitJSON = #"{"reason":"Is Nov 18 confirmed?","asked_user_id":"u_sam"}"#
        let silentWait = try JSONDecoder().decode(TaskWait.self, from: Data(waitJSON.utf8))
        #expect(silentWait.reason == "Is Nov 18 confirmed?")
        #expect(silentWait.schedule_id == nil)
        #expect(silentWait.owner_agent_id == nil)
        #expect(silentWait.session_id == nil)
        #expect(silentWait.next_check_at == nil)
        #expect(silentWait.asked_user_id == "u_sam")

        let countsJSON = #"{"proposed":2,"todo":1,"doing":1,"waiting":1,"in_review":0,"done":3,"paused":0,"backlog":4,"closed":1,"total":13}"#
        let counts = try JSONDecoder().decode(TaskCounts.self, from: Data(countsJSON.utf8))
        #expect(counts.proposedCount == 2)
        #expect(counts.backlogCount == 4)

        let legacyGraph = try fixture()
        #expect(legacyGraph.nodes.first?.direct_counts?.proposedCount == 0)
        #expect(legacyGraph.nodes.first?.direct_counts?.backlogCount == 0)
    }

    @Test func focusResponseBatchNodeSummaryAndApproveOperationMatchContracts() throws {
        let focusJSON = """
        {
          "needs_you": [{
            "graph_id": "tg_trip",
            "root_node_id": "root",
            "node_id": "stage_3",
            "revision": 4,
            "updated_at": "2026-11-26T01:00:00Z",
            "updated_by": "PA",
            "title": "Compare Shinkansen vs flight",
            "description": "Stage 2 hotel shortlist is nearly ready; draft a fare & transfer table on approval",
            "mode": "none",
            "status": "proposed",
            "root_title": "Kyoto Trip",
            "root_goal_summary": "5-day Kyoto itinerary under budget",
            "blocked_by_dag": true,
            "proposed_for_user_id": "u_owner",
            "conversation": {"id": "c_pa", "title": "PA", "visibility": "private", "is_member": true, "can_write": true}
          }],
          "stashed": [{
            "graph_id": "tg_idea",
            "root_node_id": "idea_1",
            "revision": 1,
            "updated_at": "2026-11-26T00:00:00Z",
            "updated_by": "PA",
            "title": "Try local ceramics workshop",
            "mode": "none",
            "status": "backlog",
            "conversation": {"id": "c_pa", "title": "PA", "visibility": "private", "is_member": true, "can_write": true}
          }],
          "active": [],
          "goals": [{
            "graph_id": "tg_trip",
            "root_node_id": "root",
            "revision": 4,
            "updated_at": "2026-11-26T01:00:00Z",
            "updated_by": "PA",
            "title": "Kyoto Trip",
            "mode": "dag",
            "status": "doing",
            "root_goal_summary": "5-day Kyoto itinerary under budget",
            "progress": {"done": 1, "total": 3},
            "stage_nodes": [
              {"id": "stage_1", "title": "Fix dates", "status": "done", "mode": "none"},
              {"id": "stage_2", "title": "Pick hotel", "status": "doing", "mode": "explore", "child_count": 2},
              {"id": "stage_3", "title": "Compare Shinkansen vs flight", "status": "proposed", "mode": "none"}
            ],
            "conversation": {"id": "c_pa", "title": "PA", "visibility": "private", "is_member": true, "can_write": true}
          }],
          "completed_count": 5,
          "counts": {"needs_you": 1, "stashed": 1, "active": 0, "goals": 1, "completed": 5},
          "next_cursors": {"needs_you": null, "stashed": null, "active": null, "goals": null}
        }
        """
        let focus = try JSONDecoder().decode(TaskFocusResponse.self, from: Data(focusJSON.utf8))
        #expect(focus.needs_you.count == 1)
        #expect(focus.needs_you.first?.isPrereqBlocked == true)
        #expect(focus.needs_you.first?.description == "Stage 2 hotel shortlist is nearly ready; draft a fare & transfer table on approval")
        #expect(focus.needs_you.first?.proposed_for_user_id == "u_owner")
        #expect(focus.needs_you.first?.root_goal_summary == "5-day Kyoto itinerary under budget")
        #expect(focus.stashed.first?.status == "backlog")
        #expect(focus.goals.first?.progress?.done == 1)
        #expect(focus.goals.first?.stage_nodes?.count == 3)
        #expect(focus.completed_count == 5)

        let nodesJSON = """
        {
          "graph_id": "tg_trip",
          "node_id": "stage_3",
          "root_node_id": "root",
          "revision": 4,
          "title": "Compare Shinkansen vs flight",
          "description": "Ready now; compare fares on approval",
          "mode": "none",
          "status": "proposed",
          "prereq_blocked": false,
          "root_title": "Kyoto Trip"
        }
        """
        let summary = try JSONDecoder().decode(TaskCardNodeSummary.self, from: Data(nodesJSON.utf8))
        #expect(summary.cardKey == "tg_trip:stage_3")
        #expect(summary.isPrereqBlocked == false)
        #expect(summary.description == "Ready now; compare fares on approval")

        let approvePlain = TaskOperations.approve(nodeID: "stage_3")
        #expect(approvePlain == .object(["op": .string("approve_task"), "node_id": .string("stage_3")]))
        let approveAssigned = TaskOperations.approve(nodeID: "stage_3", assignee: ActorRef(type: "agent", id: "pa-main"))
        #expect(approveAssigned["op"] == .string("approve_task"))
        #expect(approveAssigned["node_id"] == .string("stage_3"))
        #expect(approveAssigned["assignee"] == .object(["type": .string("agent"), "id": .string("pa-main")]))
    }

    private func fixture() throws -> TaskGraph {
        let json = #"{"schema_version":2,"graph_id":"tg_one","root_node_id":"n1","revision":3,"created_at":"now","updated_at":"now","updated_by":"User","relative_url":"/tasks/tg_one","dependencies":[],"conversation":{"id":"chat","title":"Group","visibility":"public","is_member":false,"can_write":false},"nodes":[{"id":"n1","container_id":null,"title":"Root","description":"","mode":"dag","status":"waiting","wait":{"reason":"Await approval, then resume purchase","schedule_id":"schedule","owner_agent_id":"worker","session_id":"session","next_check_at":"2026-10-22T12:00:00Z"},"wait_health":{"state":"unknown","checked_at":"2026-10-22T11:00:00Z","reason_code":"node_unavailable"},"result":"","selection_reason":"","links":[],"order":0,"created_at":"now","updated_at":"now","updated_by":"User","created_by":{"type":"user","id":"creator"},"assignee":{"type":"agent","id":"worker","display_name":"Worker","user_id":"agent-user"},"can_edit":false,"can_claim":false,"can_delete":false,"direct_counts":{"todo":0,"doing":0,"waiting":0,"in_review":0,"done":1,"paused":1,"closed":1,"total":3}}]}"#
        return try JSONDecoder().decode(TaskGraph.self, from: Data(json.utf8))
    }
}
