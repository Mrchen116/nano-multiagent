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

    private func fixture() throws -> TaskGraph {
        let json = #"{"schema_version":2,"graph_id":"tg_one","root_node_id":"n1","revision":3,"created_at":"now","updated_at":"now","updated_by":"User","relative_url":"/tasks/tg_one","dependencies":[],"conversation":{"id":"chat","title":"Group","visibility":"public","is_member":false,"can_write":false},"nodes":[{"id":"n1","container_id":null,"title":"Root","description":"","mode":"dag","status":"waiting","wait":{"reason":"Await approval, then resume purchase","schedule_id":"schedule","owner_agent_id":"worker","session_id":"session","next_check_at":"2026-10-22T12:00:00Z"},"wait_health":{"state":"unknown","checked_at":"2026-10-22T11:00:00Z","reason_code":"node_unavailable"},"result":"","selection_reason":"","links":[],"order":0,"created_at":"now","updated_at":"now","updated_by":"User","created_by":{"type":"user","id":"creator"},"assignee":{"type":"agent","id":"worker","display_name":"Worker","user_id":"agent-user"},"can_edit":false,"can_claim":false,"can_delete":false,"direct_counts":{"todo":0,"doing":0,"waiting":0,"in_review":0,"done":1,"paused":1,"closed":1,"total":3}}]}"#
        return try JSONDecoder().decode(TaskGraph.self, from: Data(json.utf8))
    }
}
