import Foundation
import Testing
@testable import NanoIM

struct CapabilitySelectionTests {
    @Test func detectsBusySkillWithdrawalAcrossSelectionModes() {
        let caps = AgentCapabilities(node_id: "n", models: [], skills: [.init(name:"ordinary-method")], tools: [], features: [])
        for mode in ["default_discovery", "explicit_allowlist", "explicit_denylist"] {
            var previous = AgentDraft(); previous.skills_selection_mode = mode
            previous.skills = mode == "explicit_allowlist" ? ["ordinary-method"] : []
            var next = previous
            #expect(next.changeCapability(.init(kind:"skill",name:"ordinary-method",enabled:false),capabilities:caps).isEmpty)
            let target = CapabilityTarget(kind:"skill",name:"ordinary-method")
            #expect(next.removingCapabilities(from:previous,capabilities:caps) == [target])
            let usage = CapabilityUsage(checked_at:"now",active_tasks:0,active_schedules:0,busy:[target])
            #expect(usage.blocks(removing:next.removingCapabilities(from:previous,capabilities:caps)) == [.init(code:"capability_busy",target:target)])
        }
    }
    struct Fixture: Decodable {
        struct Definition: Decodable {
            var key: String; var default_on: Bool; var requires: AgentFeature.Requirements
            var feature: AgentFeature { .init(key: key, label_i18n: key, help_i18n: key, default_on: default_on, available: true, requires: requires) }
        }
        struct Draft: Decodable {
            var features: [String: Bool]?
            var tool_allowlist: [String]?
            var skills: [String]?
            var skills_selection_mode: String?
            var work_mode: String?
            var value: AgentDraft {
                var result = AgentDraft(); result.features = features ?? [:]; result.tool_allowlist = tool_allowlist ?? []
                result.skills = skills ?? []; result.skills_selection_mode = skills_selection_mode ?? (result.skills.isEmpty ? "default_discovery" : "explicit_allowlist")
                result.work_mode = work_mode ?? "single_thread"; return result
            }
        }
        struct Catalog: Decodable { var tools: [String]?; var skills: [String]?; var fixed_tools: [String]? }
        struct Result: Decodable { var draft: Draft; var blocks: [CapabilityBlock] }
        struct Case: Decodable { var name: String; var draft: Draft; var catalog: Catalog; var actions: [CapabilityAction]; var expected: Result }
        var definitions: [Definition]; var cases: [Case]
    }
    @Test func sharedSelectionFixtures() throws {
        var root = URL(fileURLWithPath: #filePath)
        for _ in 0..<5 { root.deleteLastPathComponent() }
        let fixture = try JSONDecoder().decode(Fixture.self, from: Data(contentsOf: root.appendingPathComponent("packages/product-contracts/tests/fixtures/capabilities.json")))
        for item in fixture.cases {
            let features = fixture.definitions.map(\.feature)
            let tools = item.catalog.tools ?? Array(Set(features.flatMap { $0.requires.tools }))
            let skills = item.catalog.skills ?? Array(Set(features.flatMap { $0.requires.skills }))
            let caps = AgentCapabilities(fixed_tools: item.catalog.fixed_tools ?? ["notes", "history", "new_context", "get_context_remaining"], node_id: "n", models: [], skills: skills.map { AgentOption(name: $0) }, tools: tools.map { AgentOption(name: $0) }, features: features)
            var draft = item.draft.value
            var blocks: [CapabilityBlock] = []
            for action in item.actions { blocks = draft.changeCapability(action, capabilities: caps) }
            #expect(draft.features == item.expected.draft.value.features, Comment(rawValue: item.name))
            #expect(Set(draft.tool_allowlist) == Set(item.expected.draft.value.tool_allowlist), Comment(rawValue: item.name))
            #expect(Set(draft.skills) == Set(item.expected.draft.value.skills), Comment(rawValue: item.name))
            #expect(draft.skills_selection_mode == item.expected.draft.value.skills_selection_mode, Comment(rawValue: item.name))
            #expect(blocks == item.expected.blocks, Comment(rawValue: item.name))
        }
    }
}
