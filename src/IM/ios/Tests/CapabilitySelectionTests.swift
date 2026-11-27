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
    @Test func dreamingOffPreservesImmediateMemoryTools() {
        let tools = ["read", "write", "edit", "memory_maintenance"]
        let feature = AgentFeature(key:"dreaming", label_i18n:"feature.dreaming.label", help_i18n:"feature.dreaming.help", default_on:true, available:true, requires:.init(features:[],tools:tools,skills:[]))
        let caps = AgentCapabilities(node_id:"n",models:[],skills:[],tools:tools.map { AgentOption(name:$0) },features:[feature])
        var draft = AgentDraft(); draft.tool_allowlist = tools; draft.features = ["dreaming":true]
        #expect(draft.changeCapability(.init(kind:"feature",name:"dreaming",enabled:false),capabilities:caps).isEmpty)
        #expect(draft.features["dreaming"] == false)
        #expect(draft.tool_allowlist == tools)
    }
    @Test func pluginManagementContinuityPluginBlocksAndModeSanitization() {
        let pluginFeature = AgentFeature(
            key: "plugin_management",
            label_i18n: "feature.plugin_management.label",
            help_i18n: "feature.plugin_management.help",
            default_on: true,
            available: true,
            requires: .init(features: [], tools: ["plugin_manager", "cordis_inspect_list", "cordis_inspect_query"], skills: ["nano-plugin-development"])
        )
        let caps = AgentCapabilities(
            fixed_tools: ["notes"],
            node_id: "n",
            models: [],
            skills: [.init(name: "nano-plugin-development")],
            tools: [
                .init(name: "read"),
                .init(name: "send_message"),
                .init(name: "plugin_manager"),
                .init(name: "cordis_inspect_list"),
                .init(name: "cordis_inspect_query"),
                .init(name: "notes", enabled: true, source_group: "workspace", plugin_bundle: "dsh-agent-context", plugin_title: .string("Context")),
                .init(name: "roll_dice", enabled: true, source_group: "workspace", plugin_bundle: "dice-plugin", plugin_title: .string("Dice")),
            ],
            features: [pluginFeature]
        )

        var legacyAllowed = AgentDraft()
        legacyAllowed.work_mode = "global"
        legacyAllowed.tool_allowlist = ["plugin_manager", "read", "notes", "inbox"]
        legacyAllowed.skills_selection_mode = "default_discovery"
        #expect(legacyAllowed.effectiveFeatures(capabilities: caps)["plugin_management"] == true)
        #expect(Set(legacyAllowed.effectiveSelectedTools(capabilities: caps)) == Set(["plugin_manager", "read", "notes", "inbox", "cordis_inspect_list", "cordis_inspect_query"]))
        #expect(legacyAllowed.sanitizeStaticTools(personal: false, capabilities: caps) == ["plugin_manager", "read"])

        let pluginBlock = legacyAllowed.changeCapability(.init(kind: "tool", name: "notes", enabled: false), capabilities: caps)
        #expect(pluginBlock == [.init(code: "provided_by_plugin", target: .init(kind: "tool", name: "notes"), plugin: "Context")])

        var legacyRestricted = AgentDraft()
        legacyRestricted.work_mode = "single_thread"
        legacyRestricted.tool_allowlist = ["read", "send_message", "notes"]
        legacyRestricted.skills_selection_mode = "explicit_allowlist"
        #expect(legacyRestricted.effectiveFeatures(capabilities: caps)["plugin_management"] == false)
        #expect(legacyRestricted.sanitizeStaticTools(personal: false, capabilities: caps) == ["read", "send_message"])
        let requiresManager = legacyRestricted.changeCapability(.init(kind: "tool", name: "roll_dice", enabled: true), capabilities: caps)
        #expect(requiresManager == [.init(code: "plugin_requires_manager", target: .init(kind: "tool", name: "roll_dice"), plugin: "Dice")])

        #expect(legacyRestricted.changeCapability(.init(kind: "tool", name: "cordis_inspect_list", enabled: true), capabilities: caps).isEmpty)
        #expect(legacyRestricted.features["plugin_management"] == false)
        #expect(legacyRestricted.tool_allowlist.contains("cordis_inspect_list"))
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

    @Test func proactivePlanningEnforcesTaskGraphDependencyAndLegacyFallback() {
        let cron = AgentFeature(key: "cron_scheduling", label_i18n: "feature.cron_scheduling.label", help_i18n: "feature.cron_scheduling.help", default_on: true, available: true, requires: .init(features: [], tools: ["cron"], skills: []))
        let taskGraph = AgentFeature(key: "task_graph", label_i18n: "feature.task_graph.label", help_i18n: "feature.task_graph.help", default_on: true, available: true, requires: .init(features: ["cron_scheduling"], tools: ["task_graph"], skills: []))
        let proactive = AgentFeature(key: "proactive_planning", label_i18n: "feature.proactive_planning.label", help_i18n: "feature.proactive_planning.help", default_on: true, available: true, requires: .init(features: ["task_graph"], tools: [], skills: []))
        let caps = AgentCapabilities(
            fixed_tools: ["notes", "history"],
            node_id: "node-1",
            models: [],
            skills: [],
            tools: [AgentOption(name: "cron"), AgentOption(name: "task_graph")],
            features: [cron, taskGraph, proactive]
        )

        // Legacy PA config without explicit proactive_planning key where task_graph is disabled resolves to false.
        var legacyDraft = AgentDraft()
        legacyDraft.features = ["task_graph": false, "cron_scheduling": false]
        #expect(!legacyDraft.isFeatureEnabled(proactive))

        // Enabling proactive_planning automatically turns on task_graph and transitive cron_scheduling + tools.
        let enableBlocks = legacyDraft.changeCapability(.init(kind: "feature", name: "proactive_planning", enabled: true), capabilities: caps)
        #expect(enableBlocks.isEmpty)
        #expect(legacyDraft.features["proactive_planning"] == true)
        #expect(legacyDraft.features["task_graph"] == true)
        #expect(legacyDraft.features["cron_scheduling"] == true)
        #expect(Set(legacyDraft.tool_allowlist) == ["task_graph", "cron"])

        // Disabling task_graph while proactive_planning is on is blocked with localized proactive_planning owner text.
        let disableTaskBlocks = legacyDraft.changeCapability(.init(kind: "feature", name: "task_graph", enabled: false), capabilities: caps)
        #expect(disableTaskBlocks == [.init(code: "required_by_feature", target: .init(kind: "feature", name: "task_graph"), required_by: ["proactive_planning"])])
        #expect(legacyDraft.features["task_graph"] == true)
        #expect(disableTaskBlocks.first?.message.contains(agentFeatureName("proactive_planning")) == true)

        // Turning off proactive_planning succeeds while keeping task_graph active.
        let disableProactiveBlocks = legacyDraft.changeCapability(.init(kind: "feature", name: "proactive_planning", enabled: false), capabilities: caps)
        #expect(disableProactiveBlocks.isEmpty)
        #expect(legacyDraft.features["proactive_planning"] == false)
        #expect(legacyDraft.features["task_graph"] == true)
        #expect(legacyDraft.tool_allowlist.contains("task_graph"))
    }
}
