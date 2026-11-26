import Foundation
import CoreGraphics

extension Notification.Name {
    static let nanoTaskGraphChanged = Notification.Name("NanoIM.TaskGraph.Changed")
}

/// Lightweight message-level reference to an authoritative task-graph node.
struct TaskCardRef: Codable, Sendable, Hashable, Identifiable {
    var graph_id: String
    var node_id: String
    var id: String { cardKey }
    var cardKey: String { "\(graph_id):\(node_id)" }
}

/// Persisted waiting facts; timer fields are optional to support silent waiting on human replies.
struct TaskWait: Codable, Sendable, Hashable {
    var reason: String
    var schedule_id: String? = nil
    var owner_agent_id: String? = nil
    var session_id: String? = nil
    var next_check_at: String? = nil
    var asked_user_id: String? = nil
}

struct TaskWaitHealth: Codable, Sendable, Hashable {
    var state: String
    var checked_at: String
    var reason_code: String? = nil
}

struct TaskNode: Codable, Identifiable, Sendable, Hashable {
    var id: String
    var container_id: String?
    var title: String
    var description: String
    var mode: String
    var status: String
    var result: String
    var change_note: String?
    var derived_from_id: String?
    var selected_candidate_id: String?
    var selection_reason: String
    var links: [String]
    var order: Int
    var created_at: String
    var updated_at: String
    var updated_by: String
    var last_chat_id: String?
    var last_chat_title: String?
    var created_by: ActorRef?
    var assignee: ActorRef?
    var updated_by_actor: ActorRef?
    var can_edit: Bool?
    var can_delete: Bool?
    var can_claim: Bool?
    var direct_counts: TaskCounts?
    var proposed_for_user_id: String? = nil
    var wait: TaskWait? = nil
    var wait_health: TaskWaitHealth? = nil
    var prereq_blocked: Bool? = nil
    var blocked_by_dag: Bool? = nil
    var root_goal_summary: String? = nil

    func isPrereqBlocked(in graph: TaskGraph? = nil) -> Bool {
        if let prereq_blocked { return prereq_blocked }
        if let blocked_by_dag { return blocked_by_dag }
        return graph?.isPrereqBlocked(id) ?? false
    }
}

struct TaskDependency: Codable, Sendable, Hashable {
    let from: String
    let to: String
}

struct TaskGraph: Codable, Sendable {
    var schema_version: Int
    var graph_id: String
    var root_node_id: String
    var revision: Int
    var nodes: [TaskNode]
    var dependencies: [TaskDependency]
    var created_at: String
    var updated_at: String
    var updated_by: String
    var relative_url: String
    var conversation: TaskConversation

    var rootNode: TaskNode? {
        nodes.first { $0.id == root_node_id }
    }

    func isPrereqBlocked(_ nodeID: String) -> Bool {
        guard let node = nodes.first(where: { $0.id == nodeID }),
              let parentID = node.container_id,
              let parent = nodes.first(where: { $0.id == parentID }),
              parent.mode == "dag" else { return false }
        return dependencies.contains { edge in
            edge.to == nodeID && nodes.first(where: { $0.id == edge.from })?.status != "done"
        }
    }

    func directChildren(of scopeID: String) -> [TaskNode] {
        nodes.filter { $0.container_id == scopeID }
            .sorted { ($0.order, $0.id) < ($1.order, $1.id) }
    }

    /// Groups direct children of a scope into dependency-ordered vertical stages.
    func stageLayers(scopeID: String) -> [[TaskNode]] {
        let children = directChildren(of: scopeID)
        guard !children.isEmpty else { return [] }
        let scopeMode = nodes.first { $0.id == scopeID }?.mode ?? "none"
        if scopeMode != "dag" {
            return children.map { [$0] }
        }
        let ids = Set(children.map(\.id))
        let localEdges = dependencies.filter { ids.contains($0.from) && ids.contains($0.to) }
        if localEdges.isEmpty {
            return children.map { [$0] }
        }
        var indegree = Dictionary(uniqueKeysWithValues: children.map { ($0.id, 0) })
        var ranks = indegree
        for edge in localEdges { indegree[edge.to, default: 0] += 1 }
        var queue = children.filter { indegree[$0.id] == 0 }.map(\.id)
        while !queue.isEmpty {
            let current = queue.removeFirst()
            for edge in localEdges where edge.from == current {
                ranks[edge.to] = max(ranks[edge.to] ?? 0, (ranks[current] ?? 0) + 1)
                indegree[edge.to, default: 0] -= 1
                if indegree[edge.to] == 0 { queue.append(edge.to) }
            }
        }
        let grouped = Dictionary(grouping: children) { ranks[$0.id] ?? 0 }
        return grouped.keys.sorted().compactMap { grouped[$0] }
    }
}

struct TaskGoalProgress: Codable, Sendable, Hashable {
    var done: Int
    var total: Int
}

struct TaskGoalStage: Codable, Sendable, Hashable, Identifiable {
    var id: String
    var title: String
    var status: String
    var mode: String
    var child_count: Int? = nil
}

struct TaskSummary: Codable, Identifiable, Sendable, Hashable {
    var graph_id: String
    var root_node_id: String
    var revision: Int
    var updated_at: String
    var updated_by: String
    var relative_url: String
    var title: String
    var description: String? = nil
    var result: String? = nil
    var mode: String
    var status: String
    var node_id: String? = nil
    var scope_id: String? = nil
    var root_title: String? = nil
    var root_goal_summary: String? = nil
    var parent_path: [TaskPathPart]? = nil
    var conversation: TaskConversation
    var created_by: ActorRef? = nil
    var assignee: ActorRef? = nil
    var direct_counts: TaskCounts? = nil
    var proposed_for_user_id: String? = nil
    var wait: TaskWait? = nil
    var wait_health: TaskWaitHealth? = nil
    var prereq_blocked: Bool? = nil
    var can_edit: Bool? = nil
    var can_delete: Bool? = nil
    var can_claim: Bool? = nil
    var progress: TaskGoalProgress? = nil
    var stage_nodes: [TaskGoalStage]? = nil

    var id: String { graph_id + ":" + effectiveNodeID }
    var effectiveNodeID: String { node_id ?? root_node_id }
    var isPrereqBlocked: Bool { prereq_blocked ?? false }

    private enum CodingKeys: String, CodingKey {
        case graph_id, root_node_id, revision, updated_at, updated_by, relative_url, title
        case description, result, mode, status, node_id, scope_id, root_title, root_goal_summary
        case parent_path, conversation, created_by, assignee, direct_counts, proposed_for_user_id, wait, wait_health
        case prereq_blocked, blocked_by_dag, can_edit, can_delete, can_claim, progress, stage_nodes
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        graph_id = try c.decode(String.self, forKey: .graph_id)
        root_node_id = try c.decode(String.self, forKey: .root_node_id)
        revision = try c.decodeIfPresent(Int.self, forKey: .revision) ?? 1
        updated_at = try c.decodeIfPresent(String.self, forKey: .updated_at) ?? ""
        updated_by = try c.decodeIfPresent(String.self, forKey: .updated_by) ?? ""
        let gid = graph_id
        relative_url = try c.decodeIfPresent(String.self, forKey: .relative_url) ?? "/tasks/\(gid)"
        title = try c.decode(String.self, forKey: .title)
        description = try c.decodeIfPresent(String.self, forKey: .description)
        result = try c.decodeIfPresent(String.self, forKey: .result)
        mode = try c.decodeIfPresent(String.self, forKey: .mode) ?? "none"
        status = try c.decodeIfPresent(String.self, forKey: .status) ?? "todo"
        node_id = try c.decodeIfPresent(String.self, forKey: .node_id)
        scope_id = try c.decodeIfPresent(String.self, forKey: .scope_id)
        root_title = try c.decodeIfPresent(String.self, forKey: .root_title)
        root_goal_summary = try c.decodeIfPresent(String.self, forKey: .root_goal_summary)
        parent_path = try c.decodeIfPresent([TaskPathPart].self, forKey: .parent_path)
        conversation = try c.decode(TaskConversation.self, forKey: .conversation)
        created_by = try c.decodeIfPresent(ActorRef.self, forKey: .created_by)
        assignee = try c.decodeIfPresent(ActorRef.self, forKey: .assignee)
        direct_counts = try c.decodeIfPresent(TaskCounts.self, forKey: .direct_counts)
        proposed_for_user_id = try c.decodeIfPresent(String.self, forKey: .proposed_for_user_id)
        wait = try c.decodeIfPresent(TaskWait.self, forKey: .wait)
        wait_health = try c.decodeIfPresent(TaskWaitHealth.self, forKey: .wait_health)
        prereq_blocked = try c.decodeIfPresent(Bool.self, forKey: .prereq_blocked)
            ?? c.decodeIfPresent(Bool.self, forKey: .blocked_by_dag)
        can_edit = try c.decodeIfPresent(Bool.self, forKey: .can_edit)
        can_delete = try c.decodeIfPresent(Bool.self, forKey: .can_delete)
        can_claim = try c.decodeIfPresent(Bool.self, forKey: .can_claim)
        progress = try c.decodeIfPresent(TaskGoalProgress.self, forKey: .progress)
        stage_nodes = try c.decodeIfPresent([TaskGoalStage].self, forKey: .stage_nodes)
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(graph_id, forKey: .graph_id)
        try c.encode(root_node_id, forKey: .root_node_id)
        try c.encode(revision, forKey: .revision)
        try c.encode(updated_at, forKey: .updated_at)
        try c.encode(updated_by, forKey: .updated_by)
        try c.encode(relative_url, forKey: .relative_url)
        try c.encode(title, forKey: .title)
        try c.encodeIfPresent(description, forKey: .description)
        try c.encodeIfPresent(result, forKey: .result)
        try c.encode(mode, forKey: .mode)
        try c.encode(status, forKey: .status)
        try c.encodeIfPresent(node_id, forKey: .node_id)
        try c.encodeIfPresent(scope_id, forKey: .scope_id)
        try c.encodeIfPresent(root_title, forKey: .root_title)
        try c.encodeIfPresent(root_goal_summary, forKey: .root_goal_summary)
        try c.encodeIfPresent(parent_path, forKey: .parent_path)
        try c.encode(conversation, forKey: .conversation)
        try c.encodeIfPresent(created_by, forKey: .created_by)
        try c.encodeIfPresent(assignee, forKey: .assignee)
        try c.encodeIfPresent(direct_counts, forKey: .direct_counts)
        try c.encodeIfPresent(proposed_for_user_id, forKey: .proposed_for_user_id)
        try c.encodeIfPresent(wait, forKey: .wait)
        try c.encodeIfPresent(wait_health, forKey: .wait_health)
        try c.encodeIfPresent(prereq_blocked, forKey: .prereq_blocked)
        try c.encodeIfPresent(can_edit, forKey: .can_edit)
        try c.encodeIfPresent(can_delete, forKey: .can_delete)
        try c.encodeIfPresent(can_claim, forKey: .can_claim)
        try c.encodeIfPresent(progress, forKey: .progress)
        try c.encodeIfPresent(stage_nodes, forKey: .stage_nodes)
    }
}

/// Live node summary returned by `GET /im/v1/task-graphs/nodes` and cached locally for chat task cards.
struct TaskCardNodeSummary: Codable, Identifiable, Sendable, Hashable {
    var graph_id: String
    var node_id: String
    var root_node_id: String
    var revision: Int
    var scope_id: String? = nil
    var title: String
    var description: String? = nil
    var result: String? = nil
    var mode: String
    var status: String
    var proposed_for_user_id: String? = nil
    var wait: TaskWait? = nil
    var wait_health: TaskWaitHealth? = nil
    var prereq_blocked: Bool? = nil
    var root_title: String? = nil
    var root_goal_summary: String? = nil
    var parent_path: [TaskPathPart]? = nil
    var conversation: TaskConversation? = nil
    var assignee: ActorRef? = nil
    var created_by: ActorRef? = nil
    var direct_counts: TaskCounts? = nil
    var can_edit: Bool? = nil
    var relative_url: String? = nil
    var updated_at: String? = nil

    var id: String { cardKey }
    var cardKey: String { "\(graph_id):\(node_id)" }
    var isPrereqBlocked: Bool { prereq_blocked ?? false }

    private enum CodingKeys: String, CodingKey {
        case graph_id, node_id, root_node_id, revision, scope_id, title, description, result
        case mode, status, proposed_for_user_id, wait, wait_health, prereq_blocked, blocked_by_dag
        case root_title, root_goal_summary, parent_path, conversation, assignee, created_by
        case direct_counts, can_edit, relative_url, updated_at
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let gid = try c.decode(String.self, forKey: .graph_id)
        let nid = try c.decode(String.self, forKey: .node_id)
        graph_id = gid
        node_id = nid
        root_node_id = try c.decodeIfPresent(String.self, forKey: .root_node_id) ?? nid
        revision = try c.decodeIfPresent(Int.self, forKey: .revision) ?? 1
        scope_id = try c.decodeIfPresent(String.self, forKey: .scope_id)
        title = try c.decode(String.self, forKey: .title)
        description = try c.decodeIfPresent(String.self, forKey: .description)
        result = try c.decodeIfPresent(String.self, forKey: .result)
        mode = try c.decodeIfPresent(String.self, forKey: .mode) ?? "none"
        status = try c.decodeIfPresent(String.self, forKey: .status) ?? "todo"
        proposed_for_user_id = try c.decodeIfPresent(String.self, forKey: .proposed_for_user_id)
        wait = try c.decodeIfPresent(TaskWait.self, forKey: .wait)
        wait_health = try c.decodeIfPresent(TaskWaitHealth.self, forKey: .wait_health)
        prereq_blocked = try c.decodeIfPresent(Bool.self, forKey: .prereq_blocked)
            ?? c.decodeIfPresent(Bool.self, forKey: .blocked_by_dag)
        root_title = try c.decodeIfPresent(String.self, forKey: .root_title)
        root_goal_summary = try c.decodeIfPresent(String.self, forKey: .root_goal_summary)
        parent_path = try c.decodeIfPresent([TaskPathPart].self, forKey: .parent_path)
        conversation = try c.decodeIfPresent(TaskConversation.self, forKey: .conversation)
        assignee = try c.decodeIfPresent(ActorRef.self, forKey: .assignee)
        created_by = try c.decodeIfPresent(ActorRef.self, forKey: .created_by)
        direct_counts = try c.decodeIfPresent(TaskCounts.self, forKey: .direct_counts)
        can_edit = try c.decodeIfPresent(Bool.self, forKey: .can_edit)
        relative_url = try c.decodeIfPresent(String.self, forKey: .relative_url)
        updated_at = try c.decodeIfPresent(String.self, forKey: .updated_at)
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(graph_id, forKey: .graph_id)
        try c.encode(node_id, forKey: .node_id)
        try c.encode(root_node_id, forKey: .root_node_id)
        try c.encode(revision, forKey: .revision)
        try c.encodeIfPresent(scope_id, forKey: .scope_id)
        try c.encode(title, forKey: .title)
        try c.encodeIfPresent(description, forKey: .description)
        try c.encodeIfPresent(result, forKey: .result)
        try c.encode(mode, forKey: .mode)
        try c.encode(status, forKey: .status)
        try c.encodeIfPresent(proposed_for_user_id, forKey: .proposed_for_user_id)
        try c.encodeIfPresent(wait, forKey: .wait)
        try c.encodeIfPresent(wait_health, forKey: .wait_health)
        try c.encodeIfPresent(prereq_blocked, forKey: .prereq_blocked)
        try c.encodeIfPresent(root_title, forKey: .root_title)
        try c.encodeIfPresent(root_goal_summary, forKey: .root_goal_summary)
        try c.encodeIfPresent(parent_path, forKey: .parent_path)
        try c.encodeIfPresent(conversation, forKey: .conversation)
        try c.encodeIfPresent(assignee, forKey: .assignee)
        try c.encodeIfPresent(created_by, forKey: .created_by)
        try c.encodeIfPresent(direct_counts, forKey: .direct_counts)
        try c.encodeIfPresent(can_edit, forKey: .can_edit)
        try c.encodeIfPresent(relative_url, forKey: .relative_url)
        try c.encodeIfPresent(updated_at, forKey: .updated_at)
    }
}

struct TaskFocusCounts: Codable, Sendable, Hashable {
    var needs_you: Int = 0
    var stashed: Int = 0
    var active: Int = 0
    var goals: Int = 0
    var completed: Int = 0
}

struct TaskFocusCursors: Codable, Sendable, Hashable {
    var needs_you: String? = nil
    var stashed: String? = nil
    var active: String? = nil
    var goals: String? = nil
    var completed: String? = nil
}

/// Aggregated response for `GET /im/v1/task-graphs/focus`.
struct TaskFocusResponse: Codable, Sendable {
    var needs_you: [TaskSummary]
    var stashed: [TaskSummary]
    var active: [TaskSummary]
    var goals: [TaskSummary]
    var completed: [TaskSummary]
    var completed_count: Int
    var counts: TaskFocusCounts
    var next_cursors: TaskFocusCursors

    private enum CodingKeys: String, CodingKey {
        case needs_you, stashed, active, goals, completed, completed_count, counts, next_cursors
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let needs = try c.decodeIfPresent([TaskSummary].self, forKey: .needs_you) ?? []
        let stash = try c.decodeIfPresent([TaskSummary].self, forKey: .stashed) ?? []
        let act = try c.decodeIfPresent([TaskSummary].self, forKey: .active) ?? []
        let gls = try c.decodeIfPresent([TaskSummary].self, forKey: .goals) ?? []
        let compItems = try c.decodeIfPresent([TaskSummary].self, forKey: .completed) ?? []
        let comp = try c.decodeIfPresent(Int.self, forKey: .completed_count) ?? compItems.count
        needs_you = needs
        stashed = stash
        active = act
        goals = gls
        completed = compItems
        completed_count = comp
        counts = try c.decodeIfPresent(TaskFocusCounts.self, forKey: .counts)
            ?? TaskFocusCounts(needs_you: needs.count, stashed: stash.count, active: act.count, goals: gls.count, completed: comp)
        next_cursors = try c.decodeIfPresent(TaskFocusCursors.self, forKey: .next_cursors) ?? TaskFocusCursors()
    }
}

struct TaskGraphPage: Decodable, Sendable {
    let items: [TaskSummary]
    let next_cursor: String?
    let total: Int
}

struct TaskActivity: Decodable, Identifiable, Sendable {
    let graph_id: String
    let node_id: String
    let scope_id: String?
    let title: String
    let root_title: String
    let status: String
    let updated_at: String
    var id: String { graph_id + ":" + node_id }
}

/// Places each task in its earliest prerequisite row without changing recorded edges.
struct NativeTaskLayout {
    let nodes: [TaskNode]
    let edges: [TaskDependency]
    let positions: [String: CGPoint]
    let size: CGSize
    init(graph: TaskGraph, scopeID: String, cardWidth: CGFloat = 320, cardHeight: CGFloat = 124) {
        nodes = graph.nodes.filter { $0.container_id == scopeID }.sorted { ($0.order, $0.id) < ($1.order, $1.id) }
        let ids = Set(nodes.map(\.id))
        if graph.nodes.first(where: { $0.id == scopeID })?.mode == "explore" {
            edges = nodes.compactMap { node in node.derived_from_id.flatMap { ids.contains($0) ? TaskDependency(from: $0, to: node.id) : nil } }
        } else { edges = graph.dependencies.filter { ids.contains($0.from) && ids.contains($0.to) } }
        var indegree = Dictionary(uniqueKeysWithValues: nodes.map { ($0.id, 0) })
        var ranks = indegree
        for edge in edges { indegree[edge.to, default: 0] += 1 }
        var queue = nodes.filter { indegree[$0.id] == 0 }.map(\.id)
        while !queue.isEmpty {
            let id = queue.removeFirst()
            for edge in edges where edge.from == id {
                ranks[edge.to] = max(ranks[edge.to] ?? 0, (ranks[id] ?? 0) + 1)
                indegree[edge.to, default: 0] -= 1
                if indegree[edge.to] == 0 { queue.append(edge.to) }
            }
        }
        var rows: [Int: Int] = [:], points: [String: CGPoint] = [:]
        for node in nodes {
            let rank = ranks[node.id] ?? 0, row = rows[rank, default: 0]
            points[node.id] = CGPoint(x: 16 + CGFloat(row) * (cardWidth + 32), y: 24 + CGFloat(rank) * (cardHeight + 44))
            rows[rank] = row + 1
        }
        positions = points
        size = CGSize(width: CGFloat(rows.values.max() ?? 1) * (cardWidth + 32), height: CGFloat(ranks.values.max() ?? 0) * (cardHeight + 44) + cardHeight + 48)
    }
}

let taskStatuses = ["proposed", "todo", "doing", "waiting", "in_review", "done", "paused", "backlog", "closed"]
let taskGroups = ["proposed", "todo", "doing", "in_review", "backlog", "done", "closed"]

func isKnownTaskStatus(_ status: String) -> Bool {
    taskStatuses.contains(status)
}

/// Maps the nine canonical statuses to exact badge words while safely displaying unknown future statuses.
func taskStatus(_ status: String) -> String {
    switch status {
    case "proposed": return L("待拍板", "Proposed")
    case "todo": return L("待办", "To do")
    case "doing": return L("推进中", "Advancing")
    case "waiting": return L("等待中", "Waiting")
    case "in_review": return L("待确认", "In review")
    case "done": return L("已完成", "Done")
    case "paused": return L("已暂缓", "Paused")
    case "backlog": return L("先存着", "Backlog")
    case "closed": return L("已关闭", "Closed")
    default:
        let trimmed = status.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? L("未知状态", "Unknown") : trimmed
    }
}

func taskGroupTitle(_ group: String) -> String {
    group == "doing" ? L("进行中", "In progress") : taskStatus(group)
}

func taskEditableStatuses(_ current: String?) -> [String] {
    var base = taskStatuses.filter { $0 != "waiting" || current == "waiting" }
    if let current, !current.isEmpty, !base.contains(current) { base.append(current) }
    return base
}

func taskGroupContains(_ group: String, status: String) -> Bool {
    group == status || (group == "todo" && status == "paused") || (group == "doing" && status == "waiting")
}

struct TaskConversation: Codable, Sendable, Hashable {
    var id: String
    var title: String
    var visibility: String
    var dissolved_at: String? = nil
    var is_member: Bool
    var can_write: Bool
}

struct TaskCounts: Codable, Sendable, Hashable {
    var proposed: Int? = nil
    var todo: Int
    var doing: Int
    var waiting: Int
    var in_review: Int
    var done: Int
    var paused: Int
    var backlog: Int? = nil
    var closed: Int
    var total: Int

    var proposedCount: Int { proposed ?? 0 }
    var backlogCount: Int { backlog ?? 0 }
    var summary: String { L("直属子任务：已完成 \(done) / 共 \(total)", "Direct subtasks: \(done) done / \(total) total") }
}

struct TaskPathPart: Codable, Sendable, Hashable {
    var id: String
    var title: String
    var mode: String? = nil
}

extension ActorRef {
    var taskKey: String { type + ":" + id }
    var taskName: String { display_name ?? id }
    var taskValue: JSONValue { .object(["type": .string(type), "id": .string(id)]) }
}

enum TaskOperations {
    /// Builds the `approve_task` mutation payload for `/im/v1/task-graphs/:id/apply`.
    static func approve(nodeID: String, assignee: ActorRef? = nil) -> JSONValue {
        var payload: [String: JSONValue] = [
            "op": .string("approve_task"),
            "node_id": .string(nodeID)
        ]
        if let assignee { payload["assignee"] = assignee.taskValue }
        return .object(payload)
    }

    static func setStatus(nodeID: String, status: String) -> JSONValue {
        .object([
            "op": .string("update_task"),
            "node_id": .string(nodeID),
            "patch": .object(["status": .string(status)])
        ])
    }

    static func setMode(nodeID: String, mode: String) -> JSONValue {
        .object([
            "op": .string("update_task"),
            "node_id": .string(nodeID),
            "patch": .object(["mode": .string(mode)])
        ])
    }
}

struct TaskDraft: Equatable {
    var title = ""
    var description = ""
    var result = ""
    var mode = "none"
    var status = "todo"
    var assignee: ActorRef?
    var proposed_for_user_id: String? = nil
    var changeNote = ""

    init(node: TaskNode? = nil, defaultMode: String = "none") {
        self.mode = defaultMode
        if let node {
            title = node.title
            description = node.description
            result = node.result
            mode = node.mode
            status = node.status
            assignee = node.assignee
            proposed_for_user_id = node.proposed_for_user_id
        }
    }

    func operations(node: TaskNode?, parentID: String?) -> [JSONValue] {
        if let node {
            var patch: [String: JSONValue] = [
                "title": .string(title),
                "description": .string(description),
                "result": .string(self.result),
                "status": .string(status)
            ]
            if proposed_for_user_id != node.proposed_for_user_id {
                patch["proposed_for_user_id"] = proposed_for_user_id.map(JSONValue.string) ?? .null
            }
            var ops: [JSONValue] = [.object(["op": .string("update_task"), "node_id": .string(node.id), "patch": .object(patch)])]
            if assignee?.taskKey != node.assignee?.taskKey {
                ops.append(.object(["op": .string("set_assignee"), "node_id": .string(node.id), "assignee": assignee?.taskValue ?? .null]))
            }
            return ops
        }
        var add: [String: JSONValue] = [
            "op": .string("add_task"),
            "client_ref": .string("new"),
            "container_id": .string(parentID ?? ""),
            "title": .string(title),
            "description": .string(description),
            "mode": .string(mode),
            "status": .string(status),
            "result": .string(result),
            "assignee": assignee?.taskValue ?? .null
        ]
        if let userID = proposed_for_user_id, !userID.isEmpty {
            add["proposed_for_user_id"] = .string(userID)
        }
        return [.object(add)]
    }
}

enum TaskEditField: String, CaseIterable, Identifiable {
    case title, description, result, status, assignee
    var id: String { rawValue }
    var label: String {
        switch self {
        case .title: return L("任务标题", "Task title")
        case .description: return L("任务说明", "Description")
        case .result: return L("当前结果", "Result")
        case .status: return L("状态", "Status")
        case .assignee: return L("负责人", "Assignee")
        }
    }
    func value(in draft: TaskDraft) -> String {
        switch self {
        case .title: return draft.title
        case .description: return draft.description
        case .result: return draft.result
        case .status: return draft.status
        case .assignee: return draft.assignee?.taskKey ?? ""
        }
    }
    func display(in draft: TaskDraft) -> String {
        if self == .status { return taskStatus(draft.status) }
        if self == .assignee { return draft.assignee?.taskName ?? L("未分配", "Unassigned") }
        return value(in: draft).isEmpty ? L("未填写", "Empty") : value(in: draft)
    }
    func copy(from source: TaskDraft, to target: inout TaskDraft) {
        switch self {
        case .title: target.title = source.title
        case .description: target.description = source.description
        case .result: target.result = source.result
        case .status: target.status = source.status
        case .assignee: target.assignee = source.assignee
        }
    }
}

/// Reconciles independent edits while requiring a choice for competing edits.
/// No choice writes data; the caller must still submit against the fresh revision.
struct TaskConflict {
    let mine: TaskDraft
    let latest: TaskDraft
    let fields: [TaskEditField]
    let retained: [TaskEditField]
    let adopted: [TaskEditField]
    private let merged: TaskDraft

    init(baseline: TaskNode, draft: TaskDraft, latest: TaskNode) {
        let before = TaskDraft(node: baseline), remote = TaskDraft(node: latest)
        var merged = draft
        var fields: [TaskEditField] = [], retained: [TaskEditField] = [], adopted: [TaskEditField] = []
        for field in TaskEditField.allCases {
            let localChanged = field.value(in: draft) != field.value(in: before)
            let remoteChanged = field.value(in: remote) != field.value(in: before)
            if !localChanged {
                field.copy(from: remote, to: &merged)
                if remoteChanged { adopted.append(field) }
            } else if remoteChanged && field.value(in: draft) != field.value(in: remote) {
                fields.append(field)
            } else { retained.append(field) }
        }
        self.mine = draft; self.latest = remote; self.merged = merged
        self.fields = fields; self.retained = retained; self.adopted = adopted
    }

    func resolved(keepingMine choices: [TaskEditField: Bool]) -> TaskDraft? {
        guard fields.allSatisfy({ choices[$0] != nil }) else { return nil }
        var result = merged
        for field in fields { field.copy(from: choices[field] == true ? mine : latest, to: &result) }
        return result
    }
}

extension TaskDraft {
    func needsReworkReason(after node: TaskNode?) -> Bool {
        node?.status == "done" && status == "doing" && changeNote.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }
}

extension IMClient {
    func taskGraph(_ id: String) async throws -> TaskGraph {
        let graph: TaskGraph = try await get("/im/v1/task-graphs/\(id.pathComponent)", query: [.init(name: "view", value: "all")])
        guard graph.schema_version == 2 else { throw APIError(status: 422, detail: L("暂不支持此任务图版本。", "Unsupported task graph version.")) }
        return graph
    }

    func taskFocus(scope: String = "mine", query: String = "", assignee: ActorRef? = nil,
                   conversationID: String? = nil, section: String? = nil, cursor: String? = nil,
                   limit: Int = 30) async throws -> TaskFocusResponse {
        var params: [URLQueryItem] = [
            .init(name: "scope", value: scope),
            .init(name: "limit", value: String(limit))
        ]
        if !query.isEmpty { params.append(.init(name: "query", value: query)) }
        if scope == "assignee", let assignee {
            params.append(.init(name: "assignee_type", value: assignee.type))
            params.append(.init(name: "assignee_id", value: assignee.id))
        }
        if let conversationID, !conversationID.isEmpty {
            params.append(.init(name: "conversation_id", value: conversationID))
        }
        if let section { params.append(.init(name: "section", value: section)) }
        if let cursor { params.append(.init(name: "cursor", value: cursor)) }
        return try await get("/im/v1/task-graphs/focus", query: params)
    }

    func taskNodes(_ refs: [TaskCardRef]) async throws -> [TaskCardNodeSummary] {
        guard !refs.isEmpty else { return [] }
        struct Response: Decodable, Sendable { let items: [TaskCardNodeSummary] }
        let joined = refs.prefix(50).map(\.cardKey).joined(separator: ",")
        let response: Response = try await get("/im/v1/task-graphs/nodes", query: [.init(name: "refs", value: joined)])
        return response.items
    }

    func applyTask(_ graph: TaskGraph, operations: [JSONValue], note: String = "", key: String) async throws {
        try await applyTaskOperations(graphID: graph.graph_id, revision: graph.revision, operations: operations, note: note, key: key)
    }

    func applyTaskOperations(graphID: String, revision: Int, operations: [JSONValue], note: String = "", key: String = UUID().uuidString) async throws {
        let body: [String: JSONValue] = [
            "base_revision": .number(Double(revision)),
            "request_key": .string(key),
            "operations": .array(operations),
            "change_note": .string(note)
        ]
        do {
            let _: JSONValue = try await send("/im/v1/task-graphs/\(graphID.pathComponent)/apply", body: body)
        } catch let apiError as APIError where apiError.status == 409 || apiError.code == "version_conflict" {
            let fresh = try await taskGraph(graphID)
            let retryBody: [String: JSONValue] = [
                "base_revision": .number(Double(fresh.revision)),
                "request_key": .string(UUID().uuidString),
                "operations": .array(operations),
                "change_note": .string(note)
            ]
            let _: JSONValue = try await send("/im/v1/task-graphs/\(graphID.pathComponent)/apply", body: retryBody)
        }
        notifyTaskGraphChanged(graphID)
    }

    func approveTask(graphID: String, revision: Int, nodeID: String, assignee: ActorRef? = nil, note: String = "", key: String = UUID().uuidString) async throws {
        try await applyTaskOperations(graphID: graphID, revision: revision, operations: [TaskOperations.approve(nodeID: nodeID, assignee: assignee)], note: note, key: key)
    }

    func createQuickTask(conversationID: String, title: String, key: String = UUID().uuidString) async throws {
        let body: [String: JSONValue] = [
            "conversation_id": .string(conversationID),
            "title": .string(title),
            "mode": .string("none"),
            "status": .string("todo"),
            "request_key": .string(key)
        ]
        let receipt: JSONValue = try await send("/im/v1/task-graphs", body: body)
        notifyTaskGraphChanged(receipt["graph_id"].stringValue ?? "")
    }

    nonisolated func notifyTaskGraphChanged(_ graphID: String) {
        Task { @MainActor in
            NotificationCenter.default.post(name: .nanoTaskGraphChanged, object: self, userInfo: ["graph_id": graphID])
        }
    }
}
