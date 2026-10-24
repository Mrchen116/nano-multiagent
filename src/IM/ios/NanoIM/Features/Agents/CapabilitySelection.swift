import Foundation

struct CapabilityTarget: Codable, Equatable, Sendable {
    var kind: String
    var name: String
}
struct CapabilityAction: Codable, Sendable {
    var kind: String
    var name: String
    var enabled: Bool
    var target: CapabilityTarget { .init(kind: kind, name: name) }
}
struct CapabilityBlock: Codable, Equatable, Sendable {
    var code: String
    var target: CapabilityTarget
    var required_by: [String]? = nil
    var message: String {
        switch code {
        case "required_by_feature":
            if let owner = required_by?.first, required_by?.count == 1 { return L("请先关闭「", "Turn off “") + agentFeatureName(owner) + L("」", "” first") }
            return L("请先关闭使用此项的功能，再调整此项", "Turn off the features using this capability first")
        case "fixed_capability": return L("这是当前模式的基础能力，不能关闭", "This capability is required by the current mode")
        case "active_tasks": return L("还有进行中或等待中的任务，请先暂停或结束这些任务，再关闭 Task", "Pause or finish active and waiting tasks before turning off Task")
        case "active_schedules": return L("还有生效中的定时任务，请先停用或删除这些安排，再关闭 Cron", "Disable or delete active schedules before turning off Cron")
        case "capability_busy": return L("该能力正在使用中，请稍后再试", "This capability is in use. Try again shortly")
        default: return L("暂时无法确认能力状态，请稍后再试", "Capability status is unavailable. Try again shortly")
        }
    }
}
struct CapabilityUsage: Decodable, Sendable {
    var checked_at: String
    var active_tasks: Int
    var active_schedules: Int
    var busy: [CapabilityTarget]
    func blocks(removing targets: [CapabilityTarget]) -> [CapabilityBlock] {
        targets.compactMap { target in
            if target.name == "task_graph" && active_tasks > 0 { return .init(code: "active_tasks", target: target) }
            if target.kind == "feature" && target.name == "cron_scheduling" && active_schedules > 0 { return .init(code: "active_schedules", target: target) }
            return busy.contains(target) ? .init(code: "capability_busy", target: target) : nil
        }
    }
}

extension AgentDraft {
    func removingCapabilities(from previous: AgentDraft, capabilities: AgentCapabilities) -> [CapabilityTarget] {
        capabilities.features.filter { (previous.features[$0.key] ?? $0.default_on) && features[$0.key] != true }.map { .init(kind: "feature", name: $0.key) }
        + previous.tool_allowlist.filter { !tool_allowlist.contains($0) }.map { .init(kind: "tool", name: $0) }
        + previous.enabledSkills(candidates: capabilities.skills.map(\.name)).filter { !enabledSkills(candidates: [$0]).contains($0) }.map { .init(kind: "skill", name: $0) }
    }
    /// Applies the dependency data supplied by the owning node without inferring a feature from a tool.
    mutating func changeCapability(_ action: CapabilityAction, capabilities: AgentCapabilities) -> [CapabilityBlock] {
        var next = self
        let definitions = capabilities.features
        for feature in definitions where next.features[feature.key] == nil { next.features[feature.key] = feature.default_on }
        func owners(_ target: CapabilityTarget, _ draft: AgentDraft) -> [String] {
            definitions.filter { feature in
                draft.features[feature.key] == true && feature.requires.values(for: target.kind).contains(target.name)
            }.map(\.key)
        }
        if !action.enabled {
            let required = owners(action.target, next)
            if !required.isEmpty { return [.init(code: "required_by_feature", target: action.target, required_by: required)] }
            if action.kind == "tool" && capabilities.fixedTools(mode: work_mode).contains(action.name) { return [.init(code: "fixed_capability", target: action.target)] }
        }
        func setSkill(_ name: String, _ enabled: Bool, _ draft: inout AgentDraft) {
            if draft.skills_selection_mode == "default_discovery" {
                if enabled { return }
                draft.skills_selection_mode = "explicit_denylist"; draft.skills = []
            }
            if enabled == (draft.skills_selection_mode == "explicit_allowlist") {
                if !draft.skills.contains(name) { draft.skills.append(name) }
            } else { draft.skills.removeAll { $0 == name } }
        }
        if action.kind == "feature" {
            guard let feature = definitions.first(where: { $0.key == action.name }) else { return [.init(code: "capability_unavailable", target: action.target)] }
            next.features[action.name] = action.enabled
            if action.enabled {
                var changed = true
                while changed {
                    changed = false
                    for item in definitions where next.features[item.key] == true {
                        for key in item.requires.features where next.features[key] != true { next.features[key] = true; changed = true }
                    }
                }
                for item in definitions where next.features[item.key] == true {
                    for name in item.requires.tools where !next.tool_allowlist.contains(name) { next.tool_allowlist.append(name) }
                    for name in item.requires.skills { setSkill(name, true, &next) }
                }
            } else {
                for name in feature.requires.tools where !capabilities.fixedTools(mode: work_mode).contains(name) && owners(.init(kind: "tool", name: name), next).isEmpty { next.tool_allowlist.removeAll { $0 == name } }
                for name in feature.requires.skills where owners(.init(kind: "skill", name: name), next).isEmpty { setSkill(name, false, &next) }
            }
        } else if action.kind == "tool" {
            if action.enabled { if !next.tool_allowlist.contains(action.name) { next.tool_allowlist.append(action.name) } }
            else { next.tool_allowlist.removeAll { $0 == action.name } }
        } else { setSkill(action.name, action.enabled, &next) }
        var blocks: [CapabilityBlock] = []
        for feature in definitions where next.features[feature.key] == true {
            for kind in ["feature", "tool", "skill"] {
                for name in feature.requires.values(for: kind) {
                    let available = kind == "feature" ? definitions.contains { $0.key == name } : kind == "tool" ? capabilities.tools.contains { $0.name == name } : capabilities.skills.contains { $0.name == name }
                    let selected = kind == "feature" ? next.features[name] == true : kind == "tool" ? next.tool_allowlist.contains(name) || capabilities.fixedTools(mode: work_mode).contains(name) : next.enabledSkills(candidates: [name]).contains(name)
                    if !available || !selected {
                        let code = available ? "required_by_feature" : "capability_unavailable"
                        let target = CapabilityTarget(kind: kind, name: name)
                        if let index = blocks.firstIndex(where: { $0.code == code && $0.target == target }) { blocks[index].required_by?.append(feature.key) }
                        else { blocks.append(.init(code: code, target: target, required_by: [feature.key])) }
                    }
                }
            }
        }
        if blocks.isEmpty { self = next }
        return blocks
    }
    mutating func initializeCapabilities(_ capabilities: AgentCapabilities) {
        fixed_tools = capabilities.fixed_tools ?? []
        features = Dictionary(uniqueKeysWithValues: capabilities.features.map { ($0.key, $0.default_on) })
        for feature in capabilities.features where feature.default_on { _ = changeCapability(.init(kind: "feature", name: feature.key, enabled: true), capabilities: capabilities) }
    }
    mutating func restoreCapabilities(_ blocks: [CapabilityBlock], capabilities: AgentCapabilities) {
        for block in blocks where block.code != "capability_unavailable" {
            let name = block.target.name
            if block.target.kind == "feature" { features[name] = true }
            if block.target.kind == "tool" && !tool_allowlist.contains(name) { tool_allowlist.append(name) }
            if block.target.kind == "skill" {
                if skills_selection_mode == "explicit_allowlist" && !skills.contains(name) { skills.append(name) }
                if skills_selection_mode == "explicit_denylist" { skills.removeAll { $0 == name } }
            }
        }
        if let feature = capabilities.features.first(where: { features[$0.key] ?? $0.default_on }) { _ = changeCapability(.init(kind: "feature", name: feature.key, enabled: true), capabilities: capabilities) }
    }
}

extension AgentCapabilities {
    func fixedTools(mode: String) -> [String] {
        Array(Set((fixed_tools ?? []) + (mode == "global" ? ["inbox", "conversations", "send_message", "subagent"] : [])))
    }
}
