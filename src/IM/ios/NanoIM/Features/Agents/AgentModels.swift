import Foundation

/// Wire contracts for owner configuration and Gateway-reported capabilities.
struct AgentConfig: Codable, Sendable, Equatable {
    var agent_id: String
    var owner_id: String
    var node_id: String?
    var display_name: String
    var description: String
    var skills: [String]
    var skills_selection_mode: String?
    var tool_allowlist: [String]
    var group_reply_policy: String
    var default_model: String?
    var model_fallbacks: [String]
    var reasoning_effort: String?
    var work_mode: String
    var workspace_root: String?
    var workspace_is_default: Bool?
    var profile_version: Int
    var features: [String: Bool]
    var custom_prompt: String?
    var heartbeat_json: String?

    var draft: AgentDraft {
        var value = AgentDraft()
        value.agent_id = agent_id; value.display_name = display_name; value.description = description
        value.skills = skills
        value.skills_selection_mode = skills_selection_mode ?? (skills.isEmpty ? "default_discovery" : "explicit_allowlist")
        value.tool_allowlist = tool_allowlist; value.group_reply_policy = group_reply_policy
        value.default_model = default_model ?? ""; value.model_fallbacks = model_fallbacks
        value.reasoning_effort = reasoning_effort ?? ""; value.work_mode = work_mode
        value.workspace_root = workspace_root ?? ""; value.features = features
        value.custom_prompt = custom_prompt ?? ""
        if let data = heartbeat_json?.data(using: .utf8), let heartbeat = try? JSONDecoder().decode(AgentHeartbeat.self, from: data) {
            value.heartbeat = heartbeat
        }
        return value
    }
}

struct AgentHeartbeat: Codable, Sendable, Equatable {
    var every: String? = nil
    var active_hours: Hours? = nil
    struct Hours: Codable, Sendable, Equatable {
        var start: String? = nil
        var end: String? = nil
        var timezone: String? = nil
    }
}

struct AgentDraft: Equatable, Sendable {
    var agent_id = ""
    var display_name = ""
    var description = ""
    var default_model = ""
    var model_fallbacks: [String] = []
    var reasoning_effort = ""
    var work_mode = "single_thread"
    var workspace_root = ""
    var skills: [String] = []
    var skills_selection_mode = "explicit_allowlist"
    var tool_allowlist: [String] = []
    var features: [String: Bool] = [:]
    var custom_prompt = ""
    var group_reply_policy = "MENTION"
    var heartbeat = AgentHeartbeat()

    var effectiveTools: [String] {
        work_mode == "global" ? Array(Set(tool_allowlist + ["inbox", "conversations", "send_message", "agent"])).sorted() : tool_allowlist
    }
    mutating func setFeature(_ feature: AgentFeature, enabled: Bool) {
        features[feature.key] = enabled
        if enabled, let tool = feature.requires_tool, !tool_allowlist.contains(tool) {
            tool_allowlist.append(tool)
        }
    }
    func payload(version: Int? = nil, creating: Bool = false, customWorkspace: Bool = false, confirmed: Bool = false) -> [String: JSONValue] {
        var body: [String: JSONValue] = [
            "display_name": .string(display_name.trimmingCharacters(in: .whitespacesAndNewlines)),
            "description": .string(description), "default_model": default_model.isEmpty ? .null : .string(default_model),
            "model_fallbacks": .array(model_fallbacks.map(JSONValue.string)),
            "reasoning_effort": reasoning_effort.isEmpty ? .null : .string(reasoning_effort),
            "skills": .array(skills.map(JSONValue.string)), "skills_selection_mode": .string(skills_selection_mode),
            "tool_allowlist": .array(effectiveTools.map(JSONValue.string)),
            "features": .object(features.mapValues(JSONValue.bool)), "custom_prompt": .string(custom_prompt),
            "group_reply_policy": .string(group_reply_policy)
        ]
        if let version { body["profile_version"] = .number(Double(version)) }
        if let data = try? JSONEncoder().encode(heartbeat), let value = try? JSONDecoder().decode(JSONValue.self, from: data) { body["heartbeat"] = value }
        if creating {
            body["agent_id"] = .string(agent_id.trimmingCharacters(in: .whitespacesAndNewlines))
            body["work_mode"] = .string(work_mode)
            body["workspace_root"] = customWorkspace ? .string(workspace_root.trimmingCharacters(in: .whitespacesAndNewlines)) : .null
            body["confirm_existing_workspace"] = .bool(confirmed)
        }
        return body
    }
    func previewPayload(capabilities: AgentCapabilities?, creating: Bool, customWorkspace: Bool) -> [String: JSONValue] {
        let skillIDs = skills_selection_mode == "default_discovery" ? capabilities?.skills.map(\.name) ?? [] : skills
        var body: [String: JSONValue] = ["scenario": .string("direct"), "features": .object(features.mapValues(JSONValue.bool)), "custom_prompt": .string(custom_prompt), "tool_ids": .array(effectiveTools.map(JSONValue.string)), "skill_ids": .array(skillIDs.map(JSONValue.string)), "work_mode": .string(work_mode)]
        if creating {
            body["agent_id_hint"] = .string(agent_id)
            body["workspace_mode"] = .string(customWorkspace ? "custom" : "default")
            body["workspace_root"] = customWorkspace ? .string(workspace_root) : .null
        }
        return body
    }
}

struct AgentNode: Codable, Identifiable, Sendable {
    var node_id: String; var owner_id: String; var node_name: String; var status: String; var alias: String?
    var id: String { node_id }
    var name: String { alias.flatMap { $0.isEmpty ? nil : $0 } ?? node_name }
}
struct AgentOption: Codable, Identifiable, Sendable {
    var name: String; var description: String?; var default_on: Bool?; var location: String?; var source_group: String?
    var id: String { location ?? name }
}
struct AgentModelOption: Codable, Identifiable, Sendable {
    var name: String; var provider: String?; var reasoning: Reasoning?
    var id: String { name }
    struct Reasoning: Codable, Sendable { var kind: String; var `default`: String?; var levels: [String]? }
}
struct AgentFeature: Codable, Identifiable, Sendable {
    var key: String; var label_i18n: String; var help_i18n: String; var default_on: Bool; var available: Bool; var requires_tool: String?
    var id: String { key }
}
struct AgentCapabilities: Codable, Sendable {
    var node_id: String; var models: [AgentModelOption]; var skills: [AgentOption]; var tools: [AgentOption]
    var platform_default_model: String?; var default_workspace_template: String?; var features: [AgentFeature]
}
struct AgentContactPage: Decodable, Sendable { var items: [Contact]; var next_cursor: String? }
struct AgentPrompt: Decodable, Sendable { var prompt: String }
struct AgentChatCreated: Decodable, Sendable { var id: String }
struct AgentHeartbeatDocument: Decodable, Sendable { var content: String; var node_online: Bool }
struct AgentCronJob: Decodable, Sendable, Identifiable {
    var id: String; var name: String; var schedule: [String: JSONValue]; var instruction: String; var enabled: Bool; var delete_after_run: Bool
}
struct AgentSkillUsage: Decodable, Sendable {
    var agent_id: String; var node_id: String?; var node_online: Bool; var skills: [Skill]; var heatmap_data: [Int]; var health: Health
    struct Skill: Decodable, Identifiable, Sendable {
        var skill_id: String; var name: String; var source: String; var state: String; var use_count: Int
        var last_used_at: String?; var created_at: String?; var archived_at: String?; var archive_error: String?
        var session_refs: [SessionRef]; var recent_call_keys: [String]; var trend_buckets: [Int]
        var id: String { skill_id }
    }
    struct SessionRef: Decodable, Sendable { var session_id: String?; var tool_call_id: String?; var timestamp: String? }
    struct Health: Decodable, Sendable { var created_auto_total: Int; var active_auto_total: Int; var used_auto_total: Int }
}

func agentPath(_ id: String) -> String { "/im/v1/agents/" + agentSegment(id) }
func agentSegment(_ id: String) -> String { id.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? id }

extension JSONValue {
    var agentObject: [String: JSONValue] { if case .object(let value) = self { return value }; return [:] }
    var agentArray: [JSONValue] { if case .array(let value) = self { return value }; return [] }
    var agentString: String { if case .string(let value) = self { return value }; return "" }
}
