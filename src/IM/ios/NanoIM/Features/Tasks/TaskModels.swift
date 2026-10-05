import Foundation
import CoreGraphics

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
}
struct TaskSummary: Codable, Identifiable, Sendable {
    var graph_id: String; var root_node_id: String; var revision: Int; var updated_at: String
    var updated_by: String; var relative_url: String; var title: String; var mode: String; var status: String
    var id: String { graph_id }
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
    switch status { case "todo": return L("待办", "To do"); case "doing": return L("进行中", "In progress"); case "done": return L("完成", "Done"); case "paused": return L("暂停", "Paused"); case "dropped": return L("已放弃", "Dropped"); default: return status }
}
