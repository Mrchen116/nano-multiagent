import Foundation

/// Wire contracts for owner configuration and Gateway-reported capabilities.
struct AgentConfig: Codable, Sendable, Equatable {
    var avatar_variant: Int?
    var agent_id: String
    var owner_id: String
    var node_id: String?
    var display_name: String
    var description: String
    var skills: [String]?
    var skills_selection_mode: String?
    var tool_allowlist: [String]
    var collaboration_scope: String
    var default_model: String?
    var model_fallbacks: [String]
    var reasoning_effort: String?
    var approval_mode: String?
    var work_mode: String
    var workspace_root: String?
    var workspace_is_default: Bool?
    var profile_version: Int
    var features: [String: Bool]
    var heartbeat_json: String?

    var draft: AgentDraft {
        var value = AgentDraft()
        value.agent_id = agent_id; value.display_name = display_name; value.description = description
        value.skills = skills ?? []
        value.skills_selection_mode = skills_selection_mode ?? (value.skills.isEmpty ? "default_discovery" : "explicit_allowlist")
        value.tool_allowlist = tool_allowlist; value.collaboration_scope = collaboration_scope
        value.default_model = default_model ?? ""; value.model_fallbacks = model_fallbacks
        value.reasoning_effort = reasoning_effort ?? ""; value.work_mode = work_mode
        value.approval_mode = approval_mode ?? ""
        value.workspace_root = workspace_root ?? ""; value.features = features
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
    var approval_mode = ""
    var work_mode = "global"
    var workspace_root = ""
    var skills: [String] = []
    var skills_selection_mode = "explicit_denylist"
    var fixed_tools: [String] = []
    var tool_allowlist: [String] = []
    var features: [String: Bool] = [:]
    var initial_role = ""
    var initialRoleIsValid: Bool { initial_role.utf16.count <= 2000 }
    var collaboration_scope = "team"
    var heartbeat = AgentHeartbeat()

    func enabledSkills(candidates: [String]) -> [String] {
        if skills_selection_mode == "explicit_denylist" { return candidates.filter { !skills.contains($0) } }
        return skills_selection_mode == "default_discovery" ? candidates : skills
    }
    func isFeatureEnabled(_ feature: AgentFeature) -> Bool {
        if let explicit = features[feature.key] { return explicit }
        if feature.key == "proactive_planning" && (features["task_graph"] == false || (!tool_allowlist.isEmpty && !effectiveTools.contains("task_graph"))) {
            return false
        }
        return feature.default_on
    }
    var effectiveTools: [String] {
        effectiveTools(capabilities: nil, personal: false)
    }
    func effectiveTools(capabilities: AgentCapabilities?, personal: Bool) -> [String] {
        Array(Set(effectiveSelectedTools(capabilities: capabilities) + fixed_tools + AgentCapabilities.modeFixedTools(mode: work_mode, personal: personal))).sorted()
    }
    func payload(version: Int? = nil, creating: Bool = false, customWorkspace: Bool = false, confirmed: Bool = false, personal: Bool = false, capabilities: AgentCapabilities? = nil) -> [String: JSONValue] {
        var body: [String: JSONValue] = [
            "display_name": .string(display_name.trimmingCharacters(in: .whitespacesAndNewlines)),
            "description": .string(description), "default_model": default_model.isEmpty ? .null : .string(default_model),
            "model_fallbacks": .array(model_fallbacks.map(JSONValue.string)),
            "reasoning_effort": reasoning_effort.isEmpty ? .null : .string(reasoning_effort),
            "approval_mode": approval_mode.isEmpty ? .null : .string(approval_mode),
            "skills": .array(skills.map(JSONValue.string)), "skills_selection_mode": .string(skills_selection_mode),
            "tool_allowlist": .array(sanitizeStaticTools(personal: personal, capabilities: capabilities).map(JSONValue.string)),
            "features": .object(features.mapValues(JSONValue.bool)),
            "collaboration_scope": .string(collaboration_scope)
        ]
        if let version { body["profile_version"] = .number(Double(version)) }
        if let data = try? JSONEncoder().encode(heartbeat), let value = try? JSONDecoder().decode(JSONValue.self, from: data) { body["heartbeat"] = value }
        if creating {
            if !initial_role.isEmpty { body["initial_role"] = .string(initial_role) }
            body["agent_id"] = .string(agent_id.trimmingCharacters(in: .whitespacesAndNewlines))
            body["work_mode"] = .string(work_mode)
            body["workspace_root"] = customWorkspace ? .string(workspace_root.trimmingCharacters(in: .whitespacesAndNewlines)) : .null
            body["confirm_existing_workspace"] = .bool(confirmed)
        }
        return body
    }
    func previewPayload(capabilities: AgentCapabilities?, creating: Bool, customWorkspace: Bool, personal: Bool = false) -> [String: JSONValue] {
        let skillIDs = skills_selection_mode == "default_discovery" ? capabilities?.skills.map(\.name) ?? [] : skills
        let resolvedFeatures = effectiveFeatures(capabilities: capabilities, personal: personal)
        var body: [String: JSONValue] = ["scenario": .string("direct"), "features": .object(resolvedFeatures.mapValues(JSONValue.bool)), "tool_ids": .array(effectiveTools(capabilities: capabilities, personal: personal).map(JSONValue.string)), "skill_ids": .array(skillIDs.map(JSONValue.string)), "skills_selection_mode": .string(skills_selection_mode), "work_mode": .string(work_mode)]
        body["heartbeat_enabled"] = .bool(resolvedFeatures["heartbeat"] ?? false)
        body["cron_enabled"] = .bool(resolvedFeatures["cron_scheduling"] ?? false)
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
    var name: String; var description: String?; var default_on: Bool?; var enabled: Bool?; var location: String?; var source_group: String?
    var plugin_bundle: String?; var plugin_title: JSONValue?
    var id: String { location ?? name }
    var localizedPluginTitle: String? {
        if let plugin_title {
            if let string = plugin_title.stringValue, !string.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { return string }
            if let values = plugin_title.objectValue {
                let candidate = values[L("zh", "en")]?.stringValue ?? values[L("zh-CN", "en-US")]?.stringValue ?? values["en"]?.stringValue ?? values.sorted { $0.key < $1.key }.first?.value.stringValue
                if let candidate, !candidate.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { return candidate }
            }
        }
        if let plugin_bundle, !plugin_bundle.isEmpty { return plugin_bundle }
        return nil
    }
    func skillGroup(workspaceRoot: String) -> String {
        if let source_group { return source_group }
        let path = (location ?? "").replacingOccurrences(of: "\\", with: "/")
        let root = workspaceRoot.replacingOccurrences(of: "\\", with: "/")
        if !root.isEmpty, path.hasPrefix(root.hasSuffix("/") ? root : root + "/") { return "workspace" }
        if default_on == true || path.contains("/.nanoassistant/skills/") { return "global" }
        return "compatibility"
    }
}
struct AgentModelOption: Codable, Identifiable, Sendable {
    var name: String; var provider: String?; var reasoning: Reasoning?
    var display_name: String?; var provider_display_name: String?
    var id: String { name }
    var displayLabel: String {
        let model = display_name ?? name.split(separator: "/", maxSplits: 1).last.map(String.init) ?? name
        return model + ((provider_display_name ?? provider).map { " · " + $0 } ?? "")
    }
    struct Reasoning: Codable, Sendable { var kind: String; var `default`: String?; var levels: [String]? }
}
struct AgentFeature: Codable, Identifiable, Sendable {
    var key: String; var roles: [String]? = nil; var modes: [String]? = nil; var label_i18n: String; var help_i18n: String; var default_on: Bool; var available: Bool; var requires: Requirements
    struct Requirements: Codable, Sendable {
        var features: [String]; var tools: [String]; var skills: [String]
        func values(for kind: String) -> [String] { kind == "feature" ? features : kind == "tool" ? tools : skills }
    }
    var id: String { key }
}
struct AgentCapabilities: Codable, Sendable {
    var inherited_approval_rules: String? = nil
    var fixed_tools: [String]? = nil
    var node_id: String; var models: [AgentModelOption]; var skills: [AgentOption]; var tools: [AgentOption]
    var platform_default_model: String?; var default_workspace_template: String?; var features: [AgentFeature]
    func featuresForMode(mode: String, personal: Bool = false) -> [AgentFeature] {
        let role = personal ? "personal" : "root"
        let effectiveMode = personal ? "global" : (mode == "single_thread" ? "single_thread" : "global")
        return features.filter { feature in
            let roleMatch = feature.roles.map { $0.contains(role) } ?? true
            let modeMatch = feature.modes.map { $0.contains(effectiveMode) } ?? (personal || effectiveMode == "global" || feature.key != "proactive_planning")
            return roleMatch && modeMatch
        }
    }
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
    var statistics_since: String?; var period_start: String; var period_end: String
    var totalCalls: Int { skills.reduce(0) { $0 + $1.use_count } }
    var periodCalls: Int { heatmap_data.reduce(0, +) }
    struct Day: Identifiable { let date: String; let count: Int; var id: String { date } }
    func days(values: [Int], since: String?) -> [Day] {
        guard let since, let start = ISO8601DateFormatter().date(from: period_start + "T00:00:00Z") else { return [] }
        let formatter = ISO8601DateFormatter()
        return values.enumerated().compactMap { index, count in
            let date = String(formatter.string(from: start.addingTimeInterval(Double(index) * 86400)).prefix(10))
            return date >= String(since.prefix(10)) && date <= period_end ? Day(date: date, count: count) : nil
        }
    }
    struct Skill: Decodable, Identifiable, Sendable {
        var skill_id: String; var name: String; var source: String; var state: String; var use_count: Int
        var statistics_since: String?
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
