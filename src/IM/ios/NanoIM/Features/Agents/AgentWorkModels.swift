import Foundation

struct AgentWorkItem: Codable, Identifiable, Sendable {
    var item_id: String; var seq: Int; var kind: String; var observed_at: String?; var revision: Int?; var has_exact_child: Bool?; var payload: [String: JSONValue]
    var id: String { item_id }
}
/// A confirmed delivery can identify a chat message. Read its current text with chat permissions.
struct WorkDelivery: Equatable {
    let conversation: String
    let message: String

    init?(_ item: AgentWorkItem) {
        guard item.kind == "tool" else { return nil }
        let p = item.payload
        let fact = p["work_facts"]?.agentArray.last { $0["type"].stringValue == "message_sent" }
        let detail = p["detail"]?.agentObject
        let sent = p["name"]?.stringValue == "send_message" && detail?["status"]?.stringValue == "sent"
        guard let source = fact?.agentObject ?? (sent ? detail : nil),
              let target = (source["conversation_id"] ?? source["target"])?.stringValue, !target.isEmpty, !target.hasPrefix("local:"),
              let id = source["message_id"]?.stringValue, !id.isEmpty else { return nil }
        conversation = target
        message = id
    }
}

struct AgentWorkTurn: Codable, Identifiable, Sendable {
    var description: String?; var session_id: String; var turn_id: String; var scope: String?; var job_id: String?; var run_id: String?
    var status: String; var origin: JSONValue?; var trigger: [String: JSONValue]?; var model_id: String?
    var started_at: String?; var finished_at: String?; var elapsed_ms: Double?; var usage: JSONValue?
    var items: [AgentWorkItem]; var next_items_cursor: String?; var seq: Int?; var items_deferred: Bool?
    var maintenance_title: String?; var maintenance_stage: String?
    var id: String { session_id + ":" + turn_id }
    var title: String {
        if let maintenance_title, !maintenance_title.isEmpty { return maintenance_title }
        let kind = trigger?["kind"]?.agentString ?? (origin?.agentString.isEmpty == false ? origin?.agentString : origin?["kind"].stringValue) ?? ""
        switch kind {
        case "inbox": return L("收到新消息", "New messages")
        case "inbox-background": return L("近况同步", "Catch up on recent conversations")
        case "heartbeat": return L("主动检查", "Proactive check")
        case "cron": return (trigger?["source"]?.agentString == "manual" ? L("手动运行定时任务", "Scheduled task run manually") : L("定时任务", "Scheduled task")) + (job_id.map { " · " + $0 } ?? "")
        case "human", "user": return L("用户输入", "User input")
        case "background_task": return description ?? (scope == "subagent" ? L("子 Agent 执行", "Child Agent execution") : L("后台结果返回", "Background result"))
        default: return description ?? agentScopeName(scope)
        }
    }
}
struct AgentWorkSession: Codable, Identifiable, Sendable, Hashable {
    var session_id: String; var scope: String; var job_id: String?; var trigger: String?; var parent_session_id: String?
    var parent_tool_call_id: String?; var child_agent_id: String?; var description: String?; var title: String?; var status: String?
    var id: String { session_id }
    var label: String { description ?? title ?? child_agent_id ?? job_id ?? session_id }
    var distinctLabel: String { label == id ? id : label + " · " + String(id.suffix(8)) }
}
struct AgentWorkPage: Codable, Sendable {
    var root_agent_id: String?; var main_session_id: String?; var revision: Int?; var node_connection_state: String?; var main_execution: String?
    var record_sync_state: String?
    var latest_main_usage: JSONValue?; var other_executions: [AgentWorkSession]?; var control_items: [AgentWorkItem]?
    var turns: [AgentWorkTurn]; var next_cursor: String?; var next_turn_id: String?; var catalog: String?
    var timeline: String?; var next_turn_seq: Int?
}
struct AgentWorkItemPage: Codable, Sendable { var items: [AgentWorkItem]; var next_cursor: String?; var revision: Int? }

struct AgentWorkCatalogPage: Codable, Sendable { var sessions: [AgentWorkSession]; var next_cursor: String? }

/// Retains the adjacent turn IDs confirmed by each page, including a displaced head.
struct AgentWorkHistory {
    private var records: [String: AgentWorkTurn] = [:]
    private var older: [String: String] = [:]
    private var earlier = Set<String>()

    var turns: [AgentWorkTurn] { records.values.sorted { ($0.seq ?? 0) > ($1.seq ?? 0) } }

    private var combined = false

    private func position(_ turn: AgentWorkTurn) -> String {
        if combined, let seq = turn.seq { return String(seq) }
        return turn.turn_id
    }

    mutating func merge(_ page: AgentWorkPage, after boundary: AgentWorkTurn? = nil) {
        combined = page.timeline == "combined"
        if let boundary {
            older[boundary.id] = page.turns.first.map { position($0) }
            earlier.remove(boundary.id)
        }
        for (offset, turn) in page.turns.enumerated() {
            if boundary != nil && records[turn.id] != nil { continue }
            records[turn.id] = turn
            let next = page.turns.dropFirst(offset + 1).first
            older[turn.id] = next.map { position($0) } ?? (combined ? page.next_turn_seq.map { String($0) } : page.next_turn_id)
            if offset + 1 == page.turns.count && page.next_cursor != nil { earlier.insert(turn.id) }
            else { earlier.remove(turn.id) }
        }
    }

    /// Focus neighbors belong to the anchored session; combined pages have a different ordering.
    mutating func merge(_ focus: AgentWorkFocus) {
        let turn = focus.turn
        guard !combined, records[turn.id] == nil else { return }
        records[turn.id] = turn
        older[turn.id] = focus.older_turn_id
        if let newer = focus.newer_turn_id {
            older[turn.session_id + ":" + newer] = turn.turn_id
        }
    }

    func hasGap(after turn: AgentWorkTurn, before following: AgentWorkTurn) -> Bool {
        older[turn.id] != position(following)
    }

    func hasEarlier(after turn: AgentWorkTurn) -> Bool { older[turn.id] != nil || earlier.contains(turn.id) }
}

func agentScopeName(_ scope: String?) -> String {
    switch scope?.lowercased() { case "main", "global_main": return L("主执行", "Main execution"); case "subagent", "child": return L("子执行", "Child execution"); case "cron", "job": return L("定时任务", "Scheduled task"); case "heartbeat": return L("主动检查", "Proactive check"); case "workflow": return L("Workflow 执行", "Workflow execution"); default: return L("执行轮次", "Execution turn") }
}


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

struct AgentWorkFocus: Decodable, Sendable {
    let turn: AgentWorkTurn
    let newer_turn_id: String?
    let older_turn_id: String?
}

struct AgentActivitySession: Decodable, Identifiable, Sendable {
    let scope: String?
    let runtime: String?
    let has_work_records: Bool?
    var canOpenRecords: Bool { scope != "worker" || has_work_records == true }
    let session_id: String
    let title: String?
    let status: String
    var id: String { session_id }
}

struct AgentActivityPage: Decodable, Sendable {
    struct Tool: Decodable, Sendable { let name: String; let label: String?; let status: String? }
    let revision: Int
    let node_connection_state: String
    let record_sync_state: String
    let main_execution: String
    let latest_tool: Tool?
    let running_count: Int?
    let waiting_permission_count: Int?
    let sessions: [AgentActivitySession]
    let next_cursor: String?

    var confirmedChildren: Bool {
        node_connection_state == "online" && record_sync_state == "current" && running_count != nil && waiting_permission_count != nil
    }
}

struct AgentDelegationNode: Decodable, Identifiable, Sendable {
    struct Usage: Decodable, Sendable {
        let total_tokens: Int?
        let reported_turns: Int
        let missing_turns: Int
        var turns: Int { reported_turns + missing_turns }
    }
    let scope: String?
    let runtime: String?
    let has_work_records: Bool?
    var canOpenRecords: Bool { scope != "worker" || has_work_records == true }
    let session_id: String
    let parent_session_id: String?
    let title: String?
    let status: String
    let last_active_at: String?
    let ancestor_only: Bool?
    let usage: Usage?
    var id: String { session_id }
}

struct AgentDelegationPage: Decodable, Sendable {
    let from: String
    let until: String
    let revision: Int
    let node_connection_state: String
    let record_sync_state: String
    let main_session_id: String?
    let nodes: [AgentDelegationNode]
    let next_cursor: String?
}
