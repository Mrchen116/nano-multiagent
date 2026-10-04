import Foundation

struct AgentWorkItem: Codable, Identifiable, Sendable {
    var item_id: String; var seq: Int; var kind: String; var observed_at: String?; var payload: [String: JSONValue]
    var id: String { item_id }
}
struct AgentWorkTurn: Codable, Identifiable, Sendable {
    var description: String?; var session_id: String; var turn_id: String; var scope: String?; var job_id: String?; var run_id: String?
    var status: String; var origin: JSONValue?; var trigger: [String: JSONValue]?; var model_id: String?
    var started_at: String?; var finished_at: String?; var elapsed_ms: Double?; var usage: JSONValue?
    var items: [AgentWorkItem]; var next_items_cursor: String?
    var id: String { session_id + ":" + turn_id }
}
struct AgentWorkSession: Codable, Identifiable, Sendable, Hashable {
    var session_id: String; var scope: String; var job_id: String?; var trigger: String?; var parent_session_id: String?
    var parent_tool_call_id: String?; var child_agent_id: String?; var description: String?; var title: String?; var status: String?
    var id: String { session_id }
    var label: String { description ?? title ?? child_agent_id ?? job_id ?? session_id }
}
struct AgentWorkPage: Codable, Sendable {
    var root_agent_id: String?; var main_session_id: String?; var revision: Int?; var node_connection_state: String?; var main_execution: String?
    var latest_main_usage: JSONValue?; var other_executions: [AgentWorkSession]?; var control_items: [AgentWorkItem]?
    var turns: [AgentWorkTurn]; var next_cursor: String?
}
struct AgentWorkItemPage: Codable, Sendable { var items: [AgentWorkItem]; var next_cursor: String? }


/// Avoid repeated reasoning snapshots and background sidecars within one reported turn.
func agentVisibleWorkItems(_ source: [AgentWorkItem]) -> [AgentWorkItem] {
    var reasoningByGroup: [String: String] = [:]
    var backgroundKeys = Set<String>()
    return source.sorted { $0.seq < $1.seq }.compactMap { original in
        var item = original
        let reasoning = item.payload["reasoning_content"]?.agentString.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let group = item.payload["group_id"]?.agentString ?? ""
        if !reasoning.isEmpty && !group.isEmpty {
            let key = (item.payload["run_id"]?.agentString ?? "") + ":" + group
            if let previous = reasoningByGroup[key], reasoning.hasPrefix(previous) {
                item.payload["reasoning_content"] = .string(String(reasoning.dropFirst(previous.count)).trimmingCharacters(in: .whitespacesAndNewlines))
            }
            reasoningByGroup[key] = reasoning
        }
        func keepBackground(_ value: JSONValue) -> Bool {
            let data = value.agentObject
            guard let id = data["task_id"]?.agentString, !id.isEmpty else { return true }
            return backgroundKeys.insert((data["task_type"]?.agentString ?? "") + ":" + id).inserted
        }
        if item.kind == "background_return", !keepBackground(.object(item.payload)) { return nil }
        if let values = item.payload["background_returns"]?.agentArray {
            item.payload["background_returns"] = .array(values.filter(keepBackground))
        }
        return item
    }
}
