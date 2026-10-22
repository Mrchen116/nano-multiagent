import Foundation
import CoreGraphics

struct TaskWait: Codable, Sendable, Hashable {
    var reason: String; var schedule_id: String; var owner_agent_id: String; var session_id: String; var next_check_at: String
}
struct TaskWaitHealth: Codable, Sendable, Hashable {
    var state: String; var checked_at: String; var reason_code: String?
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
    var wait: TaskWait?
    var wait_health: TaskWaitHealth?

}
struct TaskDependency: Codable, Sendable, Hashable { let from: String; let to: String }
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
}
struct TaskSummary: Codable, Identifiable, Sendable {
    var graph_id: String; var root_node_id: String; var revision: Int; var updated_at: String
    var updated_by: String; var relative_url: String; var title: String; var mode: String; var status: String
    var node_id: String?
    var scope_id: String?
    var parent_path: [TaskPathPart]?
    var conversation: TaskConversation
    var created_by: ActorRef?
    var assignee: ActorRef?
    var direct_counts: TaskCounts?
    var wait: TaskWait?
    var wait_health: TaskWaitHealth?
    var id: String { graph_id + ":" + (node_id ?? root_node_id) }
}
struct TaskGraphPage: Decodable, Sendable { let items: [TaskSummary]; let next_cursor: String?; let total: Int }
struct TaskActivity: Decodable, Identifiable, Sendable {
    let graph_id: String; let node_id: String; let scope_id: String?; let title: String
    let root_title: String; let status: String; let updated_at: String
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

func taskStatus(_ status: String) -> String {
    switch status { case "todo": return L("待办", "To do"); case "doing": return L("推进中", "Advancing"); case "waiting": return L("等待中", "Waiting"); case "done": return L("完成", "Done"); case "paused": return L("暂缓", "Paused"); case "in_review": return L("待确认", "In review"); case "closed": return L("已关闭", "Closed"); default: return status }
}

struct TaskConversation: Codable, Sendable, Hashable {
    var id: String
    var title: String
    var visibility: String
    var dissolved_at: String?
    var is_member: Bool
    var can_write: Bool
}
struct TaskCounts: Codable, Sendable, Hashable {
    var todo: Int; var doing: Int; var waiting: Int; var in_review: Int; var done: Int; var paused: Int; var closed: Int; var total: Int
    var summary: String { L("直属子任务：已完成 \(done) / 共 \(total)", "Direct subtasks: \(done) done / \(total) total") }
}
struct TaskPathPart: Codable, Sendable, Hashable { var id: String; var title: String }
let taskStatuses = ["todo", "doing", "waiting", "in_review", "done", "paused", "closed"]
let taskGroups = ["todo", "doing", "in_review", "done", "closed"]
func taskGroupTitle(_ group: String) -> String { group == "doing" ? L("进行中", "In progress") : taskStatus(group) }
func taskEditableStatuses(_ current: String?) -> [String] { taskStatuses.filter { $0 != "waiting" || current == "waiting" } }
func taskGroupContains(_ group: String, status: String) -> Bool { group == status || (group == "todo" && status == "paused") || (group == "doing" && status == "waiting") }

extension ActorRef {
    var taskKey: String { type + ":" + id }
    var taskName: String { display_name ?? id }
    var taskValue: JSONValue { .object(["type": .string(type), "id": .string(id)]) }
}

struct TaskDraft: Equatable {
    var title = ""
    var description = ""
    var result = ""
    var mode = "dag"
    var status = "todo"
    var assignee: ActorRef?
    var changeNote = ""
    init(node: TaskNode? = nil) {
        if let node { title = node.title; description = node.description; result = node.result; mode = node.mode; status = node.status; assignee = node.assignee }
    }
    func operations(node: TaskNode?, parentID: String?) -> [JSONValue] {
        if let node {
            var result: [JSONValue] = [.object(["op": .string("update_task"), "node_id": .string(node.id), "patch": .object(["title": .string(title), "description": .string(description), "result": .string(self.result), "status": .string(status)])])]
            if assignee?.taskKey != node.assignee?.taskKey { result.append(.object(["op": .string("set_assignee"), "node_id": .string(node.id), "assignee": assignee?.taskValue ?? .null])) }
            return result
        }
        return [.object(["op": .string("add_task"), "client_ref": .string("new"), "container_id": .string(parentID ?? ""), "title": .string(title), "description": .string(description), "mode": .string(mode), "status": .string(status), "result": .string(result), "assignee": assignee?.taskValue ?? .null])]
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
    func applyTask(_ graph: TaskGraph, operations: [JSONValue], note: String = "", key: String) async throws {
        let _: JSONValue = try await send("/im/v1/task-graphs/\(graph.graph_id.pathComponent)/apply", body: ["base_revision": .number(Double(graph.revision)), "request_key": .string(key), "operations": .array(operations), "change_note": .string(note)] as [String: JSONValue])
    }
}
